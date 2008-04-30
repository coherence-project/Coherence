# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2005, Tim Potter <tpot@samba.org>
# Copyright 2006, Frank Scholz <coherence@beebits.net>

"""
TODO:

- use more XPath expressions in fromElement() methods

"""
import os
import string
from datetime import datetime

my_namespaces = {'http://purl.org/dc/elements/1.1/' : 'dc',
                 'urn:schemas-upnp-org:metadata-1-0/upnp/': 'upnp'
                 }
from coherence.extern.et import ET, namespace_map_update, ElementInterface
namespace_map_update(my_namespaces)

from coherence.upnp.core import utils

from coherence.upnp.core import dlna

from coherence import log

class Resources(list):

    """ a list of resources, always sorted after an append """

    def __init__(self, *args, **kwargs):
        list.__init__(self, *args, **kwargs)
        self.sort(cmp=self.p_sort)

    def append(self, value):
        list.append(self,value)
        self.sort(cmp=self.p_sort)

    def p_sort(self,x,y):
        """ we want the following order
            http-get is always at the beginning
            rtsp-rtp-udp the second
            anything else after that
        """
        if x.protocolInfo == None:
            return 1
        if y.protocolInfo == None:
            return -1

        x_protocol = x.protocolInfo.split(':')[0]
        y_protocol = y.protocolInfo.split(':')[0]

        x_protocol = x_protocol.lower()
        y_protocol = y_protocol.lower()
        if( x_protocol == y_protocol):
            return 0
        if(x_protocol == 'http-get'):
            return -1
        if(x_protocol == 'rtsp-rtp-udp' and y_protocol == 'http-get'):
            return 1
        if(x_protocol == 'rtsp-rtp-udp' and y_protocol != 'http-get'):
            return -1
        return 1

    def get_matching(self, local_protocol_infos, protocol_type = None):
        result = []
        if not isinstance(local_protocol_infos, list):
            local_protocol_infos = [local_protocol_infos]
        for res in self:
            #print "res", res.protocolInfo, res.data
            remote_protocol,remote_network,remote_content_format,_ = res.protocolInfo.split(':')
            #print "remote", remote_protocol,remote_network,remote_content_format
            if(protocol_type is not None and
               remote_protocol.lower() != protocol_type.lower()):
                continue
            for protocol_info in local_protocol_infos:
                local_protocol,local_network,local_content_format,_ = protocol_info.split(':')
                #print "local", local_protocol,local_network,local_content_format
                if((remote_protocol == local_protocol or
                    remote_protocol == '*' or
                    local_protocol == '*') and
                   (remote_network == local_network or
                    remote_network == '*' or
                    local_network == '*') and
                   (remote_content_format == local_content_format or
                    remote_content_format == '*' or
                    local_content_format == '*')):
                        #print result, res
                        result.append(res)
        return result

def classChooser(mimetype, sub=None):

    if mimetype == 'root':
        return Container
    if mimetype == 'item':
        return Item
    if mimetype == 'directory':
        if sub == 'music':
            return MusicAlbum
        return Container
    else:
        if string.find (mimetype,'image/') == 0:
            return Photo
        if string.find (mimetype,'audio/') == 0:
            if sub == 'music':       # FIXME: this is stupid
                return MusicTrack
            return AudioItem
        if string.find (mimetype,'video/') == 0:
            return VideoItem
        if mimetype == 'application/ogg':
            if sub == 'music':       # FIXME: this is stupid
                return MusicTrack
            return AudioItem
    return None

simple_dlna_tags = ('DLNA.ORG.PS=1',       # play speed parameter
                    'DLNA.ORG_CI=0',       # transcoded parameter
                    'DLNA.ORG_OP=01',      # operations parameter
                    'DLNA.ORG_FLAGS=01700000000000000000000000000000')


