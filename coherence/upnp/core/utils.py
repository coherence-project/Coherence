# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright (C) 2006 Fluendo, S.A. (www.fluendo.com).
# Copyright 2006, Frank Scholz <coherence@beebits.net>

from os.path import abspath
import urlparse
from urlparse import urlsplit

from coherence.extern.et import parse_xml as et_parse_xml

from coherence import SERVER_ID


from twisted.web import server, http, static
from twisted.web import client, error
from twisted.web import proxy, resource, server
from twisted.internet import reactor,protocol,defer,abstract
from twisted.python import failure

from twisted.python.util import InsensitiveDict


try:
    from twisted.protocols._c_urlarg import unquote
except ImportError:
    from urllib import unquote

try:
    import netifaces
    have_netifaces = True
except ImportError:
    have_netifaces = False


def means_true(value):
    if isinstance(value,basestring):
        value = value.lower()
    return value in [True,1,'1','true','yes','ok']

def generalise_boolean(value):
    """ standardize the different boolean incarnations

        transform anything that looks like a "True" into a '1',
        and everything else into a '0'
    """
    if means_true(value):
        return '1'
    return '0'

generalize_boolean = generalise_boolean


def parse_xml(data, encoding="utf-8"):
    return et_parse_xml(data,encoding)

def parse_http_response(data):

    """ don't try to get the body, there are reponses without """
    header = data.split('\r\n\r\n')[0]

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

    Updated to work on BSD. OpenBSD and OSX share the same value for
    SIOCGIFADDR, and its likely that other BSDs do too.

    Updated to work on Windows,
    using the optional Python module netifaces
    http://alastairs-place.net/netifaces/

    Thx Lawrence for that patch!
    """

    if have_netifaces:
        if ifname in netifaces.interfaces():
            iface = netifaces.ifaddresses(ifname)
            ifaceadr = iface[netifaces.AF_INET]
            # we now have a list of address dictionaries, there may be multiple addresses bound
            return ifaceadr[0]['addr']
    import sys
    if sys.platform in ('win32','sunos5'):
        return '127.0.0.1'

    from os import uname
    import socket
    import fcntl
    import struct

    system_type = uname()[0]

    if system_type == "Linux":
        SIOCGIFADDR = 0x8915
    else:
        SIOCGIFADDR = 0xc0206921

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        return socket.inet_ntoa(fcntl.ioctl(
            s.fileno(),
            SIOCGIFADDR,
            struct.pack('256s', ifname[:15])
        )[20:24])
    except:
        return '127.0.0.1'


def get_host_address():
    """ try to get determine the interface used for
        the default route, as this is most likely
        the interface we should bind to (on a single homed host!)
    """

    import sys
    if sys.platform == 'win32':
        if have_netifaces:
            interfaces = netifaces.interfaces()
            if len(interfaces):
                return get_ip_address(interfaces[0])    # on windows assume first interface is primary
    else:
        try:
            route_file = '/proc/net/route'
            route = open(route_file)
            if(route):
                tmp = route.readline() #skip first line
                while (tmp != ''):
                    tmp = route.readline()
                    l = tmp.split('\t')
                    if (len(l) > 2):
                        if l[1] == '00000000': #default route...
                            route.close()
                            return get_ip_address(l[0])
        except IOError, msg:
            """ fallback to parsing the output of netstat """
            from twisted.internet import utils

            def result(r):
                from os import uname
                (osname,_, _, _,_) = uname()
                osname = osname.lower()
                lines = r.split('\n')
                for l in lines:
                    l = l.strip(' \r\n')
                    parts = [x.strip() for x in l.split(' ') if len(x) > 0]
                    if parts[0] in ('0.0.0.0','default'):
                        if osname[:6] == 'darwin':
                            return get_ip_address(parts[5])
                        else:
                            return get_ip_address(parts[-1])
                return '127.0.0.1'

            def fail(f):
                return '127.0.0.1'

            d = utils.getProcessOutput('netstat', ['-rn'])
            d.addCallback(result)
            d.addErrback(fail)
            return d
        except Exception, msg:
            import traceback
            traceback.print_exc()

    """ return localhost if we haven't found anything """
    return '127.0.0.1'

def de_chunk_payload(response):

    try:
        import cStringIO as StringIO
    except ImportError:
        import StringIO
    """ This method takes a chunked HTTP data object and unchunks it."""
    newresponse = StringIO.StringIO()
    # chunked encoding consists of a bunch of lines with
    # a length in hex followed by a data chunk and a CRLF pair.
    response = StringIO.StringIO(response)

    def read_chunk_length():
        line = response.readline()
        try:
            len = int(line.strip(),16)
        except ValueError:
            len = 0
        return len

    len = read_chunk_length()
    while (len > 0):
        newresponse.write(response.read(len))
        line = response.readline() # after chunk and before next chunk length
        len = read_chunk_length()

    return newresponse.getvalue()

