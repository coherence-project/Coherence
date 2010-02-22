# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006, Frank Scholz <coherence@beebits.net>

import os, stat, glob
import tempfile
import shutil
import time
import re
from datetime import datetime
import urllib

from sets import Set

import mimetypes
mimetypes.init()
mimetypes.add_type('audio/x-m4a', '.m4a')
mimetypes.add_type('audio/x-musepack', '.mpc')
mimetypes.add_type('audio/x-wavpack', '.wv')
mimetypes.add_type('video/mp4', '.mp4')
mimetypes.add_type('video/mpegts', '.ts')
mimetypes.add_type('video/divx', '.divx')
mimetypes.add_type('video/divx', '.avi')
mimetypes.add_type('video/x-matroska', '.mkv')

from urlparse import urlsplit

from twisted.python.filepath import FilePath
from twisted.python import failure

from coherence.upnp.core.DIDLLite import classChooser, Container, Resource
from coherence.upnp.core.DIDLLite import DIDLElement
from coherence.upnp.core.DIDLLite import simple_dlna_tags
from coherence.upnp.core.soap_service import errorCode

from coherence.upnp.core import utils

try:
    from coherence.extern.inotify import INotify
    from coherence.extern.inotify import IN_CREATE, IN_DELETE, IN_MOVED_FROM, IN_MOVED_TO, IN_ISDIR
    from coherence.extern.inotify import IN_CHANGED
    haz_inotify = True
except Exception,msg:
    haz_inotify = False
    no_inotify_reason = msg

from coherence.extern.xdg import xdg_content

import coherence.extern.louie as louie

from coherence.backend import BackendItem, BackendStore

## Sorting helpers
NUMS = re.compile('([0-9]+)')
def _natural_key(s):
    # strip the spaces
    s = s.get_name().strip()
    return [ part.isdigit() and int(part) or part.lower() for part in NUMS.split(s) ]


class NoThumbnailFound(Exception):
    """no thumbnail found"""

def _find_thumbnail(filename,thumbnail_folder='.thumbs'):
    """ looks for a thumbnail file of the same basename
        in a folder named '.thumbs' relative to the file

        returns the filename of the thumb, its mimetype and the correspondig DLNA PN string
        or throws an Exception otherwise
    """
    name,ext = os.path.splitext(os.path.basename(filename))
    pattern = os.path.join(os.path.dirname(filename),thumbnail_folder,name+'.*')
    for f in glob.glob(pattern):
        mimetype,_ = mimetypes.guess_type(f, strict=False)
        if mimetype in ('image/jpeg','image/png'):
            if mimetype == 'image/jpeg':
                dlna_pn = 'DLNA.ORG_PN=JPEG_TN'
            else:
                dlna_pn = 'DLNA.ORG_PN=PNG_TN'
            return os.path.abspath(f),mimetype,dlna_pn
    else:
        raise NoThumbnailFound()

