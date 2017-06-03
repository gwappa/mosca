"""
oscillo -- an oscilloscope program in Python.

Features
--------

+ Can plot and save 1Ch dummy acquisition.

Future plans
------------

+ Make it possible to add channels for acquisition (+optional views/colors). Up to at least 8.
+ Configurable acquisition settings (rate, basename).
+ Conform to ITC-18.

Issues
------

+ Acquisition stops when in background. Splitting driver/plot/storage into different QThreads
  may change the situation?

+ Latency may be too long for real-time acquisition, but I ignore it for now.
  See how the program scales with channel number.


"""

import os
import struct
import time
from pyqtgraph.Qt import QtGui, QtCore
import pyqtgraph as pg
import numpy as np

TOGGLE_ACQ_VIEW = "View"
TOGGLE_ACQ_REC  = "Record"
TOGGLE_ACQ_ABO  = "Abort"

UPDATE_INTERVAL = 100

app = QtGui.QApplication([])
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')

twidth = 50000
name = 'Noise'
dx = 0.0001

class TestDriver(QtCore.QObject):
    dataAvailable   = QtCore.pyqtSignal(np.ndarray)
    starting        = QtCore.pyqtSignal(int)
    finished        = QtCore.pyqtSignal()

    def __init__(self, parent=None, rate=10000, interval=100):
        super().__init__(parent)
        self.timer = QtCore.QTimer()
        self.rate = rate
        self.interval = interval
        self.blocksize = rate*interval//1000
        self.timer.timeout.connect(self.__generate)
        self.blockcount = 0
        self.tstart = 0
        self.tend = 0

    def __generate(self):
        dat = np.random.normal(size=((self.interval)*10))
        self.blockcount += 1
        self.tend = time.time()
        self.dataAvailable.emit(dat)
        app.processEvents()

    def start(self, rate=None, interval=None):
        if interval is not None:
            self.interval = interval
        if rate is not None:
            self.rate = rate
        self.blocksize = self.rate * self.interval // 1000
        print("rate={0.rate}; interval={0.interval}; blocksize={0.blocksize}".format(self))
        self.blockcount = 0
        self.timer.setInterval(self.interval)
        self.starting.emit(self.blocksize)
        self.timer.start()
        self.tstart = time.time()

    def abort(self):
        self.timer.stop()
        app.processEvents()
        self.finished.emit()
        print("elapsed:", driver.tend - driver.tstart)
        print("data:", self.blockcount*self.blocksize)

class TestStorage(QtCore.QObject):

    @classmethod
    def push_float(cls, f, val, fmt):
        f.write(struct.pack('f', val))
        return 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self.enabled = True
        self.basename = "test"
        self.directory = os.getcwd()
        self.blocksize = None
        self.file = None
        self.fmt = None
        self.written = None

    def open(self, blocksize=50, dtype=float):
        if self.enabled == False:
            return
        self.file = open(self.basename, 'wb')
        self.blocksize = blocksize
        if issubclass(dtype, np.floating) or (dtype == float):
            self.fmt = 'f'
        else:
            self.fmt = 'f'
        self.written = 0

    def close(self):
        if self.enabled == False:
            return
        if not self.file.closed:
            print("saved:", self.written)
            self.file.close()
            # self.file = None
            self.fmt = None
            self.written = None

    def push(self, data):
        if self.enabled == False:
            return
        self.written += sum(self.push_float(self.file, data[i], self.fmt)\
                                 for i in range(self.blocksize))
        self.file.flush()

def start_viewing():
    # may be a try block here...
    reset()
    storage.enabled = False
    driver.start(interval=UPDATE_INTERVAL)
    viewer.setText(TOGGLE_ACQ_ABO)
    recorder.setEnabled(False)

def stop_viewing():
    driver.abort()
    viewer.setText(TOGGLE_ACQ_VIEW)
    recorder.setEnabled(True)

def start_recording():
    # may be a try block here...
    reset()
    storage.enabled = True
    driver.start(interval=UPDATE_INTERVAL)
    recorder.setText(TOGGLE_ACQ_ABO)
    viewer.setEnabled(False)

def stop_recording():
    driver.abort()
    recorder.setText(TOGGLE_ACQ_REC)
    viewer.setEnabled(True)

def toggle_viewing():
    if viewer.text() == TOGGLE_ACQ_VIEW:
        start_viewing()
    else: # aborted
        stop_viewing()

def toggle_recording():
    if recorder.text() == TOGGLE_ACQ_REC:
        start_recording()
    else: # aborted
        stop_recording()

def reset():
    global t, data
    p.setXRange(-twidth, 0, padding=0)
    p.setYRange(-5, 5, padding=0)
    t = np.arange(-twidth,0)*dx
    data = np.zeros(twidth)
    curve.setData(x=t, y=data)

def update(newdata):
    global data, t
    data = np.roll(data, -(newdata.size))
    data[-(newdata.size):] = newdata
    t = t + (newdata.size)*dx
    curve.setData(t, data)
    p.setXRange(t.min(), t.max(), padding=0)
    app.processEvents()


win = QtGui.QWidget()
content = QtGui.QGridLayout()
win.setLayout(content)

plotpanel = pg.GraphicsView()
plotbase = pg.GraphicsLayout(border=(100, 100, 100))
plotpanel.setCentralItem(plotbase)
content.addWidget(plotpanel, 0, 0, 5, 5)
win.setWindowTitle("Oscillo")
win.resize(800, 600)
win.show()
p = plotbase.addPlot()
p.setLabel('bottom', 'Time', units='ms')
p.setLabel('left', name, units='V')
curve = p.plot()
curve.setPen('b')
reset()

viewer = QtGui.QPushButton(TOGGLE_ACQ_VIEW)
recorder = QtGui.QPushButton(TOGGLE_ACQ_REC)
content.addWidget(viewer, 5, 3)
content.addWidget(recorder, 5, 4)
 
driver = TestDriver()
storage = TestStorage()
driver.dataAvailable.connect(update)
driver.starting.connect(storage.open)
driver.dataAvailable.connect(storage.push)
driver.finished.connect(storage.close)
viewer.clicked.connect(toggle_viewing)
recorder.clicked.connect(toggle_recording)

if __name__ == '__main__':
    import sys
    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        QtGui.QApplication.instance().exec_()
