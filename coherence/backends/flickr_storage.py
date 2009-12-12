# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2007,2008 Frank Scholz <coherence@beebits.net>

import time
import re
import os.path
import mimetools,mimetypes
from datetime import datetime
from email.Utils import parsedate_tz

try:
    import hashlib
    def md5(s):
        m =hashlib.md5()
        m.update(s)
        return m.hexdigest()
except ImportError:
    import md5 as oldmd5
    def md5(s):
        m=oldmd5.new()
        m.update(s)
        return m.hexdigest()

from twisted.python import failure
from twisted.web.xmlrpc import Proxy
from twisted.web import client
from twisted.internet import task
from twisted.python.filepath import FilePath

from coherence.upnp.core.utils import parse_xml, ReverseProxyResource

from coherence.upnp.core.DIDLLite import classChooser,Container,PhotoAlbum,Photo,ImageItem,Resource,DIDLElement
from coherence.upnp.core.DIDLLite import simple_dlna_tags, PlayContainerResource
from coherence.upnp.core.soap_proxy import SOAPProxy
from coherence.upnp.core.soap_service import errorCode

from coherence.upnp.core.utils import getPage
from coherence.backend import BackendItem, BackendStore

from coherence.extern.simple_plugin import Plugin

from coherence import log

from urlparse import urlsplit

ROOT_CONTAINER_ID = 0
INTERESTINGNESS_CONTAINER_ID = 100
RECENT_CONTAINER_ID = 101
FAVORITES_CONTAINER_ID = 102
GALLERY_CONTAINER_ID = 200
UNSORTED_CONTAINER_ID = 201
CONTACTS_CONTAINER_ID = 300


class FlickrAuthenticate(object):

    def __init__(self,api_key,api_secret,frob,userid,password,perms):
        from mechanize import Browser

        browser = Browser()
        browser.set_handle_robots(False)
        browser.set_handle_refresh(True,max_time=1)
        browser.set_handle_redirect(True)

        api_sig = ''.join((api_secret,'api_key',api_key,'frob',frob,'perms',perms))
        api_sig=md5(api_sig)
        login_url = "http://flickr.com/services/auth/?api_key=%s&perms=%s&frob=%s&api_sig=%s" % (api_key,perms,frob,api_sig)
        browser.open(login_url)
        browser.select_form(name='login_form')
        browser['login']=userid
        browser['passwd']=password
        browser.submit()
        for form in browser.forms():
            try:
                if form['frob'] == frob:
                    browser.form = form
                    browser.submit()
                    break;
            except:
                pass
        else:
            raise Exception('no form for authentication found') # lame :-/


class ProxyImage(ReverseProxyResource):

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