class Resource:
    """An object representing a resource."""

    def __init__(self, data=None, protocolInfo=None):
        self.data = data
        self.protocolInfo = protocolInfo
        self.bitrate = None
        self.size = None
        self.duration = None

        self.importUri = None

        if self.protocolInfo is not None:
            protocol,network,content_format,additional_info = self.protocolInfo.split(':')
            if additional_info == '*':
                if content_format == 'audio/mpeg':
                    additional_info = ';'.join(simple_dlna_tags+('DLNA.ORG_PN=MP3',))
                if content_format == 'image/jpeg':
                    additional_info = ';'.join(simple_dlna_tags+('DLNA.ORG_PN=JPEG_LRG',))
                if content_format == 'image/png':
                    additional_info = ';'.join(simple_dlna_tags+('DLNA.ORG_PN=PNG_LRG',))
                if content_format == 'video/mpeg':
                    additional_info = ';'.join(simple_dlna_tags+('DLNA.ORG_PN=MPEG_PS_PAL',))
                if content_format == 'video/mp4':
                    additional_info = ';'.join(simple_dlna_tags+('DLNA.ORG_PN=AVC_TS_BL_CIF15_AAC',))
                if content_format == 'video/x-msvideo':
                    additional_info = ';'.join(simple_dlna_tags+('DLNA.ORG_PN=MPEG4_P2_MP4_SP_AAC',))

                self.protocolInfo = ':'.join((protocol,network,content_format,additional_info))

    def toElement(self,**kwargs):

        root = ET.Element('res')
        if kwargs.get('upnp_client','') in ('XBox', 'PLAYSTATION3'):
            protocol,network,content_format,additional_info = self.protocolInfo.split(':')
            if content_format == 'video/x-msvideo':
                content_format = 'video/avi'
            if kwargs.get('upnp_client','') == 'XBox':
                """ we don't need the DLNA tags there,
                    and maybe it irritates that poor thing anyway
                """
                additional_info = '*'
            root.attrib['protocolInfo'] = ':'.join((protocol,network,content_format,additional_info))
        else:
            root.attrib['protocolInfo'] = self.protocolInfo
        root.text = self.data

        if self.bitrate is not None:
            root.attrib['bitrate'] = str(self.bitrate)

        if self.size is not None:
            root.attrib['size'] = str(self.size)

        if self.duration is not None:
            root.attrib['duration'] = self.duration

        if self.importUri is not None:
            root.attrib['importUri'] = self.importUri

        return root

    def fromElement(self, elt):
        self.protocolInfo = elt.attrib['protocolInfo']
        self.data = elt.text
        self.bitrate = elt.attrib.get('bitrate')
        self.size = elt.attrib.get('size')
        self.duration = elt.attrib.get('duration',None)
        self.importUri = elt.attrib.get('importUri',None)

    def toString(self,**kwargs):
        return ET.tostring(self.toElement(**kwargs),encoding='utf-8')

    @classmethod
    def fromString(cls, aString):
        instance = cls()
        elt = utils.parse_xml(aString)
        #elt = ElementTree(elt)
        instance.fromElement(elt.getroot())
        return instance