class FSItem(BackendItem):
    logCategory = 'fs_item'

    def __init__(self, object_id, parent, path, mimetype, urlbase, UPnPClass,update=False,store=None):
        self.id = object_id
        self.parent = parent
        if parent:
            parent.add_child(self,update=update)
        if mimetype == 'root':
            self.location = unicode(path)
        else:
            if mimetype == 'item' and path is None:
                path = os.path.join(parent.get_realpath(),unicode(self.id))
            #self.location = FilePath(unicode(path))
            self.location = FilePath(path)
        self.mimetype = mimetype
        if urlbase[-1] != '/':
            urlbase += '/'
        self.url = urlbase + str(self.id)

        self.store = store

        if parent == None:
            parent_id = -1
        else:
            parent_id = parent.get_id()

        self.item = UPnPClass(object_id, parent_id, self.get_name())
        if isinstance(self.item, Container):
            self.item.childCount = 0
        self.child_count = 0
        self.children = []
        self.sorted = False
        self.caption = None


        if mimetype in ['directory','root']:
            self.update_id = 0
            self.get_url = lambda : self.url
            self.get_path = lambda : None
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
            self.get_url = lambda : self.url

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

            if self.store.server.coherence.config.get('transcoding', 'no') == 'yes':
                if self.mimetype in ('application/ogg','audio/ogg',
                                     'audio/x-wav',
                                     'audio/x-m4a',
                                     'application/x-flac'):
                    new_res = Resource(self.url+'/transcoded.mp3',
                        'http-get:*:%s:*' % 'audio/mpeg')
                    new_res.size = None
                    #self.item.res.append(new_res)

            if mimetype != 'item':
                res = Resource('file://'+ urllib.quote(self.get_path()), 'internal:%s:%s:*' % (host,self.mimetype))
                res.size = size
                self.item.res.append(res)

            if mimetype != 'item':
                res = Resource(self.url, 'http-get:*:%s:*' % self.mimetype)
            else:
                res = Resource(self.url, 'http-get:*:*:*')

            res.size = size
            self.item.res.append(res)

            """ if this item is of type audio and we want to add a transcoding rule for it,
                this is the way to do it:

                create a new Resource object, at least a 'http-get'
                and maybe an 'internal' one too

                for transcoding to wav this looks like that

                res = Resource(url_for_transcoded audio,
                        'http-get:*:audio/x-wav:%s'% ';'.join(['DLNA.ORG_PN=JPEG_TN']+simple_dlna_tags))
                res.size = None
                self.item.res.append(res)
            """

            if self.store.server.coherence.config.get('transcoding', 'no') == 'yes':
                if self.mimetype in ('audio/mpeg',
                                     'application/ogg','audio/ogg',
                                     'audio/x-wav',
                                     'audio/x-m4a',
                                     'audio/flac',
                                     'application/x-flac'):
                    dlna_pn = 'DLNA.ORG_PN=LPCM'
                    dlna_tags = simple_dlna_tags[:]
                    #dlna_tags[1] = 'DLNA.ORG_OP=00'
                    dlna_tags[2] = 'DLNA.ORG_CI=1'
                    new_res = Resource(self.url+'?transcoded=lpcm',
                        'http-get:*:%s:%s' % ('audio/L16;rate=44100;channels=2', ';'.join([dlna_pn]+dlna_tags)))
                    new_res.size = None
                    #self.item.res.append(new_res)

                    if self.mimetype  != 'audio/mpeg':
                        new_res = Resource(self.url+'?transcoded=mp3',
                            'http-get:*:%s:*' % 'audio/mpeg')
                        new_res.size = None
                        #self.item.res.append(new_res)

            """ if this item is an image and we want to add a thumbnail for it
                we have to follow these rules:

                create a new Resource object, at least a 'http-get'
                and maybe an 'internal' one too

                for an JPG this looks like that

                res = Resource(url_for_thumbnail,
                        'http-get:*:image/jpg:%s'% ';'.join(['DLNA.ORG_PN=JPEG_TN']+simple_dlna_tags))
                res.size = size_of_thumbnail
                self.item.res.append(res)

                and for a PNG the Resource creation is like that

                res = Resource(url_for_thumbnail,
                        'http-get:*:image/png:%s'% ';'.join(simple_dlna_tags+['DLNA.ORG_PN=PNG_TN']))

                if not hasattr(self.item, 'attachments'):
                    self.item.attachments = {}
                self.item.attachments[key] = utils.StaticFile(filename_of_thumbnail)
            """

            if(self.mimetype in ('image/jpeg', 'image/png') or
               self.mimetype.startswith('video/')):
                try:
                    filename,mimetype,dlna_pn = _find_thumbnail(self.get_path())
                except NoThumbnailFound:
                    pass
                except:
                    self.warning(traceback.format_exc())
                else:
                    dlna_tags = simple_dlna_tags[:]
                    dlna_tags[3] = 'DLNA.ORG_FLAGS=00f00000000000000000000000000000'

                    hash_from_path = str(id(filename))
                    new_res = Resource(self.url+'?attachment='+hash_from_path,
                        'http-get:*:%s:%s' % (mimetype, ';'.join([dlna_pn]+dlna_tags)))
                    new_res.size = os.path.getsize(filename)
                    self.item.res.append(new_res)
                    if not hasattr(self.item, 'attachments'):
                        self.item.attachments = {}
                    self.item.attachments[hash_from_path] = utils.StaticFile(filename)

            if self.mimetype.startswith('video/'):
                # check for a subtitles file
                caption,_ =  os.path.splitext(self.get_path())
                caption = caption + '.srt'
                if os.path.exists(caption):
                    hash_from_path = str(id(caption))
                    mimetype = 'smi/caption'
                    new_res = Resource(self.url+'?attachment='+hash_from_path,
                        'http-get:*:%s:%s' % (mimetype, '*'))
                    new_res.size = os.path.getsize(caption)
                    self.caption = new_res.data
                    self.item.res.append(new_res)
                    if not hasattr(self.item, 'attachments'):
                        self.item.attachments = {}
                    self.item.attachments[hash_from_path] = utils.StaticFile(caption)

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

        res = Resource('file://'+urllib.quote(self.get_path()), 'internal:%s:%s:*' % (host,self.mimetype))
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
        self.sorted = False

    def remove_child(self, child):
        #print "remove_from %d (%s) child %d (%s)" % (self.id, self.get_name(), child.id, child.get_name())
        if child in self.children:
            self.child_count -= 1
            if isinstance(self.item, Container):
                self.item.childCount -= 1
            self.children.remove(child)
            self.update_id += 1
        self.sorted = False

    def get_children(self,start=0,request_count=0):
        if self.sorted == False:
            self.children.sort(key=_natural_key)
            self.sorted = True
        if request_count == 0:
            return self.children[start:]
        else:
            return self.children[start:request_count]

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
        if isinstance( self.location,FilePath):
            return self.location.path
        else:
            self.location

    def get_realpath(self):
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
            self.location = FilePath(path)
        else:
            self.location = path

    def get_name(self):
        if isinstance(self.location,FilePath):
            name = self.location.basename().decode("utf-8", "replace")
        else:
            name = self.location.decode("utf-8", "replace")
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
        return 'id: ' + str(self.id) + ' @ ' + self.get_name().encode('ascii','xmlcharrefreplace')

