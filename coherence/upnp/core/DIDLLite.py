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

def classChooser(mimetype, sub=None):

    if mimetype == 'root':
        return StorageFolder
    if mimetype == 'item':
        return Item
    if mimetype == 'directory':
        return StorageFolder
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


class Resource:
    """An object representing a resource."""

    def __init__(self, data=None, protocolInfo=None):
        self.data = data
        self.protocolInfo = protocolInfo
        self.bitrate = None
        self.size = None
        self.duration = None

        self.importUri = None

    def toElement(self):

        root = ET.Element('res')
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

    def toString(self):
        return ET.tostring(self.toElement())

    @classmethod
    def fromString(cls, aString):
        instance = cls()
        elt = utils.parse_xml(aString)
        #elt = ElementTree(elt)
        instance.fromElement(elt.getroot())
        return instance

class Object:
    """The root class of the entire content directory class heirachy."""

    upnp_class = 'object'
    creator = None
    #res = None
    writeStatus = None
    date = None

    def __init__(self, id=None, parentID=None, title=None, restricted=False,
                       creator=None):
        self.res = []
        self.id = id
        self.parentID = parentID
        self.title = title
        self.creator = creator
        self.restricted = restricted

    def checkUpdate(self):
        return self

    def toElement(self):

        root = ET.Element(self.elementName)

        root.attrib['id'] = str(self.id)
        root.attrib['parentID'] = str(self.parentID)
        ET.SubElement(root, 'dc:title').text = self.title
        ET.SubElement(root, 'upnp:class').text = self.upnp_class

        if self.restricted:
            root.attrib['restricted'] = 'true'
        else:
            root.attrib['restricted'] = 'false'

        if self.creator is not None:
            ET.SubElement(root, 'dc:creator').text = self.creator

        for res in self.res:
            root.append(res.toElement())

        if self.writeStatus is not None:
            ET.SubElement(root, 'upnp:writeStatus').text = self.writeStatus

        if self.date is not None:
            if isinstance(self.date, datetime):
                ET.SubElement(root, 'dc:date').text = self.date.isoformat()
            else:
                ET.SubElement(root, 'dc:date').text = self.date
        else:
            ET.SubElement(root, 'dc:date').text = utils.datefaker().isoformat()

        return root

    def toString(self):
        return ET.tostring(self.toElement())

    def fromElement(self, elt):
        """
        TODO:
         * creator
         * writeStatus
        """
        self.elementName = elt.tag
        self.id = elt.attrib['id']
        self.parentID = elt.attrib['parentID']
        if elt.attrib['restricted'] in ['true','True','1','yes','Yes']:
            self.restricted = True
        else:
            self.restricted = False

        for child in elt.getchildren():
            if child.tag.endswith('title'):
                self.title = child.text
            elif child.tag.endswith('class'):
                self.upnp_class = child.text
            elif child.tag.endswith('res'):
                res = Resource.fromString(ET.tostring(child))
                self.res.append(res)


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

    def toElement(self):

        root = Object.toElement(self)

        if self.refID is not None:
            ET.SubElement(root, 'refID').text = self.refID

        return root

    def fromElement(self, elt):
        Object.fromElement(self, elt)
        for child in elt.getchildren():
            if child.tag.endswith('refID'):
                self.refID = child.text
                break


class ImageItem(Item):
    upnp_class = Item.upnp_class + '.imageItem'

    description = None
    longDescription = None
    rating = None
    storageMedium = None
    publisher = None
    rights = None

    def toElement(self):
        root = Item.toElement(self)
        if self.description is not None:
            ET.SubElement(root, 'dc:description').text = self.description

        if self.longDescription is not None:
            ET.SubElement(root, 'upnp:longDescription').text = self.longDescription

        if self.rating is not None:
            ET.SubElement(root, 'upnp:rating').text = self.rating

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

    def toElement(self):
        root = ImageItem.toElement(self)
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
                  'langugage', 'relation', 'rights']

    def toElement(self):

        root = Item.toElement(self)

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

    artist = None
    album = None
    albumArtURI = None
    originalTrackNumber = None
    playlist = None
    storageMedium = None
    contributor = None

    def toElement(self):

        root = AudioItem.toElement(self)

        if self.artist is not None:
            ET.SubElement(root, 'upnp:artist').text = self.artist

        if self.album is not None:
            ET.SubElement(root, 'upnp:album').text = self.album

        if self.albumArtURI is not None:
            ET.SubElement(root, 'upnp:albumArtURI').text = self.albumArtURI

        if self.originalTrackNumber is not None:
            ET.SubElement(root, 'upnp:originalTrackNumber').text = \
                             self.originalTrackNumber

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
    childCount = 0
    createClass = None
    searchable = None

    def __init__(self, id=None, parentID=None, title=None,
                 restricted = 0, creator = None):
        Object.__init__(self, id, parentID, title, restricted, creator)
        self.searchClass = []

    def toElement(self):

        root = Object.toElement(self)

        root.attrib['childCount'] = str(self.childCount)

        if self.createClass is not None:
            ET.SubElement(root, 'upnp:createclass').text = self.createClass

        if not isinstance(self.searchClass, (list, tuple)):
            self.searchClass = ['searchClass']
        for i in self.searchClass:
            ET.SubElement(root, 'upnp:searchclass').text = i

        if self.searchable is not None:
            root.attrib['searchable'] = str(self.searchable)

        return root

    def fromElement(self, elt):
        Object.fromElement(self, elt)
        self.childCount = int(elt.attrib.get('childCount','0'))
        #self.searchable = int(elt.attrib.get('searchable','0'))
        self.searchable = elt.attrib.get('searchable','0') in ['True','true','1']
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

class DIDLElement(ElementInterface):
    def __init__(self):
        ElementInterface.__init__(self, 'DIDL-Lite', {})
        self.attrib['xmlns'] = 'urn:schemas-upnp-org:metadata-1-0/DIDL-Lite'
        self.attrib['xmlns:dc'] = 'http://purl.org/dc/elements/1.1/'
        self.attrib['xmlns:upnp'] = 'urn:schemas-upnp-org:metadata-1-0/upnp'
        self._items = []

    def addContainer(self, id, parentID, title, restricted = False):
        e = Container(id, parentID, title, restricted, creator = '')
        self.append(e.toElement())

    def addItem(self, item):
        self.append(item.toElement())
        self._items.append(item)

    def numItems(self):
        return len(self)

    def getItems(self):
        return self._items

    def toString(self):
        return ET.tostring(self)

    @classmethod
    def fromString(cls, aString):
        instance = cls()
        elt = utils.parse_xml(aString, 'utf-8')
        elt = elt.getroot()
        for node in elt.getchildren():
            upnp_class_name = node.tag[node.tag.find('}')+1:].title()
            upnp_class = eval(upnp_class_name)
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
