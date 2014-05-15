# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2007,, Frank Scholz <coherence@beebits.net>

import time
from coherence.extern.simple_plugin import Plugin

from coherence import log

import coherence.extern.louie as louie

from coherence.upnp.core.utils import getPage
from coherence.extern.et import parse_xml
from coherence.upnp.core import DIDLLite
from twisted.internet import defer, reactor


class Backend(log.Loggable, Plugin):

    """ the base class for all backends

        if there are any UPnP service actions, that can't
        be handled by the service classes itself, or need some
        special adjustments for the backend, they need to be
        defined here.

        Like maybe upnp_Browse for the CDS Browse action.
    """

    implements = []  # list the device classes here
                     # like [BinaryLight'] or ['MediaServer','MediaRenderer']

    logCategory = 'backend'

    def __init__(self, server, **kwargs):
        """ the init method for a backend,
            should probably most of the time be overwritten
            when the init is done, send a signal to its device

            the device will then setup and announce itself,
            after that it calls the backends upnp_init method
        """
        self.config = kwargs
        self.server = server  # the UPnP device that's hosting that backend

        """ do whatever is necessary with the stuff we can
            extract from the config dict,
            connect maybe to an external data-source and
            start up the backend
            after that's done, tell Coherence about it
        """
        log.Loggable.__init__(self)
        Plugin.__init__(self)

        """ this has to be done in the actual backend, maybe it has
            to wait for an answer from an external data-source first
        """
        #self.init_completed()

    def init_completed(self, *args, **kwargs):
        """ inform Coherence that this backend is ready for
            announcement
            this method just accepts any form of arguments
            as we don't under which circumstances it is called
        """
        louie.send('Coherence.UPnP.Backend.init_completed',
                None, backend=self)

    def upnp_init(self):
        """ this method gets called after the device is fired,
            here all initializations of service related state variables
            should happen, as the services aren't available before that point
        """
        pass


class BackendStore(Backend):

    """ the base class for all MediaServer backend stores
    """

    logCategory = 'backend_store'

    def __init__(self, server, *args, **kwargs):
        """ the init method for a MediaServer backend,
            should probably most of the time be overwritten
            when the init is done, send a signal to its device

            the device will then setup and announce itself,
            after that it calls the backends upnp_init method
        """
        Backend.__init__(self, server, *args)
        self.config = kwargs
        self.server = server  # the UPnP device that's hosting that backend
        self.update_id = 0

        """ do whatever is necessary with the stuff we can
            extract from the config dict
        """

        """ in case we want so serve something via
            the MediaServer web backend

            the BackendItem should pass an URI assembled
            of urlbase + '/' + id to the DIDLLite.Resource
        """
        self.urlbase = kwargs.get('urlbase', '')
        if not self.urlbase.endswith('/'):
            self.urlbase += '/'

        self.wmc_mapping = {'4': '4', '5': '5', '6': '6', '7': '7', '14': '14', 'F': 'F',
                            '11': '11', '16': '16', 'B': 'B', 'C': 'C', 'D': 'D',
                            '13': '13', '17': '17',
                            '8': '8', '9': '9', '10': '10', '15': '15', 'A': 'A', 'E': 'E'}

        self.wmc_mapping.update({'4': lambda: self._get_all_items(0),
                                 '8': lambda: self._get_all_items(0),
                                 'B': lambda: self._get_all_items(0),
                                })

        """ and send out the signal when ready
        """
        #louie.send('Coherence.UPnP.Backend.init_completed', None, backend=self)

    def release(self):
        """ if anything needs to be cleaned up upon
            shutdown of this backend, this is the place
            for it
        """
        pass

    def _get_all_items(self, id):
        """ a helper method to get all items as a response
            to some XBox 360 UPnP Search action
            probably never be used as the backend will overwrite
            the wmc_mapping with more appropriate methods
        """
        items = []
        item = self.get_by_id(id)
        if item is not None:
            containers = [item]
            while len(containers) > 0:
                container = containers.pop()
                if container.mimetype not in ['root', 'directory']:
                    continue
                for child in container.get_children(0, 0):
                    if child.mimetype in ['root', 'directory']:
                        containers.append(child)
                    else:
                        items.append(child)
        return items

    def get_by_id(self, id):
        """ called by the CDS or the MediaServer web

            id is the id property of our DIDLLite item

            if this MediaServer implements containers, that can
            share their content, like 'all tracks', 'album' and
            'album_of_artist' - they all have the same track item as content -
            then the id may be passed by the CDS like this:

            'id@container' or 'id@container@container@container...'

            therefore a

            if isinstance(id, basestring):
                id = id.split('@',1)
                id = id[0]

            may be appropriate as the first thing to do
            when entering this method

            should return

            - None when no matching item for that id is found,
            - a BackendItem,
            - or a Deferred

        """

        return None


