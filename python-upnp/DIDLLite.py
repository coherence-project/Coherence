# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2005, Tim Potter <tpot@samba.org>

"""
TODO:

- use cElementTree instead of elementtree
- use more XPath expressions in fromElement() methods

"""

from elementtree.ElementTree import ElementTree, Element, SubElement, fromstring, tostring, _ElementInterface
import elementtree
import utils

my_namespaces = {'http://purl.org/dc/elements/1.1/' : 'dc',
                 'urn:schemas-upnp-org:metadata-1-0/upnp/': 'upnp'
                 }
elementtree.ElementTree._namespace_map.update(my_namespaces)

class Resource:
    """An object representing a resource."""

    def __init__(self, data=None, protocolInfo=None):
        self.data = data
        self.protocolInfo = protocolInfo
        self.bitrate = None
        self.size = None

    def toElement(self):

        root = Element('res')
        root.attrib['protocolInfo'] = self.protocolInfo
        root.text = self.data

        if self.bitrate is not None:
            root.attrib['bitrate'] = str(self.bitrate)

        if self.size is not None:
            root.attrib['size'] = str(self.size)

        return root

    def fromElement(self, elt):
        self.protocolInfo = elt.attrib['protocolInfo']
        self.data = elt.text
        self.bitrate = elt.attrib.get('bitrate')
        self.size = elt.attrib.get('size')


    def toString(self):
        return tostring(self.toElement())

    @classmethod
    def fromString(cls, aString):
        instance = cls()
        elt = utils.parse_xml(aString)
        #elt = ElementTree(elt)
        instance.fromElement(elt.getroot())
        return instance

class Object:
    """The root class of the entire content directory class heirachy."""

    klass = 'object'
    creator = None
    #res = None
    writeStatus = None

    def __init__(self, id=None, parentID=None, title=None, restricted = False,
                 creator = None):
        self.res = []
        self.id = id
        self.parentID = parentID
        self.title = title
        self.creator = creator

        if restricted:
            self.restricted = 'true'
        else:
            self.restricted = 'false'

    def toElement(self):

        root = Element(self.elementName)

        root.attrib['id'] = self.id
        root.attrib['parentID'] = self.parentID
        SubElement(root, 'dc:title').text = self.title
        SubElement(root, 'upnp:class').text = self.klass

        root.attrib['restricted'] = self.restricted

        if self.creator is not None:
            SubElement(root, 'dc:creator').text = self.creator

        for res in self.res:
            root.append(res.toElement())

        if self.writeStatus is not None:
            SubElement(root, 'upnp:writeStatus').text = self.writeStatus

        return root

    def toString(self):
        return tostring(self.toElement())

    def fromElement(self, elt):
        """
        TODO:
         * creator
         * writeStatus
        """
        self.elementName = elt.tag
        self.id = elt.attrib['id']
        self.parentID = elt.attrib['parentID']
        self.restricted = elt.attrib['restricted']

        for child in elt.getchildren():
            if child.tag.endswith('title'):
                self.title = child.text
            elif child.tag.endswith('class'):
                self.klass = child.text
            elif child.tag.endswith('res'):
                res = Resource.fromString(tostring(child))
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

    klass = Object.klass + '.item'
    elementName = 'item'
    refID = None

    def toElement(self):

        root = Object.toElement(self)

        if self.refID is not None:
            SubElement(root, 'refID').text = self.refID

        return root

    def fromElement(self, elt):
        Object.fromElement(self, elt)
        for child in elt.getchildren():
            if child.tag.endswith('refID'):
                self.refID = child.text
                break


class ImageItem(Item):
    klass = Item.klass + '.imageItem'

class Photo(ImageItem):
    klass = ImageItem.klass + '.photo'

