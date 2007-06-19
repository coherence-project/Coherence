# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2007 - Frank Scholz <coherence@beebits.net>

""" SOAP-lite

    some simple functions to implement the SOAP msgs
    needed by UPnP with ElementTree

    inspired by ElementSOAP.py
"""

from coherence.extern.et import ET

NS_SOAP_ENV = "{http://schemas.xmlsoap.org/soap/envelope/}"
NS_SOAP_ENC = "{http://schemas.xmlsoap.org/soap/encoding/}"
NS_XSI = "{http://www.w3.org/1999/XMLSchema-instance}"
NS_XSD = "{http://www.w3.org/1999/XMLSchema}"

SOAP_ENCODING = "http://schemas.xmlsoap.org/soap/encoding/"

def build_soap_call(method, arguments, is_response=False,
                                       encoding=SOAP_ENCODING,
                                       envelope_attrib=None,
                                       typed=None):
    # create a shell for a SOAP request or response element
    envelope = ET.Element("s:Envelope")
    if envelope_attrib:
        for n in envelope_attrib:
            envelope.attrib.update({n[0] : n[1]})
    else:
        envelope.attrib.update({'s:encodingStyle' : "http://schemas.xmlsoap.org/soap/encoding/"})
        envelope.attrib.update({'xmlns:s' :"http://schemas.xmlsoap.org/soap/envelope/"})

    body = ET.SubElement(envelope, "s:Body")

    if method:
        # append the method call
        if is_response is True:
            method += "Response"
        re = ET.SubElement(body,method)
        if encoding:
            re.set(NS_SOAP_ENV + "encodingStyle", encoding)
    else:
        re = body

    # append the arguments
    if isinstance(arguments,dict):
        type_map = {str: 'xsd:string',
                    int: 'xsd:int',
                    float: 'xsd:float',
                    bool: 'xsd:boolean'}

        for arg_name, arg_val in arguments.iteritems():
            arg_type = type_map[type(arg_val)]
            arg_val = str(arg_val)
            if arg_type == 'xsd:boolean':
                arg_val = arg_val.lower()

            e = ET.SubElement(re, arg_name)
            if typed and arg_type:
                if not isinstance(type, ET.QName):
                    arg_type = ET.QName("http://www.w3.org/1999/XMLSchema", arg_type)
                e.set(NS_XSI + "type", arg_type)
            e.text = arg_val
    else:
        re.append(arguments)



    preamble = """<?xml version="1.0" encoding="utf-8"?>"""
    return preamble + ET.tostring(envelope)
