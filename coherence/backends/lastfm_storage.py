# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

"""
INFO  lastFM_user                 Dez 14 17:35:27  Got new sessionid: '1488f34a1cbed7c9f4232f8fd563c3bd' (coherence/backends/lastfm_storage.py:60)
DEBUG lastFM_stream               Dez 14 17:35:53  render <GET /da525474-5357-4d1b-a894-76b1293224c9/1005 HTTP/1.1> (coherence/backends/lastfm_storage.py:148)
command GET
rest /user/e0362c757ef49169e9a0f0970cc2d367.mp3
headers {'icy-metadata': '1', 'host': 'kingpin5.last.fm', 'te': 'trailers', 'connection': 'TE', 'user-agent': 'gnome-vfs/2.12.0.19 neon/0.24.7'}
ProxyClient handleStatus HTTP/1.1 200 OK
ProxyClient handleHeader Content-Type audio/mpeg
ProxyClient handleHeader Content-Length 4050441
ProxyClient handleHeader Cache-Control no-cache, must-revalidate
DEBUG lastFM_stream               Dez 14 17:35:53  render <GET /da525474-5357-4d1b-a894-76b1293224c9/1005 HTTP/1.1> (coherence/backends/lastfm_storage.py:148)
command GET
rest /user/e0362c757ef49169e9a0f0970cc2d367.mp3
headers {'icy-metadata': '1', 'host': 'kingpin5.last.fm', 'te': 'trailers', 'connection': 'TE', 'user-agent': 'gnome-vfs/2.12.0.19 neon/0.24.7'}
ProxyClient handleStatus HTTP/1.1 403 Invalid ticket
"""

# Copyright 2007, Frank Scholz <coherence@beebits.net>
# Copyright 2007, Moritz Struebe <morty@gmx.net>

from twisted.internet import defer

from coherence.upnp.core import utils

from coherence.upnp.core.DIDLLite import classChooser, Container, Resource, DIDLElement

import coherence.extern.louie as louie

from coherence.extern.simple_plugin import Plugin

from coherence import log
from coherence.backend import BackendItem, BackendStore

from urlparse import urlsplit

try:
    from hashlib import md5
except ImportError:
    # hashlib is new in Python 2.5
    from md5 import md5

import string


class LastFMUser(log.Loggable):

    logCategory = 'lastFM_user'

    user = None
    passwd = None
    host = "ws.audioscrobbler.com"
    basepath = "/radio"
    sessionid = None
    parent = None
    getting_tracks = False
    tracks = []

    def __init__(self, user, passwd):
        if user is None:
            self.warn("No User",)
        if passwd is None:
            self.warn("No Passwd",)
        self.user = user
        self.passwd = passwd

    def login(self):

        if self.sessionid != None:
            self.warning("Session seems to be valid",)
            return

        def got_page(result):
            lines = result[0].split("\n")
            for line in lines:
                tuple = line.rstrip().split("=", 1)
                if len(tuple) == 2:
                    if tuple[0] == "session":
                        self.sessionid = tuple[1]
                        self.info("Got new sessionid: %r",self.sessionid )
                    if tuple[0] == "base_url":
                        if(self.host != tuple[1]):
                            self.host = tuple[1]
                            self.info("Got new host: %s",self.host )
                    if tuple[0] == "base_path":
                        if(self.basepath != tuple[1]):
                            self.basepath = tuple[1]
                            self.info("Got new path: %s",self.basepath)
            self.get_tracks()


        def got_error(error):
            self.warning("Login to LastFM Failed! %r", error)
            self.debug("%r", error.getTraceback())

        def hexify(s): # This function might be GPL! Found this code in some other Projects, too.
            result = ""
            for c in s:
                result = result + ("%02x" % ord(c))
            return result
        password = hexify(md5(self.passwd).digest())
        req = self.basepath + "/handshake.php/?version=1&platform=win&username=" + self.user + "&passwordmd5=" + password + "&language=en&player=coherence"
        utils.getPage("http://" + self.host + req).addCallbacks(got_page, got_error, None, None, None, None)

    def get_tracks(self):
        if self.getting_tracks == True:
            return

        def got_page(result):
            result = utils.parse_xml(result, encoding='utf-8')
            self.getting_tracks = False
            print self.getting_tracks
            print "got Tracks"
            for track in result.findall('trackList/track'):
                data = {}
                def get_data(name):
                    #print track.find(name).text.encode('utf-8')
                    return track.find(name).text.encode('utf-8')
                #Fixme: This section needs some work
                print "adding Track"
                data['mimetype'] = 'audio/mpeg'
                data['name'] =get_data('creator') + " - " + get_data('title')
                data['title'] = get_data('title')
                data['artist'] = get_data('creator')
                data['creator'] = get_data('creator')
                data['album'] = get_data('album')
                data['duration'] = get_data('duration')
                #FIXME: Image is the wrong tag.
                data['image'] =get_data('image')
                data['url'] = track.find('location').text.encode('utf-8')
                item = self.parent.store.append(data, self.parent)
                self.tracks.append(item)


        def got_error(error):
            self.warning("Problem getting Tracks! %r", error)
            self.debug("%r", error.getTraceback())
            self.getting_tracks = False

        self.getting_tracks = True
        req = self.basepath + "/xspf.php?sk=" + self.sessionid + "&discovery=0&desktop=1.3.1.1"
        utils.getPage("http://" + self.host + req).addCallbacks(got_page, got_error, None, None, None, None)

    def update(self, item):
        if 0 < self.tracks.count(item):
            while True:
                track = self.tracks[0]
                if track == item:
                    break
                self.tracks.remove(track)
                # Do not remoce so the tracks to answer the browse
                # request correctly.
                #track.store.remove(track)
                #del track

        #if len(self.tracks) < 5:
        self.get_tracks()


