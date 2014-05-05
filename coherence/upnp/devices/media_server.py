# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006,2007 Frank Scholz <coherence@beebits.net>

import os
import re
import traceback
from StringIO import StringIO
import urllib

from twisted.internet import task
from twisted.internet import defer
from twisted.web import static
from twisted.web import resource, server
#from twisted.web import proxy
from twisted.python import util
from twisted.python.filepath import FilePath

from coherence.extern.et import ET, indent

from coherence import __version__

from coherence.upnp.core.service import ServiceServer
from coherence.upnp.core import utils
from coherence.upnp.core.utils import StaticFile
from coherence.upnp.core.utils import ReverseProxyResource


from coherence.upnp.services.servers.connection_manager_server import ConnectionManagerServer
from coherence.upnp.services.servers.content_directory_server import ContentDirectoryServer
from coherence.upnp.services.servers.scheduled_recording_server import ScheduledRecordingServer
from coherence.upnp.services.servers.media_receiver_registrar_server import MediaReceiverRegistrarServer
from coherence.upnp.services.servers.media_receiver_registrar_server import FakeMediaReceiverRegistrarBackend

from coherence.upnp.devices.basics import BasicDeviceMixin

from coherence import log

COVER_REQUEST_INDICATOR = re.compile(".*?cover\.[A-Z|a-z]{3,4}$")

ATTACHMENT_REQUEST_INDICATOR = re.compile(".*?attachment=.*$")

TRANSCODED_REQUEST_INDICATOR = re.compile(".*/transcoded/.*$")

