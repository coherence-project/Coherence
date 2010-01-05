# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2009, Dominik Ruf <dominikruf at googlemail dot com>

from coherence.backend import BackendItem
from coherence.backend import BackendStore
from coherence.upnp.core import DIDLLite
from coherence.upnp.core.utils import ReverseProxyUriResource

from xml.etree.ElementTree import ElementTree
import urllib
import httplib
from urlparse import urlsplit
try:
    import feedparser
except:
    raise ImportError("""
        This backend depends on the feedparser module.
        You can get it at http://www.feedparser.org/.""")

MIME_TYPES_EXTENTION_MAPPING = {'mp3': 'audio/mpeg',}

ROOT_CONTAINER_ID = 0
AUDIO_ALL_CONTAINER_ID = 51
AUDIO_ARTIST_CONTAINER_ID = 52
AUDIO_ALBUM_CONTAINER_ID = 53
VIDEO_FOLDER_CONTAINER_ID = 54

class RedirectingReverseProxyUriResource(ReverseProxyUriResource):
    def render(self, request):
        self.uri = self.follow_redirect(self.uri)
        self.resetUri(self.uri)
        return ReverseProxyUriResource.render(self, request)

    def follow_redirect(self, uri):
        netloc, path, query, fragment = urlsplit(uri)[1:]
        conn = httplib.HTTPConnection(netloc)
        conn.request('HEAD', '%s?%s#%s' % (path, query, fragment))
        res = conn.getresponse()
        if(res.status == 301 or res.status == 302):
            return self.follow_redirect(res.getheader('location'))
        else:
            return uri


class FeedStorageConfigurationException(Exception):
    pass

class FeedContainer(BackendItem):
    def __init__(self, parent_id, id, title):
        self.id = id
        self.parent_id = parent_id
        self.name = title
        self.mimetype = 'directory'
        self.item = DIDLLite.Container(self.id, self.parent_id, self.name)

        self.children = []

    def get_children(self, start=0, end=0):
        """returns all the chidlren of this container"""
        if end != 0:
            return self.children[start:end]
        return self.children[start:]

    def get_child_count(self):
        """returns the number of children in this container"""
        return len(self.children)


class FeedEnclosure(BackendItem):
    def __init__(self, store, parent, id, title, enclosure):
        self.store = store
        self.parent = parent
        self.external_id = id
        self.name = title
        self.location = RedirectingReverseProxyUriResource(enclosure.url.encode('latin-1'))

        # doing this because some (Fraunhofer Podcast) feeds say there mime type is audio/x-mpeg
        # which at least my XBOX doesn't like
        ext = enclosure.url.rsplit('.', 1)[0]
        if ext in MIME_TYPES_EXTENTION_MAPPING:
            mime_type = MIME_TYPES_EXTENTION_MAPPING[ext]
        else:
            mime_type = enclosure.type
        if(enclosure.type.startswith('audio')):
            self.item = DIDLLite.AudioItem(id, parent, self.name)
        elif(enclosure.type.startswith('video')):
            self.item = DIDLLite.VideoItem(id, parent, self.name)
        elif(enclosure.type.startswith('image')):
            self.item = DIDLLite.ImageItem(id, parent, self.name)

        res = DIDLLite.Resource("%s%d" % (store.urlbase, id), 'http-get:*:%s:*' % mime_type)

        self.item.res.append(res)

