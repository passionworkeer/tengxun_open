"""Module with decorated functions and classes."""

from functools import wraps


def my_decorator(func):
    """A simple decorator."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper


@my_decorator
def decorated_function(x):
    """Function with decorator."""
    return x * 2


class DecoratedClass:
    """Class with decorated method."""

    @my_decorator
    def decorated_method(self):
        """Decorated method."""
        pass
