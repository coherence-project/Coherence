# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2005, Tim Potter <tpot@samba.org>
# Copyright 2006 John-Mark Gurney <gurney_j@resnet.uoregon.edu>
# Copyright 2006, Frank Scholz <coherence@beebits.net>

# Content Directory service

from twisted.python import failure
from twisted.web import resource
from twisted.internet import defer


from coherence.upnp.core.soap_service import UPnPPublisher
from coherence.upnp.core.soap_service import errorCode
from coherence.upnp.core.DIDLLite import DIDLElement

from coherence.upnp.core import service

from coherence import log

class ContentDirectoryControl(service.ServiceControl,UPnPPublisher):

    def __init__(self, server):
        self.service = server
        self.variables = server.get_variables()
        self.actions = server.get_actions()


class ContentDirectoryServer(service.ServiceServer, resource.Resource,
                             log.Loggable):
    logCategory = 'content_directory_server'

    def __init__(self, device, backend=None,transcoding=False):
        self.device = device
        self.transcoding = transcoding
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
        return '<html><p>root of the ContentDirectory</p><p><ul>%s</ul></p></html>' % self.listchilds(request.uri)

    def upnp_Search(self, *args, **kwargs):
        ContainerID = kwargs['ContainerID']
        Filter = kwargs['Filter']
        StartingIndex = int(kwargs['StartingIndex'])
        RequestedCount = int(kwargs['RequestedCount'])
        SortCriteria = kwargs['SortCriteria']
        SearchCriteria = kwargs['SearchCriteria']

        total = 0
        root_id = 0
        item = None
        items = []

        parent_container = str(ContainerID)

        didl = DIDLElement(upnp_client=kwargs.get('X_UPnPClient', ''),
                           parent_container=parent_container,
                           transcoding=self.transcoding)

        def build_response(tm):
            r = {'Result': didl.toString(), 'TotalMatches': tm,
                 'NumberReturned': didl.numItems()}

            if hasattr(item, 'update_id'):
                r['UpdateID'] = item.update_id
            elif hasattr(self.backend, 'update_id'):
                r['UpdateID'] = self.backend.update_id  # FIXME
            else:
                r['UpdateID'] = 0

            return r

        def got_error(r):
            return r

        def process_result(result,total=None,found_item=None):
            if result == None:
                result = []

            l = []

            def process_items(result, tm):
                if result == None:
                    result = []
                for i in result:
                    if i[0] == True:
                        didl.addItem(i[1])

                return build_response(tm)

            for i in result:
                d = defer.maybeDeferred(i.get_item)
                l.append(d)

            if found_item != None:
                def got_child_count(count):
                    dl = defer.DeferredList(l)
                    dl.addCallback(process_items, count)
                    return dl

                d = defer.maybeDeferred(found_item.get_child_count)
                d.addCallback(got_child_count)

                return d
            elif total == None:
                total = item.get_child_count()

            dl = defer.DeferredList(l)
            dl.addCallback(process_items, total)
            return dl

        def proceed(result):
            if(kwargs.get('X_UPnPClient', '') == 'XBox' and
               hasattr(result, 'get_artist_all_tracks')):
                d = defer.maybeDeferred(result.get_artist_all_tracks, StartingIndex, StartingIndex + RequestedCount)
            else:
                d = defer.maybeDeferred(result.get_children, StartingIndex, StartingIndex + RequestedCount)
            d.addCallback(process_result,found_item=result)
            d.addErrback(got_error)
            return d

        try:
            root_id = ContainerID
        except:
            pass

        wmc_mapping = getattr(self.backend, "wmc_mapping", None)
        if kwargs.get('X_UPnPClient', '') == 'XBox':
            if(wmc_mapping != None and
               wmc_mapping.has_key(ContainerID)):
                """ fake a Windows Media Connect Server
                """
                root_id = wmc_mapping[ContainerID]
                if callable(root_id):
                    item = root_id()
                    if item  is not None:
                        if isinstance(item, list):
                            total = len(item)
                            if int(RequestedCount) == 0:
                                items = item[StartingIndex:]
                            else:
                                items = item[StartingIndex:StartingIndex + RequestedCount]
                            return process_result(items,total=total)
                        else:
                            if isinstance(item,defer.Deferred):
                                item.addCallback(proceed)
                                return item
                            else:
                                return proceed(item)

                item = self.backend.get_by_id(root_id)
                if item == None:
                    return process_result([],total=0)

                if isinstance(item,defer.Deferred):
                    item.addCallback(proceed)
                    return item
                else:
                    return proceed(item)


        item = self.backend.get_by_id(root_id)
        if item == None:
            return failure.Failure(errorCode(701))

        if isinstance(item,defer.Deferred):
            item.addCallback(proceed)
            return item
        else:
            return proceed(item)

    def upnp_Browse(self, *args, **kwargs):
        try:
            ObjectID = kwargs['ObjectID']
        except:
            self.debug("hmm, a Browse action and no ObjectID argument? An XBox maybe?")
            try:
                ObjectID = kwargs['ContainerID']
            except:
                ObjectID = 0
        BrowseFlag = kwargs['BrowseFlag']
        Filter = kwargs['Filter']
        StartingIndex = int(kwargs['StartingIndex'])
        RequestedCount = int(kwargs['RequestedCount'])
        SortCriteria = kwargs['SortCriteria']
        parent_container = None
        requested_id = None

        item = None
        total = 0
        items = []


        if BrowseFlag == 'BrowseDirectChildren':
            parent_container = str(ObjectID)
        else:
            requested_id = str(ObjectID)

        self.info("upnp_Browse request %r %r %r %r", ObjectID, BrowseFlag, StartingIndex, RequestedCount)

        didl = DIDLElement(upnp_client=kwargs.get('X_UPnPClient', ''),
                           requested_id=requested_id,
                           parent_container=parent_container,
                           transcoding=self.transcoding)

        def got_error(r):
            return r

        def process_result(result,total=None,found_item=None):
            if result == None:
                result = []
            if BrowseFlag == 'BrowseDirectChildren':
                l = []

                def process_items(result, tm):
                    if result == None:
                        result = []
                    for i in result:
                        if i[0] == True:
                            didl.addItem(i[1])

                    return build_response(tm)

                for i in result:
                    d = defer.maybeDeferred(i.get_item)
                    l.append(d)

                if found_item != None:
                    def got_child_count(count):
                        dl = defer.DeferredList(l)
                        dl.addCallback(process_items, count)
                        return dl

                    d = defer.maybeDeferred(found_item.get_child_count)
                    d.addCallback(got_child_count)

                    return d
                elif total == None:
                    total = item.get_child_count()

                dl = defer.DeferredList(l)
                dl.addCallback(process_items, total)
                return dl
            else:
                didl.addItem(result)
                total = 1

            return build_response(total)

        def build_response(tm):
            r = {'Result': didl.toString(), 'TotalMatches': tm,
                 'NumberReturned': didl.numItems()}

            if hasattr(item, 'update_id'):
                r['UpdateID'] = item.update_id
            elif hasattr(self.backend, 'update_id'):
                r['UpdateID'] = self.backend.update_id  # FIXME
            else:
                r['UpdateID'] = 0

            return r

        def proceed(result):
            if BrowseFlag == 'BrowseDirectChildren':
                d = defer.maybeDeferred(result.get_children, StartingIndex, StartingIndex + RequestedCount)
            else:
                d = defer.maybeDeferred(result.get_item)

            d.addCallback(process_result,found_item=result)
            d.addErrback(got_error)
            return d


        root_id = ObjectID

        wmc_mapping = getattr(self.backend, "wmc_mapping", None)
        if(kwargs.get('X_UPnPClient', '') == 'XBox' and
            wmc_mapping != None and
            wmc_mapping.has_key(ObjectID)):
            """ fake a Windows Media Connect Server
            """
            root_id = wmc_mapping[ObjectID]
            if callable(root_id):
                item = root_id()
                if item  is not None:
                    if isinstance(item, list):
                        total = len(item)
                        if int(RequestedCount) == 0:
                            items = item[StartingIndex:]
                        else:
                            items = item[StartingIndex:StartingIndex + RequestedCount]
                        return process_result(items,total=total)
                    else:
                        if isinstance(item,defer.Deferred):
                            item.addCallback(proceed)
                            return item
                        else:
                            return proceed(item)

            item = self.backend.get_by_id(root_id)
            if item == None:
                return process_result([],total=0)

            if isinstance(item,defer.Deferred):
                item.addCallback(proceed)
                return item
            else:
                return proceed(item)

        item = self.backend.get_by_id(root_id)
        if item == None:
            return failure.Failure(errorCode(701))

        if isinstance(item,defer.Deferred):
            item.addCallback(proceed)
            return item
        else:
            return proceed(item)