class AudioItem(Item):
    """A piece of content that when rendered generates some audio."""

    klass = Item.klass + '.audioItem'

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
            SubElement(root, 'upnp:genre').text = self.genre

        if self.description is not None:
            SubElement(root, 'dc:description').text = self.description

        if self.longDescription is not None:
            SubElement(root, 'upnp:longDescription').text = \
                             self.longDescription

        if self.publisher is not None:
            SubElement(root, 'dc:publisher').text = self.publisher

        if self.language is not None:
            SubElement(root, 'dc:language').text = self.language

        if self.relation is not None:
            SubElement(root, 'dc:relation').text = self.relation

        if self.rights is not None:
            SubElement(root, 'dc:rights').text = self.rights

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

    klass = AudioItem.klass + '.musicTrack'

    artist = None
    album = None
    originalTrackNumber = None
    playlist = None
    storageMedium = None
    contributor = None
    date = None

    def toElement(self):

        root = AudioItem.toElement(self)

        if self.artist is not None:
            SubElement(root, 'upnp:artist').text = self.artist

        if self.album is not None:
            SubElement(root, 'upnp:album').text = self.album

        if self.originalTrackNumber is not None:
            SubElement(root, 'upnp:originalTrackNumber').text = \
                             self.originalTrackNumber

        if self.playlist is not None:
            SubElement(root, 'upnp:playlist').text = self.playlist

        if self.storageMedium is not None:
            SubElement(root, 'upnp:storageMedium').text = self.storageMedium

        if self.contributor is not None:
            SubElement(root, 'dc:contributor').text = self.contributor

        if self.date is not None:
            SubElement(root, 'dc:date').text = self.date

        return root

class AudioBroadcast(AudioItem):
    klass = AudioItem.klass + '.audioBroadcast'

class AudioBook(AudioItem):
    klass = AudioItem.klass + '.audioBook'

class VideoItem(Item):
    klass = Item.klass + '.videoItem'

class Movie(VideoItem):
    klass = VideoItem.klass + '.movie'

class VideoBroadcast(VideoItem):
    klass = VideoItem.klass + '.videoBroadcast'

class MusicVideoClip(VideoItem):
    klass = VideoItem.klass + '.musicVideoClip'

class PlaylistItem(Item):
    klass = Item.klass + '.playlistItem'

class TextItem(Item):
    klass = Item.klass + '.textItem'

class Container(Object):
    """An object that can contain other objects."""

    klass = Object.klass + '.container'

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
            SubElement(root, 'upnp:createclass').text = self.createClass

        if not isinstance(self.searchClass, (list, tuple)):
            self.searchClass = ['searchClass']
        for i in self.searchClass:
            SubElement(root, 'upnp:searchclass').text = i

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
    klass = Container.klass + '.person'

class MusicArtist(Person):
    klass = Person.klass + '.musicArtist'

class PlaylistContainer(Container):
    klass = Container.klass + '.playlistContainer'

class Album(Container):
    klass = Container.klass + '.album'

class MusicAlbum(Album):
    klass = Album.klass + '.musicAlbum'

class PhotoAlbum(Album):
    klass = Album.klass + '.photoAlbum'

class Genre(Container):
    klass = Container.klass + '.genre'

class MusicGenre(Genre):
    klass = Genre.klass + '.musicGenre'

class MovieGenre(Genre):
    klass = Genre.klass + '.movieGenre'

class StorageSystem(Container):
    klass = Container.klass + '.storageSystem'

class StorageVolume(Container):
    klass = Container.klass + '.storageVolume'

class StorageFolder(Container):
    klass = Container.klass + '.storageFolder'

class DIDLElement(_ElementInterface):
    def __init__(self):
        _ElementInterface.__init__(self, 'DIDL-Lite', {})
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
        return tostring(self)

    @classmethod
    def fromString(cls, aString):
        instance = cls()
        elt = utils.parse_xml(aString, 'utf-8')
        elt = elt.getroot()
        for node in elt.getchildren():
            klass_name = node.tag[node.tag.find('}')+1:].title()
            klass = eval(klass_name)
            new_node = klass.fromString(tostring(node))
            instance.addItem(new_node)
        return instance