class FSStore(BackendStore):
    logCategory = 'fs_store'

    implements = ['MediaServer']

    description = """MediaServer exporting files from the file-system"""

    options = [{'option':'name','type':'string','default':'my media','help': 'the name under this MediaServer shall show up with on other UPnP clients'},
               {'option':'version','type':'int','default':2,'enum': (2,1),'help': 'the highest UPnP version this MediaServer shall support','level':'advance'},
               {'option':'uuid','type':'string','help':'the unique (UPnP) identifier for this MediaServer, usually automatically set','level':'advance'},
               {'option':'content','type':'string','default':xdg_content(),'help':'the path(s) this MediaServer shall export'},
               {'option':'ignore_patterns','type':'string','help':'list of regex patterns, matching filenames will be ignored'},
               {'option':'enable_inotify','type':'string','default':'yes','help':'enable real-time monitoring of the content folders'},
               {'option':'enable_destroy','type':'string','default':'no','help':'enable deleting a file via an UPnP method'},
               {'option':'import_folder','type':'string','help':'The path to store files imported via an UPnP method, if empty the Import method is disabled'}
              ]


    def __init__(self, server, **kwargs):
        BackendStore.__init__(self,server,**kwargs)
        self.next_id = 1000
        self.name = kwargs.get('name','my media')
        self.content = kwargs.get('content',None)
        if self.content != None:
                if isinstance(self.content,basestring):
                    self.content = [self.content]
                l = []
                for a in self.content:
                    l += a.split(',')
                self.content = l
        else:
            self.content = xdg_content()
            self.content = [x[0] for x in self.content]
        if self.content == None:
            self.content = 'tests/content'
        if not isinstance( self.content, list):
            self.content = [self.content]
        self.content = Set([os.path.abspath(x) for x in self.content])
        ignore_patterns = kwargs.get('ignore_patterns',[])
        self.store = {}

        self.inotify = None

        if kwargs.get('enable_inotify','yes') == 'yes':
            if haz_inotify == True:
                try:
                    self.inotify = INotify()
                except Exception,msg:
                    self.info("%s" %msg)
            else:
                self.info("%s" %no_inotify_reason)
        else:
            self.info("FSStore content auto-update disabled upon user request")


        if kwargs.get('enable_destroy','no') == 'yes':
            self.upnp_DestroyObject = self.hidden_upnp_DestroyObject

        self.import_folder = kwargs.get('import_folder',None)
        if self.import_folder != None:
            self.import_folder = os.path.abspath(self.import_folder)
            if not os.path.isdir(self.import_folder):
                self.import_folder = None

        self.ignore_file_pattern = re.compile('|'.join(['^\..*'] + list(ignore_patterns)))
        parent = None
        self.update_id = 0
        if(len(self.content)>1 or
           utils.means_true(kwargs.get('create_root',False)) or
           self.import_folder != None):
            UPnPClass = classChooser('root')
            id = str(self.getnextID())
            parent = self.store[id] = FSItem( id, parent, 'media', 'root', self.urlbase, UPnPClass, update=True,store=self)

        if self.import_folder != None:
            id = str(self.getnextID())
            self.store[id] = FSItem( id, parent, self.import_folder, 'directory', self.urlbase, UPnPClass, update=True,store=self)
            self.import_folder_id = id

        for path in self.content:
            if isinstance(path,(list,tuple)):
                path = path[0]
            if self.ignore_file_pattern.match(path):
                continue
            try:
                path = path.encode('utf-8') # patch for #267
                self.walk(path, parent, self.ignore_file_pattern)
            except Exception,msg:
                self.warning('on walk of %r: %r' % (path,msg))
                import traceback
                self.debug(traceback.format_exc())

        self.wmc_mapping.update({'14': '0',
                                 '15': '0',
                                 '16': '0',
                                 '17': '0'
                                })

        louie.send('Coherence.UPnP.Backend.init_completed', None, backend=self)

    def __repr__(self):
        return str(self.__class__).split('.')[-1]

    def release(self):
        if self.inotify != None:
            self.inotify.release()

    def len(self):
        return len(self.store)

    def get_by_id(self,id):
        #print "get_by_id", id, type(id)
        # we have referenced ids here when we are in WMC mapping mode
        if isinstance(id, basestring):
            id = id.split('@',1)
            id = id[0]
        #try:
        #    id = int(id)
        #except ValueError:
        #    id = 1000

        if id == '0':
            id = '1000'
        #print "get_by_id 2", id
        try:
            r = self.store[id]
        except:
            r = None
        #print "get_by_id 3", r
        return r

    def get_id_by_name(self, parent='0', name=''):
        self.info('get_id_by_name %r (%r) %r' % (parent, type(parent), name))
        try:
            parent = self.store[parent]
            self.debug("%r %d" % (parent,len(parent.children)))
            for child in parent.children:
                #if not isinstance(name, unicode):
                #    name = name.decode("utf8")
                self.debug("%r %r %r" % (child.get_name(),child.get_realpath(), name == child.get_realpath()))
                if name == child.get_realpath():
                    return child.id
        except:
            import traceback
            self.info(traceback.format_exc())
        self.debug('get_id_by_name not found')

        return None

    def get_url_by_name(self,parent='0',name=''):
        self.info('get_url_by_name %r %r' % (parent, name))
        id = self.get_id_by_name(parent,name)
        #print 'get_url_by_name', id
        if id == None:
            return ''
        return self.store[id].url


    def update_config(self,**kwargs):
        print "update_config", kwargs
        if 'content' in kwargs:
            new_content = kwargs['content']
            new_content = Set([os.path.abspath(x) for x in new_content.split(',')])
            new_folders = new_content.difference(self.content)
            obsolete_folders = self.content.difference(new_content)
            print new_folders, obsolete_folders
            for folder in obsolete_folders:
                self.remove_content_folder(folder)
            for folder in new_folders:
                self.add_content_folder(folder)
            self.content = new_content

    def add_content_folder(self,path):
        path = os.path.abspath(path)
        if path not in self.content:
            self.content.add(path)
            self.walk(path, self.store['1000'], self.ignore_file_pattern)

    def remove_content_folder(self,path):
        path = os.path.abspath(path)
        if path in self.content:
            id = self.get_id_by_name('1000', path)
            self.remove(id)
            self.content.remove(path)

    def walk(self, path, parent=None, ignore_file_pattern=''):
        self.debug("walk %r" % path)
        containers = []
        parent = self.append(path,parent)
        if parent != None:
            containers.append(parent)
        while len(containers)>0:
            container = containers.pop()
            try:
                self.debug('adding %r' % container.location)
                for child in container.location.children():
                    if ignore_file_pattern.match(child.basename()) != None:
                        continue
                    new_container = self.append(child.path,container)
                    if new_container != None:
                        containers.append(new_container)
            except UnicodeDecodeError:
                self.warning("UnicodeDecodeError - there is something wrong with a file located in %r", container.get_path())

    def create(self, mimetype, path, parent):
        self.debug("create ", mimetype, path, type(path), parent)
        UPnPClass = classChooser(mimetype)
        if UPnPClass == None:
            return None

        id = self.getnextID()
        if mimetype in ('root','directory'):
            id = str(id)
        else:
            _,ext =  os.path.splitext(path)
            id = str(id) + ext.lower()
        update = False
        if hasattr(self, 'update_id'):
            update = True

        self.store[id] = FSItem( id, parent, path, mimetype, self.urlbase, UPnPClass, update=True,store=self)
        if hasattr(self, 'update_id'):
            self.update_id += 1
            #print self.update_id
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
        self.debug("append ", path, type(path), parent)
        if os.path.exists(path) == False:
            self.warning("path %r not available - ignored", path)
            return None

        if stat.S_ISFIFO(os.stat(path).st_mode):
            self.warning("path %r is a FIFO - ignored", path)
            return None

        try:
            mimetype,_ = mimetypes.guess_type(path, strict=False)
            if mimetype == None:
                if os.path.isdir(path):
                    mimetype = 'directory'
            if mimetype == None:
                return None

            id = self.create(mimetype,path,parent)

            if mimetype == 'directory':
                if self.inotify is not None:
                    mask = IN_CREATE | IN_DELETE | IN_MOVED_FROM | IN_MOVED_TO | IN_CHANGED
                    self.inotify.watch(path, mask=mask, auto_add=False, callbacks=(self.notify,id))
                return self.store[id]
        except OSError, msg:
            """ seems we have some permissions issues along the content path """
            self.warning("path %r isn't accessible, error %r", path, msg)

        return None

    def remove(self, id):
        print 'FSSTore remove id', id
        try:
            item = self.store[id]
            parent = item.get_parent()
            item.remove()
            del self.store[id]
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
        self.info("Event %s on %s %s - parameter %r" % (
                    ', '.join(self.inotify.flag_to_human(mask)), iwp.path, filename, parameter))

        path = iwp.path
        if filename:
            path = os.path.join(path, filename)

        if mask & IN_CHANGED:
            # FIXME react maybe on access right changes, loss of read rights?
            #print '%s was changed, parent %d (%s)' % (path, parameter, iwp.path)
            pass

        if(mask & IN_DELETE or mask & IN_MOVED_FROM):
            self.info('%s was deleted, parent %r (%s)' % (path, parameter, iwp.path))
            id = self.get_id_by_name(parameter,os.path.join(iwp.path,filename))
            if id != None:
                self.remove(id)
        if(mask & IN_CREATE or mask & IN_MOVED_TO):
            if mask & IN_ISDIR:
                self.info('directory %s was created, parent %r (%s)' % (path, parameter, iwp.path))
            else:
                self.info('file %s was created, parent %r (%s)' % (path, parameter, iwp.path))
            if self.get_id_by_name(parameter,os.path.join(iwp.path,filename)) is None:
                if os.path.isdir(path):
                    self.walk(path, self.get_by_id(parameter), self.ignore_file_pattern)
                else:
                    if self.ignore_file_pattern.match(filename) == None:
                        self.append(path, self.get_by_id(parameter))

    def getnextID(self):
        ret = self.next_id
        self.next_id += 1
        return ret

    def backend_import(self,item,data):
        try:
            f = open(item.get_path(), 'w+b')
            if hasattr(data,'read'):
                data = data.read()
            f.write(data)
            f.close()
            item.rebuild(self.urlbase)
            return 200
        except IOError:
            self.warning("import of file %s failed" % item.get_path())
        except Exception,msg:
            import traceback
            self.warning(traceback.format_exc())
        return 500

    def upnp_init(self):
        self.current_connection_id = None
        if self.server:
            self.server.connection_manager_server.set_variable(0, 'SourceProtocolInfo',
                        [#'http-get:*:audio/mpeg:DLNA.ORG_PN=MP3;DLNA.ORG_OP=11;DLNA.ORG_FLAGS=01700000000000000000000000000000',
                         #'http-get:*:audio/x-ms-wma:DLNA.ORG_PN=WMABASE;DLNA.ORG_OP=11;DLNA.ORG_FLAGS=01700000000000000000000000000000',
                         #'http-get:*:image/jpeg:DLNA.ORG_PN=JPEG_TN;DLNA.ORG_OP=01;DLNA.ORG_FLAGS=00f00000000000000000000000000000',
                         #'http-get:*:image/jpeg:DLNA.ORG_PN=JPEG_SM;DLNA.ORG_OP=01;DLNA.ORG_FLAGS=00f00000000000000000000000000000',
                         #'http-get:*:image/jpeg:DLNA.ORG_PN=JPEG_MED;DLNA.ORG_OP=01;DLNA.ORG_FLAGS=00f00000000000000000000000000000',
                         #'http-get:*:image/jpeg:DLNA.ORG_PN=JPEG_LRG;DLNA.ORG_OP=01;DLNA.ORG_FLAGS=00f00000000000000000000000000000',
                         #'http-get:*:video/mpeg:DLNA.ORG_PN=MPEG_PS_PAL;DLNA.ORG_OP=01;DLNA.ORG_FLAGS=01700000000000000000000000000000',
                         #'http-get:*:video/x-ms-wmv:DLNA.ORG_PN=WMVMED_BASE;DLNA.ORG_OP=01;DLNA.ORG_FLAGS=01700000000000000000000000000000',
                         'internal:%s:audio/mpeg:*' % self.server.coherence.hostname,
                         'http-get:*:audio/mpeg:*',
                         'internal:%s:video/mp4:*' % self.server.coherence.hostname,
                         'http-get:*:video/mp4:*',
                         'internal:%s:application/ogg:*' % self.server.coherence.hostname,
                         'http-get:*:application/ogg:*',
                         'internal:%s:video/x-msvideo:*' % self.server.coherence.hostname,
                         'http-get:*:video/x-msvideo:*',
                         'internal:%s:video/mpeg:*' % self.server.coherence.hostname,
                         'http-get:*:video/mpeg:*',
                         'internal:%s:video/avi:*' % self.server.coherence.hostname,
                         'http-get:*:video/avi:*',
                         'internal:%s:video/divx:*' % self.server.coherence.hostname,
                         'http-get:*:video/divx:*',
                         'internal:%s:video/quicktime:*' % self.server.coherence.hostname,
                         'http-get:*:video/quicktime:*',
                         'internal:%s:image/gif:*' % self.server.coherence.hostname,
                         'http-get:*:image/gif:*',
                         'internal:%s:image/jpeg:*' % self.server.coherence.hostname,
                         'http-get:*:image/jpeg:*'],
                        default=True)
            self.server.content_directory_server.set_variable(0, 'SystemUpdateID', self.update_id)
            #self.server.content_directory_server.set_variable(0, 'SortCapabilities', '*')


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
        #print "CreateObject", kwargs
        if kwargs['ContainerID'] == 'DLNA.ORG_AnyContainer':
            if self.import_folder != None:
                ContainerID = self.import_folder_id
            else:
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
        if item.parentID == 'DLNA.ORG_AnyContainer':
            item.parentID = ContainerID
        if(item.id != '' or
           item.parentID != ContainerID or
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

        if item.upnp_class.startswith('object.item'):
            _,_,content_format,_ = item.res[0].protocolInfo.split(':')
            extension = mimetypes.guess_extension(content_format, strict=False)
            path = os.path.join(parent_item.get_realpath(),item.title+extension)
            id = self.create('item',path,parent_item)

            new_item = self.get_by_id(id)
            for res in new_item.item.res:
                res.importUri = new_item.url+'?import'
                res.data = None
            didl = DIDLElement()
            didl.addItem(new_item.item)
            return {'ObjectID': id, 'Result': didl.toString()}

        return failure.Failure(errorCode(712))

    def hidden_upnp_DestroyObject(self, *args, **kwargs):
        ObjectID = kwargs['ObjectID']

        item = self.get_by_id(ObjectID)
        if item == None:
            return failure.Failure(errorCode(701))

        print "upnp_DestroyObject", item.location
        try:
            item.location.remove()
        except Exception, msg:
            print Exception, msg
            return failure.Failure(errorCode(715))

        return {}


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
