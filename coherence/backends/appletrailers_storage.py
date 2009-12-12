# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2008, Benjamin Kampmann <ben.kampmann@googlemail.com>

"""
This is a Media Backend that allows you to access the Trailers from Apple.com
"""

from coherence.backend import BackendItem, BackendStore
from coherence.upnp.core import DIDLLite
from coherence.upnp.core.utils import ReverseProxyUriResource
from twisted.web import client
from twisted.internet import task, reactor

from coherence.extern.et import parse_xml

XML_URL = "http://www.apple.com/trailers/home/xml/current.xml"

ROOT_ID = 0

class AppleTrailerProxy(ReverseProxyUriResource):

    def __init__(self, uri):
        ReverseProxyUriResource.__init__(self, uri)

    def render(self, request):
        request.received_headers['user-agent'] = 'QuickTime/7.6.2 (qtver=7.6.2;os=Windows NT 5.1Service Pack 3)'
        return ReverseProxyUriResource.render(self, request)


class Trailer(BackendItem):

    def __init__(self, parent_id, urlbase, id=None, name=None, cover=None,
            url=None):
        self.parentid = parent_id
        self.id = id
        self.name = name
        self.cover = cover
        if( len(urlbase) and urlbase[-1] != '/'):
            urlbase += '/'
        self.url = urlbase + str(self.id)
        self.location = AppleTrailerProxy(url)
        self.item = DIDLLite.VideoItem(id, parent_id, self.name)
        self.item.albumArtURI = self.cover

    def get_path(self):
        return self.url


class Container(BackendItem):

    logCategory = 'apple_trailers'

    def __init__(self, id, parent_id, name, store=None, \
            children_callback=None):
        self.id = id
        self.parent_id = parent_id
        self.name = name
        self.mimetype = 'directory'
        self.update_id = 0
        self.children = []

        self.item = DIDLLite.Container(id, parent_id, self.name)
        self.item.childCount = None #self.get_child_count()

    def get_children(self, start=0, end=0):
        if(end - start > 25 or
           start - end == start or
           end - start == 0):
            end = start+25
        if end != 0:
            return self.children[start:end]
        return self.children[start:]

    def get_child_count(self):
        return len(self.children)

    def get_item(self):
        return self.item

    def get_name(self):
        return self.name

    def get_id(self):
        return self.id

class AppleTrailersStore(BackendStore):

    logCategory = 'apple_trailers'
    implements = ['MediaServer']

    def __init__(self, server, *args, **kwargs):
        BackendStore.__init__(self,server,**kwargs)
        self.next_id = 1000
        self.name = kwargs.get('name','Apple Trailers')
        self.refresh = int(kwargs.get('refresh', 8)) * (60 *60)

        self.trailers = {}

        self.wmc_mapping = {'15': 0}

        dfr = self.update_data()
        # first get the first bunch of data before sending init_completed
        dfr.addCallback(lambda x: self.init_completed())

    def queue_update(self, result):
        reactor.callLater(self.refresh, self.update_data)
        return result

    def update_data(self):
        dfr = client.getPage(XML_URL)
        dfr.addCallback(parse_xml)
        dfr.addCallback(self.parse_data)
        dfr.addCallback(self.queue_update)
        return dfr

    def parse_data(self, xml_data):

        def iterate(root):
            for item in root.findall('./movieinfo'):
                trailer = self._parse_into_trailer(item)
                yield trailer

        root = xml_data.getroot()
        return task.coiterate(iterate(root))

    def _parse_into_trailer(self, item):
        """
        info = item.find('info')

        for attr in ('title', 'runtime', 'rating', 'studio', 'postdate',
                     'releasedate', 'copyright', 'director', 'description'):
            setattr(trailer, attr, info.find(attr).text)
        """

        data = {}
        data['id'] = item.get('id')
        data['name'] = item.find('./info/title').text
        data['cover'] = item.find('./poster/location').text
        data['url'] = item.find('./preview/large').text

        trailer = Trailer(ROOT_ID, self.urlbase, **data)
        duration = None
        try:
            hours = 0
            minutes = 0
            seconds = 0
            duration = item.find('./info/runtime').text
            try:
                hours,minutes,seconds = duration.split(':')
            except ValueError:
                try:
                    minutes,seconds = duration.split(':')
                except ValueError:
                    seconds = duration
            duration = "%d:%02d:%02d" % (int(hours), int(minutes), int(seconds))
        except:
            pass

        try:
            trailer.item.director = item.find('./info/director').text
        except:
            pass

        try:
            trailer.item.description = item.find('./info/description').text
        except:
            pass

        res = DIDLLite.Resource(trailer.get_path(), 'http-get:*:video/quicktime:*')
        res.duration = duration
        try:
            res.size = item.find('./preview/large').get('filesize',None)
        except:
            pass
        trailer.item.res.append(res)

        if self.server.coherence.config.get('transcoding', 'no') == 'yes':
            dlna_pn = 'DLNA.ORG_PN=AVC_TS_BL_CIF15_AAC'
            dlna_tags = DIDLLite.simple_dlna_tags[:]
            dlna_tags[2] = 'DLNA.ORG_CI=1'
            url = self.urlbase + str(trailer.id)+'?transcoded=mp4'
            new_res = DIDLLite.Resource(url,
                'http-get:*:%s:%s' % ('video/mp4', ';'.join([dlna_pn]+dlna_tags)))
            new_res.size = None
            res.duration = duration
            trailer.item.res.append(new_res)

            dlna_pn = 'DLNA.ORG_PN=JPEG_TN'
            dlna_tags = DIDLLite.simple_dlna_tags[:]
            dlna_tags[2] = 'DLNA.ORG_CI=1'
            dlna_tags[3] = 'DLNA.ORG_FLAGS=00f00000000000000000000000000000'
            url = self.urlbase + str(trailer.id)+'?attachment=poster&transcoded=thumb&type=jpeg'
            new_res = DIDLLite.Resource(url,
                'http-get:*:%s:%s' % ('image/jpeg', ';'.join([dlna_pn] + dlna_tags)))
            new_res.size = None
            #new_res.resolution = "160x160"
            trailer.item.res.append(new_res)
            if not hasattr(trailer.item, 'attachments'):
                trailer.item.attachments = {}
            trailer.item.attachments['poster'] = data['cover']

        self.trailers[trailer.id] = trailer

    def get_by_id(self, id):
        try:
            if int(id) == 0:
                return self.container
            else:
                return self.trailers.get(id,None)
        except:
            return None

    def upnp_init(self):
        if self.server:
            self.server.connection_manager_server.set_variable( \
                0, 'SourceProtocolInfo', ['http-get:*:video/quicktime:*','http-get:*:video/mp4:*'])
        self.container = Container(ROOT_ID, -1, self.name)
        trailers = self.trailers.values()
        trailers.sort(cmp=lambda x,y : cmp(x.get_name().lower(),y.get_name().lower()))
        self.container.children = trailers

    def __repr__(self):
        return self.__class__.__name__