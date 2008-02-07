# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006, Frank Scholz <coherence@beebits.net>

import os
import tempfile
import shutil
import time
import re
from datetime import datetime

import mimetypes
mimetypes.init()
mimetypes.add_type('video/mp4', '.mp4')

from urlparse import urlsplit

from twisted.python.filepath import FilePath
from twisted.python import failure

from coherence.upnp.core.DIDLLite import classChooser, Container, Resource
from coherence.upnp.core.DIDLLite import DIDLElement
from coherence.upnp.core.DIDLLite import simple_dlna_tags
from coherence.upnp.core.soap_service import errorCode

from coherence.upnp.core import utils

from coherence.extern.inotify import INotify
from coherence.extern.inotify import IN_CREATE, IN_DELETE, IN_MOVED_FROM, IN_MOVED_TO, IN_ISDIR
from coherence.extern.inotify import IN_CHANGED

import louie

from coherence.backend import BackendItem, BackendStore

class FSItem(BackendItem):
    logCategory = 'fs_item'

    def __init__(self, object_id, parent, path, mimetype, urlbase, UPnPClass,update=False):
        self.id = object_id
        self.parent = parent
        if parent:
            parent.add_child(self,update=update)
        if mimetype == 'root':
            self.location = unicode(path)
        else:
            if mimetype == 'item' and path is None:
                path = os.path.join(parent.get_path(),str(self.id))
            self.location = FilePath(unicode(path))
        self.mimetype = mimetype
        if urlbase[-1] != '/':
            urlbase += '/'
        self.url = urlbase + str(self.id)


        if parent == None:
            parent_id = -1
        else:
            parent_id = parent.get_id()

        self.item = UPnPClass(object_id, parent_id, self.get_name())
        if isinstance(self.item, Container):
            self.item.childCount = 0
        self.child_count = 0
        self.children = []


        if mimetype in ['directory','root']:
            self.update_id = 0
            #self.item.searchable = True
            #self.item.searchClass = 'object'
            if(isinstance(self.location,FilePath) and
               self.location.isdir() == True):
                self.check_for_cover_art()
                if hasattr(self, 'cover'):
                    _,ext =  os.path.splitext(self.cover)
                    """ add the cover image extension to help clients not reacting on
                        the mimetype """
                    self.item.albumArtURI = ''.join((urlbase,str(self.id),'?cover',ext))
        else:
            if self.mimetype.startswith('audio/'):
                if hasattr(parent, 'cover'):
                    _,ext =  os.path.splitext(parent.cover)
                    """ add the cover image extension to help clients not reacting on
                        the mimetype """
                    self.item.albumArtURI = ''.join((urlbase,str(self.id),'?cover',ext))

            _,host_port,_,_,_ = urlsplit(urlbase)
            if host_port.find(':') != -1:
                host,port = tuple(host_port.split(':'))
            else:
                host = host_port

            try:
                size = self.location.getsize()
            except:
                size = 0

            if mimetype != 'item':
                res = Resource('file://'+self.get_path(), 'internal:%s:%s:*' % (host,self.mimetype))
                res.size = size
                self.item.res.append(res)

            if mimetype != 'item':
                res = Resource(self.url, 'http-get:*:%s:*' % self.mimetype)
            else:
                res = Resource(self.url, 'http-get:*:*:*')

            res.size = size
            self.item.res.append(res)


            """ if this item is an image and we want to add a thumbnail for it
                we have to follow these rules:

                create a new Resource object, at least a 'http-get'
                and maybe an 'internal' one too

                for an JPG this looks like that

                res = Resource(url_for_thumbnail,
                        'http-get:*:image/jpg:%s'% ';'.join(simple_dlna_tags+('DLNA.ORG_PN=JPEG_TN',)))
                res.size = size_of_thumbnail
                self.item.res.append(res)

                and for a PNG the Resource creation is like that

                res = Resource(url_for_thumbnail,
                        'http-get:*:image/png:%s'% ';'.join(simple_dlna_tags+('DLNA.ORG_PN=PNG_TN',)))

                if not hasattr(self.item, 'attachments'):
                    self.item.attachments = {}
                self.item.attachments[key] = utils.StaticFile(filename_of_thumbnail)
            """

            if self.mimetype in ('image/jpeg', 'image/png'):
                path = self.get_path()
                thumbnail = os.path.join(os.path.dirname(path),'.thumbs',os.path.basename(path))
                if os.path.exists(thumbnail):
                    mimetype,_ = mimetypes.guess_type(thumbnail, strict=False)
                    if mimetype in ('image/jpeg','image/png'):
                        if mimetype == 'image/jpeg':
                            dlna_pn = 'DLNA.ORG_PN=JPEG_TN'
                        else:
                            dlna_pn = 'DLNA.ORG_PN=PNG_TN'

                        hash_from_path = str(id(thumbnail))
                        new_res = Resource(self.url+'?attachment='+hash_from_path,
                            'http-get:*:%s:%s' % (mimetype, ';'.join(simple_dlna_tags+(dlna_pn,))))
                        new_res.size = os.path.getsize(thumbnail)
                        self.item.res.append(new_res)
                        if not hasattr(self.item, 'attachments'):
                            self.item.attachments = {}
                        self.item.attachments[hash_from_path] = utils.StaticFile(thumbnail)


            try:
                # FIXME: getmtime is deprecated in Twisted 2.6
                self.item.date = datetime.fromtimestamp(self.location.getmtime())
            except:
                self.item.date = None

    def rebuild(self, urlbase):
        #print "rebuild", self.mimetype
        if self.mimetype != 'item':
            return
        #print "rebuild for", self.get_path()
        mimetype,_ = mimetypes.guess_type(self.get_path(),strict=False)
        if mimetype == None:
            return
        self.mimetype = mimetype
        #print "rebuild", self.mimetype
        UPnPClass = classChooser(self.mimetype)
        self.item = UPnPClass(self.id, self.parent.id, self.get_name())
        if hasattr(self.parent, 'cover'):
            _,ext =  os.path.splitext(self.parent.cover)
            """ add the cover image extension to help clients not reacting on
                the mimetype """
            self.item.albumArtURI = ''.join((urlbase,str(self.id),'?cover',ext))

        _,host_port,_,_,_ = urlsplit(urlbase)
        if host_port.find(':') != -1:
            host,port = tuple(host_port.split(':'))
        else:
            host = host_port

        res = Resource('file://'+self.get_path(), 'internal:%s:%s:*' % (host,self.mimetype))
        try:
            res.size = self.location.getsize()
        except:
            res.size = 0
        self.item.res.append(res)
        res = Resource(self.url, 'http-get:*:%s:*' % self.mimetype)

        try:
            res.size = self.location.getsize()
        except:
            res.size = 0
        self.item.res.append(res)

        try:
            # FIXME: getmtime is deprecated in Twisted 2.6
            self.item.date = datetime.fromtimestamp(self.location.getmtime())
        except:
            self.item.date = None

        self.parent.update_id += 1

    def __del__(self):
        #print "FSItem __del__", self.id, self.get_name()
        pass

    def check_for_cover_art(self):
        """ let's try to find in the current directory some jpg file,
            or png if the jpg search fails, and take the first one
            that comes around
        """
        try:
            jpgs = [i.path for i in self.location.children() if i.splitext()[1] in ('.jpg', '.JPG')]
            try:
                self.cover = jpgs[0]
            except IndexError:
                pngs = [i.path for i in self.location.children() if i.splitext()[1] in ('.png', '.PNG')]
                try:
                    self.cover = pngs[0]
                except IndexError:
                    return
        except UnicodeDecodeError:
            self.warning("UnicodeDecodeError - there is something wrong with a file located in %r", self.location.path)

    def remove(self):
        #print "FSItem remove", self.id, self.get_name(), self.parent
        if self.parent:
            self.parent.remove_child(self)
        del self.item

    def add_child(self, child, update=False):
        self.children.append(child)
        self.child_count += 1
        if isinstance(self.item, Container):
            self.item.childCount += 1
        if update == True:
            self.update_id += 1

    def remove_child(self, child):
        #print "remove_from %d (%s) child %d (%s)" % (self.id, self.get_name(), child.id, child.get_name())
        if child in self.children:
            self.child_count -= 1
            if isinstance(self.item, Container):
                self.item.childCount -= 1
            self.children.remove(child)
            self.update_id += 1

    def get_children(self,start=0,request_count=0):
        if request_count == 0:
            return self.children[start:]
        else:
            return self.children[start:request_count]

    def get_child_count(self):
        return self.child_count

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
        if isinstance( self.location,FilePath):
            return self.location.path
        else:
            self.location

    def set_path(self,path=None,extension=None):
        if path is None:
            path = self.get_path()
        if extension is not None:
            path,old_ext = os.path.splitext(path)
            path = ''.join((path,extension))
        if isinstance( self.location,FilePath):
            self.location = FilePath(unicode(path))
        else:
            self.location = path

    def get_name(self):
        if isinstance( self.location,FilePath):
            name = self.location.basename()
        else:
            name = self.location
        return name

    def get_cover(self):
        try:
            return self.cover
        except:
            try:
                return self.parent.cover
            except:
                return ''

    def get_parent(self):
        return self.parent

    def get_item(self):
        return self.item

    def get_xml(self):
        return self.item.toString()

    def __repr__(self):
        return 'id: ' + str(self.id) + ' @ ' + self.location.basename()

