# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2005, Tim Potter <tpot@samba.org>
# Copyright 2006 John-Mark Gurney <gurney_j@resnet.uoregon.edu>
# Copyright 2006, Frank Scholz <coherence@beebits.net>

# Content Directory service

from twisted.python import log
from twisted.web import resource, static, soap

from twisted.python import reflect

from elementtree.ElementTree import Element, SubElement, ElementTree, tostring

from soap_service import UPnPPublisher

import service

class ContentDirectoryControl(service.ServiceControl,UPnPPublisher):

    def __init__(self, server):
        self.service = server
        self.variables = server.get_variables()
        self.actions = server.get_actions()


class ContentDirectoryServer(service.Server, resource.Resource):

    def __init__(self, version, backend):
        self.backend = backend
        resource.Resource.__init__(self)
        service.Server.__init__(self, 'ContentDirectory', version, backend)
        
        self.control = ContentDirectoryControl(self)
        self.putChild('scpd.xml', service.scpdXML(self, self.control))
        self.putChild('control', self.control)

        
    def listchilds(self, uri):
        cl = ''
        for c in self.children:
                cl += '<li><a href=%s/%s>%s</a></li>' % (uri,c,c)
        return cl

    def render(self,request):
        return '<html><p>root of the ContentDirectory</p><p><ul>%s</ul></p></html>'% self.listchilds(request.uri)
