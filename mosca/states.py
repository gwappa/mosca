
from pyqtgraph.Qt import QtGui, QtCore
from . import models

StateManager = None

class DefaultAcquisitionStateManager(QtCore.QObject):
    """a class used for the device manager to wait for view/storage managers."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.donePlotting = models.SynchronizedState(parent=self)
        self.doneStorage  = models.SynchronizedState(parent=self)

def setup(cfg):
    global StateManager
    StateManager = DefaultAcquisitionStateManager()

