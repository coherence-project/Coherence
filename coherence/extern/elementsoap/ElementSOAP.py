#
# ElementSOAP
# $Id: //modules/elementsoap/elementsoap/ElementSOAP.py#4 $
#
# a simple SOAP library based on element trees
#
# history:
# 2003-11-16 fl   created (using bits and pieces from various sources)
# 2003-11-18 fl   added fault handling
# 2003-11-22 fl   added qname handling, decoder stub
# 2003-11-23 fl   handle type attributes, decode basic types
#
# Copyright (c) 2003 by Fredrik Lundh.  All rights reserved.
#
# fredrik@pythonware.com
# http://www.pythonware.com
#

##
# This module provides helper classes for SOAP client implementations.
##

from elementtree import ElementTree
from elementtree import XMLTreeBuilder
from elementtree.ElementTree import Element, QName, SubElement, tostring
from HTTPClient import HTTPClient, HTTPError

# --------------------------------------------------------------------

def sanitycheck():
    # check that we have a version of ElementTree without the
    # "duplicate namespace prefix" bug
    elem = Element("doc")
    subelem = Element("tag")
    subelem.attrib["{url1}key"] = QName("{url2}value")
    elem.append(subelem)
    elem.append(subelem)
    try:
        ElementTree.fromstring(tostring(elem))
    except:
        import warnings
        warnings.warn(
            "This library requires ElementTree 1.2a5 or newer",
            RuntimeWarning
            )

sanitycheck()

# --------------------------------------------------------------------

# SOAP 1.1 namespaces
NS_SOAP_ENV = "{http://schemas.xmlsoap.org/soap/envelope/}"
NS_SOAP_ENC = "{http://schemas.xmlsoap.org/soap/encoding/}"
NS_XSI = "{http://www.w3.org/1999/XMLSchema-instance}"
NS_XSD = "{http://www.w3.org/1999/XMLSchema}"


soap_namespaces = {NS_SOAP_ENV[1:-1] : 'SOAP-ENV',
                   NS_SOAP_ENC[1:-1] : 'SOAP-ENC',
                   NS_XSI[1:-1]      : 'xsi',
                   NS_XSD[1:-1]      : 'xsd'
                   }

ElementTree._namespace_map.update(soap_namespaces)



##
# SOAP fault exception.
#
# @param faultcode SOAP fault code.
# @param faultstring SOAP fault description.
# @param faultactor SOAP fault actor.
# @param detail SOAP detail structure (an Element structure).

class SoapFault(Exception):

    ##
    # SOAP fault code.

    faultcode = None

    ##
    # SOAP fault description.

    faultstring = None

    ##
    # SOAP fault actor.

    faultactor = None

    ##
    # SOAP fault detail.  This is either None or an Element structure.

    detail = None

    def __init__(self, faultcode, faultstring, faultactor, detail):
        Exception.__init__(self, faultcode, faultstring, faultactor, detail)
        self.faultcode = faultcode
        self.faultstring = faultstring
        self.faultactor = faultactor
        self.detail = detail

##
# SOAP request factory.
#
# @param request SOAP request URL.
# @return A SOAP request element structure.
# @defreturn Element

def SoapRequest(request):
    # create a SOAP request element
    request = Element(request)
##     request.set(
##         NS_SOAP_ENV + "encodingStyle",
##         "http://schemas.xmlsoap.org/soap/encoding/"
##         )
    return request

##
# SOAP element factory.  This creates a value element, and appends
# it to a parent element.
#
# @param parent The parent element (usually a SOAP request element
#     another SOAP element).
# @param name Element name.
# @param type Element type.  Use None for untyped objects, a string
#     for types in the standard XML Schema namespace, or a QName.
# @param text Element value.
# @return A SOAP value element.
# @defreturn Element

def SoapElement(parent, name, type=None, text=None):
    # add a typed SOAP element to a request structure
    elem = SubElement(parent, name)
    if type:
        #if not isinstance(type, QName):
        #    type = QName("http://www.w3.org/1999/XMLSchema", type)
        #elem.set(NS_XSI + "type", type)
        elem.set("xsi:type", type)
    elem.text = text
    return elem

##
# Base class for SOAP service proxies.
#
# @param url Optional service URL.  If omitted, the URL defaults to
#    the default URL for this service (as defined by the <b>url</b>
#    class attribute).

