import sys
from collections import OrderedDict
import numpy as np
from pyqtgraph.Qt import QtGui, QtCore
from . import models
from . import utils
from . import channels
from . import states

##
## Device-related classes
##

DEFAULT_SAMPLING_RATE       = 10000
DEFAULT_SAMPLING_INTERVALS  = 1000

DeviceManager = None

class DeviceDriverManager(models.BaseDriverManager):
    starting    = QtCore.pyqtSignal(bool)
    finishing   = QtCore.pyqtSignal()
    DEFAULT_TIMEOUT = 5000000

    def start(self, save=True):
        if self.current is not None:
            self.current.prepare()
            if save == True:
                self.starting.emit(True)
            else:
                self.starting.emit(False)
            self.current.start()

    def stop(self):
        self.current.stop()
        self.finishing.emit()
        with states.StateManager.doneStorage as evt:
            evt.wait(self.DEFAULT_TIMEOUT)
        with states.StateManager.donePlotting as evt:
            evt.wait(self.DEFAULT_TIMEOUT)


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

    def __getattr__(self, name):
        if name == 'rate':
            return self.get_rate()
        elif name == 'dt':
            return 1/(self.get_rate())
        elif name == 'interval':
            return self.get_interval()
        elif name == 'availability':
            return self.get_availability()
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

    def configmap(self):
        d = OrderedDict()
        d['Sampling rate (Hz)'] = dict(typ='int',
                                    getter=self.get_rate,
                                    setter=self.set_rate)
        d['Update interval (Samples)'] = dict(typ='int',
                                    getter=self.get_interval,
                                    setter=self.set_interval)
        return d

    def set_interval(self, val):
        self._interval = utils.validate_integer(val, self.intervalrange, 'update interval')

    def set_rate(self, val):
        self._rate = utils.validate_integer(val, self.raterange, 'sampling rate')

class DummyDeviceDriver(BaseDeviceDriver):
    def __init__(self, parent=None, raterange=None, intervalrange=None):
        super().__init__('Dummy', parent=parent, raterange=None, intervalrange=None)
        self._timer = QtCore.QTimer()
        for ch in range(4):
            name = "AI{0}".format(ch)
            self._channels[name] = channels.BaseChannelModel(name, parent=self)
        self._timer.timeout.connect(self._fire_data_available)

    def _prepare_next(self):
        self._inbuf = np.random.normal(size=(self.Nsamp*self.nchan)).reshape((-1, self.nchan))

    def _fire_data_available(self):
        self.dataAvailable.emit(self._inbuf)
        self._prepare_next()

    def prepare(self):
        self.nchan = len([ch for ch in self.channels.values() if ch.inuse == True])
        self.Nsamp = self.interval
        self._timer.setInterval(self.interval*1000/(self.rate))
        self._prepare_next()

    def start(self):
        self._timer.start()

    def stop(self):
        self._timer.stop()

def setup(cfg):
    global DeviceManager
    DeviceManager = DeviceDriverManager("Acquisition")
    DeviceManager.load_drivers(cfg['devices'])






