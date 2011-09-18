.. -*- mode: rst ; ispell-local-dictionary: "american" -*-

==========================
coherence
==========================
-------------------------------------------------------------
Python UPnP/DLNA Media Server and Framework
-------------------------------------------------------------
:Authors:   Coherence was written by Frank Scholz
            <coherence@beebits.net>. This man page was created by
	    Charlie Smotherman <cjsmo@cableone.net> for
	    Frank Scholz and the Debian Project.
:Version:   Version |VERSION|
:Licence:   GNU Public Licence v3 (GPLv3)
:Date:      Thu, Mar 19 2009
:Manual section: 1

.. raw:: manpage

   .\" disable justification (adjust text to left margin only)
   .ad l

SYNOPSIS
==========

``coherence`` <options> [--plugin=<BACKEND> [ , <PARAM_NAME> : <PARAM_VALUE> ] ...]

DESCRIPTION
============

Coherence is a Python UPnP framework which enabling your application to
participate in digital living networks, at the moment primarily the
UPnP universe.

Its goal is to relieve your application from all the membership and UPnP
related tasks as much as possible.

The core of Coherence provides a (hopefully complete) implementation
of:

  * a SSDP server,
  * a MSEARCH client,
  * server and client for HTTP/SOAP requests, and
  * server and client for Event Subscription and Notification (GENA).

OPTIONS
========

-v, --version  Show program's version number and exit

--help         Show help message and exit

-d, --daemon  Daemonize

-c, --configfile=PATH  Path to config file

--noconfig           ignore any config file found

-o, --option=OPTION  activate option

-l, --logfile=PATH   Path to log file.


EXAMPLES
===========

:coherence --plugin=backend\:FSStore,name\:MyCoherence:
    Start coherence activating the `FSStore` backend.

:coherence --plugin=backend\:MediaStore,medialocation\:$HOME/Music/,mediadb\:/tmp/media.db:
    Start coherence activating the `MediaStore` backend with media
    located in `$HOME/Music` and the media metadata store in
    `/tmp/media.db`.

AVAILABLE STORES
======================

BetterLight, AmpacheStore, FlickrStore, MiroStore, ElisaPlayer,
ElisaMediaStore, Gallery2Store, DVBDStore, FSStore, BuzztardPlayer,
BuzztardStore, GStreamerPlayer, SimpleLight, ITVStore, SWR3Store,
TrackerStore, LolcatsStore, BBCStore, MediaStore, AppleTrailerStore,
LastFMStore, AxisCamStore, YouTubeStore, TEDStore, IRadioStore

FILES
===========

:$HOME/.coherence: default config file

ENVIRONMENT VARIABLES
==========================

:COHERENCE_DEBUG=<STORE>:
      Supplies debug information pertaining to the named store.


SEE ALSO
============

Project Homepage http://coherence.beebits.net/
