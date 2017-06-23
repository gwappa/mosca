#include "_corelib.h"
#include <stdio.h>
#include <string.h>
#include <errno.h>

#define get_opaque(ptr) (&((ptr)->_opaque))
#define MILLION 1000000
#define BILLION 1000000000


#ifdef _WIN32
  const int platform = PlatformIsWindows;
#else
  const int platform = PlatformIsUNIX;
#endif

int coremutex_init      (coremutex *mutex)
{
#ifdef _WIN32
    InitializeCriticalSectionAndSpinCount(get_opaque(mutex), 0x400); // try setting spin count this way for now
    return 0;
#else
    if( pthread_mutex_init(get_opaque(mutex), 0) ) // try setting mutexatttr this way for now
    {
        return errno;
    } else {
        return 0;
    }
#endif
}

int coremutex_lock      (coremutex *mutex)
{
#ifdef _WIN32
    EnterCriticalSection(get_opaque(mutex));
    return 0;
#else
    if( pthread_mutex_lock(get_opaque(mutex)) )
    {
        return errno;
    } else {
        return 0;
    }
#endif
}

int coremutex_trylock   (coremutex *mutex)
{
#ifdef _WIN32
    return (TryEnterCriticalSection(get_opaque(mutex)) != 0)? 0 : 0xA7; // returns LOCK_FAILED
#else
    switch( pthread_mutex_trylock(get_opaque(mutex)) )
    {
    case 0:
        // successful
        return 0;
    case EBUSY:
        // already locked by another thread
        return EBUSY;
    case EINVAL:
    default:
        // invalid mutex
        return errno;
    }
#endif
}

int coremutex_unlock    (coremutex *mutex)
{
#ifdef _WIN32
    LeaveCriticalSection(get_opaque(mutex));
    return 0;
#else
    if( pthread_mutex_unlock(get_opaque(mutex)) )
    {
        return errno;
    } else {
        return 0;
    }
#endif
}

int coremutex_free      (coremutex *mutex)
{
#ifdef _WIN32
    DeleteCriticalSection(get_opaque(mutex));
    return 0;
#else
    if( pthread_mutex_destroy(get_opaque(mutex)) )
    {
        return errno;
    } else {
        return 0;
    }
#endif
}

int corecond_init       (corecond *cond)
{
#ifdef _WIN32
    InitializeConditionVariable(get_opaque(cond));
    return 0;
#else
    if( pthread_cond_init(get_opaque(cond), 0) )
    {
        return errno;
    } else {
        return 0;
    }
#endif
}

int corecond_wait       (corecond *cond, coremutex *mutex, long timeout_msec)
{
#ifdef _WIN32
    if (SleepConditionVariableCS(get_opaque(cond), get_opaque(mutex), (timeout_msec>=0)? timeout_msec: INFINITE) == 0)
    {
        return GetLastError();
    } else {
        return 0;
    }
#else
    int err;
    if( timeout_msec < 0 ){
        err = pthread_cond_wait(get_opaque(cond), get_opaque(mutex));
    } else {
        struct timespec timeout;
        timeout.tv_nsec = (timeout_msec * MILLION) % BILLION;
        timeout.tv_sec = time(0) + ( timeout_msec - timeout.tv_nsec );
        err = pthread_cond_timedwait(get_opaque(cond), get_opaque(mutex), &timeout);
    }
    if( err ){
        return errno;
    } else {
        return 0;
    }
#endif
}

int corecond_notify     (corecond *cond)
{
#ifdef _WIN32
    WakeConditionVariable(get_opaque(cond));
    return 0;
#else
    if( pthread_cond_signal(get_opaque(cond)) )
    {
        return errno;
    } else {
        return 0;
    }
#endif
}

int corecond_notify_all (corecond *cond)
{
#ifdef _WIN32
    WakeAllConditionVariable(get_opaque(cond));
    return 0;
#else
    if( pthread_cond_broadcast(get_opaque(cond)) )
    {
        return errno;
    } else {
        return 0;
    }
#endif
}

int corecond_free       (corecond *cond)
{
#ifdef _WIN32
    // seems to need nothing for condition variable
    return 0;
#else
    if( pthread_cond_destroy(get_opaque(cond)) )
    {
        return errno;
    } else {
        return 0;
    }
#endif
}

size_t get_error           (int code, char *buf, size_t buflen)
{
#ifdef _WIN32
    size_t ret = FormatMessage(
                    FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS,
                    NULL,
                    code,
                    MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT),
                    (LPSTR)buf,
                    (DWORD)buflen,
                    NULL);
    if( ret == 0 ){
        fprintf(stderr, "***unexpected error occurred during platform::get_error(): %d\n", GetLastError());
    }
    return ret;
#else
    strncpy(buf, strerror(code), buflen-1);
    buf[buflen-1] = '\0';
    return strlen(buf);
#endif
}
