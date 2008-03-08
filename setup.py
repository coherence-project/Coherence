from setuptools import setup, find_packages

from coherence import __version__

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

New in this 0.5.2 release

* rework of the XBox 360 support
* refinements and improvements on the client side API,
  incorporating things we learned on extending the Rhythmbox UPnP plugin
* some efforts on smoothing the "just use it as
  a MediaServer/-Renderer" user experience
* rearrangement in the way multiple res elements are ordered,
  fixes issues which we had with some UPnP stacks
  and their 'wayward' interpretation of the specs
* and a lot more of the usual bugfixes and enhancements

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
        IRadioStore = coherence.backends.iradio_storage:IRadioStore
        LastFMStore = coherence.backends.lastfm_storage:LastFMStore
        AmpacheStore = coherence.backends.ampache_storage:AmpacheStore

        [coherence.plugins.backend.media_renderer]
        ElisaPlayer = coherence.backends.elisa_renderer:ElisaPlayer
        GStreamerPlayer = coherence.backends.gstreamer_audio_player:GStreamerPlayer
        BuzztardPlayer = coherence.backends.buzztard_control:BuzztardPlayer

    """,

    package_data = {
        'coherence': ['upnp/core/xml-service-descriptions/*.xml',
                      'web/static/*.css','web/static/*.js'],
    },
    install_requires=[
    'Louie >= 1.1',
    'ConfigObj >= 4.3',
    ],
)
