# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2008, Benjamin Kampmann <ben.kampmann@googlemail.com>

"""
This is a Media Backend that allows you to access the cool and cute pictures
from lolcats.com. This is mainly meant as a Sample Media Backend to learn how to
write a Media Backend.

So. You are still reading which allows me to assume that you want to learn how
to write a Media Backend for Coherence. NICE :) .

Once again: This is a SIMPLE Media Backend. It does not contain any big
requests, searches or even transcoding. The only thing we want to do in this
simple example, is to fetch a rss link on startup, parse it, save it and restart
the process one hour later again. Well, on top of this, we also want to provide
these informations as a Media Server in the UPnP/DLNA Network of course ;) .

Wow. You are still reading. You must be really interessted. Then let's go.
"""

########## NOTE:
# Please don't complain about the coding style of this document - I know. It is
# just this way to make it easier to document and to understand.



########## The imports
# The entry point for each kind of Backend is a 'BackendStore'. The BackendStore
# is the instance that does everything Usually. In this Example it can be
# understood as the 'Server', the object retrieving and serving the data.
from coherence.backend import BackendStore

# The data itself is stored in BackendItems. They are also the first things we
# are going to create.
from coherence.backend import BackendItem

# To make the data 'renderable' we need to define the DIDLite-Class of the Media
# we are providing. For that we have a bunch of helpers that we also want to
# import
from coherence.upnp.core import DIDLLite

# Coherence relies on the Twisted backend. I hope you are familar with the
# concept of deferreds. If not please read:
#       http://twistedmatrix.com/projects/core/documentation/howto/async.html
#
# It is a basic concept that you need to understand to understand the following
# code. But why am I talking about it? Oh, right, because we use a http-client
# based on the twisted.web.client module to do our requests.
from coherence.upnp.core.utils import getPage

# And we also import the reactor, that allows us to specify an action to happen
# later
from twisted.internet import reactor

# And to parse the RSS-Data (which is XML), we use the coherence helper
from coherence.extern.et import parse_xml


########## The models
# After the download and parsing of the data is done, we want to save it. In
# this case, we want to fetch the images and store their URL and the title of
# the image. That is the LolcatsImage class:

class LolcatsImage(BackendItem):
    # We inherit from BackendItem as it already contains a lot of helper methods
    # and implementations. For this simple example, we only have to fill the
    # item with data.

    def __init__(self, parent_id, id, title, url):
        self.parentid = parent_id       # used to be able to 'go back'

        self.update_id = 0

        self.id = id                    # each item has its own and unique id

        self.location = url             # the url of the picture

        self.name = title               # the title of the picture. Inside
                                        # coherence this is called 'name'


        # Item.item is a special thing. This is used to explain the client what
        # kind of data this is. For e.g. A VideoItem or a MusicTrack. In our
        # case, we have an image.
        self.item = DIDLLite.ImageItem(id, parent_id, self.name)

        # each Item.item has to have one or more Resource objects
        # these hold detailed information about the media data
        # and can represent variants of it (different sizes, transcoded formats)
        res = DIDLLite.Resource(self.location, 'http-get:*:image/jpeg:*')
        res.size = None #FIXME: we should have a size here
                        #       and a resolution entry would be nice too
        self.item.res.append(res)


class LolcatsContainer(BackendItem):
    # The LolcatsContainer will hold the reference to all our LolcatsImages. This
    # kind of BackenedItem is a bit different from the normal BackendItem,
    # because it has 'children' (the lolcatsimages). Because of that we have
    # some more stuff to do in here.

    def __init__(self, parent_id, id):
        # the ids as above
        self.parent_id = parent_id
        self.id = id

        # we never have a different name anyway
        self.name = 'LOLCats'

        # but we need to set it to a certain mimetype to explain it, that we
        # contain 'children'.
        self.mimetype = 'directory'

        # As we are updating our data periodically, we increase this value so
        # that our clients can check easier if something has changed since their
        # last request.
        self.update_id = 0

        # that is where we hold the children
        self.children = []

        # and we need to give a DIDLLite again. This time we want to be
        # understood as 'Container'.
        self.item = DIDLLite.Container(id, parent_id, self.name)

        self.item.childCount = None # will be set as soon as we have images

    def get_children(self, start=0, end=0):
        # This is the only important implementation thing: we have to return our
        # list of children
        if end != 0:
            return self.children[start:end]
        return self.children[start:]

    # there is nothing special in here
    # FIXME: move it to a base BackendContainer class
    def get_child_count(self):
        return len(self.children)

    def get_item(self):
        return self.item

    def get_name(self):
        return self.name

    def get_id(self):
        return self.id

########## The server
# As already said before the implementation of the server is done in an
# inheritance of a BackendStore. This is where the real code happens (usually).
# In our case this would be: downloading the page, parsing the content, saving
# it in the models and returning them on request.

