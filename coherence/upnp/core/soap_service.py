# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2005, Tim Potter <tpot@samba.org>
# Copyright 2006 John-Mark Gurney <gurney_j@resnet.uroegon.edu>
# Copyright 2006, Frank Scholz <coherence@beebits.net>

import platform

from twisted.web import soap, server
from twisted.python import log, failure
from twisted.internet import defer

from coherence.extern.et import ET
#from elementtree.ElementTree import Element, SubElement, tostring

import SOAPpy

UPNPERRORS = {401:'Invalid Action',
              402:'Invalid Args',
              501:'Action Failed',
              600:'Argument Value Invalid',
              601:'Argument Value Out of Range',
              602:'Optional Action Not Implemented',
              603:'Out Of Memory',
              604:'Human Intervention Required',
              605:'String Argument Too Long',
              606:'Action Not Authorized',
              607:'Signature Failure',
              608:'Signature Missing',
              609:'Not Encrypted',
              610:'Invalid Sequence',
              611:'Invalid Control URL',
              612:'No Such Session',}


from coherence.extern.logger import Logger
log = Logger('SOAP')

class errorCode(Exception):
    def __init__(self, status):
        Exception.__init__(self)
        self.status = status
        
class UPnPError:

    def __init__(self,status,description='without words'):
        root = ET.Element('s:Envelope')
        root.attrib['xmlns']='s=http://schemas.xmlsoap.org/soap/envelope/'
        root.attrib['s:encodingStyle']='s=http://schemas.xmlsoap.org/soap/encoding/'
        e = ET.SubElement(root,'s:Body')
        e = ET.SubElement(e,'s:Fault')
        ET.SubElement(e,'faultcode').text='s:Client'
        ET.SubElement(e,'faultstring').text='UPnPError'
        e = ET.SubElement(e,'detail')
        e = ET.SubElement(e, 'UPnPError')
        e.attrib['xmlns']='urn:schemas-upnp-org:control-1-0'
        ET.SubElement(e,'errorCode').text=str(status)
        try:
            ET.SubElement(e,'errorDescription').text=UPNPERRORS[status]
        except:
            ET.SubElement(e,'errorDescription').text=description
        self.xml = ET.tostring( root, encoding='utf-8')
        
    def get_xml(self):
        return self.xml

class UPnPPublisher(soap.SOAPPublisher):
    """UPnP requires headers and OUT parameters to be returned
    in a slightly
    different way than the SOAPPublisher class does."""

    def _sendResponse(self, request, response, status=200):
        log.info('_sendResponse', status, response)
        #request.setResponseCode(status)
        if status == 200:
            request.setResponseCode(200)
        else:
            request.setResponseCode(500)

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
        """
        response = SOAPpy.buildSOAP(SOAPpy.faultType("%s:Client" % SOAPpy.NS.ENV_T,
                                                        "UPnPError",
                                                        UPnPErrorDetail(401)),
                                                        encoding=self.encoding)
        """
        response = UPnPError(401).get_xml()
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
            """
            fault = SOAPpy.faultType("%s:Client" % SOAPpy.NS.ENV_T,
                                     "UPnPError",
                                    UPnPErrorDetail(status))
            """
        #response = SOAPpy.buildSOAP(fault, encoding=self.encoding)
        response = UPnPError(status).get_xml()
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
            if(headers.has_key('user-agent') and
                    headers['user-agent'].find('Xbox/') == 0):
                keywords['X_UPnPClient'] = 'XBox'

            for k, v in kwargs.items():
                keywords[str(k)] = v
            log.info('call', methodName, keywords)
            if hasattr(function, "useKeywords"):
                d = defer.maybeDeferred(function, **keywords)
            else:
                d = defer.maybeDeferred(function, *args, **keywords)

        d.addCallback(self._gotResult, request, methodName)
        d.addErrback(self._gotError, request, methodName)
        return server.NOT_DONE_YET
