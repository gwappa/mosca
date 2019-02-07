
import traceback
from collections import OrderedDict
from pyqtgraph.Qt import QtGui, QtCore
from . import utils

class ValueModel:
    """a model to hold a value in it (to be used from within a tuple)"""
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return "ValueModel({0})".format(repr(self.value))

def ensure_singleton(func):
    return classmethod(utils.ensure_attribute('_singleton')(func))

class SingletonManager(QtCore.QObject):
    _singleton = None

    def __init__(self, parent=None):
        super().__init__(parent)

    @ensure_singleton
    def get_instance(cls):
        return cls._singleton

class DriverInterface(QtCore.QObject):
    """An abstract interface that fits with the driver-manager model."""

    def __init__(self, parent):
        super().__init__(parent)

    def configs(self):
        """returns a list of ParameterController's
        for generation of GUI configuration forms.
        """
        return []

class BaseDriverManager(QtCore.QObject):
    """A base class that deals with management of modular drivers.

    Emits driverchanged(driver) signal when the driver selection has changed.
    """

    driverchanged = QtCore.pyqtSignal(DriverInterface)

    def __init__(self, name, parent=None):
        super().__init__(parent)
        self.name       = name
        self.current    = None
        self.drivers    = OrderedDict()
        self.driverchanging = False

    def moveToThread(self, th):
        super().moveToThread(th)
        for name, driver in self.drivers.items():
            driver.moveToThread(th)

    def add_driver(self, driver):
        if driver.name in self.drivers.keys():
            raise NameError("{0} driver with name '{1}' already exists.".format(self.name, driver.name))
        self.drivers[driver.name] = driver
        if self.current is None:
            self.current = driver

    def load_drivers(self, driverconfigs):
        registrar = """
def _():
    import {module}
    self.add_driver({module}.{class}({args}))
_()
"""
        default_driver = None
        for i, cfg in enumerate(driverconfigs):
            try:
                exec(registrar.format(**cfg), {'self':self})
                isdefault = cfg.get('default', None)
                if (isdefault is not None) and (bool(isdefault) == True):
                    default_driver = i
            except ModuleNotFoundError:
                print("***{managername}: could not load driver class: '{module}.{class}'".format(managername=self.name,
                        **cfg))
            except:
                traceback.print_exc()
                print("***{managername}: could not load driver class: '{module}.{class}'".format(managername=self.name,
                        **cfg))
        if default_driver is not None:
            self.set_driver(i)

    def get_drivers(self):
        return self.drivers

    def get_driver(self):
        return self.current

    def get_index(self, driver=None):
        if driver is None:
            driver = self.current
        return [k for k in self.drivers.values()].index(driver)

    def set_driver(self, name):
        if self.driverchanging == True:
            return

        if isinstance(name, int):
            return self.set_driver([k for k in self.drivers.keys()][name])

        if name not in self.drivers.keys():
            raise NameError(f"{self.name}: driver with name '{name}' is not found.")
        self.driverchanging = True
        try:
            self.current = self.drivers[name]
            print(f"[{self.name}] driver changed to: {self.current}")
            self.driverchanged.emit(self.current)
        except:
            traceback.print_exc()
        finally:
            self.driverchanging = False


##
## Concurrency-related
##

class SynchronizedState(QtCore.QObject):
    """a kind of a mutex-locker & condition object, in a form of a context manager.
    __enter__() locks the mutex, and __exit__() frees it.
    you need to lock it before calling wait() or notify()."""

    def __init__(self, parent=None, mutex=None):
        super().__init__(parent)
        self._mutex = QtCore.QMutex() if mutex is None else mutex
        self._condition = QtCore.QWaitCondition()
        self._state = False

    def __enter__(self):
        self._mutex.lock()
        return self

    def __exit__(self, *exc):
        self._mutex.unlock()
        return False

    def lock(self):
        self._mutex.lock()

    def unlock(self):
        self._mutex.unlock()

    def set(self):
        """sets the internal state True, and calls fire().
        acquire the lock with the object before calling set()"""
        self._state = True
        self.fire()

    def reset(self):
        """resets the internal state to False. does _not_ call fire().
        acquire the lock with the object before calling reset()."""
        self._state = False

    def fire(self):
        """sets the internal event and notifies it to all the listeners.
        acquire the lock with the object before calling fire()."""
        self._condition.wakeAll()

    def wait(self, timeout=None):
        """waits until the internal event is set and notified.
        acquire the lock with the object before calling wait()."""
        if self._state == True:
            return
        if timeout is None:
            timeout = sys.maxsize
        while self._state == False:
            self._condition.wait(self._mutex, timeout)
