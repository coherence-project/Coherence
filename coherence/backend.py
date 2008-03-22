# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2007, Frank Scholz <coherence@beebits.net>

from coherence.extern.simple_plugin import Plugin

from coherence import log

import louie

class Backend(log.Loggable,Plugin):

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

    def __init__(self,server,**kwargs):
        """ the init method for a backend,
            should probably most of the time be overwritten
            when the init is done, send a signal to its device

            the device will then setup and announce itself,
            after that it calls the backends upnp_init method
        """
        self.config = kwargs
        self.server = server # the UPnP device that's hosting that backend

        """ do whatever is necessary with the stuff we can
            extract from the config dict
        """
        louie.send('Coherence.UPnP.Backend.init_completed', None, backend=self)

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
    wmc_mapping = {'4':'4', '5':'5', '6':'6','7':'7','14':'14','F':'F',
                   '11':'11','16':'16','B':'B','C':'C','D':'D',
                   '13':'13', '17':'17',
                   '8':'8', '9':'9', '10':'10', '15':'15', 'A':'A', 'E':'E'}

    def __init__(self,server,*args,**kwargs):
        """ the init method for a MediaServer backend,
            should probably most of the time be overwritten
            when the init is done, send a signal to its device

            the device will then setup and announce itself,
            after that it calls the backends upnp_init method
        """
        self.config = kwargs
        self.server = server # the UPnP device that's hosting that backend
        self.update_id = 0

        """ do whatever is necessary with the stuff we can
            extract from the config dict
        """
        louie.send('Coherence.UPnP.Backend.init_completed', None, backend=self)

        self.wmc_mapping.update({'4':lambda: self._get_all_items(0),
                                 '8':lambda: self._get_all_items(0),
                                 'B':lambda: self._get_all_items(0),
                                })

    def _get_all_items(self,id):
        """ a helper method for to get all items as a response
            to some XBox 360 UPnP Search action
            probably never be used as the backend will overwrite
            the wmc_mapping with more appropriate methods
        """
        items = []
        item = self.get_by_id(id)
        if item is not None:
            containers = [item]
            while len(containers)>0:
                container = containers.pop()
                if container.mimetype not in ['root', 'directory']:
                    continue
                for child in container.get_children(0,0):
                    if child.mimetype in ['root', 'directory']:
                        containers.append(child)
                    else:
                        items.append(child)
        return items


class BackendItem(log.Loggable):

    """ the base class for all MediaServer backend items
    """

    logCategory = 'backend_item'

    def __init__(self, *args, **kwargs):
        """ most of the time we collect the necessary data for
            an UPnP ContentDirectoryService Container or Object
            and instantiate it here

            self.item = DIDLLite.Container(...)
        """
        self.item = None
        self.cover = None # if we have some album art image, let's put
                          # the filepath or link into here

    def get_children(self,start=0,end=0):
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
        """
        return self.item

    def get_cover(self):
        """ called the MediaServer web
            should return

            - the filepath where to find the album art file
        """
        return self.cover