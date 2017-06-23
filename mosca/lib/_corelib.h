#include <stddef.h>
#define PlatformIsUNIX    0
#define PlatformIsWindows 1

const int platform;

#ifdef _WIN32
#include <winsock2.h> // instead of windows.h

typedef CRITICAL_SECTION    _opaquemutex_t;
typedef CONDITION_VARIABLE  _opaquecond_t;

#else
#include <pthread.h>

typedef pthread_mutex_t     _opaquemutex_t;
typedef pthread_cond_t      _opaquecond_t;
#endif

typedef struct _coremutex {
    _opaquemutex_t  _opaque;
} coremutex;

typedef struct _corecond {
    _opaquecond_t   _opaque;
} corecond;

/**
*   the below function returns zero if no error.
*/

#ifdef __clang__
    #pragma clang diagnostic ignored "-Wunused-function"
#elif __GNUC__
    #pragma gcc diagnostic ignored "-Wunused-function"
#elif _MSC_VER
    #pragma warning( disable: 4930 )
    // should be: unused-function
#endif

int coremutex_init      (coremutex *mutex);
int coremutex_lock      (coremutex *mutex);
int coremutex_trylock   (coremutex *mutex);
int coremutex_unlock    (coremutex *mutex);
int coremutex_free      (coremutex *mutex);

int corecond_init       (corecond *cond);
int corecond_wait       (corecond *cond, coremutex *mutex, long timeout_msec);
int corecond_notify     (corecond *cond);
int corecond_notify_all (corecond *cond);
int corecond_free       (corecond *cond);

size_t get_error        (int code, char *buf, size_t buflen);
