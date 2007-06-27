# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2007 - Frank Scholz <coherence@beebits.net>

""" DLNA decorator functions

"""

def AudioItem(func):
    def add(*args,**kwargs):
        result = func(*args, **kwargs)
        e = result.find('upnp:albumArtURI')
        if e != None:
            e.attrib['xmlns:dlna'] = 'urn:schemas-dlna-org:metadata-1-0'
            e.attrib['dlna:profileID'] = 'JPEG_TN'
        return result
    return add
