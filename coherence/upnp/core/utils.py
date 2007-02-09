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
from twisted.web import client
from twisted.internet import reactor

import socket
import fcntl
import struct

def parse_xml(data, encoding="iso-8859-1"):
    p = cElementTree.XMLParser(encoding=encoding)
    data = data.encode(encoding)

    # Guess from who we're getting this?
    data = data.replace('\x00','')
    try:
        p.feed(data)
    except Exception, error:
        print error, repr(data)
        return None
    else:
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
    """ return localhost if we havn't found anything """
    return '127.0.0.1'

class myHTTPPageGetter(client.HTTPPageGetter):

    def handleResponse(self, response):
        if self.quietLoss:
            return
        if self.failed:
            self.factory.noPage(
                failure.Failure(
                    error.Error(
                        self.status, self.message, response)))
        elif self.factory.method != 'HEAD' and self.length != None and self.length != 0:
            self.factory.noPage(failure.Failure(
                client.PartialDownloadError(self.status, self.message, response)))
        else:
            self.factory.page(response)
        # server might be stupid and not close connection. admittedly
        # the fact we do only one request per connection is also
        # stupid...
        self.transport.loseConnection()
        
class HeaderAwareHTTPClientFactory(client.HTTPClientFactory):

    protocol = myHTTPPageGetter

    def page(self, page):
        if self.waiting:
            self.waiting = 0
            self.deferred.callback((page, self.response_headers))

def getPage(url, contextFactory=None, *args, **kwargs):
    """Download a web page as a string.

    Download a page. Return a deferred, which will callback with a
    page (as a string) or errback with a description of the error.

    See HTTPClientFactory to see what extra args can be passed.
    """
    scheme, host, port, path = client._parse(url)
    factory = HeaderAwareHTTPClientFactory(url, *args, **kwargs)
    if scheme == 'https':
        from twisted.internet import ssl
        if contextFactory is None:
            contextFactory = ssl.ClientContextFactory()
        reactor.connectSSL(host, port, factory, contextFactory)
    else:
        reactor.connectTCP(host, port, factory)
    return factory.deferred