class BackendItem(log.Loggable):

    """ the base class for all MediaServer backend items
    """

    logCategory = 'backend_item'

    def __init__(self, *args, **kwargs):
        """ most of the time we collect the necessary data for
            an UPnP ContentDirectoryService Container or Object
            and instantiate it here

            self.item = DIDLLite.Container(id,parent_id,name,...)
              or
            self.item = DIDLLite.MusicTrack(id,parent_id,name,...)

            To make that a valid UPnP CDS Object it needs one or
            more DIDLLite.Resource(uri,protocolInfo)

            self.item.res = []
            res = DIDLLite.Resource(url, 'http-get:*:%s:*' % mimetype)

                url : the urlbase of our backend + '/' + our id

            res.size = size
            self.item.res.append(res)
        """
        self.name = u'my_name' # the basename of a file, the album title,
                               # the artists name,...
                               # is expected to be unicode
        self.item = None
        self.update_id = 0 # the update id of that item,
                           # when an UPnP ContentDirectoryService Container
                           # this should be incremented on every modification

        self.location = None # the filepath of our media file, or alternatively
                             # a FilePath or a ReverseProxyResource object

        self.cover = None # if we have some album art image, let's put
                          # the filepath or link into here

    def get_children(self, start=0, end=0):
        """ called by the CDS and the MediaServer web
            should return

            - a list of its childs[start:end]
            - or a Deferred

            if end == 0, the request is for all childs
            after start - childs[start:]
        """
        pass

    def get_child_count(self):
        """ called by the CDS
            should return

            - the number of its childs - len(childs)
            - or a Deferred

        """

    def get_item(self):
        """ called by the CDS and the MediaServer web
            should return

            - an UPnP ContentDirectoryServer DIDLLite object
            - or a Deferred
        """
        return self.item

    def get_name(self):
        """ called by the MediaServer web
            should return

            - the name of the item,
              it is always expected to be in unicode
        """
        return self.name

    def get_path(self):
        """ called by the MediaServer web
            should return

            - the filepath where to find the media file
              that this item does refer to
        """
        return self.location

    def get_cover(self):
        """ called by the MediaServer web
            should return

            - the filepath where to find the album art file

            only needed when we have created for that item
            an albumArtURI property that does point back to us
        """
        return self.cover

    def __repr__(self):
        return "%s[%s]" % (self.__class__.__name__, self.get_name())


class BackendRssMixin:

    def update_data(self, rss_url, container=None, encoding="utf-8"):
        """ creates a deferred chain to retrieve the rdf file,
            parse and extract the metadata and reschedule itself
        """

        def fail(f):
            self.info("fail %r", f)
            self.debug(f.getTraceback())
            return f

        dfr = getPage(rss_url)
        dfr.addCallback(parse_xml, encoding=encoding)
        dfr.addErrback(fail)
        dfr.addCallback(self.parse_data, container)
        dfr.addErrback(fail)
        dfr.addBoth(self.queue_update, rss_url, container)
        return dfr

    def parse_data(self, xml_data, container):
        """ extract media info and create BackendItems
        """
        pass

    def queue_update(self, error_or_failure, rss_url, container):
        from twisted.internet import reactor
        reactor.callLater(self.refresh, self.update_data, rss_url, container)


