# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2007 - Frank Scholz <coherence@beebits.net>

from twisted.web import server, resource
from twisted.python import log, failure
from twisted.internet import defer

from coherence import SERVER_ID

from coherence.extern.et import ET, namespace_map_update

from coherence.upnp.core.utils import parse_xml

from coherence.upnp.core import soap_lite

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
        root = ET.Element(e,'s:Fault')
        ET.SubElement(root,'faultcode').text='s:Client'
        ET.SubElement(root,'faultstring').text='UPnPError'
        e = ET.SubElement(root,'detail')
        e = ET.SubElement(root, 'UPnPError')
        e.attrib['xmlns']='urn:schemas-upnp-org:control-1-0'
        ET.SubElement(root,'errorCode').text=str(status)
        try:
            ET.SubElement(root,'errorDescription').text=UPNPERRORS[status]
        except:
            ET.SubElement(root,'errorDescription').text=description
        self.xml = soap_lite.build_soap_call(None, root, encoding=None)

    def get_xml(self):
        return self.xml

class UPnPPublisher(resource.Resource):
    """ Based upon twisted.web.soap.SOAPPublisher and
        extracted to remove the SOAPpy dependency

        UPnP requires headers and OUT parameters to be returned
        in a slightly
        different way than the SOAPPublisher class does.
    """

    isLeaf = 1
    encoding = "UTF-8"
    envelope_attrib = None

    def _sendResponse(self, request, response, status=200):
        log.info('_sendResponse', status, response)
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
        request.setHeader("SERVER", SERVER_ID)
        request.write(response)
        request.finish()

    def _methodNotFound(self, request, methodName):
        response = UPnPError(401).get_xml()
        self._sendResponse(request, response, status=401)

    def _gotResult(self, result, request, methodName, ns):
        log.info('_gotResult', result, request, methodName, ns)

        response = soap_lite.build_soap_call("{%s}%s" % (ns, methodName), result,
                                                is_response=True,
                                                encoding=None)
        #print "SOAP-lite response", response
        self._sendResponse(request, response)

    def _gotError(self, failure, request, methodName, ns):
        log.info('_gotError', failure, failure.value)
        e = failure.value
        status = 500

        if isinstance(e, errorCode):
            status = e.status
        else:
            failure.printTraceback()

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

        def print_c(e):
            for c in e.getchildren():
                print c, c.tag
                print_c(c)

        tree = parse_xml(data)
        #root = tree.getroot()
        #print_c(root)

        body = tree.find('{http://schemas.xmlsoap.org/soap/envelope/}Body')
        method = body.getchildren()[0]
        methodName = method.tag
        ns = None

        if methodName.startswith('{') and methodName.rfind('}') > 1:
            ns, methodName = methodName[1:].split('}')

        args = []
        kwargs = {}
        for child in method.getchildren():
            kwargs[child.tag] = self.decode_result(child)
            args.append(kwargs[child.tag])

        #p, header, body, attrs = SOAPpy.parseSOAPRPC(data, 1, 1, 1)
        #methodName, args, kwargs, ns = p._name, p._aslist, p._asdict, p._ns

        try:
            headers['content-type'].index('text/xml')
        except:
            self._gotError(failure.Failure(errorCode(415)), request, methodName)
            return server.NOT_DONE_YET

        # deal with changes in SOAPpy 0.11
        #if callable(args):
        #    args = args()
        #if callable(kwargs):
        #    kwargs = kwargs()

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

        d.addCallback(self._gotResult, request, methodName, ns)
        d.addErrback(self._gotError, request, methodName, ns)
        return server.NOT_DONE_YET

    def decode_result(self, element):
        type = element.get('{http://www.w3.org/1999/XMLSchema-instance}type')
        if type is not None:
            try:
                prefix, local = type.split(":")
                if prefix == 'xsd':
                    type = local
            except ValueError:
                pass

        if type == "integer" or type == "int":
            return int(element.text)
        if type == "float" or type == "double":
            return float(element.text)
        if type == "boolean":
            return element.text == "true"

        return element.text or ""
