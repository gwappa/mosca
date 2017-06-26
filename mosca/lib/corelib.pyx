from libc.stdio cimport printf
from cpython cimport array as carray
from corelib cimport *
import array

cdef carray.array chararray = array.array('b')

cdef carray.array err = carray.clone(chararray, BUFSIZ, zero=False)

cpdef void errorcheck(int code):
    if code != 0:
        valid = get_error(code, err.data.as_chars, BUFSIZ)
        raise RuntimeError(err.tobytes()[:valid].decode('utf8'))

cdef class Mutex:
    # cdef mutex_t    _mutex
    # cdef int        _err

    def __cinit__(self):
        self._err = 0
        errorcheck(mutex_init(&(self._mutex)))

    def __dealloc__(self):
        mutex_free(&(self._mutex))

    def lock(self):
        self._err = mutex_lock(&(self._mutex))
        return self._err

    def trylock(self):
        self._err = mutex_trylock(&(self._mutex))
        return self._err

    def unlock(self):
        self._err = mutex_unlock(&(self._mutex))
        return self._err

cdef class Condition:
    # cdef cond_t     _cond
    # cdef int        _err

    def __cinit__(self):
        self._err = 0
        errorcheck(cond_init(&(self._cond)))

    def __dealloc__(self):
        cond_free(&(self._cond))

    def wait(self, Mutex mutex, long timeout_msec):
        self._err = cond_wait(&(self._cond), &(mutex._mutex), timeout_msec)
        return self._err

    def notify(self):
        self._err = cond_notify(&(self._cond))
        return self._err

    def notify_all(self):
        self._err = cond_notify_all(&(self._cond))
        return self._err