class Object(log.Loggable):
    """The root class of the entire content directory class heirachy."""

    logCategory = 'didllite'

    upnp_class = 'object'
    creator = None
    #res = None
    writeStatus = None
    date = None
    albumArtURI = None
    artist = None
    album = None
    originalTrackNumber=None

    refID = None
    server_uuid = None

    def __init__(self, id=None, parentID=None, title=None, restricted=False,
                       creator=None):
        self.id = id
        self.parentID = parentID
        self.title = title
        self.creator = creator
        self.restricted = restricted

    def checkUpdate(self):
        return self

    def toElement(self,**kwargs):

        root = ET.Element(self.elementName)

        if self.id == 1000:
            root.attrib['id'] = '0'
            ET.SubElement(root, 'dc:title').text = 'root'
        else:
            root.attrib['id'] = str(self.id)
            ET.SubElement(root, 'dc:title').text = self.title

        root.attrib['parentID'] = str(self.parentID)

        if(kwargs.get('upnp_client','') != 'XBox'):
            if self.refID:
                root.attrib['refID'] = str(self.refID)

        if kwargs.get('requested_id',None):
            if kwargs.get('requested_id') != root.attrib['id']:
                if(kwargs.get('upnp_client','') != 'XBox'):
                    root.attrib['refID'] = root.attrib['id']
                r_id = kwargs.get('requested_id')
                root.attrib['id'] = r_id
                r_id = r_id.split('@',1)
                try:
                    root.attrib['parentID'] = r_id[1]
                except IndexError:
                    pass
                self.info("Changing ID from %r to %r, with parentID %r", root.attrib['refID'], root.attrib['id'], root.attrib['parentID'])
        elif kwargs.get('parent_container',None):
            if(kwargs.get('parent_container') != '0' and
               kwargs.get('parent_container') != root.attrib['parentID']):
                if(kwargs.get('upnp_client','') != 'XBox'):
                    root.attrib['refID'] = root.attrib['id']
                root.attrib['id'] = '@'.join((root.attrib['id'],kwargs.get('parent_container')))
                root.attrib['parentID'] = kwargs.get('parent_container')
                self.info("Changing ID from %r to %r, with parentID from %r to %r", root.attrib['refID'], root.attrib['id'], root.attrib['parentID'],kwargs.get('parent_container'))


        if(isinstance(self, Container) and kwargs.get('upnp_client','') == 'XBox'):
            ET.SubElement(root, 'upnp:class').text = 'object.container.storageFolder'
        else:
            ET.SubElement(root, 'upnp:class').text = self.upnp_class

        if self.restricted:
            root.attrib['restricted'] = '1'
        else:
            root.attrib['restricted'] = '0'

        if self.creator is not None:
            ET.SubElement(root, 'dc:creator').text = self.creator

        if self.writeStatus is not None:
            ET.SubElement(root, 'upnp:writeStatus').text = self.writeStatus

        if self.date is not None:
            if isinstance(self.date, datetime):
                ET.SubElement(root, 'dc:date').text = self.date.isoformat()
            else:
                ET.SubElement(root, 'dc:date').text = self.date
        else:
            ET.SubElement(root, 'dc:date').text = utils.datefaker().isoformat()

        if self.albumArtURI is not None:
            e = ET.SubElement(root, 'upnp:albumArtURI')
            e.text = self.albumArtURI
            e.attrib['xmlns:dlna'] = 'urn:schemas-dlna-org:metadata-1-0'
            e.attrib['dlna:profileID'] = 'JPEG_TN'

        if self.artist is not None:
            ET.SubElement(root, 'upnp:artist').text = self.artist

        if self.originalTrackNumber is not None:
            ET.SubElement(root, 'upnp:originalTrackNumber').text = str(self.originalTrackNumber)

        if self.server_uuid is not None:
            ET.SubElement(root, 'upnp:server_uuid').text = self.server_uuid

        return root

    def toString(self,**kwargs):
        return ET.tostring(self.toElement(**kwargs),encoding='utf-8')

    def fromElement(self, elt):
        """
        TODO:
         * creator
         * writeStatus
        """
        self.elementName = elt.tag
        self.id = elt.attrib.get('id',None)
        self.parentID = elt.attrib.get('parentID',None)

        self.refID = elt.attrib.get('refID',None)

        if elt.attrib.get('restricted',None) in [1,'true','True','1','yes','Yes']:
            self.restricted = True
        else:
            self.restricted = False

        for child in elt.getchildren():
            if child.tag.endswith('title'):
                self.title = child.text
            elif child.tag.endswith('albumArtURI'):
                self.albumArtURI = child.text
            elif child.tag.endswith('originalTrackNumber'):
                self.originalTrackNumber = int(child.text)
            elif child.tag.endswith('artist'):
                self.artist = child.text
            elif child.tag.endswith('album'):
                self.album = child.text
            elif child.tag.endswith('class'):
                self.upnp_class = child.text
            elif child.tag.endswith('server_uuid'):
                self.server_uuid = child.text


    @classmethod
    def fromString(cls, data):
        instance = cls()
        elt = utils.parse_xml(data)
        #elt = ElementTree(elt)
        instance.fromElement(elt.getroot())
        return instance