class FeedStore(BackendStore):
    """a general feed store"""

    logCategory = 'feed_store'
    implements = ['MediaServer']

    def __init__(self,server,**kwargs):
        BackendStore.__init__(self,server,**kwargs)
        self.name = kwargs.get('name', 'Feed Store')
        self.urlbase = kwargs.get('urlbase','')
        if( len(self.urlbase)>0 and
            self.urlbase[len(self.urlbase)-1] != '/'):
            self.urlbase += '/'
        self.feed_urls = kwargs.get('feed_urls')
        self.opml_url = kwargs.get('opml_url')
        if(not(self.feed_urls or self.opml_url)):
            raise FeedStorageConfigurationException("either feed_urls or opml_url has to be set")
        if(self.feed_urls and self.opml_url):
            raise FeedStorageConfigurationException("only feed_urls OR opml_url can be set")

        self.server = server
        self.refresh = int(kwargs.get('refresh', 1)) * (60 * 60) # TODO: not used yet
        self.store = {}
        self.wmc_mapping = {'4': str(AUDIO_ALL_CONTAINER_ID),    # all tracks
                            '7': str(AUDIO_ALBUM_CONTAINER_ID),    # all albums
                            '6': str(AUDIO_ARTIST_CONTAINER_ID),    # all artists
                            '15': str(VIDEO_FOLDER_CONTAINER_ID),    # all videos
                            }

        self.store[ROOT_CONTAINER_ID] = FeedContainer(-1, ROOT_CONTAINER_ID, self.name)
        self.store[AUDIO_ALL_CONTAINER_ID] = FeedContainer(-1, AUDIO_ALL_CONTAINER_ID, 'AUDIO_ALL_CONTAINER')
        self.store[AUDIO_ALBUM_CONTAINER_ID] = FeedContainer(-1, AUDIO_ALBUM_CONTAINER_ID, 'AUDIO_ALBUM_CONTAINER')
        self.store[VIDEO_FOLDER_CONTAINER_ID] = FeedContainer(-1, VIDEO_FOLDER_CONTAINER_ID, 'VIDEO_FOLDER_CONTAINER')

        try:
            self._update_data()
        except Exception, e:
            self.error('error while updateing the feed contant for %s: %s' % (self.name, str(e)))
        self.init_completed()

    def get_by_id(self,id):
        """returns the item according to the DIDLite id"""
        if isinstance(id, basestring):
            id = id.split('@',1)
            id = id[0]
        try:
            return self.store[int(id)]
        except (ValueError,KeyError):
            self.info("can't get item %d from %s feed storage" % (int(id), self.name))
        return None

    def _update_data(self):
        """get the feed xml, parse it, etc."""
        feed_urls = []
        if(self.opml_url):
            tree = ElementTree(file=urllib.urlopen(self.opml_url))
            body = tree.find('body')
            for outline in body.findall('outline'):
                feed_urls.append(outline.attrib['url'])

        if(self.feed_urls):
            feed_urls = self.feed_urls.split()
        container_id = 100
        item_id = 1001
        for feed_url in feed_urls:
            netloc, path, query, fragment = urlsplit(feed_url)[1:]
            conn = httplib.HTTPConnection(netloc)
            conn.request('HEAD', '%s?%s#%s' % (path, query, fragment))
            res = conn.getresponse()
            if res.status >= 400:
                self.warning('error getting %s status code: %d' % (feed_url, res.status))
                continue
            fp_dict = feedparser.parse(feed_url)
            name = fp_dict.feed.title
            self.store[container_id] = FeedContainer(ROOT_CONTAINER_ID, container_id, name)
            self.store[ROOT_CONTAINER_ID].children.append(self.store[container_id])
            self.store[VIDEO_FOLDER_CONTAINER_ID].children.append(self.store[container_id])
            self.store[AUDIO_ALBUM_CONTAINER_ID].children.append(self.store[container_id])
            for item in fp_dict.entries:
                for enclosure in item.enclosures:
                    self.store[item_id] = FeedEnclosure(self, container_id, item_id, '%04d - %s' % (item_id, item.title), enclosure)
                    self.store[container_id].children.append(self.store[item_id])
                    if enclosure.type.startswith('audio'):
                        self.store[AUDIO_ALL_CONTAINER_ID].children.append(self.store[item_id])
                        if not isinstance(self.store[container_id].item, DIDLLite.MusicAlbum):
                            self.store[container_id].item = DIDLLite.MusicAlbum(container_id, AUDIO_ALBUM_CONTAINER_ID, name)

                    item_id += 1
            if container_id <= 1000:
                container_id += 1
            else:
                raise Exception('to many containers')
