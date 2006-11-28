# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright (C) 2006 Fluendo, S.A. (www.fluendo.com).
# Copyright 2006, Frank Scholz <coherence@beebits.net>

import cElementTree
import urllib2
import codecs
import cStringIO
import string
from twisted.python import log
import socket

def parse_xml(data, encoding="iso-8859-1"):
    p = cElementTree.XMLParser(encoding=encoding)
    p.feed(data.encode(encoding))
    return cElementTree.ElementTree(p.close())

def parse_http_response(data):
        
    header, payload = data.split('\r\n\r\n')

    lines = header.split('\r\n')
    cmd = string.split(lines[0], ' ')
    lines = map(lambda x: x.replace(': ', ':', 1), lines[1:])
    lines = filter(lambda x: len(x) > 0, lines)

    headers = [string.split(x, ':', 1) for x in lines]
    headers = dict(map(lambda x: (x[0].lower(), x[1]), headers))

    return cmd, headers