class MSRoot(resource.Resource, log.Loggable):
    logCategory = 'mediaserver'

    def __init__(self, server, store):
        resource.Resource.__init__(self)
        log.Loggable.__init__(self)
        self.server = server
        self.store = store


    #def delayed_response(self, resrc, request):
    #    print "delayed_response", resrc, request
    #    body = resrc.render(request)
    #    print "delayed_response", body
    #    if body == 1:
    #        print "delayed_response not yet done"
    #        return
    #    request.setHeader("Content-length", str(len(body)))
    #    request.write(response)
    #    request.finish()

    def getChildWithDefault(self, path, request):
        self.info('%s getChildWithDefault, %s, %s, %s %s', self.server.device_type,
                                request.method, path, request.uri, request.client)
        headers = request.getAllHeaders()
        self.msg( request.getAllHeaders())

        try:
            if headers['getcontentfeatures.dlna.org'] != '1':
                request.setResponseCode(400)
                return static.Data('<html><p>wrong value for getcontentFeatures.dlna.org</p></html>','text/html')
        except:
            pass

        if request.method == 'HEAD':
            if 'getcaptioninfo.sec' in headers:
                self.warning("requesting srt file for id %s", path)
                ch = self.store.get_by_id(path)
                try:
                    location = ch.get_path()
                    caption = ch.caption
                    if caption == None:
                        raise KeyError
                    request.setResponseCode(200)
                    request.setHeader('CaptionInfo.sec', caption)
                    return static.Data('','text/html')
                except:
                    print traceback.format_exc()
                    request.setResponseCode(404)
                    return static.Data('<html><p>the requested srt file was not found</p></html>','text/html')

        try:
            request._dlna_transfermode = headers['transfermode.dlna.org']
        except KeyError:
            request._dlna_transfermode = 'Streaming'
        if request.method in ('GET','HEAD'):
            if COVER_REQUEST_INDICATOR.match(request.uri):
                self.info("request cover for id %s", path)
                def got_item(ch):
                    if ch is not None:
                        request.setResponseCode(200)
                        file = ch.get_cover()
                        if os.path.exists(file):
                            self.info("got cover %s", file)
                            return StaticFile(file)
                    request.setResponseCode(404)
                    return static.Data('<html><p>cover requested not found</p></html>','text/html')

                dfr = defer.maybeDeferred(self.store.get_by_id, path)
                dfr.addCallback(got_item)
                dfr.isLeaf = True
                return dfr

            if ATTACHMENT_REQUEST_INDICATOR.match(request.uri):
                self.info("request attachment %r for id %s", request.args,path)
                def got_attachment(ch):
                    try:
                        #FIXME same as below
                        if 'transcoded' in request.args:
                            if self.server.coherence.config.get('transcoding', 'no') == 'yes':
                                format = request.args['transcoded'][0]
                                type = request.args['type'][0]
                                self.info("request transcoding %r %r", format, type)
                                try:
                                    from coherence.transcoder import TranscoderManager
                                    manager = TranscoderManager(self.server.coherence)
                                    return manager.select(format,ch.item.attachments[request.args['attachment'][0]])
                                except:
                                    self.debug(traceback.format_exc())
                                request.setResponseCode(404)
                                return static.Data('<html><p>the requested transcoded file was not found</p></html>','text/html')
                            else:
                                request.setResponseCode(404)
                                return static.Data("<html><p>This MediaServer doesn't support transcoding</p></html>",'text/html')
                        else:
                            return ch.item.attachments[request.args['attachment'][0]]
                    except:
                        request.setResponseCode(404)
                        return static.Data('<html><p>the requested attachment was not found</p></html>','text/html')
                dfr = defer.maybeDeferred(self.store.get_by_id, path)
                dfr.addCallback(got_attachment)
                dfr.isLeaf = True
                return dfr
        #if(request.method in ('GET','HEAD') and
        #   XBOX_TRANSCODED_REQUEST_INDICATOR.match(request.uri)):
        #    if self.server.coherence.config.get('transcoding', 'no') == 'yes':
        #        id = path[:-15].split('/')[-1]
        #        self.info("request transcoding to %r for id %s" % (request.args,id))
        #        ch = self.store.get_by_id(id)
        #        uri = ch.get_path()
        #        return MP3Transcoder(uri)

        if(request.method in ('GET','HEAD') and
           TRANSCODED_REQUEST_INDICATOR.match(request.uri)):
            self.info("request transcoding to %s for id %s", request.uri.split('/')[-1],path)
            if self.server.coherence.config.get('transcoding', 'no') == 'yes':
                def got_stuff_to_transcode(ch):
                    #FIXME create a generic transcoder class and sort the details there
                    format = request.uri.split('/')[-1] #request.args['transcoded'][0]
                    uri = ch.get_path()
                    try:
                        from coherence.transcoder import TranscoderManager
                        manager = TranscoderManager(self.server.coherence)
                        return manager.select(format,uri)
                    except:
                        self.debug(traceback.format_exc())
                        request.setResponseCode(404)
                        return static.Data('<html><p>the requested transcoded file was not found</p></html>','text/html')
                dfr = defer.maybeDeferred(self.store.get_by_id, path)
                dfr.addCallback(got_stuff_to_transcode)
                dfr.isLeaf = True
                return dfr

            request.setResponseCode(404)
            return static.Data("<html><p>This MediaServer doesn't support transcoding</p></html>",'text/html')

        if(request.method == 'POST' and
           request.uri.endswith('?import')):
            d = self.import_file(path,request)
            if isinstance(d, defer.Deferred):
                d.addBoth(self.import_response,path)
                d.isLeaf = True
                return d
            return self.import_response(None,path)

        if(headers.has_key('user-agent') and
           (headers['user-agent'].find('Xbox/') == 0 or      # XBox
            headers['user-agent'].startswith("""Mozilla/4.0 (compatible; UPnP/1.0; Windows""")) and  # wmp11
           path in ['description-1.xml','description-2.xml']):
            self.info('XBox/WMP alert, we need to simulate a Windows Media Connect server')
            if self.children.has_key('xbox-description-1.xml'):
                self.msg( 'returning xbox-description-1.xml')
                return self.children['xbox-description-1.xml']

        # resource http://XXXX/<deviceID>/config
        # configuration for the given device
        # accepted methods:
        # GET, HEAD: returns the configuration data (in XML format)
        # POST: stop the current device and restart it with the posted configuration data
        if path in ('config'):
            backend = self.server.backend
            backend_type = backend.__class__.__name__
            def constructConfigData(backend):
                msg = "<plugin active=\"yes\">"
                msg += "<backend>" + backend_type + "</backend>"
                for key, value in backend.config.items():
                    msg += "<" + key + ">" + value + "</" + key + ">"
                msg += "</plugin>"
                return msg

            if request.method in ('GET', 'HEAD'):
                # the client wants to retrieve the configuration parameters for the backend
                msg = constructConfigData(backend)
                request.setResponseCode(200)
                return static.Data(msg,'text/xml')
            elif request.method in ('POST'):
                # the client wants to update the configuration parameters for the backend
                # we relaunch the backend with the new configuration (after content validation)

                def convert_elementtree_to_dict (root):
                    active = False
                    for name, value in root.items():
                        if name == 'active':
                            if value in ('yes'):
                                active = True
                        break
                    if active is False:
                        return None
                    dict = {}
                    for element in root.getchildren():
                        key = element.tag
                        text = element.text
                        if (key not in ('backend')):
                            dict[key] = text
                    return dict

                new_config = None
                try:
                    element_tree = utils.parse_xml(request.content.getvalue(), encoding='utf-8')
                    new_config = convert_elementtree_to_dict(element_tree.getroot())
                    self.server.coherence.remove_plugin(self.server)
                    self.warning("%s %s (%s) with id %s desactivated", backend.name, self.server.device_type, backend, str(self.server.uuid)[5:])
                    if new_config is None :
                        msg = "<plugin active=\"no\"/>"
                    else:
                        new_backend = self.server.coherence.add_plugin(backend_type, **new_config)
                        if (self.server.coherence.writeable_config()):
                            self.server.coherence.store_plugin_config(new_backend.uuid, new_config)
                            msg = "<html><p>Device restarted. Config file has been modified with posted data.</p></html>" #constructConfigData(new_backend)
                        else:
                            msg = "<html><p>Device restarted. Config file not modified</p></html>" #constructConfigData(new_backend)
                    request.setResponseCode(202)
                    return static.Data(msg,'text/html')#'text/xml')
                except SyntaxError, e:
                    request.setResponseCode(400)
                    return static.Data("<html><p>Invalid data posted:<BR>%s</p></html>" % e,'text/html')
            else:
                # invalid method requested
                request.setResponseCode(405)
                return static.Data("<html><p>This resource does not allow the requested HTTP method</p></html>",'text/html')

        if self.children.has_key(path):
            return self.children[path]
        if request.uri == '/':
            return self
        return self.getChild(path, request)

    def requestFinished(self, result, id, request):
        self.info("finished, remove %d from connection table", id)
        self.info("finished, sentLength: %d chunked: %d code: %d", request.sentLength, request.chunked, request.code)
        self.info("finished %r", request.headers)
        self.server.connection_manager_server.remove_connection(id)

    def import_file(self,name,request):
        self.info("import file, id %s", name)
        print "import file, id %s" % name
        def got_file(ch):
            print "ch", ch
            if ch is not None:
                if hasattr(self.store,'backend_import'):
                    response_code = self.store.backend_import(ch,request.content)
                    if isinstance(response_code, defer.Deferred):
                        return response_code
                    request.setResponseCode(response_code)
                    return
            else:
                request.setResponseCode(404)
        dfr = defer.maybeDeferred(self.store.get_by_id, name)
        dfr.addCallback(got_file)

    def prepare_connection(self,request):
        new_id,_,_ = self.server.connection_manager_server.add_connection('',
                                                                    'Output',
                                                                    -1,
                                                                    '')
        self.info("startup, add %d to connection table", new_id)
        d = request.notifyFinish()
        d.addBoth(self.requestFinished, new_id, request)

    def prepare_headers(self,ch,request):
        request.setHeader('transferMode.dlna.org', request._dlna_transfermode)
        if hasattr(ch,'item') and hasattr(ch.item, 'res'):
            if ch.item.res[0].protocolInfo is not None:
                additional_info = ch.item.res[0].get_additional_info()
                if additional_info != '*':
                    request.setHeader('contentFeatures.dlna.org', additional_info)
                elif 'getcontentfeatures.dlna.org' in request.getAllHeaders():
                    request.setHeader('contentFeatures.dlna.org', "DLNA.ORG_OP=01;DLNA.ORG_CI=0;DLNA.ORG_FLAGS=01500000000000000000000000000000")

    def process_child(self,ch,name,request):
        if ch != None:
            self.info('Child found %s', ch)
            if(request.method == 'GET' or
               request.method == 'HEAD'):
                headers = request.getAllHeaders()
                if headers.has_key('content-length'):
                    self.warning('%s request with content-length %s header - sanitizing',
                                    request.method,
                                    headers['content-length'])
                    del request.received_headers['content-length']
                self.debug('data', )
                if len(request.content.getvalue()) > 0:
                    """ shall we remove that?
                        can we remove that?
                    """
                    self.warning('%s request with %d bytes of message-body - sanitizing',
                                    request.method,
                                    len(request.content.getvalue()))
                    request.content = StringIO()

            if hasattr(ch, "location"):
                self.debug("we have a location %s", isinstance(ch.location, resource.Resource))
                if(isinstance(ch.location, ReverseProxyResource) or
                   isinstance(ch.location, resource.Resource)):
                    #self.info('getChild proxy %s to %s' % (name, ch.location.uri))
                    self.prepare_connection(request)
                    self.prepare_headers(ch,request)
                    return ch.location
            try:
                p = ch.get_path()
            except TypeError:
                return self.list_content(name, ch, request)
            except Exception, msg:
                self.debug("error accessing items path %r", msg)
                self.debug(traceback.format_exc())
                return self.list_content(name, ch, request)
            if p != None and os.path.exists(p):
                self.info("accessing path %r", p)
                self.prepare_connection(request)
                self.prepare_headers(ch,request)
                ch = StaticFile(p)
            else:
                self.debug("accessing path %r failed", p)
                return self.list_content(name, ch, request)

        if ch is None:
            p = util.sibpath(__file__, name)
            if os.path.exists(p):
                ch = StaticFile(p)
        self.info('MSRoot ch %s', ch)
        return ch

    def getChild(self, name, request):
        self.info('getChild %s, %s', name, request)
        ch = self.store.get_by_id(name)
        if isinstance(ch, defer.Deferred):
            ch.addCallback(self.process_child,name,request)
            #ch.addCallback(self.delayed_response, request)
            return ch
        return self.process_child(ch,name,request)

    def list_content(self, name, item, request):
        self.info('list_content %s %s %s', name, item, request)
        page = """<html><head><title>%s</title></head><body><p>%s</p>"""% \
                                            (item.get_name().encode('ascii','xmlcharrefreplace'),
                                             item.get_name().encode('ascii','xmlcharrefreplace'))

        if( hasattr(item,'mimetype') and item.mimetype in ['directory','root']):
            uri = request.uri
            if uri[-1] != '/':
                uri += '/'

            def build_page(r,page):
                #print "build_page", r
                page += """<ul>"""
                if r is not None:
                    for c in r:
                        if hasattr(c,'get_url'):
                            path = c.get_url()
                            self.debug('has get_url %s', path)
                        elif hasattr(c,'get_path') and c.get_path != None:
                            #path = c.get_path().encode('utf-8').encode('string_escape')
                            path = c.get_path()
                            if isinstance(path,unicode):
                                path = path.encode('ascii','xmlcharrefreplace')
                            else:
                                path = path.decode('utf-8').encode('ascii','xmlcharrefreplace')
                            self.debug('has get_path %s', path)
                        else:
                            path = request.uri.split('/')
                            path[-1] = str(c.get_id())
                            path = '/'.join(path)
                            self.debug('got path %s', path)
                        title = c.get_name()
                        self.debug('title is: %s', type(title))
                        try:
                            if isinstance(title,unicode):
                                title = title.encode('ascii','xmlcharrefreplace')
                            else:
                                title = title.decode('utf-8').encode('ascii','xmlcharrefreplace')
                        except (UnicodeEncodeError,UnicodeDecodeError):
                            title = c.get_name().encode('utf-8').encode('string_escape')
                        page += '<li><a href="%s">%s</a></li>' % \
                                            (path, title)
                page += """</ul>"""
                page += """</body></html>"""
                return static.Data(page,'text/html')

            children = item.get_children()
            if isinstance(children, defer.Deferred):
                print "list_content, we have a Deferred", children
                children.addCallback(build_page,page)
                #children.addErrback(....) #FIXME
                return children

            return build_page(children,page)

        elif( hasattr(item,'mimetype') and item.mimetype.find('image/') == 0):
            #path = item.get_path().encode('utf-8').encode('string_escape')
            path = urllib.quote(item.get_path().encode('utf-8'))
            title = item.get_name().decode('utf-8').encode('ascii','xmlcharrefreplace')
            page += """<p><img src="%s" alt="%s"></p>""" % \
                                    (path, title)
        else:
            pass
        page += """</body></html>"""
        return static.Data(page,'text/html')

    def listchilds(self, uri):
        self.info('listchilds %s', uri)
        if uri[-1] != '/':
            uri += '/'
        cl = '<p><a href=%s0>content</a></p>' % uri
        cl += '<li><a href=%sconfig>config</a></li>' % uri
        for c in self.children:
                cl += '<li><a href=%s%s>%s</a></li>' % (uri,c,c)
        return cl

    def import_response(self,result,id):
        return static.Data('<html><p>import of %s finished</p></html>'% id,'text/html')

    def render(self,request):
        #print "render", request
        return '<html><p>root of the %s MediaServer</p><p><ul>%s</ul></p></html>'% \
                                        (self.server.backend,
                                         self.listchilds(request.uri))