class Container(BackendItem):

    def __init__(self, parent, title):
        BackendItem.__init__(self)

        self.parent = parent
        if self.parent is not None:
            self.parent_id = self.parent.get_id()
        else:
            self.parent_id = -1

        self.store = None
        self.storage_id = None

        self.name = title
        self.mimetype = 'directory'

        self.children = []
        self.children_ids = {}
        self.children_by_external_id = {}

        self.update_id = 0

        self.item = None

        self.sorted = False

        def childs_sort(x, y):
            return cmp(x.name, y.name)
        self.sorting_method = childs_sort

    def register_child(self, child, external_id=None):
        id = self.store.append_item(child)
        child.url = self.store.urlbase + str(id)
        child.parent = self
        if external_id is not None:
            child.external_id = external_id
            self.children_by_external_id[external_id] = child

    def add_child(self, child, external_id=None, update=True):
        id = self.register_child(child, external_id)
        if self.children is None:
            self.children = []
        self.children.append(child)
        self.sorted = False
        if update == True:
            self.update_id += 1

    def remove_child(self, child, external_id=None, update=True):
        self.children.remove(child)
        self.store.remove_item(child)
        if update == True:
            self.update_id += 1
        if external_id is not None:
            child.external_id = None
            del self.children_by_external_id[external_id]

    def get_children(self, start=0, end=0):
        if self.sorted == False:
            self.children.sort(cmp=self.sorting_method)
            self.sorted = True
        if end != 0:
            return self.children[start:end]
        return self.children[start:]

    def get_child_count(self):
        if self.children is None:
            return 0
        return len(self.children)

    def get_path(self):
        return self.store.urlbase + str(self.storage_id)

    def get_item(self):
        if self.item is None:
            self.item = DIDLLite.Container(self.storage_id, self.parent_id, self.name)
        self.item.childCount = len(self.children)
        return self.item

    def get_name(self):
        return self.name

    def get_id(self):
        return self.storage_id

    def get_update_id(self):
        return self.update_id


