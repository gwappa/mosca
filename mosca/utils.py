
import functools


def TODO(comment):
    """just a mark that there is something to do here"""
    def _todowrapper(func):
        if isinstance(func, type):
            class _wrapperclass(func):
                print("*** <TODO> {0}: {1}".format(func.__name__, comment))
                pass
            return _wrapperclass
        else:
            @functools.wraps(func)
            def _todowrapped(*args, **kwargs):
                print("*** <TODO> {0}: {1}".format(func.__name__, comment))
                return func(*args, **kwargs)
            return _todowrapped
    return _todowrapper

def ensure_attribute(attrname, genfunc=None):
    def _ensured_wrapper(func):
        @functools.wraps(func)
        def _wrapper_called(*args, **kwargs):
            obj = args[0]
            if (not hasattr(obj, attrname)) or (getattr(obj, attrname) is None):
                if genfunc is None:
                    if callable(obj):
                        _init = obj
                    else:
                        raise ValueError("could not determine how to generate '{0}'".format(attrname))
                else:
                    _init = genfunc
                setattr(obj, attrname, _init())
            return func(*args, **kwargs)
        return _wrapper_called
    return _ensured_wrapper

def validate_integer(val, rng, lab):
    try:
        val = int(val)
    except ValueError as e:
        raise ValueError("Failed to parse {0}: '{1}'".format(lab, val)) from e
    if (val < rng[0]) or (val > rng[1]):
        Lab = lab[0].upper() + lab[1:]
        raise ValueError("{0} must be >{1} and <{2}".format(Lab, *(rng)))
    return val

def ensure_directory(val):
    return val

