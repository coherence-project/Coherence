# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2008, Benjamin Kampmann <ben.kampmann@googlemail.com>

"""
Another simple rss based Media Server, this time for TED.com content
"""

# I can reuse stuff. cool. But that also means we might want to refactor it into
# a base class to reuse
from coherence.backends.lolcats_storage import LolcatsStore
from coherence.backends.appletrailers_storage import Container

from coherence.backend import BackendItem
from coherence.upnp.core import DIDLLite

class TedTalk(BackendItem):

    def __init__(self, parent_id, id, title=None, url=None,
            duration=None, size=None):
        self.parentid = parent_id
        self.update_id = 0
        self.id = id
        self.location = url
        self.name = title

        self.item = DIDLLite.VideoItem(id, parent_id, self.name)

        res = DIDLLite.Resource(self.location, 'http-get:*:video/mp4:*') # FIXME should be video/x-m4a
        res.size = size
        res.duration = duration
        self.item.res.append(res)

class TEDStore(LolcatsStore):

    implements = ['MediaServer']

    rss_url = "http://feeds.feedburner.com/tedtalks_video?format=xml"

    ROOT_ID = 0

    def __init__(self, server, *args, **kwargs):
        BackendStore.__init__(self,server,**kwargs)

        self.name = kwargs.get('name', 'TEDtalks')
        self.refresh = int(kwargs.get('refresh', 1)) * (60 *60)

        self.next_id = 1001
        self.last_updated = None

        self.container = Container(None, self.ROOT_ID, self.name)

        self.videos = {}

        dfr = self.update_data()
        dfr.addCallback(self.init_completed)

    def get_by_id(self, id):
        if int(id) == self.ROOT_ID:
            return self.container
        return self.videos.get(int(id), None)

    def upnp_init(self):
        if self.server:
            self.server.connection_manager_server.set_variable( \
                0, 'SourceProtocolInfo', ['http-get:*:video/mp4:*'])

    def parse_data(self, xml_data):

        root = xml_data.getroot()

        pub_date = root.find('./channel/lastBuildDate').text

        if pub_date == self.last_updated:
            return

        self.last_updated = pub_date

        self.container.children = []
        self.videos = {}

        # FIXME: move these to generic constants somewhere
        mrss = './{http://search.yahoo.com/mrss/}'
        itunes = './{http://www.itunes.com/dtds/podcast-1.0.dtd}'

        url_item = mrss + 'content'
        duration = itunes + 'duration'
        summary = itunes + 'summary'

        for item in root.findall('./channel/item'):
            data = {}
            data['parent_id'] = self.ROOT_ID
            data['id'] = self.next_id
            data['title'] = item.find('./title').text.replace('TEDTalks : ', '')
            # data ['summary'] = item.find(summary).text
            # data ['duration'] = item.find(duration).text

            try:
                media_entry = item.find(url_item)
                data['url'] = media_entry.get('url', None)
                data['size'] = media_entry.get('size', None)
            except IndexError:
                continue

            video = TedTalk(**data)

            self.container.children.append(video)
            self.videos[self.next_id] = video

            self.next_id += 1

        self.container.update_id += 1
        self.update_id += 1

        if self.server:
            self.server.content_directory_server.set_variable(0, 'SystemUpdateID', self.update_id)
            value = (self.ROOT_ID,self.container.update_id)
            self.server.content_directory_server.set_variable(0, 'ContainerUpdateIDs', value)