class LFMProxyStream(utils.ReverseProxyResource,log.Loggable):
    logCategory = 'lastFM_stream'

    def __init__(self, uri, parent):
        self.uri = uri
        self.parent = parent
        _,host_port,path,_,_ = urlsplit(uri)
        if host_port.find(':') != -1:
            host,port = tuple(host_port.split(':'))
            port = int(port)
        else:
            host = host_port
            port = 80

        if path == '':
            path = '/'

        #print "ProxyStream init", host, port, path
        utils.ReverseProxyResource.__init__(self, host, port, path)

    def render(self, request):
        self.debug("render %r", request)
        self.parent.store.LFM.update(self.parent)
        self.parent.played = True
        return utils.ReverseProxyResource.render(self, request)



class LastFMItem(log.Loggable):
    logCategory = 'LastFM_item'

    def __init__(self, id, obj, parent, mimetype, urlbase, UPnPClass,update=False):
        self.id = id

        self.name = obj.get('name')
        self.title = obj.get('title')
        self.artist = obj.get('artist')
        self.creator = obj.get('creator')
        self.album = obj.get('album')
        self.duration  = obj.get('duration')
        self.mimetype = mimetype

        self.parent = parent
        if parent:
            parent.add_child(self,update=update)

        if parent == None:
            parent_id = -1
        else:
            parent_id = parent.get_id()

        self.item = UPnPClass(id, parent_id, self.title,False ,self.creator)
        if isinstance(self.item, Container):
            self.item.childCount = 0
        self.child_count = 0
        self.children = []

        if( len(urlbase) and urlbase[-1] != '/'):
            urlbase += '/'

        if self.mimetype == 'directory':
            self.url = urlbase + str(self.id)
        else:
            self.url = urlbase + str(self.id)
            self.location = LFMProxyStream(obj.get('url'), self)
            #self.url = obj.get('url')

        if self.mimetype == 'directory':
            self.update_id = 0
        else:
            res = Resource(self.url, 'http-get:*:%s:%s' % (obj.get('mimetype'),
                                                                     ';'.join(('DLNA.ORG_PN=MP3',
                                                                               'DLNA.ORG_CI=0',
                                                                               'DLNA.ORG_OP=01',
                                                                               'DLNA.ORG_FLAGS=01700000000000000000000000000000'))))
            res.size = -1 #None
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
        self.info("remove_from %d (%s) child %d (%s)" % (self.id, self.get_name(), child.id, child.get_name()))
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
        if self.mimetype == 'directory':
            return 100 #Some Testing, with strange Numbers: 0/lots
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
        return 'id: ' + str(self.id) + ' @ ' + self.url + ' ' + self.name

class LastFMStore(log.Loggable,Plugin):

    logCategory = 'lastFM_store'

    implements = ['MediaServer']

    def __init__(self, server, **kwargs):
        BackendStore.__init__(self,server,**kwargs)

        self.next_id = 1000
        self.config = kwargs
        self.name = kwargs.get('name','LastFMStore')

        self.update_id = 0
        self.store = {}

        self.wmc_mapping = {'4': 1000}


        louie.send('Coherence.UPnP.Backend.init_completed', None, backend=self)


    def __repr__(self):
        return str(self.__class__).split('.')[-1]

    def append( self, obj, parent):
        if isinstance(obj, basestring):
            mimetype = 'directory'
        else:
            mimetype = obj['mimetype']

        UPnPClass = classChooser(mimetype)
        id = self.getnextID()
        update = False
        if hasattr(self, 'update_id'):
            update = True

        self.store[id] = LastFMItem( id, obj, parent, mimetype, self.urlbase,
                                        UPnPClass, update=update)
        self.store[id].store = self


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

    def remove(self, item):
        try:
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

    def len(self):
        return len(self.store)

    def get_by_id(self,id):
        if isinstance(id, basestring):
            id = id.split('@',1)
            id = id[0]
        id = int(id)
        if id == 0:
            id = 1000
        try:
            return self.store[id]
        except:
            return None

    def getnextID(self):
        ret = self.next_id
        self.next_id += 1
        return ret

    def upnp_init(self):
        self.current_connection_id = None


        parent = self.append({'name':'LastFM','mimetype':'directory'}, None)


        self.LFM = LastFMUser(self.config.get("login"), self.config.get("password"))
        self.LFM.parent = parent
        self.LFM.login()

        if self.server:
            self.server.connection_manager_server.set_variable(0, 'SourceProtocolInfo',
                                                                    ['http-get:*:audio/mpeg:*'],
                                                                    default=True)

def main():

    f = LastFMStore(None)

    def got_upnp_result(result):
        print "upnp", result

    f.upnp_init()



if __name__ == '__main__':

    from twisted.internet import reactor

    reactor.callWhenRunning(main)
    reactor.run()
