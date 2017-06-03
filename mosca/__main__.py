import sys
from pyqtgraph.Qt import QtGui, QtCore
from . import ViewManager

ViewManager.show()
if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
    QtGui.QApplication.instance().exec_()