class FlickrItem(log.Loggable):
    logCategory = 'flickr_storage'

    def __init__(self, id, obj, parent, mimetype, urlbase, UPnPClass,store=None,update=False,proxy=False):
        self.id = id
        self.real_url = None
        self.obj = obj
        self.upnp_class = UPnPClass
        self.store = store
        self.item = None
        self.date = None

        if isinstance(obj, str):
            self.name = obj
            if isinstance(self.id,basestring) and self.id.startswith('upload.'):
                self.mimetype = mimetype
            else:
                self.mimetype = 'directory'
        elif mimetype == 'directory':
            title = obj.find('title')
            self.name = title.text;
            if len(self.name) == 0:
                self.name = obj.get('id')
            self.mimetype = 'directory'
        elif mimetype == 'contact':
            self.name = obj.get('realname')
            if self.name == '':
                self.name = obj.get('username')
            self.nsid = obj.get('nsid')
            self.mimetype = 'directory'
        else:
            self.name = obj.get('title') #.encode('utf-8')
            if self.name == None:
                self.name = obj.find('title')
                if self.name != None:
                    self.name = self.name.text
            if self.name == None or len(self.name) == 0:
                self.name = 'untitled'
            self.mimetype = 'image/jpeg'

        self.parent = parent
        if not (isinstance(self.id,basestring) and self.id.startswith('upload.')):
            if parent:
                parent.add_child(self,update=update)

        if( len(urlbase) and urlbase[-1] != '/'):
            urlbase += '/'

        if self.mimetype == 'directory':
            try:
                self.flickr_id = obj.get('id')
            except:
                self.flickr_id = None
            self.url = urlbase + str(self.id)
        elif isinstance(self.id,basestring) and self.id.startswith('upload.'):
            self.url = urlbase + str(self.id)
            self.location = None
        else:
            self.flickr_id = obj.get('id')

            try:
                datetaken = obj.get('datetaken')
                date,time = datetaken.split(' ')
                year,month,day = date.split('-')
                hour,minute,second = time.split(':')
                self.date = datetime(int(year),int(month),int(day),int(hour),int(minute),int(second))
            except:
                import traceback
                self.debug(traceback.format_exc())

            self.real_url = "http://farm%s.static.flickr.com/%s/%s_%s.jpg" % (
                            obj.get('farm'),
                            obj.get('server'),
                            obj.get('id'),
                            obj.get('secret'))

            if proxy == True:
                self.url = urlbase + str(self.id)
                self.location = ProxyImage(self.real_url)
            else:
                self.url = u"http://farm%s.static.flickr.com/%s/%s_%s.jpg" % (
                        obj.get('farm').encode('utf-8'),
                        obj.get('server').encode('utf-8'),
                        obj.get('id').encode('utf-8'),
                        obj.get('secret').encode('utf-8'))

        if parent == None:
            self.parent_id = -1
        else:
            self.parent_id = parent.get_id()

        if self.mimetype == 'directory':
            self.children = []
            self.update_id = 0


    def set_item_size_and_date(self):

        def gotPhoto(result):
            self.debug("gotPhoto", result)
            _, headers = result
            length = headers.get('content-length',None)
            modified = headers.get('last-modified',None)
            if length != None:
                self.item.res[0].size = int(length[0])
            if modified != None:
                """ Tue, 06 Feb 2007 15:56:32 GMT """
                self.item.date = datetime(*parsedate_tz(modified[0])[0:6])

        def gotError(failure, url):
            self.warning("error requesting", failure, url)
            self.info(failure)

        getPage(self.real_url,method='HEAD',timeout=60).addCallbacks(gotPhoto, gotError, None, None, [self.real_url], None)

    def remove(self):
        #print "FSItem remove", self.id, self.get_name(), self.parent
        if self.parent:
            self.parent.remove_child(self)
        del self.item

    def add_child(self, child, update=False):
        self.children.append(child)
        if update == True:
            self.update_id += 1

    def remove_child(self, child):
        self.info("remove_from %d (%s) child %d (%s)" % (self.id, self.get_name(), child.id, child.get_name()))
        if child in self.children:
            self.children.remove(child)
            self.update_id += 1

    def get_children(self,start=0,request_count=0):
        if request_count == 0:
            return self.children[start:]
        else:
            return self.children[start:request_count]

    def get_child_count(self):
        return len(self.children)

    def get_id(self):
        return self.id

    def get_location(self):
        return self.location

    def get_update_id(self):
        if hasattr(self, 'update_id'):
            return self.update_id
        else:
            return None

    def get_path(self):
        if isinstance(self.id,basestring) and self.id.startswith('upload.'):
            return '/tmp/' + self.id  # FIXME
        return self.url

    def get_name(self):
        return self.name

    def get_flickr_id(self):
        return self.flickr_id

    def get_child_by_flickr_id(self, flickr_id):
        for c in self.children:
            if flickr_id == c.flickr_id:
                return c
        return None

    def get_parent(self):
        return self.parent

    def get_item(self):
        if self.item == None:
            if self.mimetype == 'directory':
                self.item = self.upnp_class(self.id, self.parent_id, self.get_name())
                self.item.childCount = self.get_child_count()
                if self.get_child_count() > 0:
                    res = PlayContainerResource(self.store.server.uuid,cid=self.get_id(),fid=self.get_children()[0].get_id())
                    self.item.res.append(res)
            else:
                return self.create_item()
        return self.item

    def create_item(self):
        def process(result):
            for size in result.getiterator('size'):
                #print size.get('label'), size.get('source')
                if size.get('label') == 'Original':
                    self.original_url = (size.get('source'),size.get('width')+'x'+size.get('height'))
                    if self.store.proxy == False:
                        self.url = self.original_url[0]
                    else:
                        self.location = ProxyImage(self.original_url[0])
                elif size.get('label') == 'Large':
                    self.large_url = (size.get('source'),size.get('width')+'x'+size.get('height'))
                    if self.store.proxy == False:
                        self.url = self.large_url[0]
                    else:
                        self.location = ProxyImage(self.large_url[0])
                elif size.get('label') == 'Medium':
                    self.medium_url = (size.get('source'),size.get('width')+'x'+size.get('height'))
                elif size.get('label') == 'Small':
                    self.small_url = (size.get('source'),size.get('width')+'x'+size.get('height'))
                elif size.get('label') == 'Thumbnail':
                    self.thumb_url = (size.get('source'),size.get('width')+'x'+size.get('height'))

            self.item = Photo(self.id,self.parent.get_id(),self.get_name())
            #print self.id, self.store.proxy, self.url
            self.item.date = self.date
            self.item.attachments = {}
            dlna_tags = simple_dlna_tags[:]
            dlna_tags[3] = 'DLNA.ORG_FLAGS=00f00000000000000000000000000000'
            if hasattr(self,'original_url'):
                dlna_pn = 'DLNA.ORG_PN=JPEG_LRG'
                if self.store.proxy == False:
                    res = Resource(self.original_url[0], 'http-get:*:%s:%s' % (self.mimetype,';'.join([dlna_pn]+dlna_tags)))
                else:
                    res = Resource(self.url+'?attachment=original', 'http-get:*:%s:%s' % (self.mimetype,';'.join([dlna_pn]+dlna_tags)))
                    self.item.attachments['original'] = ProxyImage(self.original_url[0])
                res.resolution = self.original_url[1]
                self.item.res.append(res)
            elif hasattr(self,'large_url'):
                dlna_pn = 'DLNA.ORG_PN=JPEG_LRG'
                if self.store.proxy == False:
                    res = Resource(self.large_url[0], 'http-get:*:%s:%s' % (self.mimetype,';'.join([dlna_pn]+dlna_tags)))
                else:
                    res = Resource(self.url+'?attachment=large', 'http-get:*:%s:%s' % (self.mimetype,';'.join([dlna_pn]+dlna_tags)))
                    self.item.attachments['large'] = ProxyImage(self.large_url[0])
                res.resolution = self.large_url[1]
                self.item.res.append(res)
            if hasattr(self,'medium_url'):
                dlna_pn = 'DLNA.ORG_PN=JPEG_MED'
                if self.store.proxy == False:
                    res = Resource(self.medium_url[0], 'http-get:*:%s:%s' % (self.mimetype,';'.join([dlna_pn]+dlna_tags)))
                else:
                    res = Resource(self.url+'?attachment=medium', 'http-get:*:%s:%s' % (self.mimetype,';'.join([dlna_pn]+dlna_tags)))
                    self.item.attachments['medium'] = ProxyImage(self.medium_url[0])
                res.resolution = self.medium_url[1]
                self.item.res.append(res)
            if hasattr(self,'small_url'):
                dlna_pn = 'DLNA.ORG_PN=JPEG_SM'
                if self.store.proxy == False:
                    res = Resource(self.small_url[0], 'http-get:*:%s:%s' % (self.mimetype,';'.join([dlna_pn]+dlna_tags)))
                else:
                    res = Resource(self.url+'?attachment=small', 'http-get:*:%s:%s' % (self.mimetype,';'.join([dlna_pn]+dlna_tags)))
                    self.item.attachments['small'] = ProxyImage(self.small_url[0])
                res.resolution = self.small_url[1]
                self.item.res.append(res)
            if hasattr(self,'thumb_url'):
                dlna_pn = 'DLNA.ORG_PN=JPEG_TN'
                if self.store.proxy == False:
                    res = Resource(self.thumb_url[0], 'http-get:*:%s:%s' % (self.mimetype,';'.join([dlna_pn]+dlna_tags)))
                else:
                    res = Resource(self.url+'?attachment=thumb', 'http-get:*:%s:%s' % (self.mimetype,';'.join([dlna_pn]+dlna_tags)))
                    self.item.attachments['thumb'] = ProxyImage(self.thumb_url[0])
                res.resolution = self.thumb_url[1]
                self.item.res.append(res)

            return self.item

        d = self.store.flickr_photos_getSizes(photo_id=self.flickr_id)
        d.addCallback(process)
        return d

    def get_xml(self):
        return self.item.toString()

    def __repr__(self):
        return 'id: ' + str(self.id) + ' @ ' + str(self.url)