class FSStore(BackendStore):
    logCategory = 'fs_store'

    implements = ['MediaServer']

    def __init__(self, server, **kwargs):
        BackendStore.__init__(self)
        self.next_id = 1000
        self.name = kwargs.get('name','my media')
        self.content = kwargs.get('content','tests/content')
        if not isinstance( self.content, list):
            self.content = [self.content]
        self.urlbase = kwargs.get('urlbase','')
        ignore_patterns = kwargs.get('ignore_patterns',[])

        if self.urlbase[len(self.urlbase)-1] != '/':
            self.urlbase += '/'
        self.server = server
        self.store = {}

        try:
            self.inotify = INotify()
        except:
            self.inotify = None

        l = []
        for a in self.content:
            l += a.split(',')
        self.content = l

        self.ignore_file_pattern = re.compile('|'.join(['^\..*'] + list(ignore_patterns)))
        parent = None
        self.update_id = 0
        if len(self.content)>1:
            UPnPClass = classChooser('root')
            id = self.getnextID()
            parent = self.store[id] = FSItem( id, parent, 'media', 'root', self.urlbase, UPnPClass, update=True)

        for path in self.content:
            if self.ignore_file_pattern.match(path):
                continue
            self.walk(path, parent, self.ignore_file_pattern)

        #self.update_id = 0
        louie.send('Coherence.UPnP.Backend.init_completed', None, backend=self)

    def __repr__(self):
        return str(self.__class__).split('.')[-1]

    def len(self):
        return len(self.store)

    def get_by_id(self,id):
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

    def get_id_by_name(self, parent, name):
        try:
            parent = self.store[int(parent)]
            for child in parent.children:
                if name == child.get_name():
                    return child.id
        except:
            pass

        return None

    def walk(self, path, parent=None, ignore_file_pattern=''):
        containers = []
        parent = self.append(path,parent)
        if parent != None:
            containers.append(parent)
        while len(containers)>0:
            container = containers.pop()
            try:
                for child in container.location.children():
                    if ignore_file_pattern.match(child.basename()) != None:
                        continue
                    new_container = self.append(child.path,container)
                    if new_container != None:
                        containers.append(new_container)
            except UnicodeDecodeError:
                self.warning("UnicodeDecodeError - there is something wrong with a file located in %r", container.get_path())

    def create(self, mimetype, path, parent):
        UPnPClass = classChooser(mimetype)
        if UPnPClass == None:
            return None

        id = self.getnextID()
        update = False
        if hasattr(self, 'update_id'):
            update = True

        self.store[id] = FSItem( id, parent, path, mimetype, self.urlbase, UPnPClass, update=True)
        if hasattr(self, 'update_id'):
            self.update_id += 1
            if self.server:
                if hasattr(self.server,'content_directory_server'):
                    self.server.content_directory_server.set_variable(0, 'SystemUpdateID', self.update_id)
            if parent is not None:
                value = (parent.get_id(),parent.get_update_id())
                if self.server:
                    if hasattr(self.server,'content_directory_server'):
                        self.server.content_directory_server.set_variable(0, 'ContainerUpdateIDs', value)

        return id

    def append(self,path,parent):
        #print "append", path
        mimetype,_ = mimetypes.guess_type(path, strict=False)
        if mimetype == None:
            if os.path.isdir(path) or os.path.islink(path):
                mimetype = 'directory'
        if mimetype == None:
            return None

        id = self.create(mimetype,path,parent)

        if mimetype == 'directory':
            if self.inotify is not None:
                mask = IN_CREATE | IN_DELETE | IN_MOVED_FROM | IN_MOVED_TO | IN_CHANGED
                self.inotify.watch(path, mask=mask, auto_add=False, callbacks=(self.notify,id))
            return self.store[id]

        return None

    def remove(self, id):
        #print 'FSSTore remove id', id
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


    def notify(self, iwp, filename, mask, parameter=None):
        #print "Event %s on %s %s - id %d" % (
        #    ', '.join(self.inotify.flag_to_human(mask)), iwp.path, filename, parameter)

        path = iwp.path
        if filename:
            path = os.path.join(path, filename)

        if mask & IN_CHANGED:
            # FIXME react maybe on access right changes, loss of read rights?
            #print '%s was changed, parent %d (%s)' % (path, parameter, iwp.path)
            pass

        if(mask & IN_DELETE or mask & IN_MOVED_FROM):
            #print '%s was deleted, parent %d (%s)' % (path, parameter, iwp.path)
            id = self.get_id_by_name(parameter,filename)
            self.remove(id)
        if(mask & IN_CREATE or mask & IN_MOVED_TO):
            #if mask & IN_ISDIR:
            #    print 'directory %s was created, parent %d (%s)' % (path, parameter, iwp.path)
            #else:
            #    print 'file %s was created, parent %d (%s)' % (path, parameter, iwp.path)
            if self.get_id_by_name(parameter,filename) is None:
                if mask & IN_ISDIR:
                    self.walk(path, self.get_by_id(parameter), self.ignore_file_pattern)
                else:
                    self.append(path, self.get_by_id(parameter))

    def getnextID(self):
        ret = self.next_id
        self.next_id += 1
        return ret

    def upnp_init(self):
        self.current_connection_id = None
        if self.server:
            self.server.connection_manager_server.set_variable(0, 'SourceProtocolInfo',
                        ['internal:%s:audio/mpeg:*' % self.server.coherence.hostname,
                         'http-get:*:audio/mpeg:*',
                         'internal:%s:video/mp4:*' % self.server.coherence.hostname,
                         'http-get:*:video/mp4:*',
                         'internal:%s:application/ogg:*' % self.server.coherence.hostname,
                         'http-get:*:application/ogg:*',
                         'internal:%s:video/x-msvideo:*' % self.server.coherence.hostname,
                         'http-get:*:video/x-msvideo:*',
                         'internal:%s:video/avi:*' % self.server.coherence.hostname,
                         'http-get:*:video/avi:*',
                         'internal:%s:video/quicktime:*' % self.server.coherence.hostname,
                         'http-get:*:video/quicktime:*'],
                        default=True)
            self.server.content_directory_server.set_variable(0, 'SystemUpdateID', self.update_id)


    def upnp_ImportResource(self, *args, **kwargs):
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

        def gotPage(headers):
            #print "gotPage", headers
            content_type = headers.get('content-type',[])
            if not isinstance(content_type, list):
                content_type = list(content_type)
            if len(content_type) > 0:
                extension = mimetypes.guess_extension(content_type[0], strict=False)
                item.set_path(None,extension)
            shutil.move(tmp_path, item.get_path())
            item.rebuild(self.urlbase)
            if hasattr(self, 'update_id'):
                self.update_id += 1
                if self.server:
                    if hasattr(self.server,'content_directory_server'):
                        self.server.content_directory_server.set_variable(0, 'SystemUpdateID', self.update_id)
                if item.parent is not None:
                    value = (item.parent.get_id(),item.parent.get_update_id())
                    if self.server:
                        if hasattr(self.server,'content_directory_server'):
                            self.server.content_directory_server.set_variable(0, 'ContainerUpdateIDs', value)

        def gotError(error, url):
            self.warning("error requesting", url)
            self.info(error)
            os.unlink(tmp_path)
            return failure.Failure(errorCode(718))

        tmp_fp, tmp_path = tempfile.mkstemp()
        os.close(tmp_fp)

        utils.downloadPage(SourceURI,
                           tmp_path).addCallbacks(gotPage, gotError, None, None, [SourceURI], None)

        transfer_id = 0  #FIXME

        return {'TransferID': transfer_id}

    def upnp_CreateObject(self, *args, **kwargs):
        if kwargs['ContainerID'] == 'DLNA.ORG_AnyContainer':
            """ for the moment """
            return failure.Failure(errorCode(712))
        else:
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
           int(item.parentID) != ContainerID or
           item.restricted == True or
           item.title == ''):
            return failure.Failure(errorCode(712))

        if('..' in item.title or
           '~' in item.title or
           os.sep in item.title):
            return failure.Failure(errorCode(712))

        if item.upnp_class == 'object.container.storageFolder':
            if len(item.res) != 0:
                return failure.Failure(errorCode(712))
            path = os.path.join(parent_item.get_path(),item.title)
            id = self.create('directory',path,parent_item)
            try:
                os.mkdir(path)
            except:
                self.remove(id)
                return failure.Failure(errorCode(712))

            if self.inotify is not None:
                mask = IN_CREATE | IN_DELETE | IN_MOVED_FROM | IN_MOVED_TO | IN_CHANGED
                self.inotify.watch(path, mask=mask, auto_add=False, callbacks=(self.notify,id))

            new_item = self.get_by_id(id)
            didl = DIDLElement()
            didl.addItem(new_item.item)
            return {'ObjectID': id, 'Result': didl.toString()}

        if item.upnp_class.startswith('object.item.'):
            #path = os.path.join(parent_item.get_path(),item.title)
            id = self.create('item',None,parent_item)

            new_item = self.get_by_id(id)
            for res in new_item.item.res:
                res.importUri = new_item.url+'?import'
                res.data = None
            didl = DIDLElement()
            didl.addItem(new_item.item)
            return {'ObjectID': id, 'Result': didl.toString()}

        return failure.Failure(errorCode(712))

if __name__ == '__main__':

    from twisted.internet import reactor

    p = 'tests/content'
    f = FSStore(None,name='my media',content=p, urlbase='http://localhost/xyz')

    print f.len()
    print f.get_by_id(1000).child_count, f.get_by_id(1000).get_xml()
    print f.get_by_id(1001).child_count, f.get_by_id(1001).get_xml()
    print f.get_by_id(1002).child_count, f.get_by_id(1002).get_xml()
    print f.get_by_id(1003).child_count, f.get_by_id(1003).get_xml()
    print f.get_by_id(1004).child_count, f.get_by_id(1004).get_xml()
    print f.get_by_id(1005).child_count, f.get_by_id(1005).get_xml()
    print f.store[1000].get_children(0,0)
    #print f.upnp_Search(ContainerID ='4',
    #                    Filter ='dc:title,upnp:artist',
    #                    RequestedCount = '1000',
    #                    StartingIndex = '0',
    #                    SearchCriteria = '(upnp:class = "object.container.album.musicAlbum")',
    #                    SortCriteria = '+dc:title')

    f.upnp_ImportResource(SourceURI='http://spiegel.de',DestinationURI='ttt')

    reactor.run()
