# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2013, Hartmut Goebel <h.goebel@crazy-compilers.com>

import os
import sys
import logging

LOG_FORMAT = ('%(asctime)s %(levelname)s '
             '%(name)s: %(message)s '
             '(%(filename)s:%(lineno))')

ENV_VAR_NAME = 'COHERENCE_DEBUG'

# This is taken from std.-module logging, see Logger.findCaller below.
# _srcfile is used when walking the stack to check when we've got the first
# caller stack frame.
#
if hasattr(sys, 'frozen'):  # support for py2exe
    _srcfile = "coherence%slog%s" % (os.sep, __file__[-4:])
elif __file__[-4:].lower() in ['.pyc', '.pyo']:
    _srcfile = __file__[:-4] + '.py'
else:
    _srcfile = __file__
_srcfile = os.path.normcase(_srcfile)
_srcfiles = (_srcfile, logging._srcfile)

class Logger(logging.Logger):

    def findCaller(self):
        # This is nearly a plain copy of logging.Logger.findCaller
        # Since findCaller tests for _srcfile to find the caller, we
        # need to test for this file and the loggin module.
        #
        # :fixme: If each subclass of Loggable calls __init__ properly
        # (see Loggable.__getLogger below), we can build a different
        # delegation and remove this hak/work-around.
        f = logging.currentframe()
        #On some versions of IronPython, currentframe() returns None if
        #IronPython isn't run with -X:Frames.
        if f is not None:
            f = f.f_back
        rv = "(unknown file)", 0, "(unknown function)"
        while hasattr(f, "f_code"):
            co = f.f_code
            filename = os.path.normcase(co.co_filename)
            if filename in _srcfiles:  # # chaanged line
                f = f.f_back
                continue
            rv = (co.co_filename, f.f_lineno, co.co_name)
            break
        return rv

logging.setLoggerClass(Logger)


class Loggable(object):
    """
    Base class for objects that want to be able to log messages with
    different level of severity.  The levels are, in order from least
    to most: log, debug, info, warning, error.

    @cvar logCategory: Implementors can provide a category to log their
       messages under.
    """

    logCategory = 'default'
    _Loggable__logger = None

    def __init__(self):
        self.__getLogger()

    def __getLogger(self):
        # :fixme: get rid of this. Every subclass of Loggable should
        # call Loggable.__init__.
        self.__logger = logging.getLogger(self.logCategory)

    def logObjectName(self):
        """Overridable object name function."""
        # cheat pychecker
        for name in ['logName', 'name']:
            if hasattr(self, name):
                return getattr(self, name)
        return None

    def log(self, message, *args, **kwargs):
        if self.__logger is None: self.__getLogger()
        self.__logger.log(message, *args, **kwargs)

    def warning(self, message, *args, **kwargs):
        if self.__logger is None: self.__getLogger()
        self.__logger.warning(message, *args, **kwargs)

    def info(self, message, *args, **kwargs):
        if self.__logger is None: self.__getLogger()
        self.__logger.info(message, *args, **kwargs)

    def critical(self, message, *args, **kwargs):
        if self.__logger is None: self.__getLogger()
        self.__logger.critical(message, *args, **kwargs)

    def debug(self, message, *args, **kwargs):
        if self.__logger is None: self.__getLogger()
        self.__logger.debug(message, *args, **kwargs)

    def error(self, message, *args, **kwargs):
        if self.__logger is None: self.__getLogger()
        self.__logger.error(message, *args, **kwargs)

    def exception(self, message, *args, **kwargs):
        if self.__logger is None: self.__getLogger()
        self.__logger.exception(message, *args, **kwargs)

    fatal = critical
    warn = warning
    msg = info


getLogger = logging.getLogger


def init(logfilename=None, loglevel=logging.WARN):
    logger = logging.getLogger()
    logging.addLevelName(100, 'NONE')

    logging.basicConfig(filename=logfilename, level=loglevel,
                        format=LOG_FORMAT)

    if ENV_VAR_NAME in os.environ:
        logger.setLevel(os.environ[ENV_VAR_NAME])
    else:
        logger.setLevel(loglevel)
