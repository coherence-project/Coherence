# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright (C) 2006 Fluendo, S.A. (www.fluendo.com).
# Copyright 2006, Frank Scholz <coherence@beebits.net>

import SOAPpy
from twisted.web import soap
from twisted.web import client

from coherence.extern.elementsoap.ElementSOAP import SoapRequest, SoapElement
from coherence.extern.elementsoap.ElementSOAP import NS_SOAP_ENV, soap_namespaces, decode

from elementtree.ElementTree import tostring, Element, SubElement
from elementtree import ElementTree

class SOAPProxy(soap.Proxy):

    def __init__(self, url, namespace=None, envelope_attrib=None, header=None, soapaction=None):
        soap.Proxy.__init__(self, url, namespace, header)
        self.soapaction = soapaction
        self.envelope_attrib = envelope_attrib

    def callRemote(self, soapmethod, *args, **kwargs):
        soapaction = self.soapaction or soapmethod

        ns = self.namespace
        ElementTree._namespace_map.update({ns[1]:ns[0]})

        request = SoapRequest("{%s}%s" % (ns[1], soapmethod))

        type_map = {str: 'xsd:string',
                    int: 'xsd:int',
                    bool: 'xsd:boolean'}
                    
        for arg_name, arg in kwargs.iteritems():
            arg_type = type_map[type(arg)]
            arg_val = str(arg)
            if arg_type == 'xsd:boolean':
                arg_val = arg_val.lower()
            #SoapElement(request, arg_name, arg_type, arg_val)
            SoapElement(request, arg_name, '', arg_val)

        envelope = Element("s:Envelope")
        #for n, v in soap_namespaces.iteritems():
        #    envelope.attrib.update({"xmlns:%s" % v : n})
        
        if self.envelope_attrib:
            for n in self.envelope_attrib:
                envelope.attrib.update({n[0] : n[1]})
        else:
            envelope.attrib.update({'s:encodingStyle' : "http://schemas.xmlsoap.org/soap/encoding/"})
            envelope.attrib.update({'xmlns:s' :"http://schemas.xmlsoap.org/soap/envelope/"})
        body = SubElement(envelope, "s:Body")
        body.append(request)

        preambule = """<?xml version="1.0" encoding="utf-8"?>"""
        payload = preambule + tostring(envelope)
        
        #print "soapaction:", soapaction
        #print "callRemote:", payload
        #print "url:", self.url
        
        def gotError(failure, url):
            print "error requesting", url
            print failure


        return client.getPage(self.url, postdata=payload, method="POST",
                              headers={'content-type': 'text/xml ;charset="utf-8"',
                                       'SOAPACTION': '"%s"' % soapaction,
                                       }
                              ).addCallbacks(self._cbGotResult, gotError, None, None, [self.url], None)

    def _cbGotResult(self, result):
        #print "_cbGotResult 1", result
        result = SOAPpy.parseSOAPRPC(result)            
        #print "_cbGotResult 2", result
        if len(result) == 1:
            return result[0]
        else:
            return result
        """
        tree = ElementTree.fromstring(result)
        body = tree.find('%sBody' % NS_SOAP_ENV)
        r = decode(body)
        print "_cbGotResult 3", r
        return r
        """
