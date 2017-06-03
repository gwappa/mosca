
import pyqtgraph as pg
from pyqtgraph.Qt import QtGui, QtCore
from . import models
from .messages import MessageManager

class ParameterView(QtGui.QLineEdit):
    """docstring for ParameterView"""
    @staticmethod
    def create(parent=None, typ='str', getter=None, setter=None):
        if typ == 'dir':
            raise NotImplementedError("DirectoryView has not been implemented. Swapped to ParameterView<str>.")
            return DirectoryView(parent=parent, getter=getter, setter=setter)
        else:
            return ParameterView(parent=parent, typ=typ, getter=getter, setter=setter)

    def __init__(self, parent=None, typ='str', getter=None, setter=None):
        """typ in ('str', 'int', 'float')"""
        super(ParameterView, self).__init__(parent)
        self._value = 0
        self._valuechanging = False
        self.getter = self.default_getter if getter is None else getter
        self.setter = self.default_setter if setter is None else setter
        if typ == 'int':
            self.setValidator(QtGui.QIntValidator(self))
        elif typ == 'float':
            self.setValidator(QtGui.QDoubleValidator(self))
        self.revert_value()
        self.editingFinished.connect(self.validate_value)

    def default_getter(self):
        return self._value

    def default_setter(self, val):
        self._value = val

    def revert_value(self):
        self._valuechanging = True
        self.setText(str(self.getter()))
        self._valuechanging = False

    def validate_value(self):
        if self._valuechanging:
            return
        try:
            self._valuechanging = True
            self.setter(self.text())
        except ValueError as e:
            MessageManager.warn_revert("Parameter error", str(e))
            self.revert_value()
        finally:
            self._valuechanging = False



