# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006,2007 Frank Scholz <coherence@beebits.net>
#
# a little helper to get the proper ElementTree package

import re

try:
    import cElementTree as ET
    import elementtree
    #print "we are on CET"
except ImportError:
    try:
        from elementtree import ElementTree as ET
        import elementtree
        #print "simply using ET"
    except ImportError:
        """ this seems to be necessary with the python2.5 on the Maemo platform """
        try:
            from xml.etree import cElementTree as ET
            from xml import etree as elementtree
        except ImportError:
            try:
                from xml.etree import ElementTree as ET
                from xml import etree as elementtree
            except ImportError:
                import sys
                print "no ElementTree module found, critical error"
                sys.exit(0)

#try:
#    from xml.etree import cElementTree as ET
#except ImportError:
#    try:
#        import cElementTree as ET
#    except ImportError:
#        try:
#            from xml.etree import ElementTree as ET
#        except ImportError:
#            try:
#                from elementtree import ElementTree as ET
#            except ImportError:
#                import sys
#                print "no ElementTree module found, critical error"
#               sys.exit(0)

#try:
#    from xml.etree.ElementTree import _ElementInterface
#except ImportError:
#    from elementtree.ElementTree import _ElementInterface

#try:
#    from xml.etree.ElementTree import _encode_entity as old_encode_entity
#    from xml.etree.ElementTree import _escape,_escape_map,_encode,_raise_serialization_error
#except ImportError:
#    from elementtree.ElementTree import _encode_entity as old_encode_entity
#    from elementtree.ElementTree import _escape,_escape_map,_encode,_raise_serialization_error

utf8_escape = re.compile(eval(r'u"[&<>\"]+"'))
escape = re.compile(eval(r'u"[&<>\"\u0080-\uffff]+"'))

def encode_entity(text, pattern=escape):
    # map reserved and non-ascii characters to numerical entities
    def escape_entities(m, map=elementtree.ElementTree._escape_map):
        out = []
        append = out.append
        for char in m.group():
            t = map.get(char)
            if t is None:
                t = "&#%d;" % ord(char)
            append(t)
        return ''.join(out)
    try:
        return elementtree.ElementTree._encode(pattern.sub(escape_entities, text), 'ascii')
    except TypeError:
        elementtree.ElementTree._raise_serialization_error(text)

def new_encode_entity(text, pattern=utf8_escape):
    # map reserved and non-ascii characters to numerical entities
    def escape_entities(m, map=elementtree.ElementTree._escape_map):
        out = []
        append = out.append
        for char in m.group():
            t = map.get(char)
            if t is None:
                t = "&#%d;" % ord(char)
            append(t)
        if type(text) == unicode:
            return ''.join(out)
        else:
            return u''.encode('utf-8').join(out)
    try:
        if type(text) == unicode:
            return elementtree.ElementTree._encode(escape.sub(escape_entities, text), 'ascii')
        else:
            return elementtree.ElementTree._encode(utf8_escape.sub(escape_entities, text.decode('utf-8')), 'utf-8')
    except TypeError:

        elementtree.ElementTree._raise_serialization_error(text)

elementtree.ElementTree._encode_entity = new_encode_entity

# it seems there are some ElementTree libs out there
# which have the alias XMLParser and some that haven't.
#
# So we just use the XMLTreeBuilder method for now
# if XMLParser isn't available.

if not hasattr(ET, 'XMLParser'):
    def XMLParser(encoding='utf-8'):
        return ET.XMLTreeBuilder()

    ET.XMLParser = XMLParser

def namespace_map_update(namespaces):
    #try:
    #    from xml.etree import ElementTree
    #except ImportError:
    #    from elementtree import ElementTree

    elementtree.ElementTree._namespace_map.update(namespaces)

class ElementInterface(elementtree.ElementTree._ElementInterface):
    """ helper class """

def indent(elem, level=0):
    """ generate pretty looking XML, based upon:
        http://effbot.org/zone/element-lib.htm#prettyprint
    """
    i = "\n" + level*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for elem in elem:
            indent(elem, level+1)
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i
