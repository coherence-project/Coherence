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
import urllib
from datetime import datetime

DC_NS = 'http://purl.org/dc/elements/1.1/'
UPNP_NS = 'urn:schemas-upnp-org:metadata-1-0/upnp/'

my_namespaces = { DC_NS: 'dc',
                 UPNP_NS: 'upnp'
                 }
from coherence.extern.et import ET, namespace_map_update, ElementInterface
namespace_map_update(my_namespaces)

from coherence.upnp.core import utils

from coherence.upnp.core import dlna

from coherence import log


def qname(tag,ns=''):
    if len(ns) == 0:
        return tag
    return "{%s}%s" % (ns,tag)


def is_audio(mimetype):
    """ checks for type audio,
        expects a mimetype or an UPnP
        protocolInfo
    """
    test = mimetype.split(':')
    if len(test) == 4:
        mimetype = test[2]
    if mimetype == 'application/ogg':
        return True
    if mimetype.startswith('audio/'):
        return True
    return False

def is_video(mimetype):
    """ checks for type video,
        expects a mimetype or an UPnP
        protocolInfo
    """
    test = mimetype.split(':')
    if len(test) == 4:
        mimetype = test[2]
    if mimetype.startswith('video/'):
        return True
    return False

def is_image(mimetype):
    """ checks for type image,
        expects a mimetype or an UPnP
        protocolInfo
    """
    test = mimetype.split(':')
    if len(test) == 4:
        mimetype = test[2]
    if mimetype.startswith('image/'):
        return True
    return False

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
            if res.importUri != None:
                continue
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
                   (remote_content_format.startswith(local_content_format) or
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
        if mimetype == 'application/x-flac':
            if sub == 'music':       # FIXME: this is stupid
                return MusicTrack
            return AudioItem
    return None

simple_dlna_tags = ['DLNA.ORG_OP=01',      # operations parameter
                    'DLNA.ORG_PS=1',       # play speed parameter
                    'DLNA.ORG_CI=0',       # transcoded parameter
                    'DLNA.ORG_FLAGS=01100000000000000000000000000000']

def build_dlna_additional_info(content_format,does_playcontainer=False):
    additional_info = ['*']
    if content_format == 'audio/mpeg':
        additional_info = ['DLNA.ORG_PN=MP3']+simple_dlna_tags
    if content_format == 'audio/ms-wma':
        additional_info = ['DLNA.ORG_PN=WMABASE']+simple_dlna_tags
    if content_format == 'image/jpeg':
        dlna_tags = simple_dlna_tags[:]
        dlna_tags[3] = 'DLNA.ORG_FLAGS=00900000000000000000000000000000'
        additional_info = ['DLNA.ORG_PN=JPEG_LRG']+dlna_tags
    if content_format == 'image/png':
        dlna_tags = simple_dlna_tags[:]
        dlna_tags[3] = 'DLNA.ORG_FLAGS=00900000000000000000000000000000'
        additional_info = ['DLNA.ORG_PN=PNG_LRG']+dlna_tags
    if content_format == 'video/mpeg':
        additional_info = ['DLNA.ORG_PN=MPEG_PS_PAL']+simple_dlna_tags
    if content_format == 'video/mpegts':
        additional_info = ['DLNA.ORG_PN=MPEG_TS_PAL']+simple_dlna_tags
        content_format = 'video/mpeg'
    if content_format in ['video/mp4','video/x-m4a']:
        additional_info = ['DLNA.ORG_PN=AVC_TS_BL_CIF15_AAC']+simple_dlna_tags
    if content_format in ['video/x-msvideo','video/avi','video/divx']:
        #additional_info = ';'.join(['DLNA.ORG_PN=MPEG4_P2_MP4_SP_AAC']+simple_dlna_tags)
        additional_info = ['*']
    if content_format == 'video/x-ms-wmv':
        additional_info = ['DLNA.ORG_PN=WMV_BASE']+simple_dlna_tags
    if content_format == '*':
        additional_info = simple_dlna_tags

    if does_playcontainer == True:
        i = 0
        for part in additional_info:
            if part.startswith('DLNA.ORG_FLAGS'):
                _,bits = part.split('=')
                bits = int(bits,16)
                bits |=  0x10000000000000000000000000000000
                additional_info[i] = 'DLNA.ORG_FLAGS=%.32x' % bits
                break
            i += 1
    return ';'.join(additional_info)


class Resource(object):
    """An object representing a resource."""

    def __init__(self, data=None, protocolInfo=None):
        self.data = data
        self.protocolInfo = protocolInfo
        self.bitrate = None
        self.size = None
        self.duration = None

        self.nrAudioChannels = None
        self.resolution = None

        self.importUri = None

        if self.protocolInfo is not None:
            protocol,network,content_format,additional_info = self.protocolInfo.split(':')
            if additional_info == '*':
                self.protocolInfo = ':'.join((protocol,network,content_format,build_dlna_additional_info(content_format)))
            elif additional_info == '#':
                self.protocolInfo = ':'.join((protocol,network,content_format,'*'))

    def get_additional_info(self,upnp_client=None):
        protocol,network,content_format,additional_info = self.protocolInfo.split(':')
        if upnp_client is not None:
            if upnp_client.hasTag('NO_DLNA_ADDITIONAL_INFO'):
                """ we don't need the DLNA tags there,
                    and maybe they irritate these poor things anyway
                """
                additional_info = '*'
            elif upnp_client.hasValue("dlna-additional-info-%s" % content_format):
                    additional_info = upnp_client.getValue("dlna-additional-info-%s" % content_format)
            elif upnp_client.hasValue("dlna-additional-info-audio") and is_audio(content_format):
                    additional_info = upnp_client.getValue("dlna-additional-info-audio")
            elif upnp_client.hasValue("dlna-additional-info-image") and is_image(content_format):
                    additional_info = upnp_client.getValue("dlna-additional-info-image")
            elif upnp_client.hasValue("dlna-additional-info-video") and is_video(content_format):
                    additional_info = upnp_client.getValue("dlna-additional-info-video")

        a_list = additional_info.split(';')
        for part in a_list:
            if part == 'DLNA.ORG_PS=1':
                a_list.remove(part)
                break
        additional_info = ';'.join(a_list)
        return additional_info

    def toElement(self,**kwargs):
        root = ET.Element('res')
        upnp_client=kwargs.get('upnp_client',None)
        protocol,network,content_format,additional_info = self.protocolInfo.split(':')

        # change content_format mimetype if needed by the client device
        if upnp_client is not None and upnp_client.hasValue("forced-mimetype-%s" % content_format):
            new_content_format = upnp_client.getValue("forced-mimetype-%s" % content_format)
            #print "Force mimetype %s to %s" % (content_format, new_content_format)
            content_format = new_content_format
            
        additional_info = self.get_additional_info(upnp_client=upnp_client)
        root.attrib['protocolInfo'] = ':'.join((protocol,network,content_format,additional_info))

        root.text = self.data

        if self.bitrate is not None:
            root.attrib['bitrate'] = str(self.bitrate)

        if self.size is not None:
            root.attrib['size'] = str(self.size)

        if self.duration is not None:
            root.attrib['duration'] = self.duration

        if self.nrAudioChannels is not None:
            root.attrib['nrAudioChannels'] = self.nrAudioChannels

        if self.resolution is not None:
            root.attrib['resolution'] = self.resolution

        if self.importUri is not None:
            root.attrib['importUri'] = self.importUri


        return root

    def fromElement(self, elt):
        self.protocolInfo = elt.attrib['protocolInfo']
        self.data = elt.text
        self.bitrate = elt.attrib.get('bitrate')
        self.size = elt.attrib.get('size')
        self.duration = elt.attrib.get('duration',None)
        self.resolution = elt.attrib.get('resolution',None)
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

    def transcoded(self,profile):
        protocol,network,content_format,additional_info = self.protocolInfo.split(':')
        dlna_tags = simple_dlna_tags[:]
        #dlna_tags[1] = 'DLNA.ORG_OP=00'
        dlna_tags[2] = 'DLNA.ORG_CI=1'
        if profile == 'mp3':
            if content_format == 'audio/mpeg':
                return None
            content_format='audio/mpeg'
            dlna_pn = 'DLNA.ORG_PN=MP3'
        elif profile == 'lpcm':
            dlna_pn = 'DLNA.ORG_PN=LPCM'
            content_format='audio/L16;rate=44100;channels=2'
        elif profile == 'mpegts':
            if content_format == 'video/mpeg':
                return None
            dlna_pn = 'DLNA.ORG_PN=MPEG_PS_PAL' # 'DLNA.ORG_PN=MPEG_TS_SD_EU' # FIXME - don't forget HD
            content_format='video/mpeg'
        else:
            return None

        additional_info = ';'.join([dlna_pn]+dlna_tags)
        new_protocol_info = ':'.join((protocol,network,content_format,additional_info))

        new_res = Resource(self.data+'/transcoded/%s' % profile,
                        new_protocol_info)
        new_res.size = None
        new_res.duration = self.duration
        new_res.resolution = self.resolution
        return new_res


class PlayContainerResource(Resource):
    """An object representing a DLNA playcontainer resource."""

    def __init__(self, udn, sid='urn:upnp-org:serviceId:ContentDirectory',
                            cid=None,
                            fid=None,
                            fii=0,
                            sc='',md=0,
                            protocolInfo=None):

        Resource.__init__(self)
        if cid == None:
            raise AttributeError('missing Container Id')
        if fid == None:
            raise AttributeError('missing first Child Id')
        self.protocolInfo = protocolInfo

        args = ['sid=' + urllib.quote(sid),
                'cid=' + urllib.quote(str(cid)),
                'fid=' + urllib.quote(str(fid)),
                'fii=' + urllib.quote(str(fii)),
                'sc=' + urllib.quote(''),
                'md=' + urllib.quote(str(0))]

        self.data = 'dlna-playcontainer://' + urllib.quote(str(udn)) \
                                            + '?' + '&'.join(args)


        if self.protocolInfo == None:
            self.protocolInfo = 'http-get:*:*:*'


class Object(log.Loggable):
    """The root class of the entire content directory class heirachy."""

    logCategory = 'didllite'

    upnp_class = 'object'
    creator = None
    restricted = False
    res = None
    writeStatus = None
    date = None
    albumArtURI = None
    artist = None
    genre = None
    genres = None
    album = None
    originalTrackNumber=None

    description = None
    longDescription = None

    refID = None
    server_uuid = None

    def __init__(self, id=None, parentID=None, title=None, restricted=False,
                       creator=None):
        self.id = id
        self.parentID = parentID
        self.title = title
        self.creator = creator
        self.restricted = restricted
        self.res = Resources()

    def checkUpdate(self):
        return self

    def toElement(self,**kwargs):

        root = ET.Element(self.elementName)

        #if self.id == 1000:
        #    root.attrib['id'] = '0'
        #    ET.SubElement(root, 'dc:title').text = 'root'
        #else:
        #    root.attrib['id'] = str(self.id)
        #    ET.SubElement(root, 'dc:title').text = self.title

        root.attrib['id'] = str(self.id)
        ET.SubElement(root, qname('title',DC_NS)).text = self.title

        #if self.title != None:
        #    ET.SubElement(root, 'dc:title').text = self.title
        #else:
        #    ET.SubElement(root, 'dc:title').text = 'root'

        root.attrib['parentID'] = str(self.parentID)

        if self.refID:
            if (kwargs.has_key('upnp_client') and kwargs.get('upnp_client').hasTag('NO_REF_ID')):
                # do nothing with refID
                pass
            else:
                root.attrib['refID'] = str(self.refID)

        if kwargs.get('requested_id',None):
            if kwargs.get('requested_id') == '0':
                t = root.find(qname('title',DC_NS))
                t.text = 'root'
            #if kwargs.get('requested_id') != '0' and kwargs.get('requested_id') != root.attrib['id']:
            if kwargs.get('requested_id') != root.attrib['id']:
                if(kwargs.has_key('upnp_client') and kwargs.get('upnp_client').hasTag('NO_REF_ID')):
                    # do nothing with refID
                    pass
                else:
                    root.attrib['refID'] = root.attrib['id']
                r_id = kwargs.get('requested_id')
                root.attrib['id'] = r_id
                r_id = r_id.split('@',1)
                try:
                    root.attrib['parentID'] = r_id[1]
                except IndexError:
                    pass
                if(kwargs.has_key('upnp_client') and kwargs.get('upnp_client').hasTag('NO_REF_ID')):
                    self.info("Changing ID from %r to %r, with parentID %r", self.id, root.attrib['id'], root.attrib['parentID'])
                else:
                    self.info("Changing ID from %r to %r, with parentID %r", root.attrib['refID'], root.attrib['id'], root.attrib['parentID'])
                    
        elif kwargs.get('parent_container',None):
            if(kwargs.get('parent_container') != '0' and
               kwargs.get('parent_container') != root.attrib['parentID']):
                if(kwargs.has_key('upnp_client') and kwargs.get('upnp_client').hasTag('NO_REF_ID')):
                    # Do nothing with refID
                    pass
                else:
                    root.attrib['refID'] = root.attrib['id']
                root.attrib['id'] = '@'.join((root.attrib['id'],kwargs.get('parent_container')))
                root.attrib['parentID'] = kwargs.get('parent_container')
                if(kwargs.has_key('upnp_client') and kwargs.get('upnp_client').hasTag('NO_REF_ID')):
                    self.info("Changing ID from %r to %r, with parentID from %r to %r", self.id, root.attrib['id'], self.parentID, root.attrib['parentID'])
                else:
                    self.info("Changing ID from %r to %r, with parentID from %r to %r", root.attrib['refID'], root.attrib['id'], self.parentID, root.attrib['parentID'])
             

        ET.SubElement(root, qname('class',UPNP_NS)).text = self.upnp_class

        if(kwargs.has_key('upnp_client') and kwargs.get('upnp_client').hasTag('XBox')):
            u = root.find(qname('class',UPNP_NS))
            if(kwargs.get('parent_container',None) != None and
                u.text.startswith('object.container')):
                if kwargs.get('parent_container') in ('14','15','16'):
                    u.text = 'object.container.storageFolder'
            if self.upnp_class == 'object.container':
                u.text = 'object.container.storageFolder'


        if self.restricted:
            root.attrib['restricted'] = '1'
        else:
            root.attrib['restricted'] = '0'

        if self.creator is not None:
            ET.SubElement(root, qname('creator',DC_NS)).text = self.creator

        if self.writeStatus is not None:
            ET.SubElement(root, qname('writeStatus',UPNP_NS)).text = self.writeStatus

        if self.date is not None:
            if isinstance(self.date, datetime):
                ET.SubElement(root, qname('date',DC_NS)).text = self.date.isoformat()
            else:
                ET.SubElement(root, qname('date',DC_NS)).text = self.date
        else:
            ET.SubElement(root, qname('date',DC_NS)).text = utils.datefaker().isoformat()

        if self.albumArtURI is not None:
            e = ET.SubElement(root, qname('albumArtURI',UPNP_NS))
            e.text = self.albumArtURI
            e.attrib['xmlns:dlna'] = 'urn:schemas-dlna-org:metadata-1-0'
            e.attrib['dlna:profileID'] = 'JPEG_TN'

        if self.artist is not None:
            ET.SubElement(root, qname('artist',UPNP_NS)).text = self.artist

        if self.genre is not None:
            ET.SubElement(root, qname('genre',UPNP_NS)).text = self.genre

        if self.genres is not None:
            for genre in self.genres:
                ET.SubElement(root, qname('genre',UPNP_NS)).text = genre

        if self.originalTrackNumber is not None:
            ET.SubElement(root, qname('originalTrackNumber',UPNP_NS)).text = str(self.originalTrackNumber)

        if self.description is not None:
            ET.SubElement(root, qname('description',DC_NS)).text = self.description

        if self.longDescription is not None:
            ET.SubElement(root, qname('longDescription',UPNP_NS)).text = self.longDescription

        if self.server_uuid is not None:
            ET.SubElement(root, qname('server_uuid',UPNP_NS)).text = self.server_uuid

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
            elif child.tag.endswith('description'):
                self.description = child.text
            elif child.tag.endswith('longDescription'):
                self.longDescription = child.text
            elif child.tag.endswith('artist'):
                self.artist = child.text
            elif child.tag.endswith('genre'):
                if self.genre != None:
                    if self.genres == None:
                        self.genres = [self.genre,]
                    self.genres.append(child.text)
                self.genre = child.text

            elif child.tag.endswith('album'):
                self.album = child.text
            elif child.tag.endswith('class'):
                self.upnp_class = child.text
            elif child.tag.endswith('server_uuid'):
                self.server_uuid = child.text
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

    director = None
    actors = None

    def __init__(self, *args, **kwargs):
        Object.__init__(self, *args, **kwargs)

    def toElement(self,**kwargs):

        root = Object.toElement(self,**kwargs)

        if self.director is not None:
            ET.SubElement(root, qname('director',UPNP_NS)).text = self.director

        if self.refID is not None:
            ET.SubElement(root, 'refID').text = self.refID

        if self.actors is not None:
            for actor in self.actors:
                ET.SubElement(root, qname('actor',DC_NS)).text = actor

        if kwargs.get('transcoding',False) == True:
            # the transcoded resource is the first resource with protocol type http-get
            # if none is present, no transcoding will occur
            res = self.res.get_matching(['*:*:*:*'], protocol_type='http-get')
            if len(res) > 0:
                old_res = res[0]
                protocolInfo = old_res.protocolInfo
                protocol,network,content_format,additional_info = protocolInfo.split(':')
                
                transcoders_string = 'native'
                
                upnp_client = kwargs.get('upnp_client',None)
                if upnp_client is not None:
                    if upnp_client.hasTag('NO_TRANSCODING'):
                        #we don't need transcoded resources, and maybe they irritate these poor things anyway
                        transcoders_string = 'native'
                    elif upnp_client.hasValue("transcoders-%s" % content_format):
                        transcoders_string = upnp_client.getValue("transcoders-%s" % content_format)
                    elif upnp_client.hasValue("transcoders-audio") and is_audio(content_format):
                        transcoders_string = upnp_client.getValue("transcoders-audio")
                    elif upnp_client.hasValue("transcoders-image") and is_image(content_format):
                        transcoders_string = upnp_client.getValue("transcoders-image")
                    elif upnp_client.hasValue("transcoders-video") and is_video(content_format):
                        transcoders_string = upnp_client.getValue("transcoders-video")                
                    elif is_audio(content_format):
                        transcoders_string = 'native,lpcm'
                    elif is_video(content_format):
                        transcoders_string = 'native,mpegts'
                    else:
                        transcoders_string = 'native'
                                                
                transcoders = transcoders_string.split(",")
                res_count = 0
                for transcoder in transcoders:
                    if transcoder in ('native'):
                        for res in self.res:
                            root.append(res.toElement(**kwargs))
                            res_count+=1
                    else:
                        transcoded_res = old_res.transcoded(transcoder)
                        if transcoded_res != None:
                            root.append(transcoded_res.toElement(**kwargs))
                            res_count+=1
                if res_count == 0:
                    # fallback in case no resources was actually added (for whatever reason)
                    for res in self.res:
                        root.append(res.toElement(**kwargs))
                        res_count+=1
                            
            else:
                for res in self.res:
                    root.append(res.toElement(**kwargs))
        else:
            for res in self.res:
                root.append(res.toElement(**kwargs))

        return root

    def fromElement(self, elt):
        Object.fromElement(self, elt)
        for child in elt.getchildren():
            if child.tag.endswith('refID'):
                self.refID = child.text
            elif child.tag.endswith('director'):
                self.director = child.text


class ImageItem(Item):
    """ a still image object """
    upnp_class = Item.upnp_class + '.imageItem'

    rating = None
    storageMedium = None
    publisher = None
    rights = None
  
    def toElement(self,**kwargs):
        root = Item.toElement(self,**kwargs)

        if self.rating is not None:
            ET.SubElement(root, qname('rating',UPNP_NS)).text = str(self.rating)

        if self.storageMedium is not None:
            ET.SubElement(root, qname('storageMedium',UPNP_NS)).text = self.storageMedium

        if self.publisher is not None:
            ET.SubElement(root, qname('publisher',DC_NS)).text = self.contributor

        if self.rights is not None:
            ET.SubElement(root, qname('rights',DC_NS)).text = self.rights

        return root

class Photo(ImageItem):
    """ a photo object (as opposed to, for example, an icon) """
    upnp_class = ImageItem.upnp_class + '.photo'
    album = None

    def toElement(self,**kwargs):
        root = ImageItem.toElement(self,**kwargs)
        if self.album is not None:
            ET.SubElement(root, qname('album',UPNP_NS)).text = self.album
        return root

class AudioItem(Item):
    """content that is intended for listening."""

    upnp_class = Item.upnp_class + '.audioItem'

    genre = None
    publisher = None
    language = None
    relation = None
    rights = None

    valid_keys = ['genre', 'description', 'longDescription', 'publisher',
                  'language', 'relation', 'rights', 'albumArtURI']

    #@dlna.AudioItem
    def toElement(self,**kwargs):

        root = Item.toElement(self,**kwargs)

        if self.publisher is not None:
            ET.SubElement(root, qname('publisher',DC_NS)).text = self.publisher

        if self.language is not None:
            ET.SubElement(root, qname('language',DC_NS)).text = self.language

        if self.relation is not None:
            ET.SubElement(root, qname('relation',DC_NS)).text = self.relation

        if self.rights is not None:
            ET.SubElement(root, qname('rights',DC_NS)).text = self.rights

        return root

    def fromElement(self, elt):
        Item.fromElement(self, elt)
        for child in elt.getchildren():
            tag = child.tag
            val = child.text
            if tag in self.valid_keys:
                setattr(self, tag, val)


class MusicTrack(AudioItem):
    """A discrete piece of audio that should be interpreted as music
      (as opposed to, for example, a news broadcast or an audio book)."""

    upnp_class = AudioItem.upnp_class + '.musicTrack'

    album = None
    playlist = None
    storageMedium = None
    contributor = None

    def toElement(self,**kwargs):

        root = AudioItem.toElement(self,**kwargs)

        if self.album is not None:
            ET.SubElement(root, qname('album',UPNP_NS)).text = self.album

        if self.playlist is not None:
            ET.SubElement(root, qname('playlist',UPNP_NS)).text = self.playlist

        if self.storageMedium is not None:
            ET.SubElement(root, qname('storageMedium',UPNP_NS)).text = self.storageMedium

        if self.contributor is not None:
            ET.SubElement(root, qname('contributor',DC_NS)).text = self.contributor

        return root

class AudioBroadcast(AudioItem):
    """ a continuous stream from an audio broadcast
    (as opposed to, for example, a song or an audio book). """
    upnp_class = AudioItem.upnp_class + '.audioBroadcast'

class AudioBook(AudioItem):
    """  audio content that is ther narration of a book
    (as opposed to , for example, a news broadcast or a song). """
    upnp_class = AudioItem.upnp_class + '.audioBook'

class VideoItem(Item):
    """ content intended for viewing (as a combination of video and audio). """ 
    upnp_class = Item.upnp_class + '.videoItem'
    valid_attrs = dict(genre=UPNP_NS, longDescription=UPNP_NS,
                       producer=UPNP_NS, rating=UPNP_NS,
                       actor=UPNP_NS, director=UPNP_NS,
                       description=DC_NS, publisher=DC_NS, language=DC_NS,
                       relation=DC_NS)

    def toElement(self,**kwargs):
        root = Item.toElement(self,**kwargs)

        for attr_name, ns in self.valid_attrs.iteritems():
            value = getattr(self, attr_name, None)
            if value:
                ET.SubElement(root, qname(attr_name, ns)).text = value

        return root

    def fromElement(self, elt):
        Item.fromElement(self, elt)
        for child in elt.getchildren():
            tag = child.tag
            val = child.text
            if tag in self.valid_attrs.keys():
                setattr(self, tag, val)

class Movie(VideoItem):
    """ content that is a movie
    (as opposed to, for example,a continuous TV broadcast or a music video clip. """
    upnp_class = VideoItem.upnp_class + '.movie'

    def __init__(self, *args, **kwargs):
        VideoItem.__init__(self, *args, **kwargs)
        self.valid_attrs.update(dict(storageMedium=UPNP_NS, DVDRegionCode=UPNP_NS,
                                     channelName=UPNP_NS, scheduledStartTime=UPNP_NS,
                                     sccheduledEndTime=UPNP_NS))

class VideoBroadcast(VideoItem):
    """ a continuous stream from a video broadcast
    (for example: a convential TV channel or a Webcast). """
    upnp_class = VideoItem.upnp_class + '.videoBroadcast'

class MusicVideoClip(VideoItem):
    """ video content that is a clip supporting a song
    (as opposed to, for example, a continuous TV broadcast or a movie) """
    upnp_class = VideoItem.upnp_class + '.musicVideoClip'

class PlaylistItem(Item):
    """ a playable sequence of resources """
    upnp_class = Item.upnp_class + '.playlistItem'

    valid_attrs = dict(artist=UPNP_NS, 
                       genre=UPNP_NS,
                       longDescription=UPNP_NS,
                       storageMedium=UPNP_NS,
                       description=DC_NS,
                       date=DC_NS,
                       language=DC_NS)

    def toElement(self,**kwargs):
        root = Item.toElement(self,**kwargs)

        for attr_name, ns in self.valid_attrs.iteritems():
            value = getattr(self, attr_name, None)
            if value:
                ET.SubElement(root, qname(attr_name, ns)).text = value

        return root

    def fromElement(self, elt):
        Item.fromElement(self, elt)
        for child in elt.getchildren():
            tag = child.tag
            val = child.text
            if tag in self.valid_attrs.keys():
                setattr(self, tag, val)    
    

class TextItem(Item):
    """ a content intended for reading """
    upnp_class = Item.upnp_class + '.textItem'

    valid_attrs = dict(author=UPNP_NS, 
                       longDescription=UPNP_NS,
                       storageMedium=UPNP_NS,
                       rating=UPNP_NS,
                       description=DC_NS,
                       publisher=DC_NS,
                       contributor=DC_NS,
                       date=DC_NS,
                       relation=DC_NS,
                       language=DC_NS,
                       rigths=DC_NS)

    def toElement(self,**kwargs):
        root = Item.toElement(self,**kwargs)

        for attr_name, ns in self.valid_attrs.iteritems():
            value = getattr(self, attr_name, None)
            if value:
                ET.SubElement(root, qname(attr_name, ns)).text = value

        return root

    def fromElement(self, elt):
        Item.fromElement(self, elt)
        for child in elt.getchildren():
            tag = child.tag
            val = child.text
            if tag in self.valid_attrs.keys():
                setattr(self, tag, val) 

class Container(Object):
    """An object that can contain other objects
    (individual content objects or other containers)."""

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
            ET.SubElement(root, qname('createclass',UPNP_NS)).text = self.createClass

        if not isinstance(self.searchClass, (list, tuple)):
            self.searchClass = [self.searchClass]
        for i in self.searchClass:
            sc = ET.SubElement(root, qname('searchClass',UPNP_NS))
            sc.attrib['includeDerived'] = '1'
            sc.text = i

        if self.searchable is not None:
            if self.searchable in (1, '1', True, 'true', 'True'):
                root.attrib['searchable'] = '1'
            else:
                root.attrib['searchable'] = '0'

        for res in self.res:
            root.append(res.toElement(**kwargs))
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
    """ an unordered collection of objects associated with a person """ 
    upnp_class = Container.upnp_class + '.person'


class MusicArtist(Person):
    """ Person instance, where the person associated with the container is a music artist."""
    upnp_class = Person.upnp_class + '.musicArtist'


class PlaylistContainer(Container):
    """ a collection of objects. """
    upnp_class = Container.upnp_class + '.playlistContainer'


class Album(Container):
    """ an ordered collection of objects. """
    upnp_class = Container.upnp_class + '.album'


class MusicAlbum(Album):
    """ Album container containing items of class musicTrack or sub-MusicAlbums. """
    upnp_class = Album.upnp_class + '.musicAlbum'


class PhotoAlbum(Album):
    """ Album container  containing items of class photo orsub-photoAlbums. """
    upnp_class = Album.upnp_class + '.photoAlbum'


class Genre(Container):
    """ an unordered collection of objects that all belong to the same genre. """
    upnp_class = Container.upnp_class + '.genre'


class MusicGenre(Genre):
    """ 'genre' which is interpreted as a style of music. """
    upnp_class = Genre.upnp_class + '.musicGenre'


class MovieGenre(Genre):
    """ 'genre' which is interpreted as a movie style. """
    upnp_class = Genre.upnp_class + '.movieGenre'


class StorageSystem(Container):
    """ a potentially heterogeneous collection of storage media. """
    upnp_class = Container.upnp_class + '.storageSystem'


class StorageVolume(Container):
    """ all, or a partition of, some physical storage unit of a single type. """
    upnp_class = Container.upnp_class + '.storageVolume'


class StorageFolder(Container):
    """ a collection of objects stored on some storage medium. """
    upnp_class = Container.upnp_class + '.storageFolder'


class DIDLElement(ElementInterface,log.Loggable):

    logCategory = 'didllite'

    def __init__(self, upnp_client=None,
                 parent_container=None,requested_id=None,
                 transcoding=False):
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
        self.transcoding = transcoding


    def addContainer(self, id, parentID, title, restricted = False):
        e = Container(id, parentID, title, restricted, creator = '')
        self.append(e.toElement())

    def addItem(self, item):
        self.append(item.toElement(upnp_client=self.upnp_client,
                                   parent_container=self.parent_container,
                                   requested_id=self.requested_id,
                                   transcoding=self.transcoding))
        self._items.append(item)

    def rebuild(self):
        self._children = []
        for item in self._items:
            self.append(item.toElement(upnp_client=self.upnp_client,
                                       parent_container=self.parent_container,
                                       requested_id=self.requested_id,
                                       transcoding=self.transcoding))

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
            upnp_class = instance.get_upnp_class(upnp_class_name.strip())
            new_node = upnp_class.fromString(ET.tostring(node))
            instance.addItem(new_node)
        return instance


def element_to_didl(item):
    """ a helper method to create a DIDLElement out of one ET element
        or XML fragment string
    """
    if not isinstance(item,basestring):
        item = ET.tostring(item)
    didl = """<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/"
                         xmlns:dc="http://purl.org/dc/elements/1.1/"
                         xmlns:dlna="urn:schemas-dlna-org:metadata-1-0"
                         xmlns:pv="http://www.pv.com/pvns/"
                         xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/">""" \
                         + item + \
                         """</DIDL-Lite>"""
    return didl


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
