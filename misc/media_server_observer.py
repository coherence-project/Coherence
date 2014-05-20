#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php
#
# Copyright 2009, Benjamin Kampmann <ben.kampmann@gmail.com>
# Copyright 2014, Hartmut Goebel <h.goebel@crazy-compilers.com>

from twisted.internet import reactor

from coherence.base import Coherence
from coherence.upnp.devices.control_point import ControlPoint
from coherence.upnp.core import DIDLLite


# browse callback
def process_media_server_browse(result, client):
    print "browsing root of", client.device.get_friendly_name()
    print "result contains", result['NumberReturned'],
    print "out of", result['TotalMatches'], "total matches."

    elt = DIDLLite.DIDLElement.fromString(result['Result'])
    for item in elt.getItems():

        if item.upnp_class.startswith("object.container"):
            print "  container", item.title, "(%s)" % item.id,
            print "with", item.childCount, "items."

        if item.upnp_class.startswith("object.item"):
            print "  item", item.title, "(%s)." % item.id


# called for each media server found
def media_server_found(client, udn):
    print "Media Server found:", client.device.get_friendly_name()

    d = client.content_directory.browse(0,
            browse_flag='BrowseDirectChildren', process_result=False,
            backward_compatibility=False)
    d.addCallback(process_media_server_browse, client)


# sadly they sometimes get removed as well :(
def media_server_removed(udn):
    print "Media Server gone:", udn


def start():
    control_point = ControlPoint(Coherence({'logmode': 'warning'}),
            auto_client=['MediaServer'])
    control_point.connect(media_server_found,
            'Coherence.UPnP.ControlPoint.MediaServer.detected')
    control_point.connect(media_server_removed,
            'Coherence.UPnP.ControlPoint.MediaServer.removed')

    # now we should also try to discover the ones that are already there:
    for device in control_point.coherence.devices:
        print device

if __name__ == "__main__":
    reactor.callWhenRunning(start)
    reactor.run()