class Item(Object):
    """A class used to represent atomic (non-container) content
    objects."""

    upnp_class = Object.upnp_class + '.item'
    elementName = 'item'
    refID = None

    def __init__(self, *args, **kwargs):
        Object.__init__(self, *args, **kwargs)
        self.res = Resources()

    def toElement(self,**kwargs):

        root = Object.toElement(self,**kwargs)

        if self.refID is not None:
            ET.SubElement(root, 'refID').text = self.refID

        for res in self.res:
            root.append(res.toElement(**kwargs))

        return root

    def fromElement(self, elt):
        Object.fromElement(self, elt)
        for child in elt.getchildren():
            if child.tag.endswith('refID'):
                self.refID = child.text
            elif child.tag.endswith('res'):
                res = Resource.fromString(ET.tostring(child))
                self.res.append(res)

class ImageItem(Item):
    upnp_class = Item.upnp_class + '.imageItem'

    description = None
    longDescription = None
    rating = None
    storageMedium = None
    publisher = None
    rights = None

    def toElement(self,**kwargs):
        root = Item.toElement(self,**kwargs)
        if self.description is not None:
            ET.SubElement(root, 'dc:description').text = self.description

        if self.longDescription is not None:
            ET.SubElement(root, 'upnp:longDescription').text = self.longDescription

        if self.rating is not None:
            ET.SubElement(root, 'upnp:rating').text = str(self.rating)

        if self.storageMedium is not None:
            ET.SubElement(root, 'upnp:storageMedium').text = self.storageMedium

        if self.publisher is not None:
            ET.SubElement(root, 'dc:publisher').text = self.contributor

        if self.rights is not None:
            ET.SubElement(root, 'dc:rights').text = self.rights

        return root

class Photo(ImageItem):
    upnp_class = ImageItem.upnp_class + '.photo'
    album = None

    def toElement(self,**kwargs):
        root = ImageItem.toElement(self,**kwargs)
        if self.album is not None:
            ET.SubElement(root, 'upnp:album').text = self.album
        return root

class AudioItem(Item):
    """A piece of content that when rendered generates some audio."""

    upnp_class = Item.upnp_class + '.audioItem'

    genre = None
    description = None
    longDescription = None
    publisher = None
    language = None
    relation = None
    rights = None

    valid_keys = ['genre', 'description', 'longDescription', 'publisher',
                  'langugage', 'relation', 'rights', 'albumArtURI']

    #@dlna.AudioItem
    def toElement(self,**kwargs):

        root = Item.toElement(self,**kwargs)

        if self.genre is not None:
            ET.SubElement(root, 'upnp:genre').text = self.genre

        if self.description is not None:
            ET.SubElement(root, 'dc:description').text = self.description

        if self.longDescription is not None:
            ET.SubElement(root, 'upnp:longDescription').text = \
                             self.longDescription

        if self.publisher is not None:
            ET.SubElement(root, 'dc:publisher').text = self.publisher

        if self.language is not None:
            ET.SubElement(root, 'dc:language').text = self.language

        if self.relation is not None:
            ET.SubElement(root, 'dc:relation').text = self.relation

        if self.rights is not None:
            ET.SubElement(root, 'dc:rights').text = self.rights

        return root

    def fromElement(self, elt):
        Item.fromElement(self, elt)
        for child in elt.getchildren():
            tag = child.tag
            val = child.text
            if tag in self.valid_keys:
                setattr(self, tag, val)


class MusicTrack(AudioItem):
    """A discrete piece of audio that should be interpreted as music."""

    upnp_class = AudioItem.upnp_class + '.musicTrack'

    album = None
    originalTrackNumber = None
    playlist = None
    storageMedium = None
    contributor = None

    def toElement(self,**kwargs):

        root = AudioItem.toElement(self,**kwargs)

        if self.album is not None:
            ET.SubElement(root, 'upnp:album').text = self.album

        if self.originalTrackNumber is not None:
            ET.SubElement(root, 'upnp:originalTrackNumber').text = \
                             str(self.originalTrackNumber)

        if self.playlist is not None:
            ET.SubElement(root, 'upnp:playlist').text = self.playlist

        if self.storageMedium is not None:
            ET.SubElement(root, 'upnp:storageMedium').text = self.storageMedium

        if self.contributor is not None:
            ET.SubElement(root, 'dc:contributor').text = self.contributor

        return root

