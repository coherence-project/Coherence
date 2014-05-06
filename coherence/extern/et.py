# -*- coding: utf-8 -*-
#
# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php
#
# Copyright 2006,2007 Frank Scholz <coherence@beebits.net>
# Copyright 2014 Hartmut Goebel <h.goebel@crazy-compilers.com>
#
"""
little helper to get the proper ElementTree package
"""

import re
import exceptions

try:
    import cElementTree as ET
    import elementtree
except ImportError:
    try:
        from elementtree import ElementTree as ET
        import elementtree
    except ImportError:
        # this seems to be necessary with the python2.5 on the Maemo platform
        try:
            from xml.etree import cElementTree as ET
            from xml import etree as elementtree
        except ImportError:
            try:
                from xml.etree import ElementTree as ET
                from xml import etree as elementtree
            except ImportError:
                raise ImportError("ElementTree: no ElementTree module found, "
                                  "critical error")

utf8_escape = re.compile(eval(r'u"[&<>\"]+"'))
escape = re.compile(eval(r'u"[&<>\"\u0080-\uffff]+"'))


def new_encode_entity(text, pattern=utf8_escape):
    
    def escape_entities(m, map=elementtree.ElementTree._escape_map):
        """
        map reserved and non-ascii characters to numerical entities
        """
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
            return elementtree.ElementTree._encode(
                escape.sub(escape_entities, text), 'ascii')
        else:
            return elementtree.ElementTree._encode(
                utf8_escape.sub(escape_entities, text.decode('utf-8')), 'utf-8')
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


namespace_map_update = elementtree.ElementTree._namespace_map.update


class ElementInterface(elementtree.ElementTree._ElementInterface): pass


def indent(elem, level=0):
    """
    generate pretty looking XML, based upon:
    http://effbot.org/zone/element-lib.htm#prettyprint
    """
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for elem in elem:
            indent(elem, level + 1)
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


def parse_xml(data, encoding="utf-8", dump_invalid_data=False):
    try:
        p = ET.XMLParser(encoding=encoding)
    except exceptions.TypeError:
        p = ET.XMLParser()

    # my version of twisted.web returns page_infos as a dictionary in
    # the second item of the data list
    if isinstance(data, (list, tuple)):
        data = data[0]

    try:
        data = data.encode(encoding)
    except UnicodeDecodeError:
        pass

    # Guess from who we're getting this?
    data = data.replace('\x00', '')
    try:
        p.feed(data)
    except Exception, error:
        if dump_invalid_data:
            print error, repr(data)
        p.close()
        raise
    else:
        return ET.ElementTree(p.close())
