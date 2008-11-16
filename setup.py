# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

from coherence import __version__

packages = find_packages()
packages.append('misc')

setup(
    name="Coherence",
    version=__version__,
    description="""Coherence - DLNA/UPnP framework for the digital living""",
    long_description="""Coherence is a framework written in Python,
providing a variety of UPnP MediaServer and UPnP MediaRenderer implementations
for instant use. Furthermore it enables your application to participate in
digital living networks, at the moment primarily the DLNA/UPnP universe.

Its objective and demand is to relieve your application from all the
membership/the UPnP related tasks as much as possible.

New in this 0.5.8 - Trix and Flix - release

 * a MediaServer backend for DVB-Daemon (http://www.k-d-w.org/node/42)
   * exporting atm the stored recordings
   * allowing to delete recordings from within a UPnP client, when enabled on the backend
   * will export EPG data and allow scheduling via UPnP in the future
 * client device and service implementations for BinaryLight and DimmableLight devices
 * rework of the D-Bus support
   * should now be usable from other languages (C,Perl,..) too
   * support for activating/deactivation a backend via D-Bus, allowing for instance to start a MediaServer backend via D-Bus
 * a plugin for Totem (http://www.gnome.org/projects/totem/)
   * enabling Totem to detect and browse UPnP A/V MediaServers
   * using only D-Bus to communicate with a Coherence instance
 * a basic reusable PyGTK based UPnP A/V ControlPoint widget, used in the Totem plugin
 * rework (again) of the XBox 360 support - getting closer
 * our first set of unit tests
 * include a copy of Louie (http://pylouie.org) to solve a setuptools runtime dependency issue and make the life of distribution packagers a bit easier
 * and the usual bugfixes and enhancements

""",
    author="Frank Scholz",
    author_email='coherence@beebits.net',
    license = "MIT",
    packages=packages,
    scripts = ['bin/coherence','misc/Desktop Applet/applet-coherence'],
    url = "http://coherence.beebits.net",
    download_url = 'http://coherence.beebits.net/download/Coherence-%s.tar.gz' % __version__,
    keywords=['UPnP', 'DLNA', 'multimedia', 'gstreamer'],
    classifiers = ['Development Status :: 5 - Production/Stable',
                   'Environment :: Console',
                   'Environment :: Web Environment',
                   'License :: OSI Approved :: MIT License',
                   'Operating System :: OS Independent',
                   'Programming Language :: Python',
                ],

    entry_points="""
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

        [coherence.plugins.backend.media_renderer]
        ElisaPlayer = coherence.backends.elisa_renderer:ElisaPlayer
        GStreamerPlayer = coherence.backends.gstreamer_renderer:GStreamerPlayer
        BuzztardPlayer = coherence.backends.buzztard_control:BuzztardPlayer

        [coherence.plugins.backend.binary_light]
        SimpleLight = coherence.backends.light:SimpleLight

        [coherence.plugins.backend.dimmable_light]
        BetterLight = coherence.backends.light:BetterLight

    """,

    package_data = {
        'coherence': ['upnp/core/xml-service-descriptions/*.xml',
                      'ui/icons/*.png',
                      'web/static/*.css','web/static/*.js'],
        'misc': ['Desktop Applet/*.png',
                 'device icons/*.png'],
    },
    install_requires=[
    'ConfigObj >= 4.3',
    ],
)