class FlickrStore(BackendStore):
    logCategory = 'flickr_storage'

    implements = ['MediaServer']

    def __init__(self, server, **kwargs):
        BackendStore.__init__(self,server,**kwargs)
        self.next_id = 10000
        self.name = kwargs.get('name','Flickr')
        self.proxy = kwargs.get('proxy','false')
        self.refresh = int(kwargs.get('refresh',60))*60

        self.limit = int(kwargs.get('limit',100))


        self.flickr_userid = kwargs.get('userid',None)
        self.flickr_password = kwargs.get('password',None)
        self.flickr_permissions = kwargs.get('permissions',None)

        if self.proxy in [1,'Yes','yes','True','true']:
            self.proxy = True
        else:
            self.proxy = False

        ignore_patterns = kwargs.get('ignore_patterns',[])
        ignore_file_pattern = re.compile('|'.join(['^\..*'] + list(ignore_patterns)))

        self.wmc_mapping = {'16': 0}

        self.update_id = 0
        self.flickr = Proxy('http://api.flickr.com/services/xmlrpc/')
        self.flickr_api_key = '837718c8a622c699edab0ea55fcec224'
        self.flickr_api_secret = '30a684822c341c3c'
        self.store = {}
        self.uploads = {}

        self.refresh_store_loop = task.LoopingCall(self.refresh_store)
        self.refresh_store_loop.start(self.refresh, now=False)

        #self.server.coherence.store_plugin_config(self.server.uuid, {'test':'äöüß'})

        self.flickr_userid = kwargs.get('userid',None)
        self.flickr_password = kwargs.get('password',None)
        self.flickr_permissions = kwargs.get('permissions','read')

        self.flickr_authtoken = kwargs.get('authtoken',None)

        if(self.flickr_authtoken == None and
           self.server.coherence.writeable_config() == True):
            if not None in (self.flickr_userid,self.flickr_password):
                d = self.flickr_authenticate_app()
                d.addBoth(lambda x: self.init_completed())
                return
            
        self.init_completed()

    def __repr__(self):
        return str(self.__class__).split('.')[-1]

    def append( self, obj, parent):
        if isinstance(obj, str):
            mimetype = 'directory'
        else:
            mimetype = 'image/'

        UPnPClass = classChooser(mimetype)
        id = self.getnextID()
        update = False
        if hasattr(self, 'update_id'):
            update = True

        self.store[id] = FlickrItem( id, obj, parent, mimetype, self.urlbase,
                                        UPnPClass, store=self,
                                        update=update, proxy=self.proxy)
        if hasattr(self, 'update_id'):
            self.update_id += 1
            if self.server:
                self.server.content_directory_server.set_variable(0, 'SystemUpdateID', self.update_id)
            if parent:
                #value = '%d,%d' % (parent.get_id(),parent_get_update_id())
                value = (parent.get_id(),parent.get_update_id())
                if self.server:
                    self.server.content_directory_server.set_variable(0, 'ContainerUpdateIDs', value)

        if mimetype == 'directory':
            return self.store[id]


        def update_photo_details(result, photo):
            dates = result.find('dates')
            self.debug("update_photo_details", dates.get('posted'), dates.get('taken'))
            photo.item.date = datetime(*time.strptime(dates.get('taken'),
                                               "%Y-%m-%d %H:%M:%S")[0:6])

        #d = self.flickr_photos_getInfo(obj.get('id'),obj.get('secret'))
        #d.addCallback(update_photo_details, self.store[id])

        return None

    def appendDirectory( self, obj, parent):
        mimetype = 'directory'

        UPnPClass = classChooser(mimetype)
        id = self.getnextID()
        update = False
        if hasattr(self, 'update_id'):
            update = True

        self.store[id] = FlickrItem( id, obj, parent, mimetype, self.urlbase,
                                        UPnPClass,store=self,update=update, proxy=self.proxy)
        if hasattr(self, 'update_id'):
            self.update_id += 1
            if self.server:
                self.server.content_directory_server.set_variable(0, 'SystemUpdateID', self.update_id)
            if parent:
                #value = '%d,%d' % (parent.get_id(),parent_get_update_id())
                value = (parent.get_id(),parent.get_update_id())
                if self.server:
                    self.server.content_directory_server.set_variable(0, 'ContainerUpdateIDs', value)

        return self.store[id]

    def appendPhoto( self, obj, parent):
        mimetype = 'image/'

        UPnPClass = classChooser(mimetype)
        id = self.getnextID()
        update = False
        if hasattr(self, 'update_id'):
            update = True

        self.store[id] = FlickrItem( id, obj, parent, mimetype, self.urlbase,
                                        UPnPClass,store=self,update=update, proxy=self.proxy)
        if hasattr(self, 'update_id'):
            self.update_id += 1
            if self.server:
                self.server.content_directory_server.set_variable(0, 'SystemUpdateID', self.update_id)
            if parent:
                #value = '%d,%d' % (parent.get_id(),parent_get_update_id())
                value = (parent.get_id(),parent.get_update_id())
                if self.server:
                    self.server.content_directory_server.set_variable(0, 'ContainerUpdateIDs', value)

        def update_photo_details(result, photo):
            dates = result.find('dates')
            self.debug("update_photo_details", dates.get('posted'), dates.get('taken'))
            photo.item.date = datetime(*time.strptime(dates.get('taken'),
                                               "%Y-%m-%d %H:%M:%S")[0:6])

        #d = self.flickr_photos_getInfo(obj.get('id'),obj.get('secret'))
        #d.addCallback(update_photo_details, self.store[id])

        return None

    def appendPhotoset( self, obj, parent):
        mimetype = 'directory'

        UPnPClass = classChooser(mimetype)
        id = self.getnextID()
        update = False
        if hasattr(self, 'update_id'):
            update = True

        self.store[id] = FlickrItem( id, obj, parent, mimetype, self.urlbase,
                                        UPnPClass,store=self,update=update, proxy=self.proxy)
        if hasattr(self, 'update_id'):
            self.update_id += 1
            if self.server:
                self.server.content_directory_server.set_variable(0, 'SystemUpdateID', self.update_id)
            if parent:
                #value = '%d,%d' % (parent.get_id(),parent_get_update_id())
                value = (parent.get_id(),parent.get_update_id())
                if self.server:
                    self.server.content_directory_server.set_variable(0, 'ContainerUpdateIDs', value)

        return self.store[id]

    def appendContact( self, obj, parent):
        mimetype = 'directory'

        UPnPClass = classChooser(mimetype)
        id = self.getnextID()
        update = False
        if hasattr(self, 'update_id'):
            update = True

        self.store[id] = FlickrItem( id, obj, parent, 'contact', self.urlbase,
                                        UPnPClass,store=self,update=update, proxy=self.proxy)
        if hasattr(self, 'update_id'):
            self.update_id += 1
            if self.server:
                self.server.content_directory_server.set_variable(0, 'SystemUpdateID', self.update_id)
            if parent:
                #value = '%d,%d' % (parent.get_id(),parent_get_update_id())
                value = (parent.get_id(),parent.get_update_id())
                if self.server:
                    self.server.content_directory_server.set_variable(0, 'ContainerUpdateIDs', value)

        return self.store[id]

    def remove(self, id):
        #print 'FlickrStore remove id', id
        try:
            item = self.store[int(id)]
            parent = item.get_parent()
            item.remove()
            del self.store[int(id)]
            if hasattr(self, 'update_id'):
                self.update_id += 1
                if self.server:
                    self.server.content_directory_server.set_variable(0, 'SystemUpdateID', self.update_id)
                #value = '%d,%d' % (parent.get_id(),parent_get_update_id())
                value = (parent.get_id(),parent.get_update_id())
                if self.server:
                    self.server.content_directory_server.set_variable(0, 'ContainerUpdateIDs', value)
        except:
            pass

    def append_flickr_result(self, result, parent):
        count = 0
        for photo in result.getiterator('photo'):
            self.append(photo, parent)
            count += 1
        self.info("initialized photo set %s with %d images" % (parent.get_name(), count))

    def append_flickr_photo_result(self, result, parent):
        count = 0
        for photo in result.getiterator('photo'):
            self.appendPhoto(photo, parent)
            count += 1
        self.info("initialized photo set %s with %d images" % (parent.get_name(), count))

    def append_flickr_photoset_result(self, result, parent):
        photoset_count = 0
        for photoset in result.getiterator('photoset'):
            photoset = self.appendPhotoset(photoset, parent)
            d = self.flickr_photoset(photoset,per_page=self.limit)
            d.addCallback(self.append_flickr_photo_result, photoset)
            photoset_count += 1

    def append_flickr_contact_result(self, result, parent):
        contact_count = 0
        for contact in result.getiterator('contact'):
            contact = self.appendContact(contact, parent)
            d = self.flickr_photosets(user_id=contact.nsid)
            d.addCallback(self.append_flickr_photoset_result, contact)
            contact_count += 1

    def len(self):
        return len(self.store)

    def get_by_id(self,id):
        if isinstance(id, basestring) and id.startswith('upload.'):
            self.info("get_by_id looking for %s", id)
            try:
                item = self.uploads[id]
                self.info('get_by_id found %r' % item)
                return item
            except:
                return None

        if isinstance(id, basestring):
            id = id.split('@',1)
            id = id[0]
        try:
            id = int(id)
        except ValueError:
            id = 0

        try:
            return self.store[id]
        except:
            return None

    def getnextID(self):
        ret = self.next_id
        self.next_id += 1
        return ret

    def got_error(self,error):
        self.warning("trouble refreshing Flickr data %r", error)
        self.debug("%r", error.getTraceback())

    def update_flickr_result(self,result, parent, element='photo'):
        """ - is in in the store, but not in the update,
              remove it from the store
            - the photo is already in the store, skip it
            - if in the update, but not in the store,
              append it to the store
        """
        old_ones = {}
        new_ones = {}
        for child in parent.get_children():
            old_ones[child.get_flickr_id()] = child
        for photo in result.findall(element):
            new_ones[photo.get('id')] = photo
        for id,child in old_ones.items():
            if new_ones.has_key(id):
                self.debug(id, "already there")
                del new_ones[id]
            elif child.id != UNSORTED_CONTAINER_ID:
                self.debug(child.get_flickr_id(), "needs removal")
                del old_ones[id]
                self.remove(child.get_id())
        self.info("refresh pass 1:", "old", len(old_ones), "new", len(new_ones), "store", len(self.store))
        for photo in new_ones.values():
            if element == 'photo':
                self.appendPhoto(photo, parent)
            elif element == 'photoset':
                self.appendPhotoset(photo, parent)

        self.debug("refresh pass 2:", "old", len(old_ones), "new", len(new_ones), "store", len(self.store))
        if len(new_ones) > 0:
            self.info("updated %s with %d new %ss" % (parent.get_name(), len(new_ones), element))

        if element == 'photoset':
            """ now we need to check the childs of all photosets
                something that should be reworked imho
            """
            for child in parent.get_children():
                if child.id == UNSORTED_CONTAINER_ID:
                    continue
                d = self.flickr_photoset(child,per_page=self.limit)
                d.addCallback(self.update_flickr_result, child)
                d.addErrback(self.got_error)

    def refresh_store(self):
        self.debug("refresh_store")

        d = self.flickr_interestingness()
        d.addCallback(self.update_flickr_result, self.most_wanted)
        d.addErrback(self.got_error)

        d = self.flickr_recent()
        d.addCallback(self.update_flickr_result, self.recent)
        d.addErrback(self.got_error)

        if self.flickr_authtoken != None:
            d= self.flickr_photosets()
            d.addCallback(self.update_flickr_result, self.photosets, 'photoset')
            d.addErrback(self.got_error)

            d = self.flickr_notInSet()
            d.addCallback(self.update_flickr_result, self.notinset)
            d.addErrback(self.got_error)

            d = self.flickr_favorites()
            d.addCallback(self.update_flickr_result, self.favorites)
            d.addErrback(self.got_error)

    def flickr_call(self, method, **kwargs):
        def got_result(result,method):
            self.debug('flickr_call %r result %r' % (method,result))
            result = parse_xml(result, encoding='utf-8')
            return result

        def got_error(error,method):
            self.warning("connection to Flickr %r service failed! %r" % (method, error))
            self.debug("%r", error.getTraceback())
            return error

        args = {}
        args.update(kwargs)
        args['api_key'] = self.flickr_api_key
        if 'api_sig' in args:
            args['method'] = method

        self.debug('flickr_call %s %r',method,args)
        d = self.flickr.callRemote(method, args)
        d.addCallback(got_result,method)
        d.addErrback(got_error,method)
        return d

    def flickr_test_echo(self):
        d = self.flickr_call('flickr.test.echo')
        return d

    def flickr_test_login(self):
        d = self.flickr_call('flickr.test.login',signed=True)
        return d

    def flickr_auth_getFrob(self):
        api_sig = self.flickr_create_api_signature(method='flickr.auth.getFrob')
        d = self.flickr_call('flickr.auth.getFrob',api_sig=api_sig)
        return d

    def flickr_auth_getToken(self,frob):
        api_sig = self.flickr_create_api_signature(frob=frob,method='flickr.auth.getToken')
        d = self.flickr_call('flickr.auth.getToken',frob=frob,api_sig=api_sig)
        return d

    def flickr_photos_getInfo(self, photo_id=None, secret=None):
        if secret:
            d = self.flickr_call('flickr.photos.getInfo', photo_id=photo_id, secret=secret)
        else:
            d = self.flickr_call('flickr.photos.getInfo', photo_id=photo_id)
        return d

    def flickr_photos_getSizes(self, photo_id=None):
        if self.flickr_authtoken != None:
            api_sig = self.flickr_create_api_signature(auth_token=self.flickr_authtoken,method='flickr.photos.getSizes', photo_id=photo_id)
            d = self.flickr_call('flickr.photos.getSizes', auth_token=self.flickr_authtoken, photo_id=photo_id,api_sig=api_sig)
        else:
            api_sig = self.flickr_create_api_signature(method='flickr.photos.getSizes', photo_id=photo_id)
            d = self.flickr_call('flickr.photos.getSizes',photo_id=photo_id,api_sig=api_sig)
        return d

    def flickr_interestingness(self, date=None, per_page=100):
        if date == None:
            date = time.strftime( "%Y-%m-%d", time.localtime(time.time()-86400))
        if per_page > 500:
            per_page = 500
        d = self.flickr_call('flickr.interestingness.getList',extras='date_taken',per_page=per_page)
        return d

    def flickr_recent(self, date=None, per_page=100):
        if date == None:
            date = time.strftime( "%Y-%m-%d", time.localtime(time.time()-86400))
        if per_page > 500:
            per_page = 500
        d = self.flickr_call('flickr.photos.getRecent',extras='date_taken',per_page=per_page)
        return d

    def flickr_notInSet(self, date=None, per_page=100):
        api_sig = self.flickr_create_api_signature(auth_token=self.flickr_authtoken,extras='date_taken',method='flickr.photos.getNotInSet')
        d = self.flickr_call('flickr.photos.getNotInSet',
                                    auth_token=self.flickr_authtoken,
                                    extras='date_taken',
                                    api_sig=api_sig)
        return d

    def flickr_photosets(self,user_id=None,date=None,per_page=100):
        if user_id != None:
            api_sig = self.flickr_create_api_signature(auth_token=self.flickr_authtoken,method='flickr.photosets.getList',user_id=user_id)
            d = self.flickr_call('flickr.photosets.getList',
                                    user_id=user_id,
                                    auth_token=self.flickr_authtoken,
                                    api_sig=api_sig)
        else:
            api_sig = self.flickr_create_api_signature(auth_token=self.flickr_authtoken,method='flickr.photosets.getList')
            d = self.flickr_call('flickr.photosets.getList',
                                    auth_token=self.flickr_authtoken,
                                    api_sig=api_sig)
        return d

    def flickr_photoset(self, photoset, date=None, per_page=100):
        api_sig = self.flickr_create_api_signature(auth_token=self.flickr_authtoken,extras='date_taken',method='flickr.photosets.getPhotos',photoset_id=photoset.obj.get('id'))
        d = self.flickr_call('flickr.photosets.getPhotos',
                                    photoset_id=photoset.obj.get('id'),
                                    extras='date_taken',
                                    auth_token=self.flickr_authtoken,
                                    api_sig=api_sig)
        return d

    def flickr_favorites(self, date=None, per_page=100):
        api_sig = self.flickr_create_api_signature(auth_token=self.flickr_authtoken,extras='date_taken',method='flickr.favorites.getList')
        d = self.flickr_call('flickr.favorites.getList',
                                    auth_token=self.flickr_authtoken,
                                    extras='date_taken',
                                    api_sig=api_sig)
        return d

    def flickr_contacts(self, date=None, per_page=100):
        api_sig = self.flickr_create_api_signature(auth_token=self.flickr_authtoken,method='flickr.contacts.getList')
        d = self.flickr_call('flickr.contacts.getList',
                                    auth_token=self.flickr_authtoken,
                                    api_sig=api_sig)
        return d

    def flickr_contact_recents(self, contact, date=None, per_page=100):
        api_sig = self.flickr_create_api_signature(auth_token=self.flickr_authtoken,method='flickr.photos.getContactsPhotos',photoset_id=photoset.obj.get('id'))
        d = self.flickr_call('flickr.photos.getContactsPhotos',
                                    photoset_id=photoset.obj.get('id'),
                                    auth_token=self.flickr_authtoken,
                                    api_sig=api_sig)
        return d

    def flickr_create_api_signature(self,**fields):
        api_sig = self.flickr_api_secret + 'api_key' + self.flickr_api_key
        for key in sorted(fields.keys()):
            api_sig += key + str(fields[key])
        return md5(api_sig)

    def flickr_authenticate_app(self):

        def got_error(error):
            print error

        def got_auth_token(result):
            print "got_auth_token", result
            result = result.getroot()
            token = result.find('token').text
            print 'token', token
            self.flickr_authtoken = token
            self.server.coherence.store_plugin_config(self.server.uuid, {'authtoken':token})

        def get_auth_token(result,frob):
            d =self.flickr_auth_getToken(frob)
            d.addCallback(got_auth_token)
            d.addErrback(got_error)
            return d

        def got_frob(result):
            print "flickr", result
            result = result.getroot()
            frob = result.text
            print frob
            from twisted.internet import threads
            d = threads.deferToThread(FlickrAuthenticate,self.flickr_api_key,self.flickr_api_secret,frob,self.flickr_userid,self.flickr_password,self.flickr_permissions)
            d.addCallback(get_auth_token, frob)
            d.addErrback(got_error)

        d = self.flickr_auth_getFrob()
        d.addCallback(got_frob)
        d.addErrback(got_error)
        return d

    def soap_flickr_test_echo(self, value):
        client = SOAPProxy("http://api.flickr.com/services/soap/",
                            namespace=("x","urn:flickr"),
                            envelope_attrib=[("xmlns:s", "http://www.w3.org/2003/05/soap-envelope"),
                                            ("xmlns:xsi", "http://www.w3.org/1999/XMLSchema-instance"),
                                            ("xmlns:xsd", "http://www.w3.org/1999/XMLSchema")],
                            soapaction="FlickrRequest")
        d = client.callRemote( "FlickrRequest",
                                method='flickr.test.echo',
                                name=value,
                                api_key='837718c8a622c699edab0ea55fcec224')
        def got_results(result):
            print result

        d.addCallback(got_results)
        return d

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
        self.store[ROOT_CONTAINER_ID] = FlickrItem( ROOT_CONTAINER_ID, 'Flickr', None,
                                                    'directory', self.urlbase,
                                                    Container,store=self,update=True, proxy=self.proxy)

        self.store[INTERESTINGNESS_CONTAINER_ID] = FlickrItem(INTERESTINGNESS_CONTAINER_ID, 'Most Wanted',
                                                              self.store[ROOT_CONTAINER_ID],
                                                    'directory', self.urlbase,
                                                    PhotoAlbum,store=self,update=True, proxy=self.proxy)

        self.store[RECENT_CONTAINER_ID] = FlickrItem(RECENT_CONTAINER_ID, 'Recent',
                                                        self.store[ROOT_CONTAINER_ID],
                                                        'directory', self.urlbase,
                                                        PhotoAlbum,store=self,update=True, proxy=self.proxy)

        self.most_wanted = self.store[INTERESTINGNESS_CONTAINER_ID]
        d = self.flickr_interestingness(per_page=self.limit)
        d.addCallback(self.append_flickr_result, self.most_wanted)

        self.recent = self.store[RECENT_CONTAINER_ID]
        d = self.flickr_recent(per_page=self.limit)
        d.addCallback(self.append_flickr_photo_result, self.recent)

        if self.flickr_authtoken != None:
            self.store[GALLERY_CONTAINER_ID] = FlickrItem(GALLERY_CONTAINER_ID, 'Gallery',
                                                        self.store[ROOT_CONTAINER_ID],
                                                        'directory', self.urlbase,
                                                        PhotoAlbum,store=self,update=True, proxy=self.proxy)
            self.photosets = self.store[GALLERY_CONTAINER_ID]
            d = self.flickr_photosets()
            d.addCallback(self.append_flickr_photoset_result, self.photosets)

            self.store[UNSORTED_CONTAINER_ID] = FlickrItem(UNSORTED_CONTAINER_ID, 'Unsorted - Not in set',
                                                        self.store[GALLERY_CONTAINER_ID],
                                                        'directory', self.urlbase,
                                                        PhotoAlbum,store=self,update=True, proxy=self.proxy)
            self.notinset = self.store[UNSORTED_CONTAINER_ID]
            d = self.flickr_notInSet(per_page=self.limit)
            d.addCallback(self.append_flickr_photo_result, self.notinset)

            self.store[FAVORITES_CONTAINER_ID] = FlickrItem(FAVORITES_CONTAINER_ID, 'Favorites',
                                                        self.store[ROOT_CONTAINER_ID],
                                                        'directory', self.urlbase,
                                                        PhotoAlbum,store=self,update=True, proxy=self.proxy)
            self.favorites = self.store[FAVORITES_CONTAINER_ID]
            d = self.flickr_favorites(per_page=self.limit)
            d.addCallback(self.append_flickr_photo_result, self.favorites)

            self.store[CONTACTS_CONTAINER_ID] = FlickrItem(CONTACTS_CONTAINER_ID, 'Friends & Family',
                                                        self.store[ROOT_CONTAINER_ID],
                                                        'directory', self.urlbase,
                                                        PhotoAlbum,store=self,update=True, proxy=self.proxy)
            self.contacts = self.store[CONTACTS_CONTAINER_ID]
            d = self.flickr_contacts()
            d.addCallback(self.append_flickr_contact_result, self.contacts)

    def upnp_ImportResource(self, *args, **kwargs):
        print 'upnp_ImportResource', args, kwargs
        SourceURI = kwargs['SourceURI']
        DestinationURI = kwargs['DestinationURI']

        if DestinationURI.endswith('?import'):
            id = DestinationURI.split('/')[-1]
            id = id[:-7] # remove the ?import
        else:
            return failure.Failure(errorCode(718))

        item = self.get_by_id(id)
        if item == None:
            return failure.Failure(errorCode(718))

        def gotPage(result):

            try:
                import cStringIO as StringIO
            except ImportError:
                import StringIO

            self.backend_import(item,StringIO.StringIO(result[0]))

        def gotError(error, url):
            self.warning("error requesting", url)
            self.info(error)
            return failure.Failure(errorCode(718))

        d = getPage(SourceURI)
        d.addCallbacks(gotPage, gotError, None, None, [SourceURI], None)

        transfer_id = 0  #FIXME

        return {'TransferID': transfer_id}

    def upnp_CreateObject(self, *args, **kwargs):
        print "upnp_CreateObject", args, kwargs
        ContainerID = kwargs['ContainerID']
        Elements = kwargs['Elements']

        parent_item = self.get_by_id(ContainerID)
        if parent_item == None:
            return failure.Failure(errorCode(710))
        if parent_item.item.restricted:
            return failure.Failure(errorCode(713))

        if len(Elements) == 0:
            return failure.Failure(errorCode(712))

        elt = DIDLElement.fromString(Elements)
        if elt.numItems() != 1:
            return failure.Failure(errorCode(712))

        item = elt.getItems()[0]
        if(item.id != '' or
           item.parentID != ContainerID or
           item.restricted == True or
           item.title == ''):
            return failure.Failure(errorCode(712))

        if item.upnp_class.startswith('object.container'):
            if len(item.res) != 0:
                return failure.Failure(errorCode(712))

            return failure.Failure(errorCode(712))
            ### FIXME

            new_item = self.get_by_id(new_id)
            didl = DIDLElement()
            didl.addItem(new_item.item)
            return {'ObjectID': id, 'Result': didl.toString()}

        if item.upnp_class.startswith('object.item.imageItem'):
            new_id = self.getnextID()
            new_id = 'upload.'+str(new_id)
            title = item.title or 'unknown'
            mimetype = 'image/jpeg'
            self.uploads[new_id] = FlickrItem( new_id, title, self.store[UNSORTED_CONTAINER_ID], mimetype, self.urlbase,
                                        ImageItem,store=self,update=False, proxy=self.proxy)

            new_item = self.uploads[new_id]
            for res in new_item.item.res:
                res.importUri = new_item.url+'?import'
                res.data = None
            didl = DIDLElement()
            didl.addItem(new_item.item)
            r = {'ObjectID': new_id, 'Result': didl.toString()}
            print r
            return r

        return failure.Failure(errorCode(712))


    # encode_multipart_form code is inspired by http://www.voidspace.org.uk/python/cgi.shtml#upload
    def encode_multipart_form(self,fields):
        boundary = mimetools.choose_boundary()
        body = []
        for k, v in fields.items():
            body.append("--" + boundary.encode("utf-8"))
            header = 'Content-Disposition: form-data; name="%s";' % k
            if isinstance(v, FilePath):
                header += 'filename="%s";' % v.basename()
                body.append(header)
                header = "Content-Type: application/octet-stream"
                body.append(header)
                body.append("")
                body.append(v.getContent())
            elif hasattr(v,'read'):
                header += 'filename="%s";' % 'unknown'
                body.append(header)
                header = "Content-Type: application/octet-stream"
                body.append(header)
                body.append("")
                body.append(v.read())
            else:
                body.append(header)
                body.append("")
                body.append(str(v).encode('utf-8'))
        body.append("--" + boundary.encode("utf-8"))
        content_type = 'multipart/form-data; boundary=%s' % boundary
        return (content_type, '\r\n'.join(body))

    def flickr_upload(self,image,**kwargs):
        fields = {}
        for k,v in kwargs.items():
            if v != None:
                fields[k] = v

        #fields['api_key'] = self.flickr_api_key
        fields['auth_token'] = self.flickr_authtoken

        fields['api_sig'] = self.flickr_create_api_signature(**fields)
        fields['api_key'] = self.flickr_api_key
        fields['photo'] = image

        (content_type, formdata) = self.encode_multipart_form(fields)
        headers= {"Content-Type": content_type,
                  "Content-Length": str(len(formdata))}

        d= getPage("http://api.flickr.com/services/upload/",
                              method="POST",
                              headers=headers,
                              postdata=formdata)

        def got_something(result):
            print "got_something", result
            result = parse_xml(result[0], encoding='utf-8')
            result = result.getroot()
            if(result.attrib['stat'] == 'ok' and
               result.find('photoid') != None):
                photoid = result.find('photoid').text
                return photoid
            else:
                error = result.find('err')
                return failure.Failure(Exception(error.attrib['msg']))

        d.addBoth(got_something)
        return d


    def backend_import(self,item,data):
        """ we expect a FlickrItem
            and the actual image data as a FilePath
            or something with a read() method.
            like the content attribute of a Request
        """
        d = self.flickr_upload(data,title=item.get_name())

        def got_photoid(id,item):
            d = self.flickr_photos_getInfo(photo_id=id)

            def add_it(obj,parent):
                print "add_it", obj, obj.getroot(), parent
                root = obj.getroot()
                self.appendPhoto(obj.getroot(),parent)
                return 200

            d.addCallback(add_it,item.parent)
            d.addErrback(got_fail)
            return d

        def got_fail(err):
            print err
            return err

        d.addCallback(got_photoid, item)
        d.addErrback(got_fail)
        #FIXME we should return the deferred here
        return d

