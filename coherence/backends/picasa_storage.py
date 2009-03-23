# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2009, Jean-Michel Sizun
# Copyright 2009 Frank Scholz <coherence@beebits.net>

import os.path
import time

from twisted.internet import threads

from twisted.web import server, static
from twisted.web.error import PageRedirect
from coherence.upnp.core.utils import ReverseProxyResource
from twisted.internet import task
from coherence.upnp.core import utils
from coherence.upnp.core import DIDLLite
from coherence.backend import BackendStore,BackendItem
from coherence import log

from urlparse import urlsplit

import gdata.photos.service
import gdata.media
import gdata.geo

ROOT_CONTAINER_ID = 0

class Container(BackendItem):

    def __init__(self, parent, title, force_store=None, force_id=0):
        BackendItem.__init__(self)
        
        self.parent = parent
        if self.parent is not None:
            self.parent_id = self.parent.get_id()
            self.store = parent.store
            self.storage_id = self.store.getnextID()
        else:
            self.parent_id = -1 
            self.store = force_store
            self.storage_id = force_id     
        self.name = title
        self.mimetype = 'directory'
        
        self.children = []
        self.children_ids = {}
        self.children_by_external_id = {}
                
        self.update_id = 0
        
        self.item = DIDLLite.Container(self.storage_id, self.parent_id, self.name)
        self.item.childCount = 0

        self.sorted = False

    def add_child(self, child, external_id = None, update=True):
        id = self.store.append_item(child)
        if self.children is None:
            self.children = []
        self.children.append(child)
        self.item.childCount += 1
        self.sorted = False
        if update == True:
            self.update_id += 1
        
        child.storage_id = id
        child.parent = self
        child.url = self.store.urlbase + str(id)
        
        if external_id is not None:
            child.external_id = external_id
            self.children_by_external_id[external_id] = child


    def remove_child(self, child, external_id = None, update=True):
        self.children.remove(child)
        self.store.remove_item(child)
        self.item.childCount -= 1
        child.parent = None
        child.storage_id = None
        if update == True:
            self.update_id += 1
        if external_id is not None:
            child.external_id = None
            del self.children_by_external_id[external_id]
        
    def get_children(self, start=0, end=0):

        if self.sorted == False:
            def childs_sort(x,y):
                r = cmp(x.name,y.name)
                return r

            self.children.sort(cmp=childs_sort)
            self.sorted = True
        if end != 0:
            return self.children[start:end]
        return self.children[start:]

    def get_child_count(self):
        if self.children is None:
            return 0
        return len(self.children)

    def get_path(self):
        return self.store.urlbase + str(self.storage_id)

    def get_item(self):
        return self.item

    def get_name(self):
        return self.name

    def get_id(self):
        return self.storage_id
    
    def get_update_id(self):
        return self.update_id


