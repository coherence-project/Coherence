# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php
"""

This is a compatibility-wrapper for the old coherence.external.inotify
interface.

DO NOT USE THIS anymore, directly use twisted.internet.inotify instead.

"""
# Copyright 2006-2009 Frank Scholz <coherence@beebits.net>
# Modified by Colin Laplace, added is_watched() function
# Copyright 2008 Adroll.com and Valentino Volonghi <dialtone@adroll.com>
# Modified by Valentino Volonghi.
#  * Increased isWatched efficiency, now it's O(1)
#  * Code reorganization, added docstrings, Twisted coding style
#  * Introduced an hack to partially solve a race condition in auto_add.
#  * Removed code that didn't use libc 2.4 but magic hacks
#    -> reverted, as it might still be needed somewhere (fs)
#  * Used fdesc.readFromFD to read during doRead

from functools import partial

from twisted.internet import inotify
from twisted.internet.inotify import *
from twisted.python.filepath import FilePath


def flag_to_human(mask):
    return inotify.humanReadableMask(mask)


class INotify(inotify.INotify):
    """
    Compatibility class for old coherence.external.inotify interface
    """
    def __init__(self, *args, **kwargs):
        super(INotify, self).__init__(*args, **kwargs)
        self.startReading()

    def watch(self, path, mask=IN_WATCH_MASK, auto_add=None,
              callbacks=None, recursive=False):
        if not isinstance(path, FilePath):
            path = FilePath(path)
        if callbacks is not None:
            assert len(callbacks) == 2, callbacks
            callback = partial(callbacks[0], data=callbacks[1])
            callbacks=[callbacks]
        return super(INotify, self).watch(
            path, mask, autoAdd=auto_add,
            callbacks=callbacks, recursive=recursive)

    def release(self):
        return self.connectionLost(None)

    def isWatched(self, path):
        """
        Helper function that checks if the path is already monitored
        and returns its watchdescriptor if so.

        @param path: The path that should be checked
        @type path: L{FilePath} or C{unicode} or C{str}
        """

        if not isinstance(path, FilePath):
            path = FilePath(path)
        return self._isWatched(path)


    def flag_to_human(self,mask):
        return flag_to_human(mask)

if __name__ == '__main__':

    def notify(self, filepath, mask):
        print "event %s on %s" % (
            ', '.join(inotify.humanReadableMask(mask)), filepath)

    i = INotify()
    print i
    i.watch(unicode('/tmp'), auto_add=True, callbacks=(notify,None),
            recursive=True)

    i2 = INotify()
    print i2
    i2.watch('/', auto_add=True, callbacks=(notify,None), recursive=False)

    reactor.run()
