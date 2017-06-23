"""
mosca -- Minimal OSCilloscope and Acquisition environment.

Features
--------

+ Can plot and save multi-channel dummy acquisition.

Future plans
------------

+ Make it possible to add channels for acquisition (I/O + optional views/colors).
+ Configurable acquisition settings (rate, basename, trigger etc).
+ Conform to ITC-18 and NI-DAQmx.

Issues
------

+ The code is too messy. Refactor when the first version works.


Current status
--------------

+ Split functionality among 'managers':
    - MessageManager    (logging/dialog)
    - ViewManager       (GUI: windows, widgets etc.)
    - DeviceManager     (main DAQ function)
    - StorageManager    (data I/O handling)
    - StateManager      (handles acquisition states)
+ New GUI in progress:
    - general device controls
    - storage controls
    - input channel controls (TODO: display setting)
    - runs dummy acquisition from the new GUI.
+ (TODO) disable controls while running acquisition.
+ (TODO) refactor driver properties to a more self-containing class models.
+ (TODO) split ViewManager into several ControlView's.
+ (TODO) make driver-based managers to have StackWidget-based GUI.
+ (TODO) add color control UI.
+ (TODO) make directory view.

"""
import os
import json
import traceback
import numpy as np
from pyqtgraph.Qt import QtGui, QtCore
import pyqtgraph as pg

app = QtGui.QApplication([])
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')

from . import states, storages, devices, views, messages, channels

def setup():
    modulepath = os.path.split(__file__)[0]
    configfile = os.path.join(modulepath, "config.json")
    with open(configfile, 'r') as f:
        cfg = json.load(f)
        states.setup(cfg)
        storages.setup(cfg)
        devices.setup(cfg)

setup()
StateManager = states.StateManager
StorageManager = storages.StorageManager
DeviceManager = devices.DeviceManager
MessageManager = messages.MessageManager

##
## GUI components
##

TOGGLE_ACQ_VIEW = "View"
TOGGLE_ACQ_REC  = "Record"
TOGGLE_ACQ_ABO  = "Stop"

