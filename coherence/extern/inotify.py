# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

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

import os
import struct

try:
    import ctypes
    import ctypes.util
except ImportError:
    raise SystemError("ctypes not detected on this system, can't use INotify")

from twisted.internet import reactor
from twisted.internet.abstract import FileDescriptor
from twisted.internet import fdesc
from twisted.python.filepath import FilePath

# from /usr/src/linux/include/linux/inotify.h

IN_ACCESS =         0x00000001L     # File was accessed
IN_MODIFY =         0x00000002L     # File was modified
IN_ATTRIB =         0x00000004L     # Metadata changed
IN_CLOSE_WRITE =    0x00000008L     # Writtable file was closed
IN_CLOSE_NOWRITE =  0x00000010L     # Unwrittable file closed
IN_OPEN =           0x00000020L     # File was opened
IN_MOVED_FROM =     0x00000040L     # File was moved from X
IN_MOVED_TO =       0x00000080L     # File was moved to Y
IN_CREATE =         0x00000100L     # Subfile was created
IN_DELETE =         0x00000200L     # Subfile was delete
IN_DELETE_SELF =    0x00000400L     # Self was deleted
IN_MOVE_SELF =      0x00000800L     # Self was moved
IN_UNMOUNT =        0x00002000L     # Backing fs was unmounted
IN_Q_OVERFLOW =     0x00004000L     # Event queued overflowed
IN_IGNORED =        0x00008000L     # File was ignored

IN_ONLYDIR =         0x01000000      # only watch the path if it is a directory
IN_DONT_FOLLOW =     0x02000000      # don't follow a sym link
IN_MASK_ADD =        0x20000000      # add to the mask of an already existing watch
IN_ISDIR =           0x40000000      # event occurred against dir
IN_ONESHOT =         0x80000000      # only send event once

IN_CLOSE =      IN_CLOSE_WRITE | IN_CLOSE_NOWRITE   # closes
IN_MOVED =      IN_MOVED_FROM | IN_MOVED_TO         # moves
IN_CHANGED =    IN_MODIFY | IN_ATTRIB               # changes

IN_WATCH_MASK = IN_MODIFY | IN_ATTRIB | \
                IN_CREATE | IN_DELETE | \
                IN_DELETE_SELF | IN_MOVE_SELF | \
                IN_UNMOUNT | IN_MOVED_FROM | IN_MOVED_TO


_FLAG_TO_HUMAN = {
    IN_ACCESS: 'access',
    IN_MODIFY: 'modify',
    IN_ATTRIB: 'attrib',
    IN_CLOSE_WRITE: 'close_write',
    IN_CLOSE_NOWRITE: 'close_nowrite',
    IN_OPEN: 'open',
    IN_MOVED_FROM: 'moved_from',
    IN_MOVED_TO: 'moved_to',
    IN_CREATE: 'create',
    IN_DELETE: 'delete',
    IN_DELETE_SELF: 'delete_self',
    IN_MOVE_SELF: 'move_self',
    IN_UNMOUNT: 'unmount',
    IN_Q_OVERFLOW: 'queue_overflow',
    IN_IGNORED: 'ignored',
    IN_ONLYDIR: 'only_dir',
    IN_DONT_FOLLOW: 'dont_follow',
    IN_MASK_ADD: 'mask_add',
    IN_ISDIR: 'is_dir',
    IN_ONESHOT: 'one_shot'
}

# system call numbers are architecture-specific
# see /usr/include/linux/asm/unistd.h and look for inotify
_inotify_syscalls = { 'i386': (291,292,293),  # FIXME, there has to be a better way for this
                      'i486': (291,292,293),
                      'i586': (291,292,293),
                      'i686': (291,292,293),
                      'x86_64': (253,254,255), # gotten from FC-6 and F-7
                      'armv6l':(316,317,318),              # Nokia N800
                      'armv5tej1':(316,317,318),           # Nokia N770
                      'ppc': (275,276,277),                # PPC, like PS3
                      }

def flag_to_human(mask):
    """
    Auxiliary function that converts an hexadecimal mask into a series
    of human readable flags.
    """
    s = []
    for (k, v) in _FLAG_TO_HUMAN.iteritems():
        if k & mask:
            s.append(v)
    return s


class Watch(object):
    """
    Watch object that represents a Watch point in the filesystem.

    @ivar path: The path over which this watch point is monitoring
    @ivar mask: The events monitored by this watchpoint
    @ivar auto_add: Flag that determines whether this watch point
                    should automatically add created subdirectories
    @ivar callbacks: C{list} of C{tuples} of callbacks that should be
                     called synchronously on the events monitored.
    """
    def __init__(self, path, mask=IN_WATCH_MASK, auto_add=False, callbacks=[]):
        self.path = path
        self.mask = mask
        self.auto_add = auto_add
        self.callbacks = []
        if not isinstance(callbacks, list):
            callbacks = [callbacks]
        self.callbacks = callbacks

    def addCallback(self, callback, args=None):
        """
        Add a new callback to the list with the given auxiliary
        optional argument.
        """
        self.callbacks.append((callback, args))

    def notify(self, filename, events):
        """
        Callback function used by L{INotify} to dispatch an event.
        """
        for callback in self.callbacks:
            if callback is not None:
                #wrap that so our loop isn't aborted by a faulty callback
                try:
                    callback[0](self, filename, events, callback[1])
                except:
                    import traceback
                    traceback.print_exc()


