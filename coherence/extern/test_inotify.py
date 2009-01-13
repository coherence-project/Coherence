# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php
# Copyright 2008 Adroll.com and Valentino Volonghi <dialtone@adroll.com>

# 20090113 Frank Scholz <coherence@beebits.net>
# renamed watch() kwarg autoAdd back to auto_add, to not break
# existing applications

from twisted.internet import defer, reactor
from twisted.python import filepath
from twisted.trial import unittest

import inotify

class TestINotify(unittest.TestCase):
    def setUp(self):
        self.dirname = filepath.FilePath(self.mktemp())
        self.dirname.createDirectory()
        self.inotify = inotify.INotify()

    def tearDown(self):
        self.inotify.release()
        self.inotify = None
        self.dirname.remove()

    def test_notifications(self):
        """
        Test that a notification is actually delivered on a file
        creation.
        """
        NEW_FILENAME = "new_file.file"
        EXTRA_ARG = "HELLO"
        checkMask = inotify.IN_CREATE | inotify.IN_CLOSE_WRITE
        calls = []

        # We actually expect 2 calls here, one when we create
        # and one when we close the file after writing it.
        def _callback(wp, filename, mask, data):
            try:
                self.assertEquals(filename, NEW_FILENAME)
                self.assertEquals(data, EXTRA_ARG)
                calls.append(filename)
                if len(calls) == 2:
                    self.assert_(mask & inotify.IN_CLOSE_WRITE)
                    d.callback(None)
                elif len(calls) == 1:
                    self.assert_(mask & inotify.IN_CREATE)
            except Exception, e:
                d.errback(e)

        self.inotify.watch(
            self.dirname, mask=checkMask,
            callbacks=(_callback, EXTRA_ARG)
        )
        d = defer.Deferred()
        f = self.dirname.child(NEW_FILENAME).open('wb')
        f.write("hello darling")
        f.close()
        return d

    def test_simpleSubdirectoryAutoAdd(self):
        """
        Test that when a subdirectory is added to a watched directory
        it is also added to the watched list.
        """
        def _callback(wp, filename, mask, data):
            # We are notified before we actually process new
            # directories, so we need to defer this check.
            def _():
                try:
                    self.assert_(self.inotify.isWatched(SUBDIR.path))
                    d.callback(None)
                except Exception, e:
                    d.errback(e)
            reactor.callLater(0, _)

        checkMask = inotify.IN_ISDIR | inotify.IN_CREATE
        self.inotify.watch(
            self.dirname, mask=checkMask, auto_add=True,
            callbacks=(_callback, None)
        )
        SUBDIR = self.dirname.child('test')
        d = defer.Deferred()
        SUBDIR.createDirectory()
        return d

    def test_simpleDeleteDirectory(self):
        """
        Test that when a subdirectory is added and then removed it is
        also removed from the watchlist
        """
        calls = []
        def _callback(wp, filename, mask, data):
            # We are notified before we actually process new
            # directories, so we need to defer this check.
            def _():
                try:
                    self.assert_(self.inotify.isWatched(SUBDIR.path))
                    SUBDIR.remove()
                except Exception, e:
                    print e
                    d.errback(e)
            def _eb():
                # second call, we have just removed the subdir
                try:
                    self.assert_(not self.inotify.isWatched(SUBDIR.path))
                    d.callback(None)
                except Exception, e:
                    print e
                    d.errback(e)

            if not calls:
                # first call, it's the create subdir
                calls.append(filename)
                reactor.callLater(0.1, _)

            else:
                reactor.callLater(0.1, _eb)

        checkMask = inotify.IN_ISDIR | inotify.IN_CREATE
        self.inotify.watch(
            self.dirname, mask=checkMask, auto_add=True,
            callbacks=(_callback, None)
        )
        SUBDIR = self.dirname.child('test')
        d = defer.Deferred()
        SUBDIR.createDirectory()
        return d

    def test_ignoreDirectory(self):
        """
        Test that ignoring a directory correctly removes it from the
        watchlist without removing it from the filesystem.
        """
        self.inotify.watch(
            self.dirname, auto_add=True
        )
        self.assert_(self.inotify.isWatched(self.dirname))
        self.inotify.ignore(self.dirname)
        self.assert_(not self.inotify.isWatched(self.dirname))

    def test_watchPoint(self):
        """
        Test that Watch methods work as advertised
        """
        w = inotify.Watch('/tmp/foobar')
        f = lambda : 5
        w.addCallback(f)
        self.assert_(w.callbacks, [(f, None)])

    def test_flagToHuman(self):
        """
        Test the helper function
        """
        for mask, value in inotify._FLAG_TO_HUMAN.iteritems():
            self.assert_(inotify.flag_to_human(mask)[0], value)

        checkMask = inotify.IN_CLOSE_WRITE|inotify.IN_ACCESS|inotify.IN_OPEN
        self.assert_(
            len(inotify.flag_to_human(checkMask)),
            3
        )

    def test_recursiveWatch(self):
        """
        Test that a recursive watch correctly adds all the paths in
        the watched directory.
        """
        SUBDIR = self.dirname.child('test')
        SUBDIR2 = SUBDIR.child('test2')
        SUBDIR3 = SUBDIR2.child('test3')
        SUBDIR3.makedirs()
        DIRS = [SUBDIR, SUBDIR2, SUBDIR3]
        self.inotify.watch(self.dirname, recursive=True)
        # let's even call this twice so that we test that nothing breaks
        self.inotify.watch(self.dirname, recursive=True)
        for d in DIRS:
            self.assert_(self.inotify.isWatched(d))

    def test_noAutoAddSubdirectory(self):
        """
        Test that if auto_add is off we don't add a new directory
        """
        def _callback(wp, filename, mask, data):
            # We are notified before we actually process new
            # directories, so we need to defer this check.
            def _():
                try:
                    self.assert_(not self.inotify.isWatched(SUBDIR.path))
                    d.callback(None)
                except Exception, e:
                    d.errback(e)
            reactor.callLater(0, _)

        checkMask = inotify.IN_ISDIR | inotify.IN_CREATE
        self.inotify.watch(
            self.dirname, mask=checkMask, auto_add=False,
            callbacks=(_callback, None)
        )
        SUBDIR = self.dirname.child('test')
        d = defer.Deferred()
        SUBDIR.createDirectory()
        return d

    def test_complexSubdirectoryAutoAdd(self):
        """
        Test that when we add one subdirectory with other new children
        and files we end up with the notifications for those files and
        with all those directories watched.

        This is basically the most critical testcase for inotify.
        """
        calls = set()
        def _callback(wp, filename, mask, data):
            # We are notified before we actually process new
            # directories, so we need to defer this check.
            def _():
                try:
                    self.assert_(self.inotify.isWatched(SUBDIR.path))
                    self.assert_(self.inotify.isWatched(SUBDIR2.path))
                    self.assert_(self.inotify.isWatched(SUBDIR3.path))
                    CREATED = SOME_FILES.union(
                        set([SUBDIR.basename(),
                             SUBDIR2.basename(),
                             SUBDIR3.basename()
                            ])
                    )
                    self.assert_(len(calls), len(CREATED))
                    self.assertEquals(calls, CREATED)
                except Exception, e:
                    d.errback(e)
                else:
                    d.callback(None)
            if not calls:
                # Just some delay to be sure, given how the algorithm
                # works for this we know that there's a new extra cycle
                # every subdirectory
                reactor.callLater(0.1, _)
            calls.add(filename)

        checkMask = inotify.IN_ISDIR | inotify.IN_CREATE
        self.inotify.watch(
            self.dirname, mask=checkMask, auto_add=True,
            callbacks=(_callback, None)
        )
        SUBDIR = self.dirname.child('test')
        SUBDIR2 = SUBDIR.child('test2')
        SUBDIR3 = SUBDIR2.child('test3')
        SOME_FILES = set(["file1.dat", "file2.dat", "file3.dat"])
        d = defer.Deferred()
        SUBDIR3.makedirs()

        # Add some files in pretty much all the directories so that we
        # see that we process all of them.
        for i, filename in enumerate(SOME_FILES):
            if not i:
                S = SUBDIR
            if i == 1:
                S = SUBDIR2
            else:
                S = SUBDIR3

            S.child(filename).setContent(filename)
        return d
