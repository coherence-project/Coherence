# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2007, Philippe Normand <philippe@fluendo.com>

from coherence.extern.log import log as externlog
from coherence.extern.log.log import *
import os

def human2level(levelname):
    levelname = levelname.lower()
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

    o = ""
    if object:
        o = '"' + object + '"'

    where = "(%s:%d)" % (file, line)

    try:

        # level   cat      time
        # 5 + 1 + 27 + 1 + 15 + 1 + 30 == 80

        sys.stderr.write('%-5s %-27s %-15s ' % (
            getLevelName(level), category, time.strftime("%b %d %H:%M:%S")))
        sys.stderr.write(' %s %s\n' % (message, where))

        # old: 5 + 1 + 20 + 1 + 12 + 1 + 32 + 1 + 7 == 80
        #sys.stderr.write('%-5s %-20s %-12s %-32s [%5d] %-4s %-15s %s\n' % (
        #    level, o, category, where, os.getpid(),
        #    "", time.strftime("%b %d %H:%M:%S"), message))
        sys.stderr.flush()
    except IOError, e:
        if e.errno == errno.EPIPE:
            # if our output is closed, exit; e.g. when logging over an
            # ssh connection and the ssh connection is closed
            os._exit(os.EX_OSERR)
        # otherwise ignore it, there's nothing you can do

def init(logfile=None,loglevel='*:2'):
    externlog.init('COHERENCE_DEBUG')
    externlog.setPackageScrubList('coherence', 'twisted', 'upntest')

    if logfile is not None:
        outputToFiles(logfile, logfile)

    # log WARNINGS by default
    if not os.getenv('COHERENCE_DEBUG'):
        setDebug(loglevel)

    if externlog.stderrHandler in externlog._log_handlers_limited:
        externlog.removeLimitedLogHandler(externlog.stderrHandler)
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
        self.log(msg, *args)

    def error(self, msg, *args):
        self.log(msg, *args)

    def msg(self, message, *args):
        self.info(message, *args)