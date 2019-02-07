from libc.stdint cimport uint64_t

cdef extern from "NIDAQmx.h":
    DEF DAQmx_Val_Cfg_Default               = -1

    DEF DAQmx_Val_Volts                     = 10348

    DEF DAQmx_Val_Rising                    = 10280
    DEF DAQmx_Val_Falling                   = 10171

    DEF DAQmx_Val_FiniteSamps               = 10178
    DEF DAQmx_Val_ContSamps                 = 10123

    DEF DAQmx_Val_GroupByChannel            = 0
    DEF DAQmx_Val_GroupByScanNumber         = 1

    DEF DAQmx_Val_Acquired_Into_Buffer      = 1
    DEF DAQmx_Val_Transferred_From_Buffer   = 2

    ctypedef void*  TaskHandle
    ctypedef signed long    int32
    ctypedef unsigned long  uInt32
    ctypedef uInt32         bool32
    ctypedef uint64_t       uInt64
    ctypedef double         float64

    ctypedef int32 (*DAQmxEveryNSamplesEventCallbackPtr)(TaskHandle taskHandle,
                            int32 everyNsamplesEventType,
                            uInt32 nSamples,
                            void *callbackData)

    int32 DAQmxCreateTask ( const char taskName[],
                            TaskHandle *taskHandle ) nogil
    int32 DAQmxStartTask (TaskHandle taskHandle) nogil
    int32 DAQmxStopTask (TaskHandle taskHandle) nogil
    int32 DAQmxWaitUntilTaskDone (TaskHandle taskHandle, float64 timeToWait) nogil
    int32 DAQmxClearTask (TaskHandle taskHandle) nogil
    int32 DAQmxCreateAIVoltageChan (TaskHandle taskHandle,
                                    const char physicalChannel[],
                                    const char nameToAssignToChannel[],
                                    int32 terminalConfig,
                                    float64 minVal,
                                    float64 maxVal,
                                    int32 units,
                                    const char customScaleName[]) nogil
    int32 DAQmxCfgSampClkTiming ( TaskHandle taskHandle,
                                    const char source[],
                                    float64 rate,
                                    int32 activeEdge,
                                    int32 sampleMode,
                                    uInt64 sampsPerChan ) nogil
    int32 DAQmxRegisterEveryNSamplesEvent( TaskHandle task,
                                            int32 everyNsamplesEventType,
                                            uInt32 nSamples,
                                            uInt32 options,
                                            DAQmxEveryNSamplesEventCallbackPtr callbackFunction,
                                            void *callbackData) nogil

    int32 DAQmxReadAnalogF64 ( TaskHandle taskHandle,
                                int32 numSampsPerChan,
                                float64 timeout,
                                bool32 fillMode,
                                float64 readArray[],
                                uInt32 arraySizeInSamps,
                                int32 *sampsPerChanRead,
                                bool32 *reserved ) nogil
    int32 DAQmxGetExtendedErrorInfo ( char errorString[],
                                    uInt32 bufferSize) nogil

from libc.stdio cimport printf

from cpython cimport array as carray
import array
from threading import Thread
from collections import OrderedDict

import numpy as np
cimport numpy as cnumpy
cnumpy.import_array()

cimport corelib
from mosca.channels import BaseChannelModel
from mosca.devices import BaseDeviceDriver

boardspecs = {
  "NI6321": {"AI": 16},
  "USB6002": {"AI": 8}
}

DEF bufsiz = 2048
DEF DEFAULT_TIMEOUT_SEC = 10
cdef carray.array cbuf_temp = array.array('b', [])
cdef carray.array dbuf_temp = array.array('d', [])
cdef char errbuf[bufsiz]

class NIDAQmxError(RuntimeError):
    def __init__(self, msg):
        super().__init__(msg)

cpdef void _check_error(int ret):
    cdef uInt32 size
    if ret < 0:
        size = DAQmxGetExtendedErrorInfo(errbuf, bufsiz)
        raise NIDAQmxError( (<bytes>(errbuf[:size])).decode('ascii') )


class Board(BaseDeviceDriver):
    """a wrapper implementation for NI DAQmx-based boards.
    for the moment, it only supports floating-point AI channels in RSE mode."""

    def __init__(self, name, boardtype=None, raterange=None, intervalrange=None,
                    parent=None):
        super().__init__("{0} ({1})".format(name, boardtype),
                            parent=parent,
                            raterange=raterange,
                            intervalrange=intervalrange)
        self._boardname = name
        for i in range(boardspecs[boardtype]["AI"]):
            physical = "{0}/ai{1:d}".format(name, i)
            virtual  = "AI{0:d}".format(i)
            self._channels[virtual] = BaseChannelModel(physical, parent=self)


    def prepare(self):
        self._inuse = [ch for ch in self._channels.values() if ch.inuse == True]
        self._nchan = len(self._inuse)
        self._nsamp = self.interval
        self._buf   = np.empty((self._nsamp * self._nchan,), dtype=float)
        self._buf[:]= np.nan
        self._task = OscilloTask(self, "mosca", self._inuse, self.rate, self.interval)
        self._thread = Thread(target=self._task.start)
        print("prepared: {0} channels with interval {1} samples".format(self._nchan, self._nsamp))

    def start(self):
        self._thread.start()

    def stop(self):
        self._task.stop()
        self._thread.join()
        del self._task
        del self._thread


