# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2005, Tim Potter <tpot@samba.org>
# Copyright 2006 John-Mark Gurney <gurney_j@resnet.uroegon.edu>
# Copyright 2006, Frank Scholz <coherence@beebits.net>

import platform

from twisted.web import soap, server
from twisted.python import log, failure
from twisted.internet import defer

import SOAPpy

from coherence.extern.logger import Logger
log = Logger('SOAP')

class errorCode(Exception):
    def __init__(self, status):
        Exception.__init__(self)
        self.status = status

class UPnPPublisher(soap.SOAPPublisher):
    """UPnP requires headers and OUT parameters to be returned
    in a slightly
    different way than the SOAPPublisher class does."""

    def _sendResponse(self, request, response, status=200):
        log.info('_sendResponse', status, response)
        request.setResponseCode(status)

        if self.encoding is not None:
            mimeType = 'text/xml; charset="%s"' % self.encoding
        else:
            mimeType = "text/xml"
        request.setHeader("Content-type", mimeType)
        request.setHeader("Content-length", str(len(response)))
        request.setHeader("EXT", '')
        request.setHeader("SERVER",
            ','.join([platform.system(),platform.release(),'UPnP/1.0,Coherence UPnP framework,0.1']))
        """ XXX: version string """
        request.write(response)
        request.finish()
        
    def _methodNotFound(self, request, methodName):
        response = SOAPpy.buildSOAP(SOAPpy.faultType("%s:Server" % SOAPpy.NS.ENV_T,
                                                 "Method %s not found" % methodName),
                                  encoding=self.encoding)
        self._sendResponse(request, response, status=401)

    def _gotResult(self, result, request, methodName):
        log.info('_gotResult', result, request, methodName)
        response = SOAPpy.buildSOAP(kw=result, encoding=self.encoding)
        self._sendResponse(request, response)

    def _gotError(self, failure, request, methodName):
        log.info('_gotError', failure, failure.value)
        e = failure.value
        status = 500
        if isinstance(e, SOAPpy.faultType):
            fault = e
        else:
            if isinstance(e, errorCode):
                status = e.status
            else:
                failure.printTraceback()
            fault = SOAPpy.faultType("%s:Server" % SOAPpy.NS.ENV_T, "Method %s failed with %d." % (methodName,status))
        response = SOAPpy.buildSOAP(fault, encoding=self.encoding)
        self._sendResponse(request, response, status=status)

    def lookupFunction(self, functionName):
        function = getattr(self, "soap_%s" % functionName, None)
        if not function:
            function = getattr(self, "soap__generic", None)
        if function:
            return function, getattr(function, "useKeywords", False)
        else:
            return None, None
            
    def render(self, request):
        """Handle a SOAP command."""
        data = request.content.read()
        headers = request.getAllHeaders()
        log.info('soap_request:', headers)

        p, header, body, attrs = SOAPpy.parseSOAPRPC(data, 1, 1, 1)
        methodName, args, kwargs, ns = p._name, p._aslist, p._asdict, p._ns

        try:
            headers['content-type'].index('text/xml')
        except:
            self._gotError(failure.Failure(errorCode(415)), request, methodName)
            return server.NOT_DONE_YET
            
        # deal with changes in SOAPpy 0.11
        if callable(args):
            args = args()
        if callable(kwargs):
            kwargs = kwargs()

        function, useKeywords = self.lookupFunction(methodName)
        #print 'function', function, 'keywords', useKeywords, 'args', args, 'kwargs', kwargs

        if not function:
            self._methodNotFound(request, methodName)
            return server.NOT_DONE_YET
        else:
            keywords = {'soap_methodName':methodName}
            for k, v in kwargs.items():
                keywords[str(k)] = v
            if hasattr(function, "useKeywords"):
                d = defer.maybeDeferred(function, **keywords)
            else:
                d = defer.maybeDeferred(function, *args, **keywords)

        d.addCallback(self._gotResult, request, methodName)
        d.addErrback(self._gotError, request, methodName)
        return server.NOT_DONE_YET
