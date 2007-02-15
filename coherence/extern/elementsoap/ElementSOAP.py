#
# ElementSOAP
# $Id: ElementSOAP.py 2925 2006-11-19 22:26:45Z fredrik $
#
# a simple SOAP library based on element trees
#
# history:
# 2003-11-16 fl   created (using bits and pieces from various sources)
# 2003-11-18 fl   added fault handling
# 2003-11-22 fl   added qname handling, decoder stub
# 2003-11-23 fl   handle type attributes, decode basic types
# 2005-03-09 mk   added SoapUsernameToken, SoapHeader, SoapSecurity
# 2006-11-19 fl   updated to use iterparse, Python 2.5, etc
#
# Copyright (c) 2003-2006 by Fredrik Lundh.  All rights reserved.
#
# With contributions by Michael Kenney, Florent Aide, and others.
#
# fredrik@pythonware.com
# http://www.pythonware.com
#

##
# This module provides helper classes for SOAP client implementations.
##

import ElementTree as ET

from HTTPClient import HTTPClient, HTTPError
import time, sha, random, binascii

# --------------------------------------------------------------------

# SOAP 1.1 namespaces
NS_SOAP_ENV = "{http://schemas.xmlsoap.org/soap/envelope/}"
NS_SOAP_ENC = "{http://schemas.xmlsoap.org/soap/encoding/}"
NS_XSI = "{http://www.w3.org/1999/XMLSchema-instance}"
NS_XSD = "{http://www.w3.org/1999/XMLSchema}"

SOAP_ENCODING = "http://schemas.xmlsoap.org/soap/encoding/"

# Namespaces for UsernameToken based authentication
WS_SEC = "http://schemas.xmlsoap.org/ws/2002/07/secext"
NS_WS_SEC = "{" + WS_SEC + "}"
NS_WS_UTIL = "{http://schemas.xmlsoap.org/ws/2002/07/utility}"

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
# @param encodingStyle SOAP encoding style.  Defaults to SOAP
#     encoding.  To create a request without an encodingStyle
#     attribute, pass in None.
# @return A SOAP request element structure.
# @defreturn Element

def SoapRequest(request, encodingStyle=SOAP_ENCODING):
    # create a SOAP request element
    request = ET.Element(request)
    if encodingStyle:
        request.set(NS_SOAP_ENV + "encodingStyle", encodingStyle)
    return request

##
# SOAP header factory.
#
# @return A SOAP header element structure.
# @defreturn Element

def SoapHeader():
    return ET.Element(NS_SOAP_ENV + 'Header')

##
# SOAP Security element factory.
#
# @param parent The parent element, usually a SoapHeader
# @return A SOAP Security element structure.

def SoapSecurity(parent):
    return ET.SubElement(parent, NS_WS_SEC + 'Security')

##
# SOAP UsernameToken element factory.
#
# @param parent The parent element, usually a Soap:Security header
# @param user username string
# @param pword password string
# @param expires expiration time in seconds realtive to now.
# @return A SOAP UsernameToken element structure.

def SoapUsernameToken(parent, user, pword, expires=180):
    nonce = sha.new(str(random.random())).digest()
    now = time.time()
    created = time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(now))
    expires = time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(now+expires))
    digest = sha.new(nonce + created + pword).digest()
    ut = ET.SubElement(parent, NS_WS_SEC + 'UsernameToken')
    elem = ET.SubElement(ut, NS_WS_SEC + 'Username')
    elem.text = user
    elem = ET.SubElement(ut, NS_WS_SEC + 'Password')
    elem.text = binascii.b2a_base64(digest)
    elem.set('Type', ET.QName(WS_SEC, 'PasswordDigest'))
    elem = ET.SubElement(ut, NS_WS_SEC + 'Nonce')
    elem.text = binascii.b2a_base64(nonce)
    elem = ET.SubElement(ut, NS_WS_UTIL + 'Created')
    elem.text = created
    elem = ET.SubElement(ut, NS_WS_UTIL + 'Expires')
    elem.text = expires
    return ut

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
    elem = ET.SubElement(parent, name)
    if type:
        if not isinstance(type, ET.QName):
            type = ET.QName("http://www.w3.org/1999/XMLSchema", type)
        elem.set(NS_XSI + "type", type)
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

    def call(self, action, request, header=None):

        # build SOAP envelope
        envelope = ET.Element(NS_SOAP_ENV + "Envelope")
        if header:
            envelope.append(header)
        body = ET.SubElement(envelope, NS_SOAP_ENV + "Body")
        body.append(request)

        # call the server
        try:
            response = self.__client.do_request(
                ET.tostring(envelope),
                extra_headers=[("SOAPAction", action)],
                parser=namespace_parse
                )
        except HTTPError, v:
            if v[0] == 500:
                # might be a SOAP fault
                response = namespace_parse(v[3])

        headers = response.findall(NS_SOAP_ENV + "Header")
        # FIXME: check mustunderstand attribute

        response = response.find(body.tag)[0]

        # fixup any XSI_type attributes
        # FIXME: only do this if envelope uses known soapencoding
        for elem in response.getiterator():
            type = elem.get(NS_XSI + "type")
            if type:
                elem.set(NS_XSI + "type", namespace_qname(elem, type))

        # look for fault descriptors
        if response.tag == NS_SOAP_ENV + "Fault":
            faultcode = response.find("faultcode")
            raise SoapFault(
                namespace_qname(faultcode, faultcode.text),
                response.findtext("faultstring"),
                response.findtext("faultactor"),
                response.find("detail")
                )

        response.tail = "\n\n" # nicer printouts

        return response

##
# (Experimental) Element decoder for the standard SOAP encoding
# scheme.  This function only decodes individual elements.  Use {@link
# decode} to handle nested data structures.
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
# Namespace-aware parser.  This parser attaches a namespace attribute
# to all elements.
#
# @param source Source (a file-like object).
# @return A 2-tuple containing an annotated element tree, and a qname
#     resolution helper.  The helper takes an element and a QName, and
#     returns an expanded URL/local part string.

def namespace_parse(source):
    events = ("start", "end", "start-ns", "end-ns")
    ns = []
    context = ET.iterparse(source, events=events)
    for event, elem in context:
        if event == "start-ns":
            ns.append(elem)
        elif event == "end-ns":
            ns.pop()
        elif event == "start":
            elem.set("(xmlns)", tuple(ns))
    return context.root

##
# Convert a QName string to an Element-style URL/local part string.
# Note that the parser converts element tags and attribute names
# during parsing; this method should only be used on attribute values
# and text sections.
#
# @param element An element created by the {@link namespace_parse}
#     function.
# @param qname The QName string.
# @return The expanded URL/local part string.
# @throws SyntaxError If the QName prefix is not defined for this
#     element.

def namespace_qname(element, qname):
    prefix, local = qname.split(":")
    for p, url in element.get("(xmlns)"):
        if prefix == p:
            return "{%s}%s" % (url, local)
    raise SyntaxError("unknown namespace prefix (%s)" % prefix)
