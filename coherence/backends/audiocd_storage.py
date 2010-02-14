# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# <EXPERIMENTAL>

# a backend to expose to the local network the content of an audio CD 
# inserted in a local drive
# the CD data is extracted from the CDDB/FreeDB database

# Warning: this backend does not detect insertion and ejection of CD drive
# the CD must be inserted before activating the backing.
# The backend must be disabled before ejecting the audio CD.

# Dependencies
# CDDB.py and DiscID.py (ex: debian package python-cddb)
# python-gst (with base and ugly plugins)

# TODO: switch from CDDB/FreeDB to musicBrainz
# TODO: find source for AlbumArt UI
# TODO: support other character encoding environment than ISO-8856-1

# Copyright 2010, Jean-Michel Sizun

import CDDB, DiscID

from twisted.internet import reactor,threads

from coherence.upnp.core import DIDLLite
from coherence import log

from coherence.transcoder import GStreamerPipeline

from coherence.backend import AbstractBackendStore, Container, BackendItem 

PLAY_TRACK_GST_PIPELINE = "cdiocddasrc device=%s track=%d ! wavenc name=enc"
TRACK_MIMETYPE = "audio/x-wav"
TRACK_FOURTH_FIELD = "*"

class TrackItem(BackendItem):
    logCategory = "audiocd"

    def __init__(self,device_name="/dev/cdrom", track_number=1, artist="Unknown", title="Unknown"):
        self.device_name = device_name
        self.track_number = track_number
        self.artist = artist
        self.title = title
        self.mimetype = TRACK_MIMETYPE
        self.fourth_field = TRACK_FOURTH_FIELD
        self.item = None
        self.pipeline = PLAY_TRACK_GST_PIPELINE % (self.device_name, self.track_number)
        self.location = GStreamerPipeline(self.pipeline,self.mimetype)

    def get_item(self):
        if self.item == None:
            upnp_id = self.storage_id
            upnp_parent_id = self.parent.get_id()
            url = self.store.urlbase + str(self.storage_id)
            self.item = DIDLLite.MusicTrack(upnp_id, upnp_parent_id, self.title)

            res = DIDLLite.Resource(url, 'http-get:*:%s:%s' % (self.mimetype,self.fourth_field))
            #res.duration = self.duration
            #res.size = self.get_size()
            self.item.res.append(res)
        return self.item

    def get_name(self):
        return self.title

    def get_path(self):
        return self.location  

    def get_size(self):
        return self.size
    
    def get_id (self):
        return self.storage_id


class AudioCDStore(AbstractBackendStore):

    logCategory = 'audiocd'

    implements = ['MediaServer']

    description = ('audioCD', '', None)

    options = [{'option':'version','text':'UPnP Version:','type':'int','default':2,'enum': (2,1),'help': 'the highest UPnP version this MediaServer shall support','level':'advance'},
       {'option':'uuid','text':'UUID Identifier:','type':'string','help':'the unique (UPnP) identifier for this MediaServer, usually automatically set','level':'advance'},    
       {'option':'device_name','text':'device name for audio CD:','type':'string', 'help':'device name containing the audio cd.'}
    ]

    disc_title = None
    cdrom = None

    def __init__(self, server, **kwargs):
        AbstractBackendStore.__init__(self, server, **kwargs)

        self.name = 'audio CD'
        self.device_name= kwargs.get('device_name',"/dev/cdom");

        threads.deferToThread(self.extractAudioCdInfo)
        
        # self.init_completed() # will be fired when the audio CD info is extracted


    def upnp_init(self):
        self.current_connection_id = None
        if self.server:
            self.server.connection_manager_server.set_variable(0, 'SourceProtocolInfo',
                        ['http-get:*:%s:%s' % (TRACK_MIMETYPE, TRACK_FOURTH_FIELD)],
                        default=True)
            self.server.content_directory_server.set_variable(0, 'SystemUpdateID', self.update_id)
            #self.server.content_directory_server.set_variable(0, 'SortCapabilities', '*')


    def extractAudioCdInfo (self):
        """ extract the CD info (album art + artist + tracks), and construct the UPnP items"""
        self.cdrom = DiscID.open(self.device_name)
        disc_id = DiscID.disc_id(self.cdrom)

        (query_status, query_info) = CDDB.query(disc_id)
        if query_status in (210, 211):
            query_info = query_info[0]
        (read_status, read_info) = CDDB.read(query_info['category'], query_info['disc_id'])

#        print query_info['title']
#        print disc_id[1]
#        for i in range(disc_id[1]):
#            print "Track %.02d: %s" % (i, read_info['TTITLE' + `i`])
            
        track_count = disc_id[1]
        disc_id = query_info['disc_id']
        self.disc_title = query_info['title'].encode('utf-8')
        tracks = {}
        for i in range(track_count):
            tracks[i+1] = read_info['TTITLE' + `i`].decode('ISO-8859-1').encode('utf-8')

        self.name = self.disc_title

        root_item = Container(None, self.disc_title)
        # we will sort the item by "track_number"
        def childs_sort(x,y):
            return cmp(x.track_number, y.track_number)
        root_item.sorting_method = childs_sort
        
        self.set_root_item(root_item)

        for number, title in tracks.items():
            item = TrackItem(self.device_name, number, "Unknown", title)
            external_id = "%s_%d" % (disc_id, number)
            root_item.add_child(item, external_id = external_id)

        self.info('Sharing audio CD %s' % self.disc_title)

        reactor.callLater(2,self.checkIfAudioCdStillPresent)
        self.init_completed()
        

    def  checkIfAudioCdStillPresent(self):
        try:
            disc_id = DiscID.disc_id(self.cdrom)
            reactor.callLater(2,self.checkIfAudioCdStillPresent)
        except:
            self.warning('audio CD %s ejected: closing UPnP server!' % self.disc_title)            
            self.server.coherence.remove_plugin(self.server)

        
    def __repr__(self):
        return self.__class__.__name__        
