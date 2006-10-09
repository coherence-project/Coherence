# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php
 	
# Copyright 2006, Frank Scholz <coherence@beebits.net>

from twisted.internet import task
from twisted.internet import reactor
from twisted.web import xmlrpc

class MediaServer:

    def __init__(self, coherence):
        self.coherence = coherence
        self.uuid = self.generateuuid()
        
    def register(self):
        s = self.coherence.ssdp_server
        print 'MediaServer register'
        # we need to do this after the children are there, since we send notifies
        s.register('%s::upnp:rootdevice' % uuid,
        		'upnp:rootdevice',
        		self.coherence.urlbase + self.uuid + '/' + 'root-device.xml')

        s.register(uuid,
        		uuid,
        		urlbase + 'root-device.xml')

        s.register('%s::urn:schemas-upnp-org:device:MediaServer:2' % uuid,
        		'urn:schemas-upnp-org:device:MediaServer:2',
        		self.coherence.urlbase + self.uuid + '/' + 'root-device.xml')

        s.register('%s::urn:schemas-upnp-org:service:ConnectionManager:2' % uuid,
        		'urn:schemas-upnp-org:device:ConnectionManager:2',
        		self.coherence.urlbase + self.uuid + '/' + 'root-device.xml')

        s.register('%s::urn:schemas-upnp-org:service:ContentDirectory:2' % uuid,
        		'urn:schemas-upnp-org:device:ContentDirectory:2',
        		self.coherence.urlbase + self.uuid + '/' + 'root-device.xml')


    def generateuuid(self):
        import random
        import string
    	return ''.join([ 'uuid:'] + map(lambda x: random.choice(string.letters), xrange(20)))
