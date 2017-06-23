
from collections import OrderedDict
from pyqtgraph.Qt import QtGui, QtCore
from . import models
from . import views
from .messages import MessageManager

##
## Channel-related classes
##

class ChannelSelectorModel(QtCore.QAbstractTableModel):
    """A Qt item model for display and editing of channels use."""

    _labels = ('Channel usage',)
    _attrs  = ('labels',)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.names = tuple()
        self.labels = tuple()
        self.inuse = tuple()

    def load_driver(self, driver):
        self.driver = driver
        chinfo = driver.channels
        self.names = tuple(chinfo.keys())
        self.labels = tuple(models.ValueModel(ch.label) for ch in chinfo.values())
        self.inuse = tuple(models.ValueModel(ch.inuse) for ch in chinfo.values())
        self.layoutChanged.emit()

    def updateDriver(self, ret):
        if ret == QtGui.QDialog.Accepted:
            channels = self.driver.channels
            for i, name in enumerate(self.names):
                channels[name].inuse = self.inuse[i].value
                channels[name].label = self.labels[i].value

    def rowCount(self, parent):
        if not parent.isValid():
            return len(self.names)
        else:
            return None

    def columnCount(self, parent):
        if not parent.isValid():
            return len(self._attrs)
        else:
            return None

    def flags(self, idx):
        val = super().flags(idx)
        if idx.isValid():
            val |= QtCore.Qt.ItemIsEditable
            if idx.column() == 0:
                val |= QtCore.Qt.ItemIsUserCheckable
        return val

    def headerData(self, section, orientation, role):
        if role != QtCore.Qt.DisplayRole:
            return None
        if orientation == QtCore.Qt.Horizontal:
            return self._labels[section]
        else:
            return self.names[section]

    def data(self, idx, role):
        if (role == QtCore.Qt.DisplayRole) and idx.isValid():
            return getattr(self, self._attrs[idx.column()])[idx.row()].value
        elif (role == QtCore.Qt.CheckStateRole) and idx.isValid() and (idx.column() == 0):
            return QtCore.Qt.Checked if self.inuse[idx.row()].value == True else QtCore.Qt.Unchecked
        else:
            return None

    def setData(self, idx, value, role):
        roles = (role,)
        if (role == QtCore.Qt.EditRole) and idx.isValid():
            getattr(self, self._attrs[idx.column()])[idx.row()].value = value
            if (len(value) > 0) and (self.inuse[idx.row()].value == False):
                self.inuse[idx.row()].value = True
                roles += (QtCore.Qt.CheckStateRole,)
        elif (role == QtCore.Qt.CheckStateRole) and idx.isValid():
            self.inuse[idx.row()].value = (value == QtCore.Qt.Checked)
        else:
            return False

        self.dataChanged.emit(idx, idx) #FIXME does not work on PyQt4: , roles)
        return True

class ChannelSelector(QtGui.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QtGui.QVBoxLayout(self)
        self.model = ChannelSelectorModel()
        self.table  = QtGui.QTableView()
        self.table.setModel(self.model)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.layout.addWidget(self.table)
        self.buttons = QtGui.QHBoxLayout()
        self.buttons.addStretch(5)
        self.applybutton = QtGui.QPushButton("Apply")
        self.cancelbutton = QtGui.QPushButton("Cancel")
        self.buttons.addWidget(self.cancelbutton)
        self.buttons.addWidget(self.applybutton)
        self.applybutton.setDefault(True)
        self.applybutton.clicked.connect(self.accept)
        self.cancelbutton.clicked.connect(self.reject)
        self.layout.addLayout(self.buttons)
        self.finished.connect(self.model.updateDriver)

    def exec_with_driver(self, driver):
        self.model.load_driver(driver)
        return self.exec()

class ChannelView(QtGui.QGroupBox):
    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QtGui.QSizePolicy.MinimumExpanding,
                            QtGui.QSizePolicy.Minimum)
        self.model = model
        self.layout = QtGui.QFormLayout()
        self.layout.setFieldGrowthPolicy(QtGui.QFormLayout.ExpandingFieldsGrow)
        self.setLayout(self.layout)
        self.update_title()
        self.load_contents()

    def load_contents(self):
        for j, entry in enumerate(self.model.configmap().items()):
            try:
                editor = views.ParameterView.create(**(entry[1]))
            except NotImplementedError as e:
                MessageManager.not_implemented("Not implemented", str(e))
                entry[1]['typ'] = 'str'
                editor = views.ParameterView.create(**(entry[1]))
            self.layout.addRow(entry[0], editor)

    def update_title(self):
        """update title with the current model setting."""
        label = self.model.label
        if len(label.strip()) == 0:
            title = self.model.name
        else:
            title = "{0}: {1}".format(self.model.name, label)
        self.setTitle(title)


class BaseChannelModel(QtCore.QObject):
    def __init__(self, name, parent=None):
        super().__init__(parent)
        self.name  = name
        self.label = ''
        self.inuse = False
        self._range = "±10 V"
        self._unit  = "V"
        self._scale = 1.0

    def __getattr__(self, name):
        if name == "range":
            return self.get_range()
        elif name == "unit":
            return self.get_unit()
        elif name == "scale":
            return self.get_scale()
        else:
            return super().__getattr__(name)

    def __setattr__(self, name, value):
        if name == "range":
            self.set_range(value)
        elif name == "unit":
            self.set_unit(value)
        elif name == "scale":
            self.set_scale(value)
        else:
            super().__setattr__(name, value)

    def configmap(self):
        d = OrderedDict()
        d['Input range']        = dict(typ='str',
                                    getter=self.get_range,
                                    setter=self.set_range)
        d['Unit']               = dict(typ='str',
                                    getter=self.get_unit,
                                    setter=self.set_unit)
        d['Scale (Unit/V_in)']  = dict(typ='float',
                                    getter=self.get_scale,
                                    setter=self.set_scale)
        return d

    def get_range(self):
        return self._range

    def get_unit(self):
        return self._unit

    def get_scale(self):
        return self._scale

    def set_range(self, value):
        self._range = value

    def set_unit(self, value):
        self._unit = value

    def set_scale(self, value):
        try:
            self._scale = float(value)
        except ValueError as e:
            raise ValueError("failed to parse: '{0}'".format(value)) from e
