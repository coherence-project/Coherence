# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright (C) 2006 Fluendo, S.A. (www.fluendo.com).
# Copyright 2006, Frank Scholz <coherence@beebits.net>

import cElementTree
import urllib2
import codecs
import cStringIO
import string
from twisted.python import log
import socket
import fcntl
import struct

def parse_xml(data, encoding="iso-8859-1"):
    p = cElementTree.XMLParser(encoding=encoding)
    p.feed(data.encode(encoding))
    return cElementTree.ElementTree(p.close())

def parse_http_response(data):
        
    header, payload = data.split('\r\n\r\n')

    lines = header.split('\r\n')
    cmd = string.split(lines[0], ' ')
    lines = map(lambda x: x.replace(': ', ':', 1), lines[1:])
    lines = filter(lambda x: len(x) > 0, lines)

    headers = [string.split(x, ':', 1) for x in lines]
    headers = dict(map(lambda x: (x[0].lower(), x[1]), headers))

    return cmd, headers


def get_ip_address(ifname):
    """
    determine the IP address by interface name
    
    http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/439094
    (c) Paul Cannon
    Uses the Linux SIOCGIFADDR ioctl to find the IP address associated
    with a network interface, given the name of that interface, e.g. "eth0".
    The address is returned as a string containing a dotted quad.
    """
    
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(
        s.fileno(),
        0x8915,  # SIOCGIFADDR
        struct.pack('256s', ifname[:15])
    )[20:24])

def get_host_address():
    route_file = '/proc/net/route'
    route = open(route_file)
    if (route):
        tmp = route.readline() #skip first line
        while (tmp != ''):
            tmp = route.readline()
            l = tmp.split('\t')
            if (len(l) > 2):
                if l[2] != '00000000': #default gateway...
                    route.close()
                    return get_ip_address(l[0])