class RootDeviceXML(static.Data):

    def __init__(self, hostname, uuid, urlbase,
                        device_type='MediaServer',
                        version=2,
                        friendly_name='Coherence UPnP A/V MediaServer',
                        xbox_hack=False,
                        services=[],
                        devices=[],
                        icons=[],
                        presentationURL=None):
        uuid = str(uuid)
        root = ET.Element('root')
        root.attrib['xmlns']='urn:schemas-upnp-org:device-1-0'
        device_type = 'urn:schemas-upnp-org:device:%s:%d' % (device_type, int(version))
        e = ET.SubElement(root, 'specVersion')
        ET.SubElement(e, 'major').text = '1'
        ET.SubElement(e, 'minor').text = '0'

        #if version == 1:
        #    ET.SubElement(root, 'URLBase').text = urlbase + uuid[5:] + '/'

        d = ET.SubElement(root, 'device')
        ET.SubElement(d, 'deviceType').text = device_type
        if xbox_hack == False:
            ET.SubElement(d, 'friendlyName').text = friendly_name
        else:
            ET.SubElement(d, 'friendlyName').text = friendly_name + ' : 1 : Windows Media Connect'
        ET.SubElement(d, 'manufacturer').text = 'beebits.net'
        ET.SubElement(d, 'manufacturerURL').text = 'http://coherence.beebits.net'
        ET.SubElement(d, 'modelDescription').text = 'Coherence UPnP A/V MediaServer'
        if xbox_hack == False:
            ET.SubElement(d, 'modelName').text = 'Coherence UPnP A/V MediaServer'
        else:
            ET.SubElement(d, 'modelName').text = 'Windows Media Connect'
        ET.SubElement(d, 'modelNumber').text = __version__
        ET.SubElement(d, 'modelURL').text = 'http://coherence.beebits.net'
        ET.SubElement(d, 'serialNumber').text = '0000001'
        ET.SubElement(d, 'UDN').text = uuid
        ET.SubElement(d, 'UPC').text = ''

        if len(icons):
            e = ET.SubElement(d, 'iconList')
            for icon in icons:

                icon_path = ''
                if icon.has_key('url'):
                    if icon['url'].startswith('file://'):
                        icon_path = icon['url'][7:]
                    elif icon['url'] == '.face':
                        icon_path = os.path.join(os.path.expanduser('~'), ".face")
                    else:
                        from pkg_resources import resource_filename
                        icon_path = os.path.abspath(resource_filename(__name__, os.path.join('..','..','..','misc','device-icons',icon['url'])))

                if os.path.exists(icon_path) == True:
                    i = ET.SubElement(e, 'icon')
                    for k,v in icon.items():
                        if k == 'url':
                            if v.startswith('file://'):
                                ET.SubElement(i, k).text = '/'+uuid[5:]+'/'+os.path.basename(v)
                                continue
                            elif v == '.face':
                                ET.SubElement(i, k).text = '/'+uuid[5:]+'/'+'face-icon.png'
                                continue
                            else:
                                ET.SubElement(i, k).text = '/'+uuid[5:]+'/'+os.path.basename(v)
                                continue
                        ET.SubElement(i, k).text = str(v)

        if len(services):
            e = ET.SubElement(d, 'serviceList')
            for service in services:
                id = service.get_id()
                if xbox_hack == False and id == 'X_MS_MediaReceiverRegistrar':
                    continue
                s = ET.SubElement(e, 'service')
                try:
                    namespace = service.namespace
                except:
                    namespace = 'schemas-upnp-org'
                if( hasattr(service,'version') and
                    service.version < version):
                    v = service.version
                else:
                    v = version
                ET.SubElement(s, 'serviceType').text = 'urn:%s:service:%s:%d' % (namespace, id, int(v))
                try:
                    namespace = service.id_namespace
                except:
                    namespace = 'upnp-org'
                ET.SubElement(s, 'serviceId').text = 'urn:%s:serviceId:%s' % (namespace,id)
                ET.SubElement(s, 'SCPDURL').text = '/' + uuid[5:] + '/' + id + '/' + service.scpd_url
                ET.SubElement(s, 'controlURL').text = '/' + uuid[5:] + '/' + id + '/' + service.control_url
                ET.SubElement(s, 'eventSubURL').text = '/' + uuid[5:] + '/' + id + '/' + service.subscription_url

                #ET.SubElement(s, 'SCPDURL').text = id + '/' + service.scpd_url
                #ET.SubElement(s, 'controlURL').text = id + '/' + service.control_url
                #ET.SubElement(s, 'eventSubURL').text = id + '/' + service.subscription_url

        if len(devices):
            e = ET.SubElement(d, 'deviceList')

        if presentationURL is None:
            presentationURL = '/' + uuid[5:]
        ET.SubElement(d, 'presentationURL').text = presentationURL

        x = ET.SubElement(d, 'dlna:X_DLNADOC')
        x.attrib['xmlns:dlna']='urn:schemas-dlna-org:device-1-0'
        x.text = 'DMS-1.50'
        x = ET.SubElement(d, 'dlna:X_DLNADOC')
        x.attrib['xmlns:dlna']='urn:schemas-dlna-org:device-1-0'
        x.text = 'M-DMS-1.50'
        x=ET.SubElement(d, 'dlna:X_DLNACAP')
        x.attrib['xmlns:dlna']='urn:schemas-dlna-org:device-1-0'
        x.text = 'av-upload,image-upload,audio-upload'

        #if self.has_level(LOG_DEBUG):
        #    indent( root)
        self.xml = """<?xml version="1.0" encoding="utf-8"?>""" + ET.tostring( root, encoding='utf-8')
        static.Data.__init__(self, self.xml, 'text/xml')

