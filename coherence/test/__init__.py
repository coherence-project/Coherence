
# Copyright 2014 Hartmut Goebel <h.goebel@crazy-compilers.com>

import functools

def wrapped(deferred):
    """
    Decorator for wrapping functions by try-except and ensure
    errback() is called on failure.
    """
    def decorator(callback):
        @functools.wraps(callback)
        def wrapper(*args, **kwargs):
            try:
                callback(*args, **kwargs)
            except:
                deferred.errback()
        return wrapper
    return decorator
