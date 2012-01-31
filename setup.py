# -*- coding: utf-8 -*-

try:
    from coherence import __version__
except ImportError:
    raise SystemExit(1)
import sys

try:
    from setuptools import setup, find_packages
    packages = find_packages()
except:
    setuptools = None
    from distutils.core import setup

    import os

    packages = ['coherence',]

    def find_packages(path):
        for f in os.listdir(path):
            if f[0] == '.':
                continue
            if os.path.isdir(os.path.join(path,f)) == True:
                next_path = os.path.join(path,f)
                if '__init__.py' in os.listdir(next_path):
                    packages.append(next_path.replace(os.sep,'.'))
                find_packages(next_path)

    find_packages('coherence')

packages.append('misc')

from distutils.core import Command
from distutils import log
import os

class build_docs(Command):
    description = "build documentation from rst-files"
    user_options=[]

    def initialize_options (self): pass
    def finalize_options (self):
        self.docpages = DOCPAGES
        
    def run(self):
        substitutions = ('.. |VERSION| replace:: '
                         + self.distribution.get_version())
        for writer, rstfilename, outfilename in self.docpages:
            distutils.dir_util.mkpath(os.path.dirname(outfilename))
            log.info("creating %s page %s", writer, outfilename)
            if not self.dry_run:
                try:
                    rsttext = open(rstfilename).read()
                except IOError, e:
                    sys.exit(e)
                rsttext = '\n'.join((substitutions, rsttext))
                # docutils.core does not offer easy reading from a
                # string into a file, so we need to do it ourself :-(
                doc = docutils.core.publish_string(source=rsttext,
                                                   source_path=rstfilename,
                                                   writer_name=writer)
                try:
                    rsttext = open(outfilename, 'w').write(doc)
                except IOError, e:
                    sys.exit(e)

cmdclass = {}

try:
    import docutils.core
    import docutils.io
    import docutils.writers.manpage
    import distutils.command.build
    distutils.command.build.build.sub_commands.append(('build_docs', None))
    cmdclass['build_docs'] = build_docs
except ImportError:
    log.warn("docutils not installed, can not build man pages. "
             "Using pre-build ones.")

DOCPAGES = (
    ('manpage', 'docs/man/coherence.rst', 'docs/man/coherence.1'),
    )

setup_args = {
    'name':"Coherence",
    'version':__version__,
    'description':"""Coherence - DLNA/UPnP framework for the digital living""",
    'long_description':"""
Coherence is a framework written in Python, providing a variety of
UPnP MediaServer and UPnP MediaRenderer implementations for instant
use.

It includes an UPnP ControlPoint, which is accessible via D-Bus too.

Furthermore it enables your application to participate in
digital living networks, at the moment primarily the DLNA/UPnP universe.
Its objective and demand is to relieve your application from all the
membership/the UPnP related tasks as much as possible.

New in this %s - the Red-Nosed Reindeer - release

 * new MediaServer backends that allow access to
   * Banshee - exports audio and video files from Banshees media db
     (http://banshee-project.org/)
   * FeedStore - a MediaServer serving generic RSS feeds
   * Playlist - exposes the list of video/audio streams from a m3u
     playlist (e.g. web TV listings published by french ISPs such as
     Free, SFR...)
   * YAMJ - serves the movie/TV series data files and metadata from a
     given YAMJ (Yet Another Movie Jukebox) library
     (http://code.google.com/p/moviejukebox/)
 * updates on Mirabeau - our "UPnP over XMPP" bridge
 * simplifications in the D-Bus API
 * a first implementation of an JSON/REST API
 * advancements of the GStreamer MediaRenderer, supporting now GStreamers
   playbin2
 * upgrade of the DVB-Daemon MediaServer
 * refinements in the transcoding section, having now the choice to use
   GStreamer pipelines or external processes like mencoder
 * more 'compatibility' improvements for different devices (e.g.
   Samsung TVs or Apache Felix)
 * and - as every time - the usual bugfixes and enhancements

Kudos go to:

 * Benjamin (lightyear) Kampmann,
 * Charlie (porthose) Smotherman
 * Dominik (schrei5) Ruf,
 * Frank (dev) Scholz,
 * Friedrich (frinring) Kossebau,
 * Jean-Michel (jmsizun) Sizun,
 * Philippe (philn) Normand,
 * Sebastian (sebp) Poelsterl,
 * Zaheer (zaheerm) Merali


""" % __version__,
    'author':"Frank Scholz",
    'author_email':'dev@coherence-project.org',
    'license' : "MIT",
    'packages':packages,
    'scripts' : ['bin/coherence','misc/Desktop-Applet/applet-coherence'],
    'url' : "http://coherence-project.org",
    'download_url' : 'http://coherence-project.org/download/Coherence-%s.tar.gz' % __version__,
    'keywords':['UPnP', 'DLNA', 'multimedia', 'gstreamer'],
    'classifiers' : ['Development Status :: 5 - Production/Stable',
                   'Environment :: Console',
                   'Environment :: Web Environment',
                   'License :: OSI Approved :: MIT License',
                   'Operating System :: OS Independent',
                   'Programming Language :: Python',
                ],
    'package_data' : {
        'coherence': ['upnp/core/xml-service-descriptions/*.xml',
                      'ui/icons/*.png',
                      'web/static/*.css','web/static/*.js'],
        'misc': ['Desktop-Applet/*.png',
                 'device-icons/*.png'],
    },
}