class MediaServer(log.Loggable,BasicDeviceMixin):
    logCategory = 'mediaserver'

    device_type = 'MediaServer'

    presentationURL = None

    def fire(self,backend,**kwargs):

        if kwargs.get('no_thread_needed',False) == False:
            """ this could take some time, put it in a  thread to be sure it doesn't block
                as we can't tell for sure that every backend is implemented properly """

            from twisted.internet import threads
            d = threads.deferToThread(backend, self, **kwargs)

            def backend_ready(backend):
                self.backend = backend

            def backend_failure(x):
                self.warning('backend %s not installed, MediaServer activation aborted - %s', backend, x.getErrorMessage())
                self.debug(x)

            d.addCallback(backend_ready)
            d.addErrback(backend_failure)

            # FIXME: we need a timeout here so if the signal we wait for not arrives we'll
            #        can close down this device
        else:
            self.backend = backend(self, **kwargs)

    def init_complete(self, backend):
        if self.backend != backend:
            return
        self._services = []
        self._devices = []

        try:
            self.connection_manager_server = ConnectionManagerServer(self)
            self._services.append(self.connection_manager_server)
        except LookupError,msg:
            self.warning('ConnectionManagerServer %s', msg)
            raise LookupError(msg)

        try:
            transcoding = False
            if self.coherence.config.get('transcoding', 'no') == 'yes':
                transcoding = True
            self.content_directory_server = ContentDirectoryServer(self,transcoding=transcoding)
            self._services.append(self.content_directory_server)
        except LookupError,msg:
            self.warning('ContentDirectoryServer %s', msg)
            raise LookupError(msg)

        try:
            self.media_receiver_registrar_server = MediaReceiverRegistrarServer(self,
                                                        backend=FakeMediaReceiverRegistrarBackend())
            self._services.append(self.media_receiver_registrar_server)
        except LookupError,msg:
            self.warning('MediaReceiverRegistrarServer (optional) %s', msg)

        try:
            self.scheduled_recording_server = ScheduledRecordingServer(self)
            self._services.append(self.scheduled_recording_server)
        except LookupError,msg:
            self.info('ScheduledRecordingServer %s', msg)

        upnp_init = getattr(self.backend, "upnp_init", None)
        if upnp_init:
            upnp_init()

        self.web_resource = MSRoot( self, backend)
        self.coherence.add_web_resource( str(self.uuid)[5:], self.web_resource)

        version = int(self.version)
        while version > 0:
            self.web_resource.putChild( 'description-%d.xml' % version,
                                    RootDeviceXML( self.coherence.hostname,
                                    str(self.uuid),
                                    self.coherence.urlbase,
                                    self.device_type, version,
                                    friendly_name=self.backend.name,
                                    services=self._services,
                                    devices=self._devices,
                                    icons=self.icons,
                                    presentationURL = self.presentationURL))
            self.web_resource.putChild( 'xbox-description-%d.xml' % version,
                                    RootDeviceXML( self.coherence.hostname,
                                    str(self.uuid),
                                    self.coherence.urlbase,
                                    self.device_type, version,
                                    friendly_name=self.backend.name,
                                    xbox_hack=True,
                                    services=self._services,
                                    devices=self._devices,
                                    icons=self.icons,
                                    presentationURL = self.presentationURL))
            version -= 1

        self.web_resource.putChild('ConnectionManager', self.connection_manager_server)
        self.web_resource.putChild('ContentDirectory', self.content_directory_server)
        if hasattr(self,"scheduled_recording_server"):
            self.web_resource.putChild('ScheduledRecording', self.scheduled_recording_server)
        if hasattr(self,"media_receiver_registrar_server"):
            self.web_resource.putChild('X_MS_MediaReceiverRegistrar', self.media_receiver_registrar_server)

        for icon in self.icons:
            if icon.has_key('url'):
                if icon['url'].startswith('file://'):
                    if os.path.exists(icon['url'][7:]):
                        self.web_resource.putChild(os.path.basename(icon['url']),
                                                   StaticFile(icon['url'][7:],defaultType=icon['mimetype']))
                elif icon['url'] == '.face':
                    face_path = os.path.abspath(os.path.join(os.path.expanduser('~'), ".face"))
                    if os.path.exists(face_path):
                        self.web_resource.putChild('face-icon.png',StaticFile(face_path,defaultType=icon['mimetype']))
                else:
                    from pkg_resources import resource_filename
                    icon_path = os.path.abspath(resource_filename(__name__, os.path.join('..','..','..','misc','device-icons',icon['url'])))
                    if os.path.exists(icon_path):
                        self.web_resource.putChild(icon['url'],StaticFile(icon_path,defaultType=icon['mimetype']))

        self.register()
        self.warning("%s %s (%s) activated with id %s", self.device_type, self.backend.name, self.backend, str(self.uuid)[5:])