class ViewManager(models.SingletonManager):
    DEFAULT_PLOT_WIDTH = 5 # in sec

    @models.ensure_singleton
    def show(cls):
        cls._singleton.mainwidget.show()

    @models.ensure_singleton
    def prepare(cls, save=True):
        cls._singleton._prepare()
        with StateManager.donePlotting as evt:
            evt.reset()

    @models.ensure_singleton
    def finalize(cls):
        cls._singleton._finalize()
        with StateManager.donePlotting as evt:
            evt.set()

    @models.ensure_singleton
    def update_with_acquisition(cls, typ, val):
        cls._singleton._update_with_acquisition(typ, val)

    @classmethod
    def update_with_acq_driver(cls, name):
        if cls._singleton is None:
            pass
        else:
            cls._singleton._update_with_acq_driver(name)

    @classmethod
    def update_with_io_driver(cls, name):
        if cls._singleton is None:
            pass
        else:
            cls._singleton._update_with_io_driver(name)

    @classmethod
    def show_warning(cls, title, msg):
        QtGui.QMessageBox.warning(None, title, msg)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._viewchanging = False
        self._populate_control()
        self._oscillo = None
        self._load_acq_drivers(DeviceManager.get_drivers())
        self._load_io_drivers(StorageManager.get_drivers())
        self._update_with_channels()
        self.cheditor = channels.ChannelSelector()

    def _populate_control(self):
        """(temporary) populate 'Control' window and display it."""
        self.mainwidget         = QtGui.QWidget()
        self.mainwidget.setWindowTitle("Controls")
        self.mainwidget.resize(680,300)

        # widgets to be populated
        self.viewbutton     = QtGui.QPushButton(TOGGLE_ACQ_VIEW)
        self.recordbutton   = QtGui.QPushButton(TOGGLE_ACQ_REC)
        self.viewbutton.clicked.connect(self.toggle_viewing)
        self.recordbutton.clicked.connect(self.toggle_recording)
        self.channelview = QtGui.QScrollArea()
        self.channelview.setSizePolicy(QtGui.QSizePolicy.MinimumExpanding,
                                QtGui.QSizePolicy.MinimumExpanding)
        self.channelview.setFrameShadow(QtGui.QFrame.Sunken)
        self.channelview.setFrameShape(QtGui.QFrame.NoFrame)
        self.channelview.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.channelview.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        self.channeledit = QtGui.QPushButton("Edit channels...")
        self.channeledit.clicked.connect(self._edit_channels)
        self._channellist = None # to be initialized upon _update_with_channels()

        # the base layout that contains '_generalcontrols', '_commandbox'
        self._baselayout         = QtGui.QGridLayout()
        self.mainwidget.setLayout(self._baselayout)
        self._commandbox          = QtGui.QHBoxLayout()
        self._generalcontrols    = QtGui.QVBoxLayout()
        self._inputchannels  = QtGui.QGroupBox("Input Channels")
        self._baselayout.addLayout(self._generalcontrols, 0, 0, 8, 1)
        self._baselayout.addLayout(self._commandbox, 9, 0, 1, 2)
        self._baselayout.addWidget(self._inputchannels, 0, 1, 8, 1)

        # populating '_commnadbox'
        self._commandbox.addStretch(1)
        self._commandbox.addWidget(self.viewbutton)
        self._commandbox.addWidget(self.recordbutton)

        # populating '_generalcontrols': '_devicecontrol', '_iocontrol'
        self._devicecontrol = QtGui.QGroupBox("Acquisition Device")
        self._iocontrol = QtGui.QGroupBox("Storage")
        self._generalcontrols.addWidget(self._devicecontrol)
        self._generalcontrols.addWidget(self._iocontrol)

        # populating '_devicecontrol'
        self.devicelayout = QtGui.QGridLayout()
        self._devicecontrol.setLayout(self.devicelayout)

        # populating '_iocontrol'
        self.iolayout = QtGui.QGridLayout()
        self._iocontrol.setLayout(self.iolayout)

        # populating '_inputchannels'
        self._ichannellayout = QtGui.QVBoxLayout()
        self._inputchannels.setLayout(self._ichannellayout)
        self._inputchannels.setSizePolicy(QtGui.QSizePolicy.MinimumExpanding,
                                QtGui.QSizePolicy.MinimumExpanding)
        self._ichannellayout.addWidget(self.channelview)
        self._ichcommandbox = QtGui.QHBoxLayout()
        self._ichcommandbox.addStretch(5)
        self._ichcommandbox.addWidget(self.channeledit)
        self._ichannellayout.addLayout(self._ichcommandbox)

    def _load_acq_drivers(self, driverdict):
        self.acqselector = QtGui.QComboBox()
        self.acqselector.addItems([str(k) for k in driverdict.keys()])
        self.devicelayout.addWidget(QtGui.QLabel("DAQ:"),0,0,1,1)
        self.devicelayout.addWidget(self.acqselector,0,1,1,1)
        self.deviceconfigs = QtGui.QStackedWidget()
        for i, driver in enumerate(driverdict.values()):
            config = QtGui.QWidget()
            layout = QtGui.QFormLayout()
            layout.setFieldGrowthPolicy(QtGui.QFormLayout.ExpandingFieldsGrow)
            config.setLayout(layout)
            for j, entry in enumerate(driver.configmap().items()):
                try:
                    editor = views.ParameterView.create(**(entry[1]))
                except NotImplementedError as e:
                    MessageManager.not_implemented("Not implemented", str(e))
                    entry[1]['typ'] = 'str'
                    editor = views.ParameterView.create(**(entry[1]))
                layout.addRow(entry[0], editor)
            self.deviceconfigs.insertWidget(i, config)
        self.devicelayout.addWidget(self.deviceconfigs, 1,0,3,5)
        cur = DeviceManager.get_index()
        self.acqselector.setCurrentIndex(cur)
        self.deviceconfigs.setCurrentIndex(cur)
        self.acqselector.currentIndexChanged.connect(self.deviceconfigs.setCurrentIndex)
        self.acqselector.currentIndexChanged.connect(DeviceManager.set_driver)

    def _load_io_drivers(self, driverdict):
        self.ioselector = QtGui.QComboBox()
        self.ioselector.addItems([str(k) for k in driverdict.keys()])
        self.iolayout.addWidget(QtGui.QLabel("I/O:"),0,0,1,1)
        self.iolayout.addWidget(self.ioselector,0,1,1,1)
        self.ioconfigs = QtGui.QStackedWidget()
        for i, driver in enumerate(driverdict.values()):
            config = QtGui.QWidget()
            layout = QtGui.QFormLayout()
            layout.setFieldGrowthPolicy(QtGui.QFormLayout.ExpandingFieldsGrow)
            config.setLayout(layout)
            for j, entry in enumerate(driver.configmap().items()):
                try:
                    editor = views.ParameterView.create(**(entry[1]))
                except NotImplementedError as e:
                    MessageManager.not_implemented("Not implemented", str(e))
                    entry[1]['typ'] = 'str'
                    editor = views.ParameterView.create(**(entry[1]))
                layout.addRow(entry[0], editor)
            self.ioconfigs.insertWidget(i, config)
        self.iolayout.addWidget(self.ioconfigs, 1,0,3,5)
        cur = StorageManager.get_index()
        self.ioselector.setCurrentIndex(cur)
        self.ioconfigs.setCurrentIndex(cur)
        self.ioselector.currentIndexChanged.connect(self.ioconfigs.setCurrentIndex)
        self.ioselector.currentIndexChanged.connect(StorageManager.set_driver)

    def _update_with_acq_driver(self, name):
        if self._viewchanging == True:
            return
        else:
            self._viewchanging = True
            try:
                # TODO
                pass
            except:
                traceback.print_exc()
            finally:
                self._viewchanging = False

    def _update_with_io_driver(self, name):
        if self._viewchanging == True:
            return
        else:
            self._viewchanging = True
            try:
                # TODO
                pass
            except:
                traceback.print_exc()
            finally:
                self._viewchanging = False

    def _update_with_acquisition(self, typ, val):
        if typ == TOGGLE_ACQ_VIEW:
            if val == True:
                self.viewbutton.setText(TOGGLE_ACQ_ABO)
                self.recordbutton.setEnabled(False)
            else:
                self.viewbutton.setText(TOGGLE_ACQ_VIEW)
                self.recordbutton.setEnabled(True)
        else:
            if val == True:
                self.recordbutton.setText(TOGGLE_ACQ_ABO)
                self.viewbutton.setEnabled(False)
            else:
                self.recordbutton.setText(TOGGLE_ACQ_REC)
                self.viewbutton.setEnabled(True)

    def _update_with_channels(self):
        chinfo = DeviceManager.get_driver().channels
        if self._channellist:
            del self._channellist
        self._channellist = QtGui.QWidget()
        self._channellist.setSizePolicy(QtGui.QSizePolicy.MinimumExpanding,
                                        QtGui.QSizePolicy.Minimum)
        self._channellistbox = QtGui.QVBoxLayout()
        self._channellist.setLayout(self._channellistbox)
        for ch in chinfo.values():
            if ch.inuse == True:
                self._channellistbox.addWidget(channels.ChannelView(ch))
        self.channelview.setWidget(self._channellist)

    def _edit_channels(self):
        """adds channel to the current acquisition object."""
        if self.cheditor.exec_with_driver(DeviceManager.get_driver()) == QtGui.QDialog.Accepted:
            self._update_with_channels()

    def _prepare(self):
        """prepares for the next acquisition."""
        channels = DeviceManager.current.channels
        self.dt = DeviceManager.current.dt
        DeviceManager.current.dataAvailable.connect(self._update)

        if self._oscillo is not None:
            self._oscillo.hide()
            del self._oscillo
        if len([ch for ch in channels.values() if ch.inuse == True]) == 0:
            return

        self._oscillo = pg.GraphicsLayoutWidget(border=(255,255,255))
        self._oscillo.setWindowTitle("Oscillo")
        self._oscillo.resize(800,600)
        self._oscillo.move(0,0)
        self.scales = []
        self.curves = []
        self.plots = []
        self.ydata = []

        # initialize time points
        width = self.DEFAULT_PLOT_WIDTH
        samplesize = width*(DeviceManager.current.rate)
        self.time = np.arange(samplesize)*(self.dt) - width

        # load channels
        # TODO: display it only when 'display' attribute is set True
        for i, entry in enumerate(channels.items()):
            ch = entry[1]
            if ch.inuse == True:
                plot = pg.PlotItem()
                plot.setLabel('left', text=ch.label, units=ch.unit)
                plot.setLabel('bottom', units='s')
                y = np.zeros(samplesize, dtype=float)
                curve = plot.plot(self.time, y, pen=pg.mkPen('b'))
                self._oscillo.addItem(plot, row=i, col=0)
                self.plots.append(plot)
                self.curves.append(curve)
                self.ydata.append(y)
                self.scales.append(ch.scale)
        self._oscillo.show()

    def _update(self, data):
        """called during acquisition."""
        size, nchan = data.shape
        self.time += size*(self.dt)
        trng = (self.time.min(), self.time.max())
        for i in range(nchan):
            self.ydata[i] = np.roll(self.ydata[i], (-size))
            self.ydata[i][-size:] = data[:,i]*(self.scales[i])
            self.curves[i].setData(self.time, self.ydata[i])
            self.plots[i].setXRange(*trng, padding=0)
        app.processEvents()

    def _finalize(self):
        """finalizes the current acquisition"""
        DeviceManager.current.dataAvailable.disconnect(self._update)

    def toggle_viewing(self):
        if self.viewbutton.text() == TOGGLE_ACQ_VIEW:
            try:
                start_viewing()
            except:
                traceback.print_exc()
        else: # aborted
            try:
                stop_viewing()
            except:
                traceback.print_exc()

    def toggle_recording(self):
        if self.recordbutton.text() == TOGGLE_ACQ_REC:
            try:
                start_recording()
            except:
                traceback.print_exc()
        else: # aborted
            try:
                stop_recording()
            except:
                traceback.print_exc()


