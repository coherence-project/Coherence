# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2008, Benjamin Kampmann <ben.kampmann@googlemail.com>

"""
This is a Media Backend that allows you to access the Trailers from Apple.com
"""

from coherence.backend import BackendItem, BackendStore
from coherence.upnp.core import DIDLLite
from twisted.web import client
from twisted.internet import task, reactor

from coherence.extern.et import parse_xml
import coherence.extern.louie as louie


XML_URL = "http://www.apple.com/trailers/home/xml/current.xml"

ROOT_ID = 0


class Trailer(BackendItem):

    def __init__(self, parent_id, id=None, name=None, cover=None,
            location=None):
        self.parentid = parent_id
        self.id = id
        self.name = name
        self.cover = cover
        self.location = location
        self.item = DIDLLite.VideoItem(id, parent_id, self.name)

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

        self.next_id = 1000
        self.name = kwargs.get('name','Apple Trailers')
        self.refresh = int(kwargs.get('refresh', 8)) * (60 *60)

        self.urlbase = kwargs.get('urlbase','')
        if self.urlbase[len(self.urlbase)-1] != '/':
            self.urlbase += '/'

        self.server = server # the UPnP device that's hosting that backend
        self.update_id = 0
        self.trailers = {}

        dfr = self.update_data()
        # first get the first bunch of data before sending init_completed
        dfr.addCallback(self._send_init)

    def _send_init(self, result):
        louie.send('Coherence.UPnP.Backend.init_completed',
                None, backend=self)

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
        data['location'] = item.find('./preview/large').text

        trailer = Trailer(ROOT_ID, **data)
        res = DIDLLite.Resource(trailer.location, 'http-get:*:video/quicktime:*')
        trailer.item.res.append(res)

        if self.server.coherence.config.get('transcoding', 'no') == 'yes':
            dlna_pn = 'DLNA.ORG_PN=AVC_TS_BL_CIF15_AAC'
            dlna_tags = DIDLLite.simple_dlna_tags[:]
            dlna_tags[1] = 'DLNA.ORG_CI=1'
            url = self.urlbase + str(trailer.id)+'?transcoded=mp4'
            new_res = DIDLLite.Resource(url,
                'http-get:*:%s:%s' % ('video/mp4', ';'.join([dlna_pn]+dlna_tags)))
            new_res.size = None
            trailer.item.res.append(new_res)

            dlna_pn = 'DLNA.ORG_PN=JPEG_TN'
            dlna_tags = DIDLLite.simple_dlna_tags[:]
            dlna_tags[1] = 'DLNA.ORG_CI=1'
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
        if int(id) == 0:
            return self.container
        else:
            return self.trailers.get(id,None)

    def upnp_init(self):
        if self.server:
            self.server.connection_manager_server.set_variable( \
                0, 'SourceProtocolInfo', ['http-get:*:video/quicktime:*','http-get:*:video/mp4:*'])
        self.container = Container(ROOT_ID, -1, self.name)
        trailers = self.trailers.values()
        trailers.sort(cmp=lambda x,y : cmp(x.get_name().lower(),y.get_name().lower()))
        self.container.children = trailers