class AudioBroadcast(AudioItem):
    upnp_class = AudioItem.upnp_class + '.audioBroadcast'

class AudioBook(AudioItem):
    upnp_class = AudioItem.upnp_class + '.audioBook'

class VideoItem(Item):
    upnp_class = Item.upnp_class + '.videoItem'

class Movie(VideoItem):
    upnp_class = VideoItem.upnp_class + '.movie'

class VideoBroadcast(VideoItem):
    upnp_class = VideoItem.upnp_class + '.videoBroadcast'

class MusicVideoClip(VideoItem):
    upnp_class = VideoItem.upnp_class + '.musicVideoClip'

class PlaylistItem(Item):
    upnp_class = Item.upnp_class + '.playlistItem'

class TextItem(Item):
    upnp_class = Item.upnp_class + '.textItem'

class Container(Object):
    """An object that can contain other objects."""

    upnp_class = Object.upnp_class + '.container'

    elementName = 'container'
    childCount = None
    createClass = None
    searchable = None

    def __init__(self, id=None, parentID=None, title=None,
                 restricted = False, creator = None):
        Object.__init__(self, id, parentID, title, restricted, creator)
        self.searchClass = []

    def toElement(self,**kwargs):

        root = Object.toElement(self,**kwargs)

        if self.childCount is not None:
            root.attrib['childCount'] = str(self.childCount)

        if self.createClass is not None:
            ET.SubElement(root, 'upnp:createclass').text = self.createClass

        if not isinstance(self.searchClass, (list, tuple)):
            self.searchClass = [self.searchClass]
        for i in self.searchClass:
            sc = ET.SubElement(root, 'upnp:searchClass')
            sc.attrib['includeDerived'] = '1'
            sc.text = i

        if self.searchable is not None:
            if self.searchable in (1, '1', True, 'true', 'True'):
                root.attrib['searchable'] = '1'
            else:
                root.attrib['searchable'] = '0'

        return root

    def fromElement(self, elt):
        Object.fromElement(self, elt)
        v = elt.attrib.get('childCount',None)
        if v is not None:
            self.childCount = int(v)
        #self.searchable = int(elt.attrib.get('searchable','0'))
        self.searchable = elt.attrib.get('searchable','0') in [1,'True','true','1']
        self.searchClass = []
        for child in elt.getchildren():
            if child.tag.endswith('createclass'):
                self.createClass = child.text
            elif child.tag.endswith('searchClass'):
                self.searchClass.append(child.text)


class Person(Container):
    upnp_class = Container.upnp_class + '.person'

class MusicArtist(Person):
    upnp_class = Person.upnp_class + '.musicArtist'

class PlaylistContainer(Container):
    upnp_class = Container.upnp_class + '.playlistContainer'

class Album(Container):
    upnp_class = Container.upnp_class + '.album'

class MusicAlbum(Album):
    upnp_class = Album.upnp_class + '.musicAlbum'

class PhotoAlbum(Album):
    upnp_class = Album.upnp_class + '.photoAlbum'

class Genre(Container):
    upnp_class = Container.upnp_class + '.genre'

class MusicGenre(Genre):
    upnp_class = Genre.upnp_class + '.musicGenre'

class MovieGenre(Genre):
    upnp_class = Genre.upnp_class + '.movieGenre'

class StorageSystem(Container):
    upnp_class = Container.upnp_class + '.storageSystem'

class StorageVolume(Container):
    upnp_class = Container.upnp_class + '.storageVolume'

class StorageFolder(Container):
    upnp_class = Container.upnp_class + '.storageFolder'