StorageThread = QtCore.QThread()
StorageManager.moveToThread(StorageThread)
StorageManager.driverchanged.connect(ViewManager.update_with_io_driver)

DeviceThread = QtCore.QThread()
DeviceManager.moveToThread(DeviceThread)
DeviceManager.driverchanged.connect(ViewManager.update_with_acq_driver)
DeviceManager.starting.connect(ViewManager.prepare)
DeviceManager.starting.connect(StorageManager.prepare)
DeviceManager.finishing.connect(ViewManager.finalize)
DeviceManager.finishing.connect(StorageManager.finalize)

StorageThread.start(QtCore.QThread.TimeCriticalPriority)
DeviceThread.start(QtCore.QThread.TimeCriticalPriority)


def start_viewing():
    # may be a try block here...
    DeviceManager.start(save=False)
    ViewManager.update_with_acquisition(TOGGLE_ACQ_VIEW, True)

def stop_viewing():
    DeviceManager.stop()
    ViewManager.update_with_acquisition(TOGGLE_ACQ_VIEW, False)

def start_recording():
    # may be a try block here...
    DeviceManager.start(save=True)
    ViewManager.update_with_acquisition(TOGGLE_ACQ_REC, True)

def stop_recording():
    DeviceManager.stop()
    ViewManager.update_with_acquisition(TOGGLE_ACQ_REC, False)
