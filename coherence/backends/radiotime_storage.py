# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# an internet radio media server for the Coherence UPnP Framework
# based on the radiotime (http://radiotime.com) catalog service

# Copyright 2007, Frank Scholz <coherence@beebits.net>
# Copyright 2009-2010, Jean-Michel Sizun <jmDOTsizunATfreeDOTfr>

from twisted.internet import defer,reactor
from twisted.python.failure import Failure
from twisted.web import server

from coherence.upnp.core import utils

from coherence.upnp.core import DIDLLite
from coherence.upnp.core.DIDLLite import classChooser, Resource, DIDLElement

from coherence import log
from coherence.backend import BackendItem, BackendStore, Container, LazyContainer, AbstractBackendStore
#from coherence.backends.iradio_storage import PlaylistStreamProxy
from urlparse import urlsplit
from coherence.extern.et import parse_xml

OPML_BROWSE_URL = 'http://opml.radiotime.com/Browse.ashx'

# we only handle mp3 audio streams for now
DEFAULT_FORMAT = "mp3"
DEFAULT_MIMETYPE = "audio/mpeg"
# TODO : extend format handling using radiotime API
      
class RadiotimeAudioItem(BackendItem):
    logCategory = 'radiotime'

    def __init__(self, outline):
        self.preset_id = outline.get('preset_id')
        self.name = outline.get('text')
        self.mimetype = DEFAULT_MIMETYPE
        self.stream_url = outline.get('URL')
        self.image = outline.get('image')
        
        #self.location = PlaylistStreamProxy(self.stream_url)
        #self.url = self.stream_url
        
        self.item = None


    def replace_by (self, item):
        # do nothing: we suppose the replacement item is the same
        return
    
    def get_item(self):
        if self.item == None:
            upnp_id = self.get_id()
            upnp_parent_id = self.parent.get_id()
            self.item = DIDLLite.AudioBroadcast(upnp_id, upnp_parent_id, self.name)
            self.item.albumArtURI = self.image
            res = Resource(self.stream_url, 'http-get:*:%s:%s' % (self.mimetype,
                                                           ';'.join(('DLNA.ORG_PN=MP3',
                                                                     'DLNA.ORG_CI=0',
                                                                     'DLNA.ORG_OP=01',
                                                                     'DLNA.ORG_FLAGS=01700000000000000000000000000000'))))
            res.size = 0 #None
            self.item.res.append(res)
        return self.item

    def get_path(self):
        return self.url

    def get_id(self):
        return self.storage_id
    
    
class RadiotimeStore(AbstractBackendStore):

    logCategory = 'radiotime'

    implements = ['MediaServer']

    def __init__(self, server, **kwargs):
        AbstractBackendStore.__init__(self,server,**kwargs)
 
        self.name = kwargs.get('name','radiotimeStore')
        self.refresh = int(kwargs.get('refresh',60))*60

        self.browse_url = self.config.get('browse_url', OPML_BROWSE_URL)
        self.partner_id = self.config.get('partner_id', 'TMe3Cn6v')
        self.username = self.config.get('username', None)
        self.locale = self.config.get('locale', 'en')
        self.serial = server.uuid
        
        # construct URL for root menu
        if self.username is not None:
            identification_param = "username=%s" % self.username
        else:
            identification_param = "serial=%s" % self.serial
        formats_value = DEFAULT_FORMAT
        root_url =  "%s?partnerId=%s&%s&formats=%s&locale=%s" % (self.browse_url, self.partner_id, identification_param, formats_value, self.locale)
        
        # set root item
        root_item = LazyContainer(None, "root", "root", self.refresh, self.retrieveItemsForOPML, url=root_url)
        self.set_root_item(root_item)
   
        self.init_completed()


    def upnp_init(self):
        self.current_connection_id = None

        self.wmc_mapping = {'4': self.get_root_id()}

        if self.server:
            self.server.connection_manager_server.set_variable(0, 'SourceProtocolInfo',
                                                                    ['http-get:*:audio/mpeg:*',
                                                                     'http-get:*:audio/x-scpls:*'],
                                                                     default=True)


    def retrieveItemsForOPML (self, parent, url):
        
        def append_outline (parent, outline):
            type = outline.get('type')
            if type is None:
                # This outline is just a classification item containing other outline elements
                # the corresponding item will a static Container
                text = outline.get('text')
                key = outline.get('key')
                external_id = None
                if external_id is None and key is not None:
                    external_id = "%s_%s" % (parent.external_id, key)
                if external_id is None:
                    external_id = outline_url
                item = Container(parent, text)
                item.external_id = external_id
                item.store = parent.store
                parent.add_child(item, external_id=external_id)
                sub_outlines = outline.findall('outline')
                for sub_outline in sub_outlines:
                    append_outline(item, sub_outline)
                    
            elif type in ('link'):
                # the corresponding item will a self-populating Container
                text = outline.get('text')
                outline_url = outline.get('URL')
                key = outline.get('key')
                guide_id = outline.get('guide_id')
                external_id = guide_id
                if external_id is None and key is not None:
                    external_id = "%s_%s" % (parent.external_id, key)
                if external_id is None:
                    external_id = outline_url                 
                item = LazyContainer(parent, text, external_id, self.refresh, self.retrieveItemsForOPML, url=outline_url)
                parent.add_child(item, external_id=external_id)

            elif type in ('audio'):
                item = RadiotimeAudioItem(outline)
                parent.add_child(item, external_id=item.preset_id)
        
        def got_page(result):
            self.info('connection to Radiotime service successful for url %s' % url)
            
            outlines = result.findall('body/outline')
            for outline in outlines:
                append_outline(parent, outline)
          
            return True


        def got_error(error):
            self.warning("connection to Radiotime service failed for url %s" % url)
            self.debug("%r", error.getTraceback())
            parent.childrenRetrievingNeeded = True # we retry
            return Failure("Unable to retrieve items for url %s" % url)

        def got_xml_error(error):
            self.warning("Data received from Radiotime service is invalid: %s" % url)
            #self.debug("%r", error.getTraceback())
            print error.getTraceback()
            parent.childrenRetrievingNeeded = True # we retry
            return Failure("Unable to retrieve items for url %s" % url)
            
        d = utils.getPage(url, )
        d.addCallback(parse_xml)
        d.addErrback(got_error)
        d.addCallback(got_page)
        d.addErrback(got_xml_error)
        return d
    
