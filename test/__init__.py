import warnings
import sys
import errno
import functools
import socket

from nose.plugins.skip import SkipTest

from urllib3.exceptions import MaxRetryError, HTTPWarning
from urllib3.packages import six

# We need a host that will not immediately close the connection with a TCP
# Reset. SO suggests this hostname
TARPIT_HOST = '10.255.255.1'

# (Arguments for socket, is it IPv6 address?)
VALID_SOURCE_ADDRESSES = [(('::1', 0), True), (('127.0.0.1', 0), False)]
# RFC 5737: 192.0.2.0/24 is for testing only.
# RFC 3849: 2001:db8::/32 is for documentation only.
INVALID_SOURCE_ADDRESSES = [('192.0.2.255', 0), ('2001:db8::1', 0)]


def clear_warnings(cls=HTTPWarning):
    new_filters = []
    for f in warnings.filters:
        if issubclass(f[2], cls):
            continue
        new_filters.append(f)
    warnings.filters[:] = new_filters

def setUp():
    clear_warnings()
    warnings.simplefilter('ignore', HTTPWarning)


def onlyPy26OrOlder(test):
    """Skips this test unless you are on Python2.6.x or earlier."""

    @functools.wraps(test)
    def wrapper(*args, **kwargs):
        msg = "{name} only runs on Python2.6.x or older".format(name=test.__name__)
        if sys.version_info >= (2, 7):
            raise SkipTest(msg)
        return test(*args, **kwargs)
    return wrapper

def onlyPy27OrNewer(test):
    """Skips this test unless you are on Python 2.7.x or later."""

    @functools.wraps(test)
    def wrapper(*args, **kwargs):
        msg = "{name} requires Python 2.7.x+ to run".format(name=test.__name__)
        if sys.version_info < (2, 7):
            raise SkipTest(msg)
        return test(*args, **kwargs)
    return wrapper

def onlyPy3(test):
    """Skips this test unless you are on Python3.x"""

    @functools.wraps(test)
    def wrapper(*args, **kwargs):
        msg = "{name} requires Python3.x to run".format(name=test.__name__)
        if not six.PY3:
            raise SkipTest(msg)
        return test(*args, **kwargs)
    return wrapper

def requires_network(test):
    """Helps you skip tests that require the network"""

    def _is_unreachable_err(err):
        return getattr(err, 'errno', None) in (errno.ENETUNREACH,
                                               errno.EHOSTUNREACH) # For OSX

    @functools.wraps(test)
    def wrapper(*args, **kwargs):
        msg = "Can't run {name} because the network is unreachable".format(
            name=test.__name__)
        try:
            return test(*args, **kwargs)
        except socket.error as e:
            # This test needs an initial network connection to attempt the
            # connection to the TARPIT_HOST. This fails if you are in a place
            # without an Internet connection, so we skip the test in that case.
            if _is_unreachable_err(e):
                raise SkipTest(msg)
            raise
        except MaxRetryError as e:
            if _is_unreachable_err(e.reason):
                raise SkipTest(msg)
            raise
    return wrapper


# Based on http://stackoverflow.com/a/26347105/1405898
class catch_all_warnings(warnings.catch_warnings):
    """A context manager that builds on ``warnings.catch_warnings``, and
       additionally resets filters and warning registries."""

    def __init__(self):
        import urllib3
        self.modules = [urllib3.util.ssl_]
        self._warnreg_copies = {}
        super(catch_all_warnings, self).__init__(record=True)

    def __enter__(self):
        for mod in self.modules:
            if hasattr(mod, '__warningregistry__'):
                reg = mod.__warningregistry__
                self._warnreg_copies[mod] = reg.copy()
                reg.clear()
        result = super(catch_all_warnings, self).__enter__()
        warnings.simplefilter("always")
        return result

    def __exit__(self, *exc_info):
        super(catch_all_warnings, self).__exit__(*exc_info)
        for mod in self.modules:
            if hasattr(mod, '__warningregistry__'):
                mod.__warningregistry__.clear()
            if mod in self._warnreg_copies:
                mod.__warningregistry__.update(self._warnreg_copies[mod])