class Request(server.Request):


    def process(self):
        "Process a request."

        # get site from channel
        self.site = self.channel.site

        # set various default headers
        self.setHeader('server', SERVER_ID)
        self.setHeader('date', http.datetimeToString())
        self.setHeader('content-type', "text/html")

        # Resource Identification
        url = self.path

        #remove trailing "/", if ever
        url = url.rstrip('/')

        scheme, netloc, path, query, fragment = urlsplit(url)
        self.prepath = []
        if path == "":
            self.postpath = []
        else:
            self.postpath = map(unquote, path[1:].split('/'))

        try:
            def deferred_rendering(r):
                self.render(r)

            resrc = self.site.getResourceFor(self)
            if resrc is None:
                self.setResponseCode(http.NOT_FOUND, "Error: No resource for path %s" % path)
                self.finish()
            elif isinstance(resrc, defer.Deferred):
                resrc.addCallback(deferred_rendering)
                resrc.addErrback(self.processingFailed)
            else:
                self.render(resrc)

        except:
            self.processingFailed(failure.Failure())


class Site(server.Site):

    noisy = False
    requestFactory = Request

    def startFactory(self):
        pass
        #http._logDateTimeStart()


class ProxyClient(http.HTTPClient):
    """Used by ProxyClientFactory to implement a simple web proxy."""

    def __init__(self, command, rest, version, headers, data, father):
        self.father = father
        self.command = command
        self.rest = rest
        if headers.has_key("proxy-connection"):
            del headers["proxy-connection"]
        #headers["connection"] = "close"
        self.headers = headers
        #print "command", command
        #print "rest", rest
        #print "headers", headers
        self.data = data
        self.send_data = 0

    def connectionMade(self):
        self.sendCommand(self.command, self.rest)
        for header, value in self.headers.items():
            self.sendHeader(header, value)
        self.endHeaders()
        self.transport.write(self.data)

    def handleStatus(self, version, code, message):
        if message:
            # Add a whitespace to message, this allows empty messages
            # transparently
            message = " %s" % (message,)

        if version == 'ICY':
            version = 'HTTP/1.1'
        #print "ProxyClient handleStatus", version, code, message
        self.father.transport.write("%s %s %s\r\n" % (version, code, message))

    def handleHeader(self, key, value):
        #print "ProxyClient handleHeader", key, value
        if not key.startswith('icy-'):
            #print "ProxyClient handleHeader", key, value
            self.father.transport.write("%s: %s\r\n" % (key, value))

    def handleEndHeaders(self):
        #self.father.transport.write("%s: %s\r\n" % ( 'Keep-Alive', ''))
        #self.father.transport.write("%s: %s\r\n" % ( 'Accept-Ranges', 'bytes'))
        #self.father.transport.write("%s: %s\r\n" % ( 'Content-Length', '2000000'))
        #self.father.transport.write("%s: %s\r\n" % ( 'Date', 'Mon, 26 Nov 2007 11:04:12 GMT'))
        #self.father.transport.write("%s: %s\r\n" % ( 'Last-Modified', 'Sun, 25 Nov 2007 23:19:51 GMT'))
        ##self.father.transport.write("%s: %s\r\n" % ( 'Server', 'Apache/2.0.52 (Red Hat)'))
        self.father.transport.write("\r\n")

    def handleResponsePart(self, buffer):
        #print "ProxyClient handleResponsePart", len(buffer), self.father.chunked
        self.send_data += len(buffer)
        self.father.write(buffer)

    def handleResponseEnd(self):
        #print "handleResponseEnd", self.send_data
        self.transport.loseConnection()
        self.father.channel.transport.loseConnection()


class ProxyClientFactory(protocol.ClientFactory):
    """
    Used by ProxyRequest to implement a simple web proxy.
    """

    protocol = proxy.ProxyClient


    def __init__(self, command, rest, version, headers, data, father):
        self.father = father
        self.command = command
        self.rest = rest
        self.headers = headers
        self.data = data
        self.version = version


    def buildProtocol(self, addr):
        return self.protocol(self.command, self.rest, self.version,
                             self.headers, self.data, self.father)


    def clientConnectionFailed(self, connector, reason):
        self.father.transport.write("HTTP/1.0 501 Gateway error\r\n")
        self.father.transport.write("Content-Type: text/html\r\n")
        self.father.transport.write("\r\n")
        self.father.transport.write('''<H1>Could not connect</H1>''')
        self.father.transport.loseConnection()