cdef class OscilloTask:

    cdef double *_buf
    cdef cnumpy.ndarray _array

    cdef carray.array name
    cdef int          _nchan
    cdef uInt32       _interval
    cdef uInt32       _chunksiz
    cdef TaskHandle   _handle
    cdef object       _parent

    cdef corelib.mutex_t _io
    cdef corelib.cond_t  _update
    cdef int          _term
    cdef int32        _read

    def __cinit__(self, parent, name, channels, rate, interval):
        self.name       = array.array('b', name.encode('utf8')+b'\0')
        self._interval  = interval
        self._nchan      = <int>len(channels)
        self._chunksiz  = len(channels)*self._interval
        self._array     = np.empty((self._interval, self._nchan), dtype=np.float64, order='C')

        cdef double[:,:] proxy = self._array
        self._buf       = &(proxy[0,0])
        self._handle    = NULL
        assert isinstance(parent, Board)
        self._parent    = parent
        corelib.errorcheck(corelib.mutex_init(&(self._io)))
        corelib.errorcheck(corelib.cond_init(&(self._update)))
        _check_error(DAQmxCreateTask(self.name.data.as_chars, &self._handle))

    def __dealloc__(self):
        self.close()
        corelib.mutex_free(&(self._io))
        corelib.cond_free(&(self._update))


    def __init__(self, parent, name, channels, rate, interval):
        cdef carray.array namebuf
        cdef float64 _rate = rate
        try:
            for ch in channels:
                namebuf = array.array('b', ch.name.encode('utf8')+b'\0')
                printf("init: AI: %s...", namebuf.data.as_chars)
                _check_error(DAQmxCreateAIVoltageChan(self._handle,
                                namebuf.data.as_chars,
                                "",
                                DAQmx_Val_Cfg_Default,
                                -10.0,
                                10.0,
                                DAQmx_Val_Volts,
                                NULL))
                printf("done.\n")
            printf("init: rate: %d...", _rate)
            _check_error(DAQmxCfgSampClkTiming(self._handle,
                            "",
                            _rate,
                            DAQmx_Val_Rising,
                            DAQmx_Val_ContSamps,
                            self._interval))
            printf("done.\n")
            printf("init: interval: %d...", self._interval)
            _check_error(DAQmxRegisterEveryNSamplesEvent(self._handle,
                            DAQmx_Val_Acquired_Into_Buffer,
                            self._interval,
                            0,
                            OscilloTask.update,
                            <void *>self))
            printf("done.\n")
        except NIDAQmxError as e:
            self.close()
            raise e
        printf("init: done.\n")

    def start(self):
        try:
            self._term      = 0
            corelib.errorcheck(corelib.mutex_lock(&(self._io)))
            printf("starting...\n")
            _check_error(DAQmxStartTask(self._handle))
            printf("started.\n")
            with nogil:
                while self._term == 0:
                    corelib.cond_wait(&(self._update), &(self._io), -1)
                    # printf("update: %d\n", self._read)
                    with gil:
                        self.fire_update()
                corelib.mutex_unlock(&(self._io))
        except NIDAQmxError as e:
            self.close()
            raise e

    def stop(self):
        DAQmxStopTask(self._handle)
        try:
            _check_error(DAQmxWaitUntilTaskDone(self._handle, DEFAULT_TIMEOUT_SEC))
            with nogil:
                corelib.mutex_lock(&(self._io))
                self._term = 1
                corelib.cond_notify_all(&(self._update))
                corelib.mutex_unlock(&(self._io))
        except NIDAQmxError as e:
            raise e
        finally:
            printf("stop\n")
            self.close()

    @staticmethod
    cdef int32 update(TaskHandle handle, int32 evttype, uInt32 nsamp, void *wrapper):
        """registered and called as EveryNSamplesEvent from NIDAQmx.
        'wrapper' should be the pointer to an OscilloTask object for the task.

        Note that the caller thread is _not_ a Python thread, and thus Python can crush
        miserably when you try to call a Python method/function directly from this function.
        Use another thread to wait for the buffer to be filled in."""
        cdef OscilloTask obj
        cdef int32 status
        obj = <OscilloTask>wrapper
        corelib.mutex_lock(&(obj._io))
        status = DAQmxReadAnalogF64(
                        obj._handle,
                        obj._interval,
                        DEFAULT_TIMEOUT_SEC,
                        DAQmx_Val_GroupByScanNumber,
                        obj._buf,
                        obj._chunksiz,
                        &(obj._read),
                        NULL
                    )
        if status < 0:
            obj._read = 0
            obj._term = 1
            obj.close()
            printf("abort\n")

        corelib.cond_notify_all(&(obj._update))
        corelib.mutex_unlock(&(obj._io))
        return 0

    def fire_update(self):
        self._parent.dataAvailable.emit(self._array[:(self._read)])

    def close(self):
        if self._handle is not NULL:
            DAQmxStopTask(self._handle)
            DAQmxClearTask(self._handle)
            self._handle = NULL
            printf("task handle destroyed.\n")
