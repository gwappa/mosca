"""
mosca -- Minimal OSCilloscope and Acquisition environment.

Features
--------

+ Can plot and save multi-channel dummy and NI-DAQmx acquisition.

Future plans
------------

+ Configurable acquisition settings (trigger etc).
+ Conform to ITC-18.

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
    - ViewManager consists of:
        > DAQ control
        > storage control
        > analog input control
        > View/Record buttons
        > Oscillo toggle button
    - runs dummy/NI-DAQmx acquisition from the new GUI.

+ (TODO) reflect display settings to the acquisition.
+ (TODO) do __NOT__ call global instances directly! add get_instance() methods to ensure existence everywhere.
+ (TODO) add "DataBuffer" class so that Oscillo view do not block data update for the plots.
+ (TODO) make plot width dynamically configurable.
+ (TODO) make directory view.
+ (TODO) add color control UI (QColorDialog) for channels.
+ (TODO) cythonize numpy IO.
+ (TODO) add Notebook functionality (reST-like syntax)

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

from . import states, storages, devices, param, messages, channels

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
TOGGLE_OSCILLO  = "Oscillo"

def quitSequence():
    print("quit sequence...")
    for th in threads:
        th.quit()

class ControlPanel(QtGui.QWidget):
    closed = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

    def closeEvent(self, evt):
        evt.accept()
        self.closed.emit()

class DriverPanel(QtGui.QGroupBox):

    def __init__(self, manager, title, optionlabel="Selection", parent=None):
        super().__init__(title, parent)
        self.manager     = manager
        self.optionlabel = optionlabel
        self.populate()
        print(f"[{manager.name}]: done driver initialization.")

    def populate(self):
        self._layout = QtGui.QGridLayout()
        self.setLayout(self._layout)
        self.setSizePolicy(QtGui.QSizePolicy.MinimumExpanding,
                                QtGui.QSizePolicy.MinimumExpanding)

    def load_drivers(self, driverdict):
        self.selector = QtGui.QComboBox()
        self.selector.addItems([str(k) for k in driverdict.keys()])
        self._layout.addWidget(QtGui.QLabel("{0}:".format(self.optionlabel)),0,0,1,1)
        self._layout.addWidget(self.selector,0,1,1,1)
        self.configs = QtGui.QStackedWidget()
        self.configs.setSizePolicy(QtGui.QSizePolicy.MinimumExpanding,
                                QtGui.QSizePolicy.MinimumExpanding)
        for i, driver in enumerate(driverdict.values()):
            config = QtGui.QWidget()
            layout = QtGui.QFormLayout()
            layout.setFieldGrowthPolicy(QtGui.QFormLayout.ExpandingFieldsGrow)
            config.setLayout(layout)
            for entry in driver.configs():
                try:
                    label, editor = param.FormView.create(entry)
                except NotImplementedError as e:
                    MessageManager.not_implemented("Not implemented", str(e))
                    label, editor = param.FormView.create(entry, mode='str')
                layout.addRow(label, editor)
            self.configs.insertWidget(i, config)
        self._layout.addWidget(self.configs, 1,0,3,5)
        cur = self.manager.get_index()
        self.selector.setCurrentIndex(cur)
        self.configs.setCurrentIndex(cur)
        self.selector.currentIndexChanged.connect(self.configs.setCurrentIndex)
        self.selector.currentIndexChanged.connect(self.manager.set_driver)

class ChannelTableModel(QtCore.QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._baseparams = [c.label for c in channels.BaseChannelModel("dummy").configs()]
        self._params = self._baseparams
        self._titles = []

    def columnCount(self, idx):
        return 0 if idx.isValid() else len(self._titles)

    def rowCount(self, idx):
        return 0 if idx.isValid() else len(self._params)

    def headerData(self, idx, ori, role):
        if role == QtCore.Qt.DisplayRole:
            if ori == QtCore.Qt.Horizontal:
                return self._titles[idx]
            else:
                return self._params[idx]
        else:
            return None

    def data(self, idx, role):
        if idx.isValid():
            param = self._models[idx.column()][idx.row()]
            if role == QtCore.Qt.DisplayRole or role == QtCore.Qt.EditRole:
                if param.mode == 'bool':
                    return ""
                else:
                    return param.get_value()
            elif param.mode == 'bool' and role == QtCore.Qt.CheckStateRole:
                return QtCore.Qt.Checked if param.get_value() == True else QtCore.Qt.Unchecked
            else:
                return None
        else:
            return None

    def setData(self, idx, value, role):
        if idx.isValid():
            param = self._models[idx.column()][idx.row()]
            if role == QtCore.Qt.EditRole:
                if param.mode == 'bool':
                    return False
                else:
                    try:
                        param.set_value(value)
                        self.dataChanged.emit(idx, idx)
                        return True
                    except ValueError as e:
                        MessageManager.warn_revert("changing '{0}' failed".format(param.label), str(e))
                        return False
            elif role == QtCore.Qt.CheckStateRole:
                if param.mode == 'bool':
                    param.set_value(value == QtCore.Qt.Checked)
                    self.dataChanged.emit(idx, idx)
                    return True
                else:
                    return False
        else:
            return False

    def flags(self, idx):
        if idx.isValid():
            base = QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
            param = self._models[idx.column()][idx.row()]
            if param.mode == 'bool':
                base |= QtCore.Qt.ItemIsUserCheckable
            elif param.readonly == True:
                pass
            else:
                base |= QtCore.Qt.ItemIsEditable
            return base
        else:
            return QtCore.Qt.ItemIsEnabled

    def reload(self, chinfo):
        self.beginResetModel()
        self._params = []
        self._titles = []
        self._models = []

        for ch in chinfo.values():
            if ch.inuse == True:
                if len(ch.label.strip()) == 0:
                    self._titles.append(ch.name)
                else:
                    self._titles.append("{0}: {1}".format(ch.name, ch.label))
                configs = ch.configs()
                if len(self._params) == 0:
                    self._params = [c.label for c in configs]
                self._models.append(configs)
        if len(self._params) == 0:
            self._params = self._baseparams
        self.endResetModel()

class ChannelPanel(QtGui.QGroupBox):
    channelsLoaded = QtCore.pyqtSignal()

    def __init__(self, title="Channels", parent=None):
        super().__init__(title, parent)
        self.cheditor = channels.ChannelSelector()
        self.populate()

    def populate(self):
        self._layout = QtGui.QVBoxLayout()
        self.setLayout(self._layout)
        self.setSizePolicy(QtGui.QSizePolicy.MinimumExpanding,
                                QtGui.QSizePolicy.Minimum)

        self.configview = QtGui.QTableView()
        # TODO: how can I make background transparent?
        self.configview.setSizePolicy(QtGui.QSizePolicy.MinimumExpanding,
                                QtGui.QSizePolicy.MinimumExpanding)
        # self.configview.setFrameShadow(QtGui.QFrame.Sunken)
        # self.configview.setFrameShape(QtGui.QFrame.NoFrame)
        self.configview.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.configview.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        self.model = ChannelTableModel()
        self.configview.setModel(self.model)

        self.editorbutton = QtGui.QPushButton("Configure...")
        self.editorbutton.clicked.connect(self._edit_channels)
        # self._channellist = None # to be initialized upon update()

        self._layout.addWidget(self.configview)
        self.commands = QtGui.QHBoxLayout()
        self.commands.addWidget(self.editorbutton)
        self.commands.addStretch(5)
        self._layout.addLayout(self.commands)
        self.commands.addStretch(-1)

    def load_channels(self, chinfo):
        self.model.reload(chinfo)
        self.channelsLoaded.emit()

    def _edit_channels(self):
        """adds channel to the current acquisition object."""
        if self.cheditor.exec_with_driver(DeviceManager.get_driver()) == QtGui.QDialog.Accepted:
            self.load_channels(DeviceManager.get_driver().channels)

class ViewManager(models.SingletonManager):
    DEFAULT_PLOT_WIDTH = 5 # in sec
    DEFAULT_CHUNK_LENGTH = 1

    @models.ensure_singleton
    def widget(cls):
        return cls._singleton.mainwidget

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
    def show_warning(cls, title, msg):
        QtGui.QMessageBox.warning(None, title, msg)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._viewchanging = False
        self._populate_control()
        self.oscillo = None
        self.device.load_drivers(DeviceManager.get_drivers())
        self.storage.load_drivers(StorageManager.get_drivers())
        self.AI.load_channels(DeviceManager.get_driver().channels)

    def _populate_control(self):
        """(temporary) populate 'Control' window and display it."""
        self.mainwidget         = ControlPanel()
        self.mainwidget.setWindowTitle("Mosca Control")

        # command widgets to be populated
        self.tools    = QtGui.QHBoxLayout()
        self.viewbutton     = QtGui.QPushButton(TOGGLE_ACQ_VIEW)
        self.recordbutton   = QtGui.QPushButton(TOGGLE_ACQ_REC)
        self.oscillobutton  = QtGui.QPushButton(TOGGLE_OSCILLO)
        self.viewbutton.clicked.connect(self.toggle_viewing)
        self.recordbutton.clicked.connect(self.toggle_recording)
        self.oscillobutton.setCheckable(True)
        self.oscillobutton.setEnabled(False)
        self.oscillobutton.toggled.connect(self.toggle_oscillo)

        self.tools.addWidget(self.oscillobutton)
        self.tools.addStretch(1)
        self.tools.addWidget(self.viewbutton)
        self.tools.addWidget(self.recordbutton)

        # layout components
        self._layout         = QtGui.QGridLayout()
        self.mainwidget.setLayout(self._layout)
        self.device = DriverPanel(DeviceManager, "Device", "DAQ selection")
        self.storage = DriverPanel(StorageManager, "Storage", "I/O selection")
        self.AI  = ChannelPanel("Analog Inputs")
        self.AI.channelsLoaded.connect(self._update_with_channels)
        self._layout.addWidget(self.device, 0, 0, 1, 1) # row: 0, col: 0
        self._layout.addWidget(self.AI, 0, 1, 1, 1) # row: 0, col: 1
        self._layout.addWidget(self.storage, 0, 2, 1, 1) # row: 0, col: 2
        self._layout.addLayout(self.tools, 1, 0, 1, 3) # row: 3, col: 0-2
        self._layout.setColumnStretch(0, 1)
        self._layout.setColumnStretch(1, 3)
        self._layout.setColumnStretch(2, 1)
        self._layout.setRowStretch(0, 4)
        self._layout.setRowStretch(1, 3)
        self.mainwidget.resize(1250,250)
        self.mainwidget.move(40,40)

    def _update_with_channels(self):
        enable = len([ch for ch in DeviceManager.current.channels.values() if ch.inuse == True]) > 0
        self.recordbutton.setEnabled(enable)
        self.viewbutton.setEnabled(enable)

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

    def _prepare(self):
        """prepares for the next acquisition."""
        channels = DeviceManager.current.channels
        self.dt = DeviceManager.current.dt
        DeviceManager.current.dataAvailable.connect(self._update)

        if self.oscillo is not None:
            self.oscillo.hide()
            del self.oscillo
        if len([ch for ch in channels.values() if ch.inuse == True]) == 0:
            return

        self.oscillo = pg.GraphicsLayoutWidget(border=(255,255,255))
        self.oscillo.setWindowTitle("Mosca oscillo")
        self.oscillo.resize(800,600)
        self.oscillo.move(0,0)
        self.scales = []
        self.curves = []
        self.plots = []
        self.ydata = []
        self.data = []

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
                self.oscillo.addItem(plot, row=i, col=0)
                self.plots.append(plot)
                self.curves.append(curve)
                self.ydata.append(y)
                self.scales.append(ch.scale)
        self.ydata = np.stack(self.ydata, axis=-1)
        self.scales = np.array(self.scales).reshape((1,-1))
        self.oscillobutton.setEnabled(True)
        self.oscillobutton.setChecked(True)
        self.set_setting_enabled(False)

    def _update(self, data):
        """called during acquisition."""
        self.data.append(data)
        if len(self.data) >= self.DEFAULT_CHUNK_LENGTH:
            data = np.concatenate(self.data, axis=0)
            self.data = []
            size, nchan = data.shape
            self.time += size*(self.dt)
            trng = (self.time.min(), self.time.max())
            self.ydata = np.roll(self.ydata, (-size), axis=0)
            self.ydata[-size:,:] = data*(self.scales)
            for i in range(nchan):
                self.curves[i].setData(self.time, self.ydata[:,i])
                self.plots[i].setXRange(*trng, padding=0)
            # app.processEvents()

    def _finalize(self):
        """finalizes the current acquisition"""
        DeviceManager.current.dataAvailable.disconnect(self._update)
        self.set_setting_enabled(True)

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

    def toggle_oscillo(self, toggled):
        if self.oscillo is None:
            pass
        else:
            self.oscillo.setVisible(toggled)

    def set_setting_enabled(self, val):
        self.device.setEnabled(val)
        self.storage.setEnabled(val)
        self.AI.setEnabled(val)

class IndependentWorker(QtCore.QThread):
    def __init__(self, worker, parent=None):
        super().__init__(parent)
        self.worker = worker
        self.worker.moveToThread(self)

    def run(self):
        ret = self.exec()

threads = []

StorageThread = IndependentWorker(StorageManager)
# StorageManager.moveToThread(StorageThread)

DeviceThread = IndependentWorker(DeviceManager)
# DeviceManager.moveToThread(DeviceThread)
DeviceManager.starting.connect(ViewManager.prepare)
DeviceManager.starting.connect(StorageManager.prepare)
DeviceManager.finishing.connect(ViewManager.finalize)
DeviceManager.finishing.connect(StorageManager.finalize)

ViewManager.widget().closed.connect(app.quit)
app.aboutToQuit.connect(quitSequence)

StorageThread.start(QtCore.QThread.TimeCriticalPriority)
threads.append(StorageThread)
DeviceThread.start(QtCore.QThread.TimeCriticalPriority)
threads.append(DeviceThread)


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
