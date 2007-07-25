# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright (C) 2006 Fluendo, S.A. (www.fluendo.com).
# Copyright 2006, Frank Scholz <coherence@beebits.net>

from coherence.extern.et import parse_xml as et_parse_xml

from twisted.web import server, http, static
from twisted.web import client, error
from twisted.internet import reactor
from twisted.python import failure

import socket
import fcntl
import struct
import string

def parse_xml(data, encoding="utf-8"):
    return et_parse_xml(data,encoding)

def parse_http_response(data):

    header, payload = data.split('\r\n\r\n')

    lines = header.split('\r\n')
    cmd = lines[0].split(' ')
    lines = map(lambda x: x.replace(': ', ':', 1), lines[1:])
    lines = filter(lambda x: len(x) > 0, lines)

    headers = [x.split(':', 1) for x in lines]
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
    return socket.inet_ntoa(fcntl.ioctl(s.fileno(), 0x8915, struct.pack('256s', ifname[:15]) )[20:24])

def get_host_address():
    """ try to get determine the interface used for
        the default route, as this is most likely
        the interface we should bind to (on a single homed host!)
    """
    try:
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
    except IOerror:
        """ fallback to parsing the output of netstat """
        import os, posix
        (osname,_, _, _,_) = os.uname()
        osname = osname.lower()
        f = posix.popen('netstat -rn')
        lines = f.readlines()
        f.close()
        for l in lines:
            parts = [x.strip() for x in l.split(' ') if len(x) > 0]
            if parts[0] in ('0.0.0.0','default'):
                if osname[:6] == 'darwin':
                    return get_ip_address(parts[5])
                else:
                    return get_ip_address(parts[-1])

    """ return localhost if we havn't found anything """
    return '127.0.0.1'

class Site(server.Site):

    noisy = False

    def startFactory(self):
        http._logDateTimeStart()

class myHTTPPageGetter(client.HTTPPageGetter):

    def handleStatus_500(self):
        #print 'Status code 500 received'
        pass

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
    noisy = False

    def page(self, page):
        if self.waiting:
            self.waiting = 0
            self.deferred.callback((page, self.response_headers))


class HeaderAwareHTTPDownloader(client.HTTPDownloader):

    def gotHeaders(self, headers):
        self.value = headers
        if self.requestedPartial:
            contentRange = headers.get("content-range", None)
            if not contentRange:
                # server doesn't support partial requests, oh well
                self.requestedPartial = 0
                return
            start, end, realLength = http.parseContentRange(contentRange[0])
            if start != self.requestedPartial:
                # server is acting wierdly
                self.requestedPartial = 0

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

def downloadPage(url, file, contextFactory=None, *args, **kwargs):
    """Download a web page to a file.

    @param file: path to file on filesystem, or file-like object.

    See HTTPDownloader to see what extra args can be passed.
    """
    scheme, host, port, path = client._parse(url)
    factory = HeaderAwareHTTPDownloader(url, file, *args, **kwargs)
    factory.noisy = False
    if scheme == 'https':
        from twisted.internet import ssl
        if contextFactory is None:
            contextFactory = ssl.ClientContextFactory()
        reactor.connectSSL(host, port, factory, contextFactory)
    else:
        reactor.connectTCP(host, port, factory)
    return factory.deferred

class StaticFile(static.File):
    """ taken from twisted.web.static and modified
        accordingly to the patch by John-Mark Gurney
        http://resnet.uoregon.edu/~gurney_j/jmpc/dist/twisted.web.static.patch
    """

    def render(self, request):
        """You know what you doing."""
        self.restat()

        if self.type is None:
            self.type, self.encoding = static.getTypeAndEncoding(self.basename(),
                                                          self.contentTypes,
                                                          self.contentEncodings,
                                                          self.defaultType)

        if not self.exists():
            return self.childNotFound.render(request)

        if self.isdir():
            return self.redirect(request)

        #for content-length
        fsize = size = self.getFileSize()

        request.setHeader('accept-ranges','bytes')

        if self.type:
            request.setHeader('content-type', self.type)
        if self.encoding:
            request.setHeader('content-encoding', self.encoding)

        try:
            f = self.openForReading()
        except IOError, e:
            import errno
            if e[0] == errno.EACCES:
                return error.ForbiddenResource().render(request)
            else:
                raise

        if request.setLastModified(self.getmtime()) is http.CACHED:
            return ''

        trans = True

        range = request.getHeader('range')

        tsize = size
        if range is not None:
            # This is a request for partial data...
            bytesrange = string.split(range, '=')
            assert bytesrange[0] == 'bytes',\
                   "Syntactically invalid http range header!"
            start, end = string.split(bytesrange[1],'-', 1)
            if start:
                f.seek(int(start))
                if end:
                    end = int(end)
                else:
                    end = size - 1
            else:
                lastbytes = int(end)
                if size < lastbytes:
                    lastbytes = size
                start = size - lastbytes
                f.seek(start)
                fsize = lastbytes
                end = size - 1
            size = end + 1
            fsize = end - int(start) + 1
            # start is the byte offset to begin, and end is the byte offset
            # to end..  fsize is size to send, tsize is the real size of
            # the file, and size is the byte position to stop sending.

            if fsize <= 0:
                request.setResponseCode(http.REQUESTED_RANGE_NOT_SATISFIABLE)
                fsize = tsize
                trans = False
            else:
                request.setResponseCode(http.PARTIAL_CONTENT)
                request.setHeader('content-range',"bytes %s-%s/%s " % (
                    str(start), str(end), str(tsize)))

        request.setHeader('content-length', str(fsize))
        if request.method == 'HEAD' or trans == False:
            # pretend we're a HEAD request, so content-length
            # won't be overwritten.
            request.method = 'HEAD'
            return ''

        # return data
        # size is the byte position to stop sending, not how many bytes to send
        static.FileTransfer(f, size, request)
        # and make sure the connection doesn't get closed
        return server.NOT_DONE_YET


from datetime import datetime, tzinfo, timedelta
import random

class CET(tzinfo):

    def __init__(self):
        self.__offset = timedelta(minutes=60)
        self.__name = 'CET'

    def utcoffset(self, dt):
        return self.__offset

    def tzname(self, dt):
        return self.__name

    def dst(self,dt):
        return timedelta(0)

class CEST(tzinfo):

    def __init__(self):
        self.__offset = timedelta(minutes=120)
        self.__name = 'CEST'

    def utcoffset(self, dt):
        return self.__offset

    def tzname(self, dt):
        return self.__name

    def dst(self,dt):
        return timedelta(0)

bdates = [ datetime(1997,2,28,17,20,tzinfo=CET()),   # Sebastian Oliver
           datetime(1999,9,19,4,12,tzinfo=CEST()),   # Patrick Niklas
           datetime(2000,9,23,4,8,tzinfo=CEST()),    # Saskia Alexa
           datetime(2003,7,23,1,18,tzinfo=CEST()),   # Mara Sophie
                                                     # you are the best!
         ]

def datefaker():
    return random.choice(bdates)