class LazyContainer(Container):
    logCategory = 'lazyContainer'

    def __init__(self, parent, title, external_id=None, refresh=0, childrenRetriever=None, **kwargs):
        Container.__init__(self, parent, title)

        self.childrenRetrievingNeeded = True
        self.childrenRetrievingDeferred = None
        self.childrenRetriever = childrenRetriever
        self.children_retrieval_campaign_in_progress = False
        self.childrenRetriever_params = kwargs
        self.childrenRetriever_params['parent'] = self
        self.has_pages = (self.childrenRetriever_params.has_key('per_page'))

        self.external_id = None
        self.external_id = external_id

        self.retrieved_children = {}

        self.last_updated = 0
        self.refresh = refresh

    def replace_by(self, item):
        if self.external_id is not None and item.external_id is not None:
            return (self.external_id == item.external_id)
        return True

    def add_child(self, child, external_id=None, update=True):
        if self.children_retrieval_campaign_in_progress is True:
            self.retrieved_children[external_id] = child
        else:
            Container.add_child(self, child, external_id=external_id, update=update)

    def update_children(self, new_children, old_children):
        children_to_be_removed = {}
        children_to_be_replaced = {}
        children_to_be_added = {}

        # Phase 1
        # let's classify the item between items to be removed,
        # to be updated or to be added
        self.debug("Refresh pass 1:%d %d", len(new_children), len(old_children))
        for id, item in old_children.items():
            children_to_be_removed[id] = item
        for id, item in new_children.items():
            if old_children.has_key(id):
                #print(id, "already there")
                children_to_be_replaced[id] = old_children[id]
                del children_to_be_removed[id]
            else:
                children_to_be_added[id] = new_children[id]

        # Phase 2
        # Now, we remove, update or add the relevant items
        # to the list of items
        self.debug("Refresh pass 2: %d %d %d", len(children_to_be_removed), len(children_to_be_replaced), len(children_to_be_added))
        # Remove relevant items from Container children
        for id, item in children_to_be_removed.items():
            self.remove_child(item, external_id=id, update=False)
        # Update relevant items from Container children
        for id, item in children_to_be_replaced.items():
            old_item = item
            new_item = new_children[id]
            replaced = False
            if self.replace_by:
                #print "Replacement method available: Try"
                replaced = old_item.replace_by(new_item)
            if replaced is False:
                #print "No replacement possible: we remove and add the item again"
                self.remove_child(old_item, external_id=id, update=False)
                self.add_child(new_item, external_id=id, update=False)
        # Add relevant items to COntainer children
        for id, item in children_to_be_added.items():
            self.add_child(item, external_id=id, update=False)

        self.update_id += 1

    def start_children_retrieval_campaign(self):
        #print "start_update_campaign"
        self.last_updated = time.time()
        self.retrieved_children = {}
        self.children_retrieval_campaign_in_progress = True

    def end_children_retrieval_campaign(self, success=True):
        #print "end_update_campaign"
        self.children_retrieval_campaign_in_progress = False
        if success is True:
            self.update_children(self.retrieved_children, self.children_by_external_id)
            self.update_id += 1
        self.last_updated = time.time()
        self.retrieved_children = {}

    def retrieve_children(self, start=0, page=0):

        def items_retrieved(result, page, start_offset):
            if self.childrenRetrievingNeeded is True:
                new_offset = len(self.retrieved_children)
                return self.retrieve_children(new_offset, page + 1)  # we try the next page
            return self.retrieved_children

        self.childrenRetrievingNeeded = False
        if self.has_pages is True:
            self.childrenRetriever_params['offset'] = start
            self.childrenRetriever_params['page'] = page
        d = self.childrenRetriever(**self.childrenRetriever_params)
        d.addCallback(items_retrieved, page, start)
        return d

    def retrieve_all_children(self, start=0, request_count=0):

        def all_items_retrieved (result):
            #print "All children retrieved!"
            self.end_children_retrieval_campaign(True)
            return Container.get_children(self, start, request_count)

        def error_while_retrieving_items (error):
            #print "Error while retrieving all children!"
            self.end_children_retrieval_campaign(False)
            return Container.get_children(self, start, request_count)
        # if first retrieval and refresh required
        # we start a looping call to periodically update the children
        #if ((self.last_updated == 0) and (self.refresh > 0)):
        #    task.LoopingCall(self.retrieve_children,0,0).start(self.refresh, now=False)

        self.start_children_retrieval_campaign()
        if self.childrenRetriever is not None:
            d = self.retrieve_children(start)
            if start == 0:
                d.addCallbacks(all_items_retrieved, error_while_retrieving_items)
            return d
        else:
            self.end_children_retrieval_campaign()
            return self.children

    def get_children(self, start=0, request_count=0):

        # Check if an update is needed since last update
        current_time = time.time()
        delay_since_last_updated = current_time - self.last_updated
        period = self.refresh
        if (period > 0) and (delay_since_last_updated > period):
            self.info("Last update is older than %d s -> update data", period)
            self.childrenRetrievingNeeded = True

        if self.childrenRetrievingNeeded is True:
            #print "children Retrieving IS Needed (offset is %d)" % start
            return self.retrieve_all_children()
        else:
            return Container.get_children(self, start, request_count)

ROOT_CONTAINER_ID = 0
SEED_ITEM_ID = 1000


class AbstractBackendStore (BackendStore):
    def __init__(self, server, **kwargs):
        BackendStore.__init__(self, server, **kwargs)
        self.next_id = SEED_ITEM_ID
        self.store = {}

    def len(self):
        return len(self.store)

    def set_root_item(self, item):
        return self.append_item(item, storage_id=ROOT_CONTAINER_ID)

    def get_root_id(self):
        return ROOT_CONTAINER_ID

    def get_root_item(self):
        return self.get_by_id(ROOT_CONTAINER_ID)

    def append_item(self, item, storage_id=None):
        if storage_id is None:
            storage_id = self.getnextID()
        self.store[storage_id] = item
        item.storage_id = storage_id
        item.store = self
        return storage_id

    def remove_item(self, item):
        del self.store[item.storage_id]
        item.storage_id = -1
        item.store = None

    def get_by_id(self, id):
        if isinstance(id, basestring):
            id = id.split('@', 1)
            id = id[0].split('.')[0]
        try:
            return self.store[int(id)]
        except (ValueError, KeyError):
            pass
        return None

    def getnextID(self):
        ret = self.next_id
        self.next_id += 1
        return ret

    def __repr__(self):
        return self.__class__.__name__
