# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2007, Frank Scholz <coherence@beebits.net>
# Copyright 2008, Jean-Michel Sizun <jm.sizun@free.fr>

from twisted.internet import defer

from coherence.upnp.core import utils
from coherence.upnp.core.utils import ReverseProxyUriResource

from coherence.upnp.core.DIDLLite import classChooser, Container, Resource, DIDLElement

from coherence.backend import BackendStore
from coherence.backend import BackendItem

from urlparse import urlsplit

from coherence.extern.galleryremote import Gallery


class ProxyGallery2Image(ReverseProxyUriResource):

    def __init__(self, uri):
        ReverseProxyUriResource.__init__(self, uri)

    def render(self, request):
        del request.received_headers['referer']
        return ReverseProxyUriResource.render(self, request)


class Gallery2Item(BackendItem):
    logCategory = 'gallery2_item'

    def __init__(self, id, obj, parent, mimetype, urlbase, UPnPClass,update=False):
        self.id = id

        self.name = obj.get('title')#.encode('utf-8')
        if self.name == None:
            self.name = obj.get('name')
        if self.name == None:
            self.name = id

        self.mimetype = mimetype

        self.gallery2_id = obj.get('gallery2_id')

        self.parent = parent
        if parent:
            parent.add_child(self,update=update)

        if parent == None:
            parent_id = -1
        else:
            parent_id = parent.get_id()

        self.item = UPnPClass(id, parent_id, self.name)
        if isinstance(self.item, Container):
            self.item.childCount = 0
        self.child_count = 0
        self.children = None

        if( len(urlbase) and urlbase[-1] != '/'):
            urlbase += '/'

        if parent == None:
            self.gallery2_url = None
            self.url = urlbase + str(self.id)
        elif self.mimetype == 'directory':
            #self.gallery2_url = parent.store.get_url_for_album(self.gallery2_id)
            self.url = urlbase + str(self.id)
        else:
            self.gallery2_url = parent.store.get_url_for_image(self.gallery2_id)
            self.url = urlbase + str(self.id)
            self.location = ProxyGallery2Image(self.gallery2_url)

        if self.mimetype == 'directory':
            self.update_id = 0
        else:
            res = Resource(self.gallery2_url, 'http-get:*:%s:*' % self.mimetype)
            res.size = None
            self.item.res.append(res)


    def remove(self):
        if self.parent:
            self.parent.remove_child(self)
        del self.item

    def add_child(self, child, update=False):
        if self.children == None:
            self.children = []
        self.children.append(child)
        self.child_count += 1
        if isinstance(self.item, Container):
            self.item.childCount += 1
        if update == True:
            self.update_id += 1


    def remove_child(self, child):
        #self.info("remove_from %d (%s) child %d (%s)" % (self.id, self.get_name(), child.id, child.get_name()))
        if child in self.children:
            self.child_count -= 1
            if isinstance(self.item, Container):
                self.item.childCount -= 1
            self.children.remove(child)
            self.update_id += 1


    def get_children(self,start=0,request_count=0):
        def process_items(result = None):
            if self.children == None:
                return  []
            if request_count == 0:
                return self.children[start:]
            else:
                return self.children[start:request_count]

        if (self.children == None):
            d = self.store.retrieveItemsForAlbum(self.gallery2_id, self)
            d.addCallback(process_items)
            return d
        else:
            return process_items()


    def get_child_count(self):
        return self.child_count

    def get_id(self):
        return self.id

    def get_update_id(self):
        if hasattr(self, 'update_id'):
            return self.update_id
        else:
            return None

    def get_path(self):
        return self.url

    def get_name(self):
        return self.name

    def get_parent(self):
        return self.parent

    def get_item(self):
        return self.item

    def get_xml(self):
        return self.item.toString()

    def __repr__(self):
        return 'id: ' + str(self.id)


