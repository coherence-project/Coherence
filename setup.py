from setuptools import setup, find_packages

from coherence import __version__

setup(
    name="Coherence",
    version=__version__,
    description="""Coherence - DLNA/UPnP framework for the digital living""",
    long_description="""Coherence is a framework written in Python enabling
your application to participate in digital living networks, at the moment
primarily the DLNA/UPnP universe.

Its objective and demand is to relieve your application from all the
membership/the UPnP related tasks as much as possible.

This 0.4 release brings

* integration of a new logging module
  logging can now be configured via the config file or through an
  environment variable COHERENCE_DEBUG, which overrides the config values.

  Usage is like
      COHERENCE_DEBUG=*:3           emit INFO level messages from all modules
      COHERENCE_DEBUG=*:2,ssdp:4    WARNING level messages from all modules,
                                    plus debug level for the ssdp module

* removed the dependency for SOAPpy, now using own methods and ElementTree only
* start reworking the client API, to make things there easier too,
  see as an example https://coherence.beebits.net/wiki/CoherenceMediaRenderer
* serving cover art now to DLNA MediaRenderers
* refinements on the object creation and the import into the MediaServers
* an installable package for the Nokia Maemo platform on the N800,
  complete with all dependecies, thanks to Rob Tylor of http://codethink.co.uk
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

        [coherence.plugins.backend.media_renderer]
        ElisaPlayer = coherence.backends.elisa_renderer:ElisaPlayer
        GStreamerPlayer = coherence.backends.gstreamer_audio_player:GStreamerPlayer
        BuzztardPlayer = coherence.backends.buzztard_control:BuzztardPlayer

    """,

    package_data = {
        'coherence': ['upnp/core/xml-service-descriptions/*.xml',
                      'web/static/*.css','web/static/*.js'],
    }
)
