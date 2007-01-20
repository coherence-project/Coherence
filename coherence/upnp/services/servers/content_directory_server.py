# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2005, Tim Potter <tpot@samba.org>
# Copyright 2006 John-Mark Gurney <gurney_j@resnet.uoregon.edu>
# Copyright 2006, Frank Scholz <coherence@beebits.net>

# Content Directory service

from twisted.python import log
from twisted.python import failure
from twisted.web import resource, static, soap

from twisted.python import reflect

from elementtree.ElementTree import Element, SubElement, ElementTree, tostring

from coherence.upnp.core.soap_service import UPnPPublisher
from coherence.upnp.core.DIDLLite import DIDLElement

from coherence.upnp.core import service

class ContentDirectoryControl(service.ServiceControl,UPnPPublisher):

    def __init__(self, server):
        self.service = server
        self.variables = server.get_variables()
        self.actions = server.get_actions()


class ContentDirectoryServer(service.ServiceServer, resource.Resource):

    def __init__(self, device, backend=None):
        self.device = device
        if backend == None:
            backend = self.device.backend
        resource.Resource.__init__(self)
        service.ServiceServer.__init__(self, 'ContentDirectory', self.device.version, backend)
        
        self.control = ContentDirectoryControl(self)
        self.putChild('scpd.xml', service.scpdXML(self, self.control))
        self.putChild('control', self.control)

        self.set_variable(0, 'SystemUpdateID', 0)
        self.set_variable(0, 'ContainerUpdateIDs', '')
        
    def listchilds(self, uri):
        cl = ''
        for c in self.children:
                cl += '<li><a href=%s/%s>%s</a></li>' % (uri,c,c)
        return cl

    def render(self,request):
        return '<html><p>root of the ContentDirectory</p><p><ul>%s</ul></p></html>'% self.listchilds(request.uri)

    def upnp_Search(self, *args, **kwargs):
        ContainerID = kwargs['ContainerID']
        Filter = kwargs['Filter']
        StartingIndex = int(kwargs['StartingIndex'])
        RequestedCount = int(kwargs['RequestedCount'])
        SortCriteria = kwargs['SortCriteria']
        SearchCriteria = kwargs['SearchCriteria']
        
        total = 0

        """ fake a Windows Media Connect Server
            and return for the moment an empty results
            for the things we can't support now
        """
        if ContainerID in ['1','2','3','5','6','7','8','9',
                           '10','11','12','13','14','15','16','17',
                           'A','B','C','D','E','F']:
            didl = DIDLElement()
            r = { 'Result': didl.toString(), 'TotalMatches': 0,
                  'UpdateID': self.update_id, 'NumberReturned': didl.numItems()}
            return r
        
        """ a request for all music items served by a Windows Media Connect Server """
        if ContainerID == '4':
            root_id = 1000
            item = self.get_by_id(root_id)
            if item  == None:
                return failure.Failure(errorCode(701))
                
            items = []
            containers = [item]
            while len(containers)>0:
                container = containers.pop()
                if container.mimetype != 'directory':
                    continue
                for child in container.get_children(0,0):
                    if child.mimetype == 'directory':
                        containers.append(child)
                    else:
                        items.append(child)
                        total += 1

        else:
            ContainerID = int(ContainerID)
            if ContainerID == 0:
                root_id = 1000

            item = self.get_by_id(root_id)
            if item  == None:
                return failure.Failure(errorCode(701))
                
            items = item.get_children(StartingIndex, StartingIndex + RequestedCount)
            total = item.child_count

        didl = DIDLElement()
        for i in items:
            didl.addItem(i.item)

        r = { 'Result': didl.toString(), 'TotalMatches': total,
            'NumberReturned': didl.numItems()}

        if hasattr(item, 'update_id'):
            r['UpdateID'] = item.update_id
        else:
            r['UpdateID'] = self.update_id

        return r

    def upnp_Browse(self, *args, **kwargs):
        ObjectID = int(kwargs['ObjectID'])
        BrowseFlag = kwargs['BrowseFlag']
        Filter = kwargs['Filter']
        StartingIndex = int(kwargs['StartingIndex'])
        RequestedCount = int(kwargs['RequestedCount'])
        SortCriteria = kwargs['SortCriteria']

        item = self.backend.get_by_id(ObjectID)
        
        if item  == None:
            return failure.Failure(errorCode(701))
            
        didl = DIDLElement()

        if BrowseFlag == 'BrowseDirectChildren':
            childs = item.get_children(StartingIndex, StartingIndex + RequestedCount)
            for i in childs:
                didl.addItem(i.item)
            total = item.child_count
        else:
            didl.addItem(item.item)
            total = 1

        r = { 'Result': didl.toString(), 'TotalMatches': total,
            'NumberReturned': didl.numItems()}

        if hasattr(item, 'update_id'):
            r['UpdateID'] = item.update_id
        else:
            r['UpdateID'] = self.backend.update_id # FIXME

        return r
