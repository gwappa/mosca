import sys, math
from collections import OrderedDict
import numpy as np
from pyqtgraph.Qt import QtGui, QtCore
from . import models
from . import utils
from . import channels
from . import states
from . import param

##
## Device-related classes
##

DEFAULT_SAMPLING_RATE       = 10000
DEFAULT_SAMPLING_INTERVALS  = 1000

DeviceManager = None

class DeviceDriverManager(models.BaseDriverManager):
    preparing       = QtCore.pyqtSignal()
    starting        = QtCore.pyqtSignal(bool)
    aboutToStart    = QtCore.pyqtSignal()
    aboutToFinish   = QtCore.pyqtSignal()
    finishing       = QtCore.pyqtSignal()
    DEFAULT_TIMEOUT = 5000000

    def start(self, save=True):
        if self.current is not None:
            self.preparing.connect(self.current.prepare)
            self.aboutToStart.connect(self.current.start)
            self.aboutToFinish.connect(self.current.stop)
            self.preparing.emit()
            if save == True:
                self.starting.emit(True)
            else:
                self.starting.emit(False)
            self.aboutToStart.emit()

    def stop(self):
        self.aboutToFinish.emit()
        self.finishing.emit()
        with states.StateManager.doneStorage as evt:
            evt.wait(self.DEFAULT_TIMEOUT)
        with states.StateManager.donePlotting as evt:
            evt.wait(self.DEFAULT_TIMEOUT)
        self.preparing.disconnect(self.current.prepare)
        self.aboutToStart.disconnect(self.current.start)
        self.aboutToFinish.disconnect(self.current.stop)


class BaseDeviceDriver(models.DriverInterface):
    """Basic behaviors as an acquisition driver."""
    dataAvailable = QtCore.pyqtSignal(np.ndarray)

    def __init__(self, name, parent=None, raterange=None, intervalrange=None):
        super().__init__(parent)
        if raterange is None:
            raterange       = (0, sys.maxsize)
        if intervalrange is None:
            intervalrange   = (0, sys.maxsize)
        self.name           = name
        self.raterange      = raterange
        self.intervalrange  = intervalrange
        self._rate          = DEFAULT_SAMPLING_RATE
        self._interval      = DEFAULT_SAMPLING_INTERVALS # in samples*channels
        self._channels      = OrderedDict()
        self._configs       = []
        self._configs.append(param.ParameterController(label='Sampling rate (Hz)',
                                                        mode='int',
                                                        getter=self.get_rate,
                                                        setter=self.set_rate))
        self._configs.append(param.ParameterController(label='Update interval (Samples)',
                                                        mode='int',
                                                        getter=self.get_interval,
                                                        setter=self.set_interval))

    def __getattr__(self, name):
        if name == 'rate':
            return self.get_rate()
        elif name == 'dt':
            return 1/(self.get_rate())
        elif name == 'interval':
            return self.get_interval()
        elif name == 'channels':
            return self.get_channels()
        else:
            raise AttributeError(name)

    def __setattr__(self, name, val):
        if name == 'rate':
            return self.set_rate(val)
        elif name == 'interval':
            return self.set_interval(val)
        else:
            super().__setattr__(name, val)

    def prepare(self):
        """prepares the acquisition task using the current configurations."""
        pass

    def start(self):
        """starts the acquisition task that is created using prepare()."""
        pass

    def stop(self):
        """stops the currently running acquisition task."""
        pass

    def get_channels(self):
        if hasattr(self, '_channels'):
            return getattr(self, '_channels')
        else:
            raise AttributeError("{0} has no 'channels'".format(self.__class__.__name__))

    def get_interval(self):
        return self._interval

    def get_rate(self):
        return self._rate

    def configs(self):
        return self._configs

    def set_interval(self, val):
        self._interval = utils.validate_integer(val, self.intervalrange, 'update interval')

    def set_rate(self, val):
        self._rate = utils.validate_integer(val, self.raterange, 'sampling rate')

class DummyDeviceDriver(BaseDeviceDriver):
    def __init__(self, parent=None, raterange=None, intervalrange=None):
        super().__init__('Dummy', parent=parent, raterange=None, intervalrange=None)
        for ch in range(4):
            name = "AI{0}".format(ch)
            self._channels[name] = channels.BaseChannelModel(name, parent=self)

    def _prepare_next(self):
        self.source = np.roll(self.source, (-self.Nsamp), axis=0)

    def _fire_data_available(self):
        self.dataAvailable.emit(self.source[:(self.Nsamp)])
        self._prepare_next()

    def prepare(self):
        self.nchan = len([ch for ch in self.channels.values() if ch.inuse == True])
        self.Nsamp = self.interval
        self.source = np.empty((20000, self.nchan), dtype=float)
        y = np.sin(2*math.pi*np.arange(20000)/4000)
        delta = 20000 // (self.nchan)
        for i in range(self.nchan):
            self.source[:,i] = np.roll(y, delta*i)
        self._timer = QtCore.QTimer(parent=self)
        self._timer.setInterval(self.interval*1000/(self.rate))
        self._timer.timeout.connect(self._fire_data_available)

    def start(self):
        self._timer.start()

    def stop(self):
        self._timer.stop()

def setup(cfg):
    global DeviceManager
    DeviceManager = DeviceDriverManager("Device")
    DeviceManager.load_drivers(cfg['devices'])
