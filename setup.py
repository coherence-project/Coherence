from setuptools import setup, find_packages

from coherence import __version__

setup(
    name="Coherence",
    version=__version__,
    description="""Coherence - Python framework for the digital living""",
    long_description="""Coherence is a framework written in Python enabling your application to
participate in digital living networks, at the moment primarily the UPnP universe.

Its objective and demand is to relieve your application from all the
membership/the UPnP related tasks as much as possible.

This 0.3 release brings

* better DLNA support, especially for the PlayStation 3
* cover art in the MediaServers
* object creation and import in the MediaServers
* a new experimental MediaServer with an All, Artist, Album based structure
* support for deployment on the Nokia N800 - notably a working GStreamer UPnP MediaRenderer there, with mp3 and ogg playback
* an album art (helper) module to fetch the album covers from the Amazon WebService
* icon support in the UPnP device description
* the usual bugfixes

""",
    author="Frank Scholz",
    author_email='coherence@beebits.net',
    license = "MIT",
    packages=find_packages(),
    scripts = ['bin/coherence'],
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

        [coherence.plugins.backend.media_renderer]
        ElisaPlayer = coherence.backends.elisa_renderer:ElisaPlayer
        GStreamerPlayer = coherence.backends.gstreamer_audio_player:GStreamerMediaRenderer
        BuzztardPlayer = coherence.backends.buzztard_control:BuzztardPlayer

    """,

    package_data = {
        'coherence': ['upnp/core/xml-service-descriptions/*.xml',
                      'web/static/*.css','web/static/*.js'],
    }
)