class LazyContainer(Container, log.Loggable):
    logCategory = 'lazyContainer'
    
    def __init__(self, parent, title, external_id=None, refresh=0, childrenRetriever=None, **kwargs):
        Container.__init__(self, parent, title)
        
        self.childrenRetrievingNeeded = False       
        self.childrenRetrievingDeferred = None
        self.childrenRetriever = childrenRetriever
        self.children_retrieval_campaign_in_progress = False
        self.childrenRetriever_params = kwargs
        self.childrenRetriever_params['parent']=self
        self.has_pages = (self.childrenRetriever_params.has_key('per_page'))
        
        self.external_id = None
        self.external_id = external_id
            
        self.retrieved_children = {}
        
        self.last_updated = 0
        self.refresh = refresh
        
    def replace_by(self, item):
        if self.external_id is not None and item.external_id is not None:
            return (self.external_id == item.external_id)
        return True

    def add_child(self, child, external_id = None, update=True):
        if self.children_retrieval_campaign_in_progress is True:
            self.retrieved_children[external_id] = child
        else:
            Container.add_child(self, child, external_id=external_id, update=update)
            
           
    def update_children(self, new_children, old_children):
        children_to_be_removed = {}
        children_to_be_replaced = {}
        children_to_be_added = {}
        
        # Phase 1
        # let's classify the item between items to be removed,
        # to be updated or to be added
        self.debug("Refresh pass 1:%d %d" % (len(new_children), len(old_children)))
        for id,item in old_children.items():
            children_to_be_removed[id] = item
        for id,item in new_children.items():
            if old_children.has_key(id):
                #print(id, "already there")
                children_to_be_replaced[id] = old_children[id]
                del children_to_be_removed[id]
            else:
                children_to_be_added[id] = new_children[id]
        
        # Phase 2
        # Now, we remove, update or add the relevant items
        # to the list of items            
        self.debug("Refresh pass 2: %d %d %d" % (len(children_to_be_removed), len(children_to_be_replaced), len(children_to_be_added)))
        # Remove relevant items from Container children
        for id,item in children_to_be_removed.items():
            self.remove_child(item, external_id=id, update=False)
        # Update relevant items from Container children
        for id,item in children_to_be_replaced.items():
            old_item = item
            new_item = new_children[id]
            replaced = False
            if self.replace_by:
                #print "Replacement method available: Try"
                replaced = old_item.replace_by(new_item) 
            if replaced is False:
                #print "No replacement possible: we remove and add the item again"
                self.remove_child(old_item, external_id=id, update=False)
                self.add_child(new_item, external_id=id, update=False)
        # Add relevant items to COntainer children
        for id,item in children_to_be_added.items():
            self.add_child(item, external_id=id, update=False)
        
        self.update_id += 1

    def start_children_retrieval_campaign(self):
        #print "start_update_campaign"
        self.last_updated = time.time()
        self.retrieved_children = {}
        self.children_retrieval_campaign_in_progress = True
        
    def end_children_retrieval_campaign(self, success=True):
        #print "end_update_campaign"
        self.children_retrieval_campaign_in_progress = False
        if success is True:
            self.update_children(self.retrieved_children, self.children_by_external_id)          
            self.update_id += 1
        self.last_updated = time.time()
        self.retrieved_children = {}
    
    def retrieve_children(self, start=0):

        def items_retrieved(result, source_deferred):
            childrenRetrievingOffset = len(self.retrieved_children)
            if self.childrenRetrievingNeeded is True:
                return self.retrieve_children(childrenRetrievingOffset)
            return self.retrieved_children
        
        self.childrenRetrievingNeeded = False
        if self.has_pages is True:
            self.childrenRetriever_params['offset'] = start
        d = self.childrenRetriever(**self.childrenRetriever_params)
        d.addCallback(items_retrieved, d)
        return d


    def retrieve_all_children(self, start=0, request_count=0):
           
        def all_items_retrieved (result):
            #print "All items retrieved!"
            self.end_children_retrieval_campaign(True)
            return Container.get_children(self, start, request_count)

        def error_while_retrieving_items (error):
            #print "All items retrieved!"
            self.end_children_retrieval_campaign(False)
            return Container.get_children(self, start, request_count)

        # if first retrieval and refresh required
        # we start a looping call to periodically update the children       
        #if ((self.last_updated == 0) and (self.refresh > 0)):
        #    task.LoopingCall(self.retrieve_children,0,0).start(self.refresh, now=False)
        
        self.start_children_retrieval_campaign()        
        if self.childrenRetriever is not None:
            d = self.retrieve_children(start)
            if start == 0:
                d.addCallbacks(all_items_retrieved, error_while_retrieving_items)
            return d
        else:
            self.end_children_retrieval_campaign()
            return self.children
                    
    
    def get_children(self,start=0,request_count=0):

        # Check if an update is needed since last update
        current_time = time.time()
        delay_since_last_updated = current_time - self.last_updated
        period = self.refresh
        if (period > 0) and (delay_since_last_updated > period):
            self.info("Last update is older than %d s -> update data" % period)
            self.childrenRetrievingNeeded = True

        if self.childrenRetrievingNeeded is True:
            #print "children Retrieving IS Needed (offset is %d)" % start
            return self.retrieve_all_children()
        else:
            return Container.get_children(self, start, request_count)



class PicasaProxy(ReverseProxyResource):

    def __init__(self, uri):
        self.uri = uri
        _,host_port,path,_,_ = urlsplit(uri)
        if host_port.find(':') != -1:
            host,port = tuple(host_port.split(':'))
            port = int(port)
        else:
            host = host_port
            port = 80

        ReverseProxyResource.__init__(self, host, port, path)

    def render(self, request):
        del request.received_headers['referer']
        return ReverseProxyResource.render(self, request)

class PicasaPhotoItem(BackendItem):
    def __init__(self, photo):
        #print photo
        self.photo = photo

        self.name = photo.title.text
        self.duration = None
        self.size = None
        self.mimetype = photo.content.type
        self.description = photo.summary.text
        self.date = None
        self.item = None
            
        self.photo_url = photo.content.src
        self.thumbnail_url = photo.media.thumbnail[0].url
        
        self.url = None
        
        self.location = PicasaProxy(self.photo_url)

    def replace_by(self, item):
        #print photo
        self.photo = item.photo
        self.name = self.photo.title.text
        self.mimetype = self.photo.content.type
        self.description = self.photo.summary.text
        self.photo_url = self.photo.content.src
        self.thumbnail_url = self.photo.media.thumbnail[0].url
        self.location = PicasaProxy(self.photo_url)
        return True
        

    def get_item(self):
        if self.item == None:
            upnp_id = self.storage_id
            upnp_parent_id = self.parent.get_id()
            self.item = DIDLLite.Photo(upnp_id,upnp_parent_id,self.title)
            res = DIDLLite.Resource(self.url, 'http-get:*:%s:*' % self.mimetype)
            self.item.res.append(res)
        return self.item

    def get_path(self):
        return self.url

    def get_id(self):
        return self.storage_id


