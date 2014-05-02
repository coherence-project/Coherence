# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2013, Hartmut Goebel <h.goebel@crazy-compilers.com>

import os
import logging

LOG_FORMAT =('%(levelname)s %(name)-27s '
             '%(asctime)s %(message)s '
             '(%(filename)s:%(lineno))')

ENV_VAR_NAME = 'COHERENCE_DEBUG'


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