class Gallery2Store(BackendStore):

    logCategory = 'gallery2_store'

    implements = ['MediaServer']

    description = ('Gallery2', 'exposes the photos from a Gallery2 photo repository.', None)

    options = [{'option':'name', 'text':'Server Name:', 'type':'string','default':'my media','help': 'the name under this MediaServer shall show up with on other UPnP clients'},
       {'option':'version','text':'UPnP Version:','type':'int','default':2,'enum': (2,1),'help': 'the highest UPnP version this MediaServer shall support','level':'advance'},
       {'option':'uuid','text':'UUID Identifier:','type':'string','help':'the unique (UPnP) identifier for this MediaServer, usually automatically set','level':'advance'},    
       {'option':'server_url','text':'Server URL:','type':'string'},
       {'option':'username','text':'User ID:','type':'string','group':'User Account'},
       {'option':'password','text':'Password:','type':'string','group':'User Account'},
    ]

    def __init__(self, server, **kwargs):
        BackendStore.__init__(self,server,**kwargs)

        self.next_id = 1000
        self.config = kwargs
        self.name = kwargs.get('name','gallery2Store')

        self.wmc_mapping = {'16': 1000}

        self.update_id = 0
        self.store = {}

        self.gallery2_server_url = self.config.get('server_url', 'http://localhost/gallery2')
        self.gallery2_username = self.config.get('username',None)
        self.gallery2_password = self.config.get('password',None)

        self.store[1000] = Gallery2Item( 1000, {'title':'Gallery2','gallery2_id':'0','mimetype':'directory'}, None,
                                                        'directory', self.urlbase,Container,update=True)
        self.store[1000].store = self

        self.gallery2_remote = Gallery(self.gallery2_server_url, 2)
        if not None in [self.gallery2_username, self.gallery2_password]:
            d = self.gallery2_remote.login(self.gallery2_username, self.gallery2_password)
            d.addCallback(lambda x : self.retrieveAlbums('0', self.store[1000]))
            d.addCallback(self.init_completed)
        else:
            d = self.retrieveAlbums('0', self.store[1000])
            d.addCallback(self.init_completed)

    def __repr__(self):
        return self.__class__.__name__ 

    def append( self, obj, parent):
        if isinstance(obj, basestring):
            mimetype = 'directory'
        else:
            mimetype = obj['mimetype']

        UPnPClass = classChooser(mimetype)
        id = self.getnextID()
        update = False
        #if hasattr(self, 'update_id'):
        #    update = True

        item = Gallery2Item( id, obj, parent, mimetype, self.urlbase,
                                        UPnPClass, update=update)
        self.store[id] = item
        self.store[id].store = self
        if hasattr(self, 'update_id'):
            self.update_id += 1
            if self.server:
                self.server.content_directory_server.set_variable(0, 'SystemUpdateID', self.update_id)
            #if parent:
            #    value = (parent.get_id(),parent.get_update_id())
            #    if self.server:
            #        self.server.content_directory_server.set_variable(0, 'ContainerUpdateIDs', value)

        if mimetype == 'directory':
            return self.store[id]

        return None

    def len(self):
        return len(self.store)

    def get_by_id(self,id):
        if isinstance(id, basestring):
            id = id.split('@',1)
            id = id[0]
        try:
            id = int(id)
        except ValueError:
            id = 1000

        if id == 0:
            id = 1000
        try:
            return self.store[id]
        except:
            return None

    def getnextID(self):
        self.next_id += 1
        return self.next_id

    def get_url_for_image(self, gallery2_id):
        url = self.gallery2_remote.get_URL_for_image(gallery2_id)
        return url

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


    def retrieveAlbums(self, album_gallery2_id, parent):
        d = self.gallery2_remote.fetch_albums()

        def gotAlbums (albums):
            if albums :
                albums = [album for album in albums.values() if album.get('parent') == album_gallery2_id]
                if album_gallery2_id == '0' and len(albums) == 1:
                    album = albums[0]
                    self.store[1000].gallery2_id = album.get('name')
                    self.store[1000].name = album.get('title')
                    self.store[1000].description = album.get('summary')
                else:
                    for album in albums:
                        gallery2_id = album.get('name')
                        parent_gallery2_id = album.get('parent')
                        title = album.get('title')
                        description = album.get('summary')
                        store_item = {
                                  'name':id,
                                  'gallery2_id':gallery2_id,
                                  'parent_id':parent_gallery2_id,
                                  'title':title,
                                  'description':description,
                                  'mimetype':'directory',
                                    }
                        self.append(store_item, parent)

        d.addCallback(gotAlbums)
        return d

    def retrieveItemsForAlbum (self, album_id, parent):
        # retrieve subalbums
        d1 = self.retrieveAlbums(album_id, parent)

        # retrieve images
        d2 = self.gallery2_remote.fetch_album_images(album_id)

        def gotImages(images):
            if images :
                for image in images:
                    image_gallery2_id = image.get('name')
                    parent_gallery2_id = image.get('parent')
                    thumbnail_gallery2_id = image.get('thumbName')
                    resized_gallery2_id = image.get('resizedName')
                    title = image.get('title')
                    description = image.get('description')

                    gallery2_id =  resized_gallery2_id
                    if gallery2_id == '':
                        gallery2_id = image_gallery2_id

                    store_item = {
                                  'name':id,
                                  'gallery2_id':gallery2_id,
                                  'parent_id':parent_gallery2_id,
                                  'thumbnail_gallery2_id':thumbnail_gallery2_id,
                                  'title':title,
                                  'description':description,
                                  'mimetype':'image/jpeg',
                                }
                    self.append(store_item, parent)

        d2.addCallback(gotImages)
        dl = defer.DeferredList([d1,d2])
        return dl



def main():

    f = Gallery2Store(None)

    def got_upnp_result(result):
        print "upnp", result

    f.upnp_init()


if __name__ == '__main__':

    from twisted.internet import reactor

    reactor.callWhenRunning(main)
    reactor.run()