class PicasaStore(BackendStore):

    logCategory = 'picasa_store'

    implements = ['MediaServer']

    wmc_mapping = {'16': ROOT_CONTAINER_ID}

    def __init__(self, server, **kwargs):
        self.next_id = 1000
        self.config = kwargs
        self.name = kwargs.get('name','Picasa Web Albums')

        self.refresh = int(kwargs.get('refresh',60))*60

        self.login = kwargs.get('userid',kwargs.get('login',''))
        self.password = kwargs.get('password','')
        
        self.urlbase = kwargs.get('urlbase','')
        if( len(self.urlbase)>0 and
            self.urlbase[len(self.urlbase)-1] != '/'):
            self.urlbase += '/'

        self.server = server
        self.update_id = 0
        self.store = {}

        rootContainer = Container(None, self.name, force_store=self, force_id = ROOT_CONTAINER_ID)
        self.set_root_item(rootContainer)
        
        self.AlbumsContainer = LazyContainer(rootContainer, 'My Albums', None, self.refresh, self.retrieveAlbums)
        rootContainer.add_child(self.AlbumsContainer)

        self.FeaturedContainer = LazyContainer(rootContainer, 'Featured photos', None, self.refresh, self.retrieveFeaturedPhotos)
        rootContainer.add_child(self.FeaturedContainer)

        self.init_completed()


    def __repr__(self):
        return str(self.__class__).split('.')[-1]

    def len(self):
        return len(self.store)

    def set_root_item(self, item):
        storage_id = ROOT_CONTAINER_ID
        self.store[storage_id] = item
        return storage_id

    def append_item(self, child):
        storage_id = self.getnextID()
        self.store[storage_id] = child
        return storage_id

    def remove_item(self, child):
        del self.store[child.storage_id]

    def get_by_id(self,id):
        if isinstance(id, basestring):
            id = id.split('@',1)
            id = id[0].split('.')[0]
        try:
            return self.store[int(id)]
        except (ValueError,KeyError):
            pass
        return None

    def getnextID(self):
        ret = self.next_id
        self.next_id += 1
        return ret

    def upnp_init(self):
        self.current_connection_id = None

        if self.server:
            self.server.connection_manager_server.set_variable(0, 'SourceProtocolInfo',
                                                                  'http-get:*:image/jpeg:DLNA.ORG_PN=JPEG_TN;DLNA.ORG_OP=01;DLNA.ORG_FLAGS=00f00000000000000000000000000000,'
                                                                  'http-get:*:image/jpeg:DLNA.ORG_PN=JPEG_SM;DLNA.ORG_OP=01;DLNA.ORG_FLAGS=00f00000000000000000000000000000,'
                                                                  'http-get:*:image/jpeg:DLNA.ORG_PN=JPEG_MED;DLNA.ORG_OP=01;DLNA.ORG_FLAGS=00f00000000000000000000000000000,'
                                                                  'http-get:*:image/jpeg:DLNA.ORG_PN=JPEG_LRG;DLNA.ORG_OP=01;DLNA.ORG_FLAGS=00f00000000000000000000000000000,'
                                                                  'http-get:*:image/jpeg:*,'
                                                                  'http-get:*:image/gif:*,'
                                                                  'http-get:*:image/png:*',
                                                                default=True)
            
        self.gd_client = gdata.photos.service.PhotosService()
        self.gd_client.email = self.login
        self.gd_client.password = self.password
        self.gd_client.source = 'Coherence UPnP backend'
        if len(self.login) > 0:
            d = threads.deferToThread(self.gd_client.ProgrammaticLogin)


    def retrieveAlbums(self, parent=None):
        albums = threads.deferToThread(self.gd_client.GetUserFeed)

        def gotAlbums(albums):
           if albums is None:
               print "Unable to retrieve albums"
               return
           for album in albums.entry:
               title = album.title.text
               album_id = album.gphoto_id.text
               item = LazyContainer(parent, title, album_id, self.refresh, self.retrieveAlbumPhotos, album_id=album_id)
               parent.add_child(item, external_id=album_id)

        def gotError(error):
            print "ERROR: %s" % error

        albums.addCallbacks(gotAlbums, gotError)
        return albums

    def retrieveFeedPhotos (self, parent=None, feed_uri=''):
        #print feed_uri
        photos = threads.deferToThread(self.gd_client.GetFeed, feed_uri)

        def gotPhotos(photos):
           if photos is None:
               print "Unable to retrieve photos for feed %s" % feed_uri
               return
           for photo in photos.entry:
               photo_id = photo.gphoto_id.text
               item = PicasaPhotoItem(photo)
               parent.add_child(item, external_id=photo_id)

        def gotError(error):
            print "ERROR: %s" % error

        photos.addCallbacks(gotPhotos, gotError)
        return photos

    def retrieveAlbumPhotos (self, parent=None, album_id=''):
        album_feed_uri = '/data/feed/api/user/%s/albumid/%s?kind=photo' % (self.login, album_id)       
        return self.retrieveFeedPhotos(parent, album_feed_uri)

    def retrieveFeaturedPhotos (self, parent=None):       
        feed_uri = 'http://picasaweb.google.com/data/feed/api/featured'
        return self.retrieveFeedPhotos(parent, feed_uri)