class ReverseProxyResource(proxy.ReverseProxyResource):
    """
    Resource that renders the results gotten from another server

    Put this resource in the tree to cause everything below it to be relayed
    to a different server.

    @ivar proxyClientFactoryClass: a proxy client factory class, used to create
        new connections.
    @type proxyClientFactoryClass: L{ClientFactory}

    @ivar reactor: the reactor used to create connections.
    @type reactor: object providing L{twisted.internet.interfaces.IReactorTCP}
    """

    proxyClientFactoryClass = ProxyClientFactory

    def __init__(self, host, port, path, reactor=reactor):
        """
        @param host: the host of the web server to proxy.
        @type host: C{str}

        @param port: the port of the web server to proxy.
        @type port: C{port}

        @param path: the base path to fetch data from. Note that you shouldn't
            put any trailing slashes in it, it will be added automatically in
            request. For example, if you put B{/foo}, a request on B{/bar} will
            be proxied to B{/foo/bar}.
        @type path: C{str}
        """
        resource.Resource.__init__(self)
        self.host = host
        self.port = port
        self.path = path
        self.qs = ''
        self.reactor = reactor

    def getChild(self, path, request):
        return ReverseProxyResource(
            self.host, self.port, self.path + '/' + path)

    def render(self, request):
        """
        Render a request by forwarding it to the proxied server.
        """
        # RFC 2616 tells us that we can omit the port if it's the default port,
        # but we have to provide it otherwise
        if self.port == 80:
            request.received_headers['host'] = self.host
        else:
            request.received_headers['host'] = "%s:%d" % (self.host, self.port)
        request.content.seek(0, 0)
        qs = urlparse.urlparse(request.uri)[4]
        if qs == '':
            qs = self.qs
        if qs:
            rest = self.path + '?' + qs
        else:
            rest = self.path
        clientFactory = self.proxyClientFactoryClass(
            request.method, rest, request.clientproto,
            request.getAllHeaders(), request.content.read(), request)
        self.reactor.connectTCP(self.host, self.port, clientFactory)
        return server.NOT_DONE_YET

    def resetTarget(self,host,port,path,qs=''):
        self.host = host
        self.port = port
        self.path = path
        self.qs = qs

class ReverseProxyUriResource(ReverseProxyResource):

    uri = None

    def __init__(self, uri, reactor=reactor):
        self.uri = uri
        _,host_port,path,params,_ = urlsplit(uri)
        if host_port.find(':') != -1:
            host,port = tuple(host_port.split(':'))
            port = int(port)
        else:
            host = host_port
            port = 80
        if path =='':
            path = '/'
        if params == '':
            rest = path
        else:
            rest = '?'.join((path, params))
        ReverseProxyResource.__init__(self, host, port, rest, reactor)

    def resetUri (self, uri):
        self.uri = uri
        _,host_port,path,params,_ =  urlsplit(uri)
        if host_port.find(':') != -1:
            host,port = tuple(host_port.split(':'))
            port = int(port)
        else:
            host = host_port
            port = 80
        self.resetTarget(host, port, path, params)


class myHTTPPageGetter(client.HTTPPageGetter):

    followRedirect = True

    def connectionMade(self):
        method = getattr(self, 'method', 'GET')
        #print "myHTTPPageGetter", method, self.factory.path
        self.sendCommand(method, self.factory.path)
        self.sendHeader('Host', self.factory.headers.get("host", self.factory.host))
        self.sendHeader('User-Agent', self.factory.agent)
        if self.factory.cookies:
            l=[]
            for cookie, cookval in self.factory.cookies.items():
                l.append('%s=%s' % (cookie, cookval))
            self.sendHeader('Cookie', '; '.join(l))
        data = getattr(self.factory, 'postdata', None)
        if data is not None:
            self.sendHeader("Content-Length", str(len(data)))
        for (key, value) in self.factory.headers.items():
            if key.lower() != "content-length":
                # we calculated it on our own
                self.sendHeader(key, value)
        self.endHeaders()
        self.headers = {}

        if data is not None:
            self.transport.write(data)

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
            if(self.headers.has_key('transfer-encoding') and
               self.headers['transfer-encoding'][0].lower() == 'chunked'):
                self.factory.page(de_chunk_payload(response))
            else:
                self.factory.page(response)
        # server might be stupid and not close connection. admittedly
        # the fact we do only one request per connection is also
        # stupid...
        self.quietLoss = 1
        self.transport.loseConnection()


