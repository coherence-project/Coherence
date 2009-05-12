# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2007 - Frank Scholz <coherence@beebits.net>

DLNA_BUS_NAME = 'org.DLNA'     # bus name for DLNA API

BUS_NAME = 'org.Coherence'     # the one with the dots
OBJECT_PATH = '/org/Coherence'  # the one with the slashes ;-)

DEVICE_IFACE = '%s.device' % BUS_NAME
SERVICE_IFACE = '%s.service' % BUS_NAME

CDS_SERVICE = '%s.DMS.CDS' % DLNA_BUS_NAME
