import platform
import sys

__version_info__ = (0,6,7)
__version__ = '.'.join(map(str,__version_info__))

SERVER_ID = ','.join([platform.system(),
                      platform.release(),
                      'UPnP/1.0,Coherence UPnP framework',
                      __version__])


try:
    from twisted import version as twisted_version
    from twisted.web import version as twisted_web_version
    from twisted.python.versions import Version
except ImportError, exc:
    # log error to stderr, might be useful for debugging purpose
    sys.stderr.write("Twisted >= 2.5 and Twisted.Web >= 2.5 are required. "\
                     "Please install them.\n")
    raise

try:
    if twisted_version < Version("twisted", 2, 5, 0):
        raise ImportError("Twisted >= 2.5 is required. Please install it.")

    if twisted_web_version < Version("twisted.web", 2, 5, 0):
        raise ImportError("Twisted.Web >= 2.5 is required. Please install it")
except ImportError, exc:
    # log error to stderr, might be useful for debugging purpose
    for arg in exc.args:
        sys.stderr.write("%s\n" % arg)
    raise