class HeaderAwareHTTPClientFactory(client.HTTPClientFactory):

    protocol = myHTTPPageGetter
    noisy = False

    def buildProtocol(self, addr):
        p = client.HTTPClientFactory.buildProtocol(self, addr)
        p.method = self.method
        p.followRedirect = self.followRedirect
        return p

    def page(self, page):
        client.HTTPClientFactory.page(self, (page, self.response_headers))


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
    """
    Download a web page as a string.

    Download a page. Return a deferred, which will callback with a
    page (as a string) or errback with a description of the error.

    See HTTPClientFactory to see what extra args can be passed.
    """
    kwargs['agent'] = "Coherence PageGetter"
    return client._makeGetterFactory(
        url,
        HeaderAwareHTTPClientFactory,
        contextFactory=contextFactory,
        *args, **kwargs).deferred


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


# StaticFile used to be a patched version of static.File. The later
# was fixed in TwistedWeb 8.2.0 and 9.0.0, while the patched variant
# contained deprecated and removed code.
StaticFile = static.File


class BufferFile(static.File):
    """ taken from twisted.web.static and modified
        accordingly to the patch by John-Mark Gurney
        http://resnet.uoregon.edu/~gurney_j/jmpc/dist/twisted.web.static.patch
    """

    def __init__(self, path, target_size=0, *args):
        static.File.__init__(self, path, *args)
        self.target_size = target_size
        self.upnp_retry = None

    def render(self, request):
        #print ""
        #print "BufferFile", request

        # FIXME detect when request is REALLY finished
        if request is None or request.finished :
            print "No request to render!"
            return ''

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
        if (self.target_size > 0):
            fsize = size = int(self.target_size)
        else:
            fsize = size = int(self.getFileSize())

        #print fsize

        if size == int(self.getFileSize()):
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
        #print "StaticFile", range

        tsize = size
        if range is not None:
            # This is a request for partial data...
            bytesrange = range.split('=')
            assert bytesrange[0] == 'bytes',\
                   "Syntactically invalid http range header!"
            start, end = bytesrange[1].split('-', 1)
            if start:
                start = int(start)
                # Are we requesting something beyond the current size of the file?
                if (start >= self.getFileSize()):
                    # Retry later!
                    print bytesrange
                    print "Requesting data beyond current scope -> postpone rendering!"
                    self.upnp_retry = reactor.callLater(1.0, self.render, request)
                    return server.NOT_DONE_YET

                f.seek(start)
                if end:
                    #print ":%s" % end
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
                #print "StaticFile", start, end, tsize

        request.setHeader('content-length', str(fsize))

        if request.method == 'HEAD' or trans == False:
            # pretend we're a HEAD request, so content-length
            # won't be overwritten.
            request.method = 'HEAD'
            return ''

        #print "StaticFile out", request.headers, request.code

        # return data
        # size is the byte position to stop sending, not how many bytes to send

        BufferFileTransfer(f, size - f.tell(), request)
		# and make sure the connection doesn't get closed
        return server.NOT_DONE_YET


class BufferFileTransfer(object):
    """
    A class to represent the transfer of a file over the network.
    """
    request = None

    def __init__(self, file, size, request):
        self.file = file
        self.size = size
        self.request = request
        self.written = self.file.tell()
        request.registerProducer(self, 0)

    def resumeProducing(self):
        #print "resumeProducing", self.request,self.size,self.written
        if not self.request:
            return
        data = self.file.read(min(abstract.FileDescriptor.bufferSize, self.size - self.written))
        if data:
            self.written += len(data)
            # this .write will spin the reactor, calling .doWrite and then
            # .resumeProducing again, so be prepared for a re-entrant call
            self.request.write(data)
        if self.request and self.file.tell() == self.size:
            self.request.unregisterProducer()
            self.request.finish()
            self.request = None

    def pauseProducing(self):
        pass

    def stopProducing(self):
        #print "stopProducing",self.request
        self.request.unregisterProducer()
        self.file.close()
        self.request.finish()
        self.request = None


from datetime import datetime, tzinfo, timedelta
import random

class _tz(tzinfo):
    def utcoffset(self, dt):
        return self._offset

    def tzname(self, dt):
        return self._name

    def dst(self,dt):
        return timedelta(0)

class _CET(_tz):
    _offset = timedelta(minutes=60)
    _name = 'CET'

class _CEST(_tz):
    _offset = timedelta(minutes=120)
    _name = 'CEST'

_bdates = [datetime(1997,2,28,17,20,tzinfo=_CET()),  # Sebastian Oliver
           datetime(1999,9,19,4,12,tzinfo=_CEST()),  # Patrick Niklas
           datetime(2000,9,23,4,8,tzinfo=_CEST()),   # Saskia Alexa
           datetime(2003,7,23,1,18,tzinfo=_CEST()),  # Mara Sophie
                                                     # you are the best!
         ]

def datefaker():
    return random.choice(bdates)
