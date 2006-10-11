# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php
 	
# Copyright 2006, Frank Scholz <coherence@beebits.net>

from twisted.internet import task
from twisted.internet import reactor
from twisted.web import xmlrpc, resource, static

from elementtree.ElementTree import Element, SubElement, ElementTree, tostring

class MSRoot(resource.Resource):
    def __init__(self):
        resource.Resource.__init__(self)
        
    def childFactory(self, ctx, name):
        ch = super(WebUI, self).childFactory(ctx, name)
        if ch is None:
            p = util.sibpath(__file__, name)
            if os.path.exists(p):
                ch = static.File(p)
        return ch
        
    def render(self,request):
        return '<html><p>root of the MediaServer</p></html>'


class RootDeviceXML(static.Data):

    def __init__(self, hostname, uuid, urlbase,
                        device_type="urn:schemas-upnp-org:device:MediaServer:2",
                        friendly_name='Coherence MediaServer'):
        root = Element('root')
        root.attrib['xmlns']='urn:schemas-upnp-org:device-1-0'
        e = SubElement(root, 'specVersion')
        SubElement( e, 'major').text = '1'
        SubElement( e, 'minor').text = '0'

        SubElement(root, 'URLBase').text = urlbase

        d = SubElement(root, 'device')
        SubElement( d, 'deviceType').text = ''
        SubElement( d, 'friendlyName').text = device_type
        SubElement( d, 'manufacturer').text = ''
        SubElement( d, 'manufacturerURL').text = ''
        SubElement( d, 'modelDescription').text = ''
        SubElement( d, 'modelName').text = ''
        SubElement( d, 'modelNumber').text = ''
        SubElement( d, 'modelURL').text = ''
        SubElement( d, 'serialNumber').text = ''
        SubElement( d, 'UDN').text = uuid
        SubElement( d, 'UPC').text = ''
        SubElement( d, 'presentationURL').text = ''

        e = SubElement( d, 'serviceList')
        s = SubElement( e, 'service')
        SubElement( s, 'serviceType').text = ''
        SubElement( s, 'serviceId').text = ''
        SubElement( s, 'SCPDURL').text = ''
        SubElement( s, 'controlURL').text = ''
        SubElement( s, 'eventSubURL').text = ''

        e = SubElement( d, 'deviceList')

        #indent( root, 0)
        self.xml = tostring( root, encoding='utf-8')
        static.Data.__init__(self, self.xml, 'text/xml')
        
class MediaServer:

    def __init__(self, coherence):
        self.coherence = coherence
        self.uuid = self.generateuuid()
        print self.uuid
        
        self.web_resource = MSRoot()
        self.coherence.add_web_resource( self.uuid, self.web_resource)
        self.web_resource.putChild( 'description.xml',
                                RootDeviceXML( self.coherence.hostname,
                                self.uuid,
                                self.coherence.urlbase))
        #self.register()

        
    def register(self):
        s = self.coherence.ssdp_server
        print 'MediaServer register'
        # we need to do this after the children are there, since we send notifies
        s.register('%s::upnp:rootdevice' % self.uuid,
        		'upnp:rootdevice',
        		self.coherence.urlbase + self.uuid + '/' + 'description.xml',
                '', '')

        """                
        s.register(self.uuid,
        		self.uuid,
        		self.coherence.urlbase + self.uuid + '/' + 'description.xml')

        s.register('%s::urn:schemas-upnp-org:device:MediaServer:2' % self.uuid,
        		'urn:schemas-upnp-org:device:MediaServer:2',
        		self.coherence.urlbase + self.uuid + '/' + 'descriptiondevice.xml')

        s.register('%s::urn:schemas-upnp-org:service:ConnectionManager:2' % self.uuid,
        		'urn:schemas-upnp-org:device:ConnectionManager:2',
        		self.coherence.urlbase + self.uuid + '/' + 'root-device.xml')

        s.register('%s::urn:schemas-upnp-org:service:ContentDirectory:2' % self.uuid,
        		'urn:schemas-upnp-org:device:ContentDirectory:2',
        		self.coherence.urlbase + self.uuid + '/' + 'root-device.xml')
        """
        

    def generateuuid(self):
        import random
        import string
    	return ''.join([ 'uuid:'] + map(lambda x: random.choice(string.letters), xrange(20)))