def main():

    log.init(None, 'debug')

    f = FlickrStore(None,userid='x',password='xx',
                    permissions='xxx',
                    authtoken='xxx-x')

    def got_flickr_result(result):
        print "flickr", result
        for photo in result.getiterator('photo'):
            title = photo.get('title').encode('utf-8')
            if len(title) == 0:
                title = u'untitled'

            for k,item in photo.items():
                print k, item

            url = "http://farm%s.static.flickr.com/%s/%s_%s.jpg" % (
                        photo.get('farm').encode('utf-8'),
                        photo.get('server').encode('utf-8'),
                        photo.get('id').encode('utf-8'),
                        photo.get('secret').encode('utf-8'))
            #orginal_url = "http://farm%s.static.flickr.com/%s/%s_%s_o.jpg" % (
            #            photo.get('farm').encode('utf-8'),
            #            photo.get('server').encode('utf-8'),
            #            photo.get('id').encode('utf-8'),
            #            photo.get('originalsecret').encode('utf-8'))
            print photo.get('id').encode('utf-8'), title, url

    def got_upnp_result(result):
        print "upnp", result

    def got_error(error):
        print error

    #f.flickr_upload(FilePath('/tmp/image.jpg'),title='test')

    #d = f.flickr_test_echo()
    #d = f.flickr_interestingness()
    #d.addCallback(got_flickr_result)


    #f.upnp_init()
    #print f.store
    #r = f.upnp_Browse(BrowseFlag='BrowseDirectChildren',
    #                    RequestedCount=0,
    #                    StartingIndex=0,
    #                    ObjectID=0,
    #                    SortCriteria='*',
    #                    Filter='')
    #got_upnp_result(r)


if __name__ == '__main__':

    from twisted.internet import reactor

    reactor.callWhenRunning(main)
    reactor.run()
