# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2007 - Frank Scholz <coherence@beebits.net>

""" SOAP-lite

    some simple functions to implement the SOAP msgs
    needed by UPnP with ElementTree

    inspired by ElementSOAP.py
"""
from twisted.python.util import OrderedDict

from coherence.extern.et import ET

NS_SOAP_ENV = "{http://schemas.xmlsoap.org/soap/envelope/}"
NS_SOAP_ENC = "{http://schemas.xmlsoap.org/soap/encoding/}"
NS_XSI = "{http://www.w3.org/1999/XMLSchema-instance}"
NS_XSD = "{http://www.w3.org/1999/XMLSchema}"

SOAP_ENCODING = "http://schemas.xmlsoap.org/soap/encoding/"

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

def build_soap_error(status,description='without words'):
    """ builds an UPnP SOAP error msg
    """
    root = ET.Element('s:Fault')
    ET.SubElement(root,'faultcode').text='s:Client'
    ET.SubElement(root,'faultstring').text='UPnPError'
    e = ET.SubElement(root,'detail')
    e = ET.SubElement(e, 'UPnPError')
    e.attrib['xmlns']='urn:schemas-upnp-org:control-1-0'
    ET.SubElement(e,'errorCode').text=str(status)
    ET.SubElement(e,'errorDescription').text=UPNPERRORS.get(status,description)
    return build_soap_call(None, root, encoding=None)

def build_soap_call(method, arguments, is_response=False,
                                       encoding=SOAP_ENCODING,
                                       envelope_attrib=None,
                                       typed=None):
    """ create a shell for a SOAP request or response element
        - set method to none to omitt the method element and
          add the arguments directly to the body (for an error msg)
        - arguments can be a dict or an ET.Element
    """
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
    if isinstance(arguments,(dict,OrderedDict)) :
        type_map = {str: 'xsd:string',
                    unicode: 'xsd:string',
                    int: 'xsd:int',
                    float: 'xsd:float',
                    bool: 'xsd:boolean'}

        for arg_name, arg_val in arguments.iteritems():
            arg_type = type_map[type(arg_val)]
            if arg_type == 'xsd:string' and type(arg_val) == unicode:
                arg_val = arg_val.encode('utf-8')
            if arg_type == 'xsd:int' or arg_type == 'xsd:float':
                arg_val = str(arg_val)
            if arg_type == 'xsd:boolean':
                if arg_val == True:
                    arg_val = '1'
                else:
                    arg_val = '0'

            e = ET.SubElement(re, arg_name)
            if typed and arg_type:
                if not isinstance(type, ET.QName):
                    arg_type = ET.QName("http://www.w3.org/1999/XMLSchema", arg_type)
                e.set(NS_XSI + "type", arg_type)
            e.text = arg_val
    else:
        if arguments == None:
            arguments = {}
        re.append(arguments)



    preamble = """<?xml version="1.0" encoding="utf-8"?>"""
    return preamble + ET.tostring(envelope,'utf-8')
