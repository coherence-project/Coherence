# Elisa - Home multimedia server
# Copyright (C) 2006 Fluendo, S.A. (www.fluendo.com).
# All rights reserved.
# 
# This software is available under three license agreements.
# 
# There are various plugins and extra modules for Elisa licensed
# under the MIT license. For instance our upnp module uses this license.
# 
# The core of Elisa is licensed under GPL version 2.
# See "LICENSE.GPL" in the root of this distribution including a special 
# exception to use Elisa with Fluendo's plugins.
# 
# The GPL part is also available under a commerical licensing
# agreement.
# 
# The second license is the Elisa Commercial License Agreement.
# This license agreement is available to licensees holding valid
# Elisa Commercial Agreement licenses.
# See "LICENSE.Elisa" in the root of this distribution.

from twisted.internet import reactor, defer
from twisted.python import log
import sys, threading
import DIDLLite, utils

from service import ServiceClient

global work, pending
work = []
pending = {}


class ContentDirectoryClient( ServiceClient):

    def __init__(self, service):
        self.service = service
        self.namespace = service.get_type()
        self.url = service.get_control_url()
        #print "ContentDirectoryClient __init__", self.url

    def get_sort_capabilities(self):
        client = self._get_client("GetSortCapabilities")
        d = client.callRemote("GetSortCapabilities")
        def got_results(results):
            print "sort capabilities: %r" % results
        d.addCallback(got_results)
        return d

    def get_system_update_id(self):
        client = self._get_client("GetSystemUpdateID")
        d = client.callRemote("GetSystemUpdateID")
        def got_results(results):
            print "system update id: %r" % results
        d.addCallback(got_results)
        return d

    def get_search_capabilities(self):
        client = self._get_client("GetSearchCapabilities")
        d = client.callRemote("GetSearchCapabilities")
        def got_results(results):
            print "search capabilities: %r" % results
        d.addCallback(got_results)
        return d

    def search(self, container_id, criteria, starting_index=0,
               requested_count=0):
        #print "search:", criteria
        client = self._get_client("Search")
        starting_index = str(starting_index)
        requested_count = str(requested_count)
        #print "search:", self.url, starting_index, requested_count
        d = client.callRemote('Search', ContainerID=container_id,
                              SearchCriteria=criteria,
                              Filter="*",
                              StartingIndex=starting_index,
                              RequestedCount=requested_count,
                              SortCriteria="")
        d.addErrback(self._failure)

        def gotResults(results):
            items = []
            if results is not None:
                elt = DIDLLite.DIDLElement.fromString(results['Result'])
                items = elt.getItems()
            return items

        d.addCallback(gotResults)
        return d

    def browse(self, object_id=0, browse_flag='BrowseDirectChildren',
               starting_index=0, requested_count=0,
               recursive=False):
        """
        """
        finished = defer.Deferred()
        infos = {}
        client = self._get_client("Browse")
        d = client.callRemote('Browse', ObjectID=object_id,
                              BrowseFlag=browse_flag,
                              Filter="*",SortCriteria="",
                              StartingIndex=str(starting_index),
                              RequestedCount=str(requested_count))

        def gotResults(results):
            global work, pending

            returned_nb = results['NumberReturned']
            total_matches = results['TotalMatches']

            log.msg("Returned %s results. Total matches: %s" % (returned_nb,
                                                                total_matches))
            elt = DIDLLite.DIDLElement.fromString(results['Result'])
            work.extend(elt.getItems())

            _infos = {}
            while work:
                item = work.pop()
                if isinstance(item, DIDLLite.Container):
                    childCount = 1
                else:
                    childCount = 0
                _infos[item.id] = {'title': item.title,
                                   'childCount': childCount,
                                   'parentID': item.parentID}
                title = item.title.encode('iso-8859-15')
                log.msg("%s <- %s : %s (%s)" % (item.parentID, item.id,
                                                title, childCount))
                if isinstance(item, DIDLLite.Container):
                    log.msg('Folder "%s" with %s children' % (title,
                                                              item.childCount))
                    _infos[item.id].update({'search_class': item.searchClass})
                    if recursive:
                        nextD = client.callRemote('Browse',
                                                  ObjectID=item.id,
                                                  BrowseFlag=browse_flag,
                                                  Filter="*",
                                                  SortCriteria="",
                                                  StartingIndex="0",
                                                  RequestedCount="0")
                        nextD.addCallback(gotResults)
                        nextD.addErrback(finished.errback)
                        pending[item.id] = int(item.childCount)

                elif isinstance(item, DIDLLite.Object):
                    urls = {}                    
                    for res in item.res:
                        url = res.data
                        protocolInfo = res.protocolInfo
                        urls[url] = protocolInfo
                    _infos[item.id].update({'urls': urls})

                pending.keys().sort()
                if item.parentID in pending.keys():
                    if pending[item.parentID] > 0:
                        pending[item.parentID] -= 1

                for k in pending.keys():
                    v = pending[k]
                    if not v:
                        del pending[k]

                infos.update(_infos)

            if not pending and not finished.called:
                finished.callback(infos)

        d.addCallback(gotResults)
        d.addErrback(self._failure)
        return finished

    def _failure(self, error):
        log.msg(error.getTraceback(), debug=True)
        error.trap(Exception)
