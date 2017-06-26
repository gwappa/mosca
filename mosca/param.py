
import pyqtgraph as pg
from pyqtgraph.Qt import QtGui, QtCore
from . import models
from .messages import MessageManager

class ParameterController(QtCore.QObject):
    """a proxy class for handling specific types of parameter access and update.

    Attributes
    -----------

    mode    -- the data type e.g. 'str', 'bool', 'int', 'float', 'choice', 'label', 'dir'
                if the specified data type is registered to FormView, you can automatically
                create a corresponding widget through FormView.create().

    label   -- A string object used for displaying purposes.
                Typically it is shown as a label in the form layout.

    getter  --
    setter  -- Functions to access or change this parameter.
                Note that, in the setter method, you can validate the value
                and raise a ValueError when it fails.
                In addition, you can leave the setter None if you want it to be
                a read-only parameter.

    signal  -- The PyQt signal object to be capture the changes that are made
                from outside of this ParameterController's scope.

    """

    mode = 'str' # 'str', 'bool', 'int', 'float', 'dir', 'choice', 'label'
    get_value = None # a compulsive getter method
    set_value = None # leave it None, and it becomes a read-only value

    def __init__(self, mode='str', label='', getter=None, setter=None, signal=None, parent=None):
        super().__init__(parent)
        self.mode       = mode
        self.label      = label
        self.get_value  = getter
        self.set_value  = setter if setter is not None else self.read_only
        self.changed    = signal
        self.readonly   = (setter is None)

    def read_only(self, value):
        raise ValueError("this parameter is read-only: no setter is specified")


class FormView(object):
    """a base class to define the behavior of the form objects.

    Because it is intended to be used through a multiple inheritance with a QWidget,
    its __init__ is intentionally left blank (to accept any combinations of arguments).

    Use __configure__ to perform the initialization as a FormView object.
    Without calling __configure__, FormView does not function properly."""

    @staticmethod
    def create(controller, mode=None, parent=None):
        """formats a ParameterController instance into a QWidget form item.
        returns (label string, widget) pair.

        optionally, you can force the type of the object via `mode` keyword ('str', 'float', 'int', 'bool').
        """
        assert isinstance(controller, ParameterController), "needs to be a ParameterController, got {0}".format(controller.__class__)
        mode = controller.mode if mode is None else mode
        if mode in ('str', 'int', 'float'):
            return (controller.label, LineEditView(controller, parent))
        elif mode == 'bool':
            return ('', CheckBoxView(controller, parent))
        else:
            raise NotImplementedError("mode '{0}' has not been implemented. Swapped to 'str'.".format(controller.mode))
            # return DirectoryView(controller, parent)


    def __init__(self, *args, **kwargs):
        """intentionally left blank to work with any type of __init__ call for a QWidget object.
        see __configure__ for initializing a FormView."""
        pass

    def __configure__(self, model=None, viewreader=None, viewwriter=None, formatter=str):
        """used as another initializer for a FormView object.

        Parameters
        ----------

        model       -- the ParameterController object to work with.

        viewreader  -- the 'read' method to read the value from the GUI widget.

        viewwriter  -- the 'write' method to change the value of the GUI widget.

        formatter   -- the single-argument function to format the data from the GUI widget to pass to the 'model'.

        """
        self._valuechanging = False
        self.model      = model
        self.viewreader = viewreader
        self.viewwriter = viewwriter
        self.formatter  = formatter
        self.__readmodel__()
        if self.model.changed is not None:
            self.model.changed.connect(self.read_model)

    def __writemodel__(self):
        """the worker method for view-read, model-write operation.
        use validate_value() instead to avoid infinite recursion.
        """
        self.model.set_value(self.viewreader())

    def __readmodel__(self):
        """the worker method for model-read, view-write operation.
        use read_model() instead to avoid infinite recursion.
        """
        self.viewwriter(self.formatter(self.model.get_value()))

    def read_model(self):
        """model-read, view-write operation."""
        self._valuechanging = True
        self.__readmodel__()
        self._valuechanging = False

    def validate_value(self):
        """view-read, model-write operation.

        It properly handles errors, and avoids going into infinite recursion.
        """
        if self._valuechanging:
            return
        try:
            self._valuechanging = True
            self.__writemodel__()
        except ValueError as e:
            MessageManager.warn_revert("Parameter error", str(e))
            self.__readmodel__()
        finally:
            self._valuechanging = False

class CheckBoxView(QtGui.QCheckBox, FormView):
    """A default FormView for type 'bool'."""

    def __init__(self, controller, parent=None):
        super().__init__(controller.label, parent)
        self.__configure__(model=controller, viewreader=self.isChecked, viewwriter=self.setChecked, formatter=bool)
        self.clicked.connect(self.validate_value)

class LineEditView(QtGui.QLineEdit, FormView):
    """A default FormView for types 'str', 'int' and 'float'."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        if controller.mode == 'int':
            self.setValidator(QtGui.QIntValidator(self))
        elif controller.mode == 'float':
            self.setValidator(QtGui.QDoubleValidator(self))
        self.__configure__(model=controller, viewreader=self.text, viewwriter=self.setText, formatter=str)
        self.editingFinished.connect(self.validate_value)