class SoapService:

    def __init__(self, url=None):
        self.__client = HTTPClient(url or self.url)

    ##
    # Calls a remote SOAP method.
    #
    # @param action The SOAP action string.
    # @param request Request element.
    # @return A response element structure.  This is the contents
    #     of the SOAP Body element.
    # @defreturn Element
    # @throws SoapFault If the server returned a SOAP Fault.
    # @throws HTTPError If the server returned an HTTP error code
    #     other than 200 (OK) or 500 (SOAP error).

    def call(self, action, request):

        # build SOAP envelope
        envelope = Element(NS_SOAP_ENV + "Envelope")
        body = SubElement(envelope, NS_SOAP_ENV + "Body")
        body.append(request)

        # call the server
        try:
            parser = NamespaceParser()
            response = self.__client.do_request(
                tostring(envelope),
                extra_headers=[("SOAPAction", action)],
                parser=parser
                )
        except HTTPError, v:
            if v[0] == 500:
                # might be a SOAP fault
                response = ElementTree.parse(v[3], parser)

        headers = response.findall(NS_SOAP_ENV + "Header")
        # FIXME: check mustunderstand attribute

        response = response.find(body.tag)[0]

        # fixup any XSI_type attributes
        # FIXME: only do this if envelope uses known soapencoding
        for elem in response.getiterator():
            type = elem.get(NS_XSI + "type")
            if type:
                elem.set(NS_XSI + "type", parser.qname(elem, type))

        # look for fault descriptors
        if response.tag == NS_SOAP_ENV + "Fault":
            faultcode = response.find("faultcode")
            raise SoapFault(
                parser.qname(faultcode, faultcode.text),
                response.findtext("faultstring"),
                response.findtext("faultactor"),
                response.find("detail")
                )

        response.tail = "\n\n" # nicer printouts

        return response

##
# (Experimental) Element decoder for the standard SOAP encoding
# scheme.  This function only decodes individual elements.  Use {@link
# #decode} to handle nested data structures.
#
# @param element Element.
# @return A Python object, or None if the element argument was None.
# @throws ValueError If the element has an unknown type.

def decode_element(element):
    if element is None:
        return None
    type = element.get(NS_XSI + "type")
    if type == NS_XSD + "string":
        return element.text or ""
    if type == NS_XSD + "integer" or type == NS_XSD + "int":
        return int(element.text)
    if type == NS_XSD + "float" or type == NS_XSD + "double":
        return float(element.text)
    if type == NS_XSD + "boolean":
        return element.text == "true"
    if type == NS_SOAP_ENC + "base64":
        import base64
        return base64.decodestring(element.text)
    raise ValueError("type %s not supported" % type)


##
# (Experimental) Decoder for the standard SOAP encoding scheme.  This
# function supports SOAP arrays, and maps custom types to Python
# dictionaries (using accessor names as keys, and decoded elements
# as values).
#
# @param element Element.
# @return A Python object structure.
# @throws ValueError If a subelement has an unknown type.

def decode(element):
    type = element.get(NS_XSI + "type")
    # is it an array?
    if type == NS_SOAP_ENC + "Array":
        value = []
        for elem in element:
            value.append(decode(elem))
        return value
    # is it a primitive type?
    try:
        return decode_element(element)
    except ValueError:
        if type and type.startswith(NS_XSD):
            raise # unknown primitive type
    # assume it's a structure
    value = {}
    for elem in element:
        value[elem.tag] = decode(elem)
    return value

##
# Namespace-aware parser.  This parser attaches a <b>namespaces</b>
# attribute to all elements.

class NamespaceParser(XMLTreeBuilder.FancyTreeBuilder):

    ##
    # (Internal hook) Attach namespace attribute to element.

    def start(self, element):
        element.namespaces = tuple(self.namespaces)

    ##
    # Convert a QName string to an Element-style URL/local part
    # string.  Note that the parser converts element tags and
    # attribute names during parsing; this method should only be used
    # on attribute values and text sections.
    #
    # @param element An element created by this parser.
    # @param qname The QName string.
    # @return The expanded URL/local part string.
    # @throws SyntaxError If the QName prefix is not defined for this
    #     element.

    def qname(self, element, qname):
        prefix, local = qname.split(":")
        for p, url in element.namespaces:
            if prefix == p:
                return "{%s}%s" % (url, local)
        raise SyntaxError("unknown namespace prefix (%s)" % prefix)