class LolcatsStore(BackendStore):

    # this *must* be set. Because the (most used) MediaServer Coherence also
    # allows other kind of Backends (like remote lights).
    implements = ['MediaServer']

    # this is only for this implementation: the http link to the lolcats rss
    # feed that we want to read and parse:
    rss_url = "http://feeds.feedburner.com/ICanHasCheezburger?format=xml"

    # as we are going to build a (very small) tree with the items, we need to
    # define the first (the root) item:
    ROOT_ID = 0

    def __init__(self, server, *args, **kwargs):
        # first we inizialize our heritage
        BackendStore.__init__(self,server,**kwargs)

        # When a Backend is initialized, the configuration is given as keyword
        # arguments to the initialization. We receive it here as a dicitonary
        # and allow some values to be set:

        # the name of the MediaServer as it appears in the network
        self.name = kwargs.get('name', 'Lolcats')

        # timeout between updates in hours:
        self.refresh = int(kwargs.get('refresh', 1)) * (60 *60)

        # the UPnP device that's hosting that backend, that's already done
        # in the BackendStore.__init__, just left here the sake of completeness
        self.server = server

        # internally used to have a new id for each item
        self.next_id = 1000

        # we store the last update from the rss feed so that we know if we have
        # to parse again, or not:
        self.last_updated = None

        # initialize our lolcats container (no parent, this is the root)
        self.container = LolcatsContainer(None, self.ROOT_ID)

        # but as we also have to return them on 'get_by_id', we have our local
        # store of images per id:
        self.images = {}

        # we tell that if an XBox sends a request for images we'll
        # map the WMC id of that request to our local one
        self.wmc_mapping = {'16': 0}

        # and trigger an update of the data
        dfr = self.update_data()

        # So, even though the initialize is kind of done, Coherence does not yet
        # announce our Media Server.
        # Coherence does wait for signal send by us that we are ready now.
        # And we don't want that to happen as long as we don't have succeeded
        # in fetching some first data, so we delay this signaling after the update is done:
        dfr.addCallback(self.init_completed)
        dfr.addCallback(self.queue_update)

    def get_by_id(self, id):
        print "asked for", id, type(id)
        # what ever we are asked for, we want to return the container only
        if isinstance(id, basestring):
            id = id.split('@',1)
            id = id[0]
        if int(id) == self.ROOT_ID:
            return self.container
        return self.images.get(int(id), None)

    def upnp_init(self):
        # after the signal was triggered, this method is called by coherence and

        # from now on self.server is existing and we can do
        # the necessary setup here

        # that allows us to specify our server options in more detail.

        # here we define what kind of media content we do provide
        # mostly needed to make some naughty DLNA devices behave
        # will probably move into Coherence internals one day
        self.server.connection_manager_server.set_variable( \
            0, 'SourceProtocolInfo', ['http-get:*:image/jpeg:DLNA.ORG_PN=JPEG_TN;DLNA.ORG_OP=01;DLNA.ORG_FLAGS=00f00000000000000000000000000000',
                                      'http-get:*:image/jpeg:DLNA.ORG_PN=JPEG_SM;DLNA.ORG_OP=01;DLNA.ORG_FLAGS=00f00000000000000000000000000000',
                                      'http-get:*:image/jpeg:DLNA.ORG_PN=JPEG_MED;DLNA.ORG_OP=01;DLNA.ORG_FLAGS=00f00000000000000000000000000000',
                                      'http-get:*:image/jpeg:DLNA.ORG_PN=JPEG_LRG;DLNA.ORG_OP=01;DLNA.ORG_FLAGS=00f00000000000000000000000000000',
                                      'http-get:*:image/jpeg:*'])

        # and as it was done after we fetched the data the first time
        # we want to take care about the server wide updates as well
        self._update_container()

    def _update_container(self, result=None):
        # we need to inform Coherence about these changes
        # again this is something that will probably move
        # into Coherence internals one day
        if self.server:
            self.server.content_directory_server.set_variable(0,
                    'SystemUpdateID', self.update_id)
            value = (self.ROOT_ID,self.container.update_id)
            self.server.content_directory_server.set_variable(0,
                    'ContainerUpdateIDs', value)
        return result

    def update_loop(self):
        # in the loop we want to call update_data
        dfr = self.update_data()
        # aftert it was done we want to take care about updating
        # the container
        dfr.addCallback(self._update_container)
        # in ANY case queue an update of the data
        dfr.addBoth(self.queue_update)

    def update_data(self):
        # trigger an update of the data

        # fetch the rss
        dfr = getPage(self.rss_url)

        # push it through our xml parser
        dfr.addCallback(parse_xml)

        # then parse the data into our models
        dfr.addCallback(self.parse_data)

        return dfr

    def parse_data(self, xml_data):
        # So. xml_data is a cElementTree Element now. We can read our data from
        # it now.

        # each xml has a root element
        root = xml_data.getroot()

        # from there, we look for the newest update and compare it with the one
        # we have saved. If they are the same, we don't need to go on:
        pub_date = root.find('./channel/lastBuildDate').text

        if pub_date == self.last_updated:
            return

        # not the case, set this as the last update and continue
        self.last_updated = pub_date

        # and reset the childrens list of the container and the local storage
        self.container.children = []
        self.images = {}

        # Attention, as this is an example, this code is meant to be as simple
        # as possible and not as efficient as possible. IMHO the following code
        # pretty much sucks, because it is totally blocking (even though we have
        # 'only' 20 elements)

        # we go through our entries and do something specific to the
        # lolcats-rss-feed to fetch the data out of it
        url_item = './{http://search.yahoo.com/mrss/}content'
        for item in root.findall('./channel/item'):
            title = item.find('./title').text
            try:
                url = item.findall(url_item)[1].get('url', None)
            except IndexError:
                continue

            if url is None:
                continue

            image = LolcatsImage(self.ROOT_ID, self.next_id, title, url)
            self.container.children.append(image)
            self.images[self.next_id] = image

            # increase the next_id entry every time
            self.next_id += 1

        # and increase the container update id and the system update id
        # so that the clients can refresh with the new data
        self.container.update_id += 1
        self.update_id += 1

    def queue_update(self, error_or_failure):
        # We use the reactor to queue another updating of our data
        print error_or_failure
        reactor.callLater(self.refresh, self.update_loop)
