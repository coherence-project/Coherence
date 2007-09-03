# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2007, Philippe Normand <philippe@fluendo.com>

from coherence.extern.log import log as externlog
from coherence.extern.log.log import *
import os

def human2level(levelname):
    levelname = levelname.lower()
    if levelname.startswith('none'):
        return 0
    if levelname.startswith('error'):
        return 1
    if levelname.startswith('warn'):
        return 2
    if levelname.startswith('info'):
        return 3
    if levelname.startswith('debug'):
        return 4
    return 5

def customStderrHandler(level, object, category, file, line, message):
    """
    A log handler that writes to stderr.

    @type level:    string
    @type object:   string (or None)
    @type category: string
    @type message:  string
    """
    if not isinstance(message, basestring):
        message = str(message)

    if isinstance(message, unicode):
        message = message.encode('utf-8')

    message = "".join(message.splitlines())
    where = "(%s:%d)" % (file, line)

    formatted_level = getFormattedLevelName(level)
    formatted_time = time.strftime("%b %d %H:%M:%S")
    formatted = '%s %-27s %-15s ' % (formatted_level, category,
                                     formatted_time)

    safeprintf(sys.stderr, formatted)
    safeprintf(sys.stderr, ' %s %s\n', message, where)

    sys.stderr.flush()

def init(logfile=None,loglevel='*:2'):
    externlog.init('COHERENCE_DEBUG', True)
    externlog.setPackageScrubList('coherence', 'twisted')

    if logfile is not None:
        outputToFiles(stdout=None, stderr=logfile)

    # log WARNINGS by default
    if not os.getenv('COHERENCE_DEBUG'):
        if loglevel.lower() != 'none':
            setDebug(loglevel)

    if externlog.stderrHandler in externlog._log_handlers_limited:
        externlog.removeLimitedLogHandler(externlog.stderrHandler)
        if os.getenv('COHERENCE_DEBUG') or loglevel.lower() != 'none':
            "print addLimitedLogHandler(customStderrHandler)"
            externlog.addLimitedLogHandler(customStderrHandler)

def set_debug(loglevel):
    setDebug(loglevel)

def show_levels():
    print externlog._categories

# Make Loggable a new-style object
class Loggable(externlog.Loggable, object):

    def logFunction(self, *args):
        if len(args) > 1:
            format = args[0]
            arguments = args[1:]
            try:
                format % arguments
            except TypeError:
                format += " ".join(["%r" for i in arguments])
            args = (format,) + arguments
        return args

    def critical(self, msg, *args):
        self.warning(msg, *args)

    #def error(self, msg, *args):
    #    self.log(msg, *args)

    def msg(self, message, *args):
        self.info(message, *args)
