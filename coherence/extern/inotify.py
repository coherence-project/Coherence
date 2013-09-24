# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php
"""
This is a compatibility-wrapper for the old coherence.external.inotify
interface.

DO NOT USE THIS anymore, directly use twisted.internet.inotify instead.

Sorry, but the old coherence.external.inotify implementation had some
nasty bugs. So it's better to make a rather hard cut instead of
trying to keep the bugs.


Converting your callbacks:
----------------------------

Instead of::

  my_inotify.watch(..., callbacks=(_callback, EXTRA_ARG))
  my_inotify.watch(..., callbacks=(my_callback, None))

use::

  from functools import partial
  my_inotify.watch(..., callbacks=[partial(_callbacks, data=EXTRA_ARG)])
  my_inotify.watch(..., callbacks=[my_callback])

Please note: The callbacks are now called with a FilePath as second
argument.

"""
# Copyright 2006-2009 Frank Scholz <coherence@beebits.net>
# Modified by Colin Laplace, added is_watched() function
# Copyright 2008 Adroll.com and Valentino Volonghi <dialtone@adroll.com>
# Copyright 2013 Hartmut Goebel <h.goebel@crazy-compilers.com>

from functools import partial

import warnings
warnings.warn("coherence.extern.inotify is deprecated.")

from twisted.internet import inotify
from twisted.internet.inotify import *
from twisted.python.filepath import FilePath


def flag_to_human(mask):
    return inotify.humanReadableMask(mask)


class INotify(inotify.INotify):
    """
    Compatibility class for old coherence.external.inotify interface.

    DO NOT USE THIS anymore, directly use twisted.internet.inotify instead.
    """
    def __init__(self, reactor=None):
        super(INotify, self).__init__(reactor)
        self.startReading()

    def watch(self, path, mask=IN_WATCH_MASK, autoAdd=None,
              callbacks=None, recursive=False):
        if not isinstance(path, FilePath):
            path = FilePath(path)
        assert callbacks is None or isinstance(callbacks, list)
        return super(INotify, self).watch(
            path, mask, autoAdd, callbacks, recursive)

    def release(self):
        return self.connectionLost(None)

    def flag_to_human(self,mask):
        return flag_to_human(mask)

if __name__ == '__main__':
    from twisted.internet import reactor

    def notify(self, filepath, mask, data=None):
        print "event %s on %s" % (
            ', '.join(inotify.humanReadableMask(mask)), filepath)

    i = INotify()
    print i
    i.watch(unicode('/tmp/aaa'), autoAdd=True, callbacks=[notify],
            recursive=True)

    i2 = INotify()
    print i2
    i2.watch('/', autoAdd=True, callbacks=[notify], recursive=False)

    reactor.run()