class DIDLElement(ElementInterface,log.Loggable):

    logCategory = 'didllite'

    def __init__(self, upnp_client='', parent_container=None, requested_id=None):
        ElementInterface.__init__(self, 'DIDL-Lite', {})
        self.attrib['xmlns'] = 'urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/'
        self.attrib['xmlns:dc'] = 'http://purl.org/dc/elements/1.1/'
        self.attrib['xmlns:upnp'] = 'urn:schemas-upnp-org:metadata-1-0/upnp/'
        self.attrib['xmlns:dlna'] = 'urn:schemas-dlna-org:metadata-1-0'
        self.attrib['xmlns:pv'] = 'http://www.pv.com/pvns/'
        self._items = []
        self.upnp_client = upnp_client
        self.parent_container = parent_container
        self.requested_id = requested_id


    def addContainer(self, id, parentID, title, restricted = False):
        e = Container(id, parentID, title, restricted, creator = '')
        self.append(e.toElement())

    def addItem(self, item):
        self.append(item.toElement(upnp_client=self.upnp_client,
                                   parent_container=self.parent_container,
                                   requested_id=self.requested_id))
        self._items.append(item)

    def numItems(self):
        return len(self)

    def getItems(self):
        return self._items

    def toString(self):
        """ sigh - having that optional preamble here
            breaks some of the older ContentDirectoryClients
        """
        #preamble = """<?xml version="1.0" encoding="utf-8"?>"""
        #return preamble + ET.tostring(self,encoding='utf-8')
        return ET.tostring(self,encoding='utf-8')

    def get_upnp_class(self,name):
        try:
            return upnp_classes[name]()
        except KeyError:
            self.warning("upnp_class %r not found, trying fallback", name)
            parts = name.split('.')
            parts.pop()
            while len(parts) > 1:
                try:
                    return upnp_classes['.'.join(parts)]()
                except KeyError:
                    parts.pop()

        self.warning("WTF - no fallback for upnp_class %r found ?!?", name)
        return None

    @classmethod
    def fromString(cls, aString):
        instance = cls()
        elt = utils.parse_xml(aString, 'utf-8')
        elt = elt.getroot()
        for node in elt.getchildren():
            upnp_class_name =  node.findtext('{%s}class' % 'urn:schemas-upnp-org:metadata-1-0/upnp/')
            upnp_class = instance.get_upnp_class(upnp_class_name)
            new_node = upnp_class.fromString(ET.tostring(node))
            instance.addItem(new_node)
        return instance

upnp_classes = {'object': Object,
                'object.item': Item,
                'object.item.imageItem': ImageItem,
                'object.item.imageItem.photo': Photo,
                'object.item.audioItem': AudioItem,
                'object.item.audioItem.musicTrack': MusicTrack,
                'object.item.audioItem.audioBroadcast': AudioBroadcast,
                'object.item.audioItem.audioBook': AudioBook,
                'object.item.videoItem': VideoItem,
                'object.item.videoItem.movie': Movie,
                'object.item.videoItem.videoBroadcast': VideoBroadcast,
                'object.item.videoItem.musicVideoClip': MusicVideoClip,
                'object.item.playlistItem': PlaylistItem,
                'object.item.textItem': TextItem,
                'object.container': Container,
                'object.container.person': Person,
                'object.container.person.musicArtist': MusicArtist,
                'object.container.playlistContainer': PlaylistContainer,
                'object.container.album': Album,
                'object.container.album.musicAlbum': MusicAlbum,
                'object.container.album.photoAlbum': PhotoAlbum,
                'object.container.genre': Genre,
                'object.container.genre.musicGenre': MusicGenre,
                'object.container.genre.movieGenre': MovieGenre,
                'object.container.storageSystem': StorageSystem,
                'object.container.storageVolume': StorageVolume,
                'object.container.storageFolder': StorageFolder,
}


if __name__ == '__main__':

    res = Resources()
    res.append(Resource('1','file:*:*:*'))
    res.append(Resource('2','rtsp-rtp-udp:*:*:*'))
    res.append(Resource('3',None))
    res.append(Resource('4','internal:*:*:*'))
    res.append(Resource('5','http-get:*:*:*'))
    res.append(Resource('6','something:*:*:*'))
    res.append(Resource('7','http-get:*:*:*'))

    for r in res:
        print r.data, r.protocolInfo