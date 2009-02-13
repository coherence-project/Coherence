# -*- coding: utf-8 -*-

from coherence import __version__

try:
    from setuptools import setup, find_packages
    packages = find_packages()
    haz_setuptools = True
except:
    from distutils.core import setup

    import os

    packages = []

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
    haz_setuptools = False

packages.append('misc')

setup_args = {
    'name':"Coherence",
    'version':__version__,
    'description':"""Coherence - DLNA/UPnP framework for the digital living""",
    'long_description':"""Coherence is a framework written in Python,
providing a variety of UPnP MediaServer and UPnP MediaRenderer implementations
for instant use. Furthermore it enables your application to participate in
digital living networks, at the moment primarily the DLNA/UPnP universe.

Its objective and demand is to relieve your application from all the
membership/the UPnP related tasks as much as possible.

New in this 0.6.0 - The late Pumpkin - release

 * new MediaServer backends that allow access to
   * movie trailers from the Apple HD trailers site (http://www.apple.com/trailers)
   * images hosted at a Gallery site - an open source web based photo album organizer (http://gallery.menalto.com)
   * Lolcats images from http://icanhascheezburger.com
   * podcasts from the BBC (http://open.bbc.co.uk/labs/)
   * videos from TED (http://www.ted.com)
 * an extended Flickr MediaServer backend
   * enables user-authenticated access to your Flickr account
   * access to your images and the one of your frieds via an UPnP device
   * upload an image directly from an UPnP device to your Flickr account
 * transcoding of audio files based on GStreamer for DLNA devices like the PS3, and even XBox 360
 * several plugins for the Nautlilus filemanager (http://www.gnome.org/projects/nautilus)
   * sharing folders from within Nautilus
   * upload files from Nautilus to UPnP A/V MediaServers
   * play files from Nautilus on an UPnP A/V MediaRenderer
 * an experimental plugin for EOG - the Gnome Image Viewer (http://projects.gnome.org/eog/)
 * greatly improved XBox 360 support, including audio transcoding
 * and the usual bugfixes and enhancements

Kudos go especially to jmsizun, lightyear, superdump for their work
on the backends and their patient debugging sessions!

""",
    'author':"Frank Scholz",
    'author_email':'coherence@beebits.net',
    'license' : "MIT",
    'packages':packages,
    'scripts' : ['bin/coherence','misc/Desktop Applet/applet-coherence'],
    'url' : "http://coherence.beebits.net",
    'download_url' : 'http://coherence.beebits.net/download/Coherence-%s.tar.gz' % __version__,
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
        'misc': ['Desktop Applet/*.png',
                 'device icons/*.png'],
    },
}

if haz_setuptools == True:
    setup_args['install_requires'] = [
    'ConfigObj >= 4.3',
    'Twisted >= 2.5.0',
    ]
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
        MiroStore = coherence.backends.miro_storage:MiroStore
        ITVStore = coherence.backends.itv_storage:ITVStore
 
        [coherence.plugins.backend.media_renderer]
        ElisaPlayer = coherence.backends.elisa_renderer:ElisaPlayer
        GStreamerPlayer = coherence.backends.gstreamer_renderer:GStreamerPlayer
        BuzztardPlayer = coherence.backends.buzztard_control:BuzztardPlayer

        [coherence.plugins.backend.binary_light]
        SimpleLight = coherence.backends.light:SimpleLight

        [coherence.plugins.backend.dimmable_light]
        BetterLight = coherence.backends.light:BetterLight
    """


setup(**setup_args)
