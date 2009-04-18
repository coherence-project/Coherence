# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2007,, Frank Scholz <coherence@beebits.net>

from coherence.extern.simple_plugin import Plugin

from coherence import log

import coherence.extern.louie as louie

from coherence.upnp.core.utils import getPage
from coherence.extern.et import parse_xml


class Backend(log.Loggable,Plugin):

    """ the base class for all backends

        if there are any UPnP service actions, that can't
        be handled by the service classes itself, or need some
        special adjustments for the backend, they need to be
        defined here.

        Like maybe upnp_Browse for the CDS Browse action.
    """

    implements = []  # list the device classes here
                     # like [BinaryLight'] or ['MediaServer','MediaRenderer']

    logCategory = 'backend'

    def __init__(self,server,**kwargs):
        """ the init method for a backend,
            should probably most of the time be overwritten
            when the init is done, send a signal to its device

            the device will then setup and announce itself,
            after that it calls the backends upnp_init method
        """
        self.config = kwargs
        self.server = server # the UPnP device that's hosting that backend

        """ do whatever is necessary with the stuff we can
            extract from the config dict,
            connect maybe to an external data-source and
            start up the backend
            after that's done, tell Coherence about it
        """
        self.init_completed()

    def init_completed(self, *args, **kwargs):
        """ inform Coherence that this backend is ready for
            announcement
            this method just accepts any form of arguments
            as we don't under which circumstances it is called
        """
        louie.send('Coherence.UPnP.Backend.init_completed',
                None, backend=self)

    def upnp_init(self):
        """ this method gets called after the device is fired,
            here all initializations of service related state variables
            should happen, as the services aren't available before that point
        """
        pass


class BackendStore(Backend):

    """ the base class for all MediaServer backend stores
    """

    logCategory = 'backend_store'

    def __init__(self,server,*args,**kwargs):
        """ the init method for a MediaServer backend,
            should probably most of the time be overwritten
            when the init is done, send a signal to its device

            the device will then setup and announce itself,
            after that it calls the backends upnp_init method
        """
        self.config = kwargs
        self.server = server # the UPnP device that's hosting that backend
        self.update_id = 0

        """ do whatever is necessary with the stuff we can
            extract from the config dict
        """

        """ in case we want so serve something via
            the MediaServer web backend

            the BackendItem should pass an URI assembled
            of urlbase + '/' + id to the DIDLLite.Resource
        """
        self.urlbase = kwargs.get('urlbase','')
        if not self.urlbase.endswith('/'):
            self.urlbase += '/'

        self.wmc_mapping = {'4':'4', '5':'5', '6':'6','7':'7','14':'14','F':'F',
                            '11':'11','16':'16','B':'B','C':'C','D':'D',
                            '13':'13', '17':'17',
                            '8':'8', '9':'9', '10':'10', '15':'15', 'A':'A', 'E':'E'}

        self.wmc_mapping.update({'4':lambda: self._get_all_items(0),
                                 '8':lambda: self._get_all_items(0),
                                 'B':lambda: self._get_all_items(0),
                                })

        """ and send out the signal when ready
        """
        #louie.send('Coherence.UPnP.Backend.init_completed', None, backend=self)

    def release(self):
        """ if anything needs to be cleaned up upon
            shutdown of this backend, this is the place
            for it
        """
        pass


    def _get_all_items(self,id):
        """ a helper method to get all items as a response
            to some XBox 360 UPnP Search action
            probably never be used as the backend will overwrite
            the wmc_mapping with more appropriate methods
        """
        items = []
        item = self.get_by_id(id)
        if item is not None:
            containers = [item]
            while len(containers)>0:
                container = containers.pop()
                if container.mimetype not in ['root', 'directory']:
                    continue
                for child in container.get_children(0,0):
                    if child.mimetype in ['root', 'directory']:
                        containers.append(child)
                    else:
                        items.append(child)
        return items

    def get_by_id(self,id):
        """ called by the CDS or the MediaServer web

            id is the id property of our DIDLLite item

            if this MediaServer implements containers, that can
            share their content, like 'all tracks', 'album' and
            'album_of_artist' - they all have the same track item as content -
            then the id may be passed by the CDS like this:

            'id@container' or 'id@container@container@container...'

            therefore a

            if isinstance(id, basestring):
                id = id.split('@',1)
                id = id[0]

            may be appropriate as the first thing to do
            when entering this method

            should return

            - None when no matching item for that id is found,
            - a BackendItem,
            - or a Deferred

        """

        return None

class BackendItem(log.Loggable):

    """ the base class for all MediaServer backend items
    """

    logCategory = 'backend_item'

    def __init__(self, *args, **kwargs):
        """ most of the time we collect the necessary data for
            an UPnP ContentDirectoryService Container or Object
            and instantiate it here

            self.item = DIDLLite.Container(id,parent_id,name,...)
              or
            self.item = DIDLLite.MusicTrack(id,parent_id,name,...)

            To make that a valid UPnP CDS Object it needs one or
            more DIDLLite.Resource(uri,protocolInfo)

            self.item.res = []
            res = DIDLLite.Resource(url, 'http-get:*:%s:*' % mimetype)

                url : the urlbase of our backend + '/' + our id

            res.size = size
            self.item.res.append(res)
        """
        self.name = u'my_name' # the basename of a file, the album title,
                               # the artists name,...
                               # is expected to be unicode
        self.item = None
        self.update_id = 0 # the update id of that item,
                           # when an UPnP ContentDirectoryService Container
                           # this should be incremented on every modification

        self.location = None # the filepath of our media file, or alternatively
                             # a FilePath or a ReverseProxyResource object

        self.cover = None # if we have some album art image, let's put
                          # the filepath or link into here

    def get_children(self,start=0,end=0):
        """ called by the CDS and the MediaServer web
            should return

            - a list of its childs[start:end]
            - or a Deferred

            if end == 0, the request is for all childs
            after start - childs[start:]
        """
        pass

    def get_child_count(self):
        """ called by the CDS
            should return

            - the number of its childs - len(childs)
            - or a Deferred

        """

    def get_item(self):
        """ called by the CDS and the MediaServer web
            should return

            - an UPnP ContentDirectoryServer DIDLLite object
        """
        return self.item

    def get_name(self):
        """ called by the MediaServer web
            should return

            - the name of the item,
              it is always expected to be in unicode
        """
        return self.name

    def get_path(self):
        """ called by the MediaServer web
            should return

            - the filepath where to find the media file
              that this item does refer to
        """
        return self.location

    def get_cover(self):
        """ called by the MediaServer web
            should return

            - the filepath where to find the album art file

            only needed when we have created for that item
            an albumArtURI property that does point back to us
        """
        return self.cover


class BackendRssMixin:

    def update_data(self,rss_url,container=None,encoding="utf-8"):
        """ creates a deferred chain to retrieve the rdf file,
            parse and extract the metadata and reschedule itself
        """

        def fail(f):
            self.info("fail %r", f)
            self.debug(f.getTraceback())
            return f

        dfr = getPage(rss_url)
        dfr.addCallback(parse_xml, encoding=encoding)
        dfr.addErrback(fail)
        dfr.addCallback(self.parse_data,container)
        dfr.addErrback(fail)
        dfr.addBoth(self.queue_update,rss_url,container)
        return dfr

    def parse_data(self,xml_data,container):
        """ extract media info and create BackendItems
        """
        pass

    def queue_update(self, error_or_failure,rss_url,container):
        from twisted.internet import reactor
        reactor.callLater(self.refresh, self.update_data,rss_url,container)
