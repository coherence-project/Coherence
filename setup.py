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

New in this 0.5.4 - Fools Garden - release

* a DesktopApplet to easily start a Coherence instance from your desktops panel
  Thx to Erwan Velu, Helio Chissini de Castro and Nicolas Lécureuil!
* more efforts to simplify the ordinary user experience
  * allow now the backend definition via commandline, to just start up
    a MediaServer or anything else, without bothering oneself with the config file
  * specify logfile location and daemonization on the commandline too
  * a bit more usable --help output
  Thx again Erwan Velu!
* a MediaServer backend for Ampache - a Web-based Audio file manager (http://ampache.org)
  Thx to the awesome help of Karl Vollmer!
* device implementations for BinaryLight and DimmableLight
* a little helper to extract device and service xml files and
  send them to us - a beginning of our UPnP device fingerprint program
* and the usual bugfixes and enhancements

""",
    author="Frank Scholz",
    author_email='coherence@beebits.net',
    license = "MIT",
    packages=packages,
    scripts = ['bin/coherence','misc/Desktop Applet/applet-coherence'],
    url = "http://coherence.beebits.net",
    download_url = 'https://coherence.beebits.net/download/Coherence-%s.tar.gz' % __version__,
    keywords=['UPnP', 'DLNA', 'multimedia', 'gstreamer'],
    classifiers = ['Development Status :: 4 - Beta',
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

        [coherence.plugins.backend.media_renderer]
        ElisaPlayer = coherence.backends.elisa_renderer:ElisaPlayer
        GStreamerPlayer = coherence.backends.gstreamer_audio_player:GStreamerPlayer
        BuzztardPlayer = coherence.backends.buzztard_control:BuzztardPlayer

        [coherence.plugins.backend.binary_light]
        SimpleLight = coherence.backends.light:SimpleLight

        [coherence.plugins.backend.dimmable_light]
        BetterLight = coherence.backends.light:BetterLight

    """,

    package_data = {
        'coherence': ['upnp/core/xml-service-descriptions/*.xml',
                      'web/static/*.css','web/static/*.js'],
        'misc': ['Desktop Applet/*.png'],
    },
    install_requires=[
    'Louie >= 1.1',
    'ConfigObj >= 4.3',
    ],
)
