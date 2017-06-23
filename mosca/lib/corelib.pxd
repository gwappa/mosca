
""" a thin wrapper for _corelib.

you can have access to all the functions, plus:

+ you can refer to platformas as constants UNIX/WINDOWS.
+ mutex/conditional type is renamed as mutex_t and cond_t, respectively.
+ Mutex/Condition wrapper Python class is available.
+ errorcheck() Python function is available for raising RuntimeError's.

"""

cdef extern from "_corelib.h":
    DEF PlatformIsUNIX       = 0
    DEF PlatformIsWindows    = 1
    const int platform

    ctypedef struct mutex_t "coremutex":
        pass
    ctypedef struct cond_t "corecond":
        pass

    int mutex_init      "coremutex_init"    (mutex_t *mutex) nogil
    int mutex_lock      "coremutex_lock"    (mutex_t *mutex) nogil
    int mutex_trylock   "coremutex_trylock" (mutex_t *mutex) nogil
    int mutex_unlock    "coremutex_unlock"  (mutex_t *mutex) nogil
    int mutex_free      "coremutex_free"    (mutex_t *mutex) nogil

    int cond_init       "corecond_init"     (cond_t *cond) nogil
    int cond_wait       "corecond_wait"     (cond_t *cond, mutex_t *mutex, long timeout_msec) nogil
    int cond_notify     "corecond_notify"   (cond_t *cond) nogil
    int cond_notify_all "corecond_notify_all" (cond_t *cond) nogil
    int cond_free       "corecond_free"     (cond_t *cond) nogil

    int get_error    (int code, char *buf, int buflen) nogil

cdef int UNIX    = PlatformIsUNIX
cdef int WINDOWS = PlatformIsWindows
cdef size_t BUFSIZ  = 2048

cpdef void errorcheck(int code)

cdef class Mutex:
    cdef mutex_t    _mutex
    cdef int        _err


cdef class Condition:
    cdef cond_t     _cond
    cdef int        _err
