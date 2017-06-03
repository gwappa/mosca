
import sys, os, pprint, struct
from collections import OrderedDict
import numpy as np
from pyqtgraph.Qt import QtGui, QtCore
from . import models
from . import utils
from . import states
from . import devices
from .utils import validate_integer

##
## I/O-related classes
##

BASETYPE = np.dtype('float')

StorageManager = None

class IODriverManager(models.BaseDriverManager):
    def prepare(self, save=True):
        if (save == True) and (self.current is not None):
            self.current.prepare()
        self.saved = save
        with states.StateManager.doneStorage as evt:
            evt.reset()

    def finalize(self):
        if self.saved == True:
            self.current.finalize()
        del self.saved
        with states.StateManager.doneStorage as evt:
            evt.set()

class BaseIODriver(models.DriverInterface):
    """Defines basic behaviors as an I/O driver."""

    def __init__(self, name, parent=None):
        super().__init__(parent)
        self.name       = name
        self._directory = os.getcwd()
        self._basename  = 'wave'
        self._acqno     = 1

    def prepare(self):
        """prepares for the next acquisition."""
        pass

    def update(self, data):
        """a slot to update with newly acquired data."""
        pass

    def finalize(self):
        """finalizes the current acquisition"""
        pass

    def __getattr__(self, name):
        if name == 'directory':
            return self.get_directory()
        elif name == 'basename':
            return self.get_basename()
        elif name == 'acqno':
            return self.get_acqno()
        else:
            raise AttributeError(name)

    def __setattr__(self, name, val):
        if name == 'directory':
            return self.set_directory(val)
        elif name == 'basename':
            return self.set_basename(val)
        elif name == 'acqno':
            return self.set_acqno(val)
        else:
            super().__setattr__(name, val)

    def get_directory(self):
        return self._directory

    def get_basename(self):
        return self._basename

    def get_acqno(self):
        return self._acqno

    def set_directory(self, val):
        self._directory = val

    def set_basename(self, val):
        self._basename = val

    def set_acqno(self, val):
        self._acqno = validate_integer(val, (-sys.maxsize, sys.maxsize), 'acquisition number')

    def configmap(self):
        d = OrderedDict()
        d['Directory'] =    dict(typ='dir',
                                    getter=self.get_directory,
                                    setter=self.set_directory)
        d['Basename']  =    dict(typ='str',
                                    getter=self.get_basename,
                                    setter=self.set_basename)
        d['Acquisition number'] = dict(typ='int',
                                    getter=self.get_acqno,
                                    setter=self.set_acqno)
        return d


class NumpyIODriver(BaseIODriver):
    """For saving the acquired data in the numpy NPY format.

    for specification, please refer to: https://docs.scipy.org/doc/numpy/neps/npy-format.html"""
    
    _magic      = b'\x93NUMPY'
    _version    = b'\x01\x00'

    def __init__(self, parent=None):
        super().__init__('NumPy Binary', parent=parent)

    def prepare(self):
        devices.DeviceManager.current.dataAvailable.connect(self.update)
        utils.ensure_directory(self.directory)
        self._nchan = len([ch for ch in devices.DeviceManager.current.channels.values() if ch.inuse == True])
        self._info = dict(descr=BASETYPE.descr[0][1], fortran_order=False, 
            shape=(sys.maxsize, self._nchan))
        self._size = 0
        self._scales = tuple(ch.scale for ch in devices.DeviceManager.current.channels.values() if ch.inuse == True)

        self._headeroffset = len(self._magic) + len(self._version) + 2
        self._header = pprint.pformat(self._info).encode('utf-8')
        headerlen = len(self._header) + 1
        chunklen = self._headeroffset + headerlen
        r = chunklen % 16
        self._headerlen = headerlen if r == 0 else headerlen + (16 - r)

        # TODO: ask if we can overwrite file
        self._target = open(os.path.join(self.directory, 
            "{0}_{1:03d}.npy".format(self.basename, self.acqno)), 'wb')
        self._target.write(self._magic)
        self._target.write(self._version)
        self._target.write(struct.pack('<H', self._headerlen))
        self._target.write(self._header)
        for i in range(self._headerlen - len(self._header) - 1):
            self._target.write(b' ')
        self._target.write(b'\n')

    def update(self, data):
        data = np.array(data, dtype=BASETYPE)
        for i in range(self._nchan):
            data[:,i] *= self._scales[i]
        self._target.write(bytes(data.reshape((-1,), order='C')))
        self._size += data.shape[0]

    def finalize(self):
        devices.DeviceManager.current.dataAvailable.disconnect(self.update)
        self._info['shape'] = (self._size, self._nchan)
        self._header = pprint.pformat(self._info).encode('utf-8')
        self._target.seek(self._headeroffset)
        self._target.write(self._header)
        for i in range(self._headerlen - len(self._header) - 1):
            self._target.write(b' ')
        self._target.write(b'\n')
        self._target.close()

def setup(cfg):
    global StorageManager
    StorageManager = IODriverManager("I/O")
    StorageManager.load_drivers(cfg['storages'])
    # StorageManager.add_driver(NumpyIODriver())





    