class INotify(FileDescriptor, object):
    """
    The INotify file descriptor, it basically does everything related
    to INotify, from reading to notifying watch points.
    """
    _instance_ = None  # Singleton

    def __new__(cls, *args, **kwargs):
        obj = getattr(cls, '_instance_', None)
        if obj is not None:
            return obj
        else:
            obj = super(INotify, cls).__new__(cls, *args, **kwargs)

            # Check inotify support by checking for the required functions
            obj.libc = ctypes.cdll.LoadLibrary(ctypes.util.find_library('c'))
            if len([function for function in "inotify_add_watch inotify_init inotify_rm_watch".split() if hasattr(obj.libc, function)]) == 3:
                obj.inotify_init = obj.libc.inotify_init
                obj.inotify_add_watch = obj.libc_inotify_add_watch
                obj.inotify_rm_watch = obj.libc_inotify_rm_watch
            else:
                print("inotify.py - can't use libc6, 2.4 or higher needed")
                import platform
                if platform.system() != 'Linux':
                    raise SystemError, "unknown system '%r', INotify support disabled" % platform.uname()
                machine = platform.machine()
                try:
                    obj._init_syscall_id = _inotify_syscalls[machine][0]
                    obj._add_watch_syscall_id = _inotify_syscalls[machine][1]
                    obj._rm_watch_syscall_id = _inotify_syscalls[machine][2]

                    obj.inotify_init = obj._inotify_init
                    obj.inotify_add_watch = obj._inotify_add_watch
                    obj.inotify_rm_watch = obj._inotify_rm_watch
                except:
                    raise SystemError, "unknown system '%s', INotify support disabled" % machine

            FileDescriptor.__init__(obj)

            obj._fd = obj.inotify_init()
            if obj._fd < 0:
                raise SystemError("INotify initialization error.")
            fdesc.setNonBlocking(obj._fd)
            reactor.addReader(obj)

            obj._buffer = ''
            # Mapping from wds to Watch objects
            obj._watchpoints = {}
            # Mapping from paths to wds
            obj._watchpaths = {}
            cls._instance_ = obj
            return obj

    def _addWatch(self, path, mask, auto_add, callbacks):
        """
        Private helpers that abstract the use of ctypes and help
        managing state related to those calls.
        """
        wd = self.inotify_add_watch(
            os.path.normpath(path),
            mask
        )

        if wd < 0:
            raise IOError("Failed to add watch on '%r' - (%r)" % (path, wd))

        iwp = Watch(path, mask, auto_add, callbacks)

        self._watchpoints[wd] = iwp
        self._watchpaths[path] = wd

        return wd

    def _rmWatch(self, wd):
        """
        Private helpers that abstract the use of ctypes and help
        managing state related to those calls.
        """
        self.inotify_rm_watch(wd)
        iwp = self._watchpoints.pop(wd)
        self._watchpaths.pop(iwp.path)
        del iwp


    def _inotify_init(self):
        return self.libc.syscall(self._init_syscall_id)

    def _inotify_add_watch(self, path, mask):
        if type(path) is unicode:
            path = path.encode('utf-8')
            self.libc.syscall.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
        else:
            self.libc.syscall.argtypes = None
        return self.libc.syscall(self._add_watch_syscall_id, self._fd, path, mask)

    def _inotify_rm_watch(self, wd):
        return self.libc.syscall(self._rm_watch_syscall_id, self._fd, wd)

    def libc_inotify_add_watch(self, path, mask):
        if type(path) is unicode:
            path = path.encode('utf-8')
            self.libc.inotify_add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
        else:
            self.libc.inotify_add_watch.argtypes = None
        return self.libc.inotify_add_watch(self._fd, path, mask)

    def libc_inotify_rm_watch(self, wd):
        return self.libc.inotify_rm_watch(self._fd, wd)

    def release(self):
        """
        Release the inotify file descriptor and do the necessary cleanup
        """
        reactor.removeReader(self)
        if hasattr(self, '_fd') and self._fd >= 0:
            try:
                os.close(self._fd)
            except OSError:
                pass

        if hasattr(INotify, '_instance_'):
            del INotify._instance_

    # I'd rather not have this...
    __del__ = release

    def fileno(self):
        """
        Get the underlying file descriptor from this inotify observer.
        """
        return self._fd

    def notify(self, iwp, filename, mask, *args):
        """
        A simple callback that you can use for tests
        """
        print "event %s on %s %s" % (
            ', '.join(flag_to_human(mask)), iwp.path, filename)

    def doRead(self):
        """
        Read some data from the observed file descriptors
        """
        fdesc.readFromFD(self._fd, self._doRead)

    def _doRead(self, in_):
        """
        Work on the data just read from the file descriptor.
        """
        self._buffer += in_
        while True:
            if len(self._buffer) < 16:
                break

            wd, mask, cookie, size = struct.unpack("=LLLL", self._buffer[0:16])

            if size:
                name = self._buffer[16:16+size].rstrip('\0')
            else:
                name = None

            self._buffer = self._buffer[16+size:]

            try:
                iwp = self._watchpoints[wd]
            except:
                continue # can this happen?

            path = iwp.path
            if name:
                path = os.path.join(path, name)
                iwp.notify(name, mask)
            else:
                iwp.notify(path, mask)

            if (iwp.auto_add and mask & IN_ISDIR and mask & IN_CREATE):
                # Note that this is a fricking hack... it's because we
                # cannot be fast enough in adding a watch to a directory
                # and so we basically end up getting here too late if
                # some operations have already been going on in the
                # subdir, we basically need to catchup.
                # This eventually ends up meaning that we generate
                # double events, your app must be resistant.
                def _addChildren(iwp):
                    try:
                        listdir = os.listdir(iwp.path)
                    except OSError:
                        # Somebody or something (like a test)
                        # removed this directory while we were in the
                        # callLater(0...) waiting. It doesn't make
                        # sense to process it anymore
                        return

                    # note that it's true that listdir will only see
                    # the subdirs inside path at the moment of the call
                    # but path is monitored already so if something is
                    # created we will receive an event.
                    for f in listdir:
                        inner = os.path.join(iwp.path, f)

                        # It's a directory, watch it and then add its
                        # children
                        if os.path.isdir(inner):
                            wd = self.watch(
                                inner, mask=iwp.mask, auto_add=True,
                                callbacks=iwp.callbacks
                            )
                            iwp.notify(f, IN_ISDIR|IN_CREATE)
                            # now inner is watched, we can add its children
                            # the callLater is to avoid recursion
                            reactor.callLater(0,
                                _addChildren, self._watchpoints[wd])

                        # It's a file and we notify it.
                        if os.path.isfile(inner):
                            iwp.notify(f, IN_CREATE|IN_CLOSE_WRITE)

                if os.path.isdir(path):
                    new_wd = self.watch(
                        path, mask=iwp.mask, auto_add=True,
                        callbacks=iwp.callbacks
                    )
                    # This is very very very hacky and I'd rather
                    # not do this but we have no other alternative
                    # that is less hacky other than surrender
                    # We use callLater because we don't want to have
                    # too many events waiting while we process these
                    # subdirs, we must always answer events as fast
                    # as possible or the overflow might come.
                    reactor.callLater(0,
                        _addChildren, self._watchpoints[new_wd])
            if mask & IN_DELETE_SELF:
                self._rmWatch(wd)

    def watch(self, path, mask=IN_WATCH_MASK, auto_add=None, callbacks=[], recursive=False):
        """
        Watch the 'mask' events in given path.

        @param path: The path needing monitoring
        @type path: L{FilePath} or C{str} or C{unicode}

        @param mask: The events that should be watched
        @type mask: C{hex}

        @param auto_add: if True automatically add newly created
                        subdirectories
        @type auto_add: C{boolean}

        @param callbacks: A list of callbacks that should be called
                          when an event happens in the given path.
        @type callbacks: C{list} of C{tuples}

        @param recursive: Also add all the subdirectories in this path
        @type recursive: C{boolean}
        """
        if isinstance(path, FilePath):
            path = path.path
        if type(path) is unicode:
            path = path.encode('utf-8')
        path = os.path.realpath(path)

        if recursive:
            for root, dirs, files in os.walk(path):
                self.watch(root, mask, auto_add, callbacks, False)
        else:
            wd = self.isWatched(path)
            if wd:
                return wd

            mask = mask | IN_DELETE_SELF

            return self._addWatch(path, mask, auto_add, callbacks)

    def ignore(self, path):
        """
        Remove the watch point monitoring the given path

        @param path: The path that should be ignored
        @type path: L{FilePath} or C{unicode} or C{str}
        """
        if isinstance(path, FilePath):
            path = path.path
        if type(path) is unicode:
            path = path.encode('utf-8')
        path = os.path.realpath(path)
        wd = self.isWatched(path)
        if wd:
            self._rmWatch(wd)

    def isWatched(self, path):
        """
        Helper function that checks if the path is already monitored
        and returns its watchdescriptor if so.

        @param path: The path that should be checked
        @type path: L{FilePath} or C{unicode} or C{str}
        """
        if isinstance(path, FilePath):
            path = path.path
        if type(path) is unicode:
            path = path.encode('utf-8')
        return self._watchpaths.get(path, False)

    def flag_to_human(self,mask):
        return flag_to_human(mask)

if __name__ == '__main__':

    i = INotify()
    print i
    i.watch(unicode('/tmp'), auto_add=True, callbacks=(i.notify,None), recursive=True)

    i2 = INotify()
    print i2
    i2.watch('/', auto_add=True, callbacks=(i2.notify,None), recursive=False)

    reactor.run()
