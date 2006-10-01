# Elisa - Home multimedia server
# Copyright (C) 2006 Fluendo, S.A. (www.fluendo.com).
# All rights reserved.
# 
# This software is available under three license agreements.
# 
# There are various plugins and extra modules for Elisa licensed
# under the MIT license. For instance our upnp module uses this license.
# 
# The core of Elisa is licensed under GPL version 2.
# See "LICENSE.GPL" in the root of this distribution including a special 
# exception to use Elisa with Fluendo's plugins.
# 
# The GPL part is also available under a commerical licensing
# agreement.
# 
# The second license is the Elisa Commercial License Agreement.
# This license agreement is available to licensees holding valid
# Elisa Commercial Agreement licenses.
# See "LICENSE.Elisa" in the root of this distribution.



import cElementTree
import urllib2
import codecs
import cStringIO
import string
from twisted.python import log
import socket

socket.setdefaulttimeout(15)

def url_fetch(url):
    #log.msg('Fetching %r' % url)
    req = urllib2.Request(url)
    try:
        handle = urllib2.urlopen(req)
    except IOError, e:
        if hasattr(e, 'reason'):
            log.msg('We failed to reach a server. Reason: %s' % e.reason)
        elif hasattr(e, 'code'):
            log.msg('The server couldn\'t fulfill the request. Error code: %s' % e.code)
        handle = None
    return handle

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