if setuptools:
    setup_args['install_requires'] = [
        'ConfigObj >= 4.3'
        ]
    if sys.platform in ('win32','sunos5'):
        setup_args['install_requires'].append('Netifaces >= 0.4')

    setup_args['entry_points'] = """
        [coherence.plugins.backend.media_server]
        FSStore = coherence.backends.fs_storage:FSStore
        MediaStore = coherence.backends.mediadb_storage:MediaStore
        ElisaMediaStore = coherence.backends.elisa_storage:ElisaMediaStore
        FlickrStore = coherence.backends.flickr_storage:FlickrStore
        AxisCamStore = coherence.backends.axiscam_storage:AxisCamStore
        BuzztardStore = coherence.backends.buzztard_control:BuzztardStore
        IRadioStore = coherence.backends.iradio_storage:IRadioStore
        LastFMStore = coherence.backends.lastfm_storage:LastFMStore
        AmpacheStore = coherence.backends.ampache_storage:AmpacheStore
        TrackerStore = coherence.backends.tracker_storage:TrackerStore
        DVBDStore = coherence.backends.dvbd_storage:DVBDStore
        AppleTrailersStore = coherence.backends.appletrailers_storage:AppleTrailersStore
        LolcatsStore = coherence.backends.lolcats_storage:LolcatsStore
        TEDStore = coherence.backends.ted_storage:TEDStore
        BBCStore = coherence.backends.bbc_storage:BBCStore
        SWR3Store = coherence.backends.swr3_storage:SWR3Store
        Gallery2Store = coherence.backends.gallery2_storage:Gallery2Store
        YouTubeStore = coherence.backends.youtube_storage:YouTubeStore
        MiroGuideStore = coherence.backends.miroguide_storage:MiroGuideStore
        ITVStore = coherence.backends.itv_storage:ITVStore
        PicasaStore = coherence.backends.picasa_storage:PicasaStore
        TestStore = coherence.backends.test_storage:TestStore
        PlaylistStore = coherence.backends.playlist_storage:PlaylistStore
        YamjStore = coherence.backends.yamj_storage:YamjStore
        BansheeStore = coherence.backends.banshee_storage:BansheeStore
        FeedStore = coherence.backends.feed_storage:FeedStore
        RadiotimeStore = coherence.backends.radiotime_storage:RadiotimeStore
        AudioCDStore = coherence.backends.audiocd_storage:AudioCDStore
        
        [coherence.plugins.backend.media_renderer]
        ElisaPlayer = coherence.backends.elisa_renderer:ElisaPlayer
        GStreamerPlayer = coherence.backends.gstreamer_renderer:GStreamerPlayer
        BuzztardPlayer = coherence.backends.buzztard_control:BuzztardPlayer

        [coherence.plugins.backend.binary_light]
        SimpleLight = coherence.backends.light:SimpleLight

        [coherence.plugins.backend.dimmable_light]
        BetterLight = coherence.backends.light:BetterLight
    """


setup(cmdclass=cmdclass, **setup_args)
