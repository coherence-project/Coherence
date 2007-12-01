#
# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2007, Frank Scholz <coherence@beebits.net>

from coherence.extern.et import ET

class Config(dict):
    """
    an incomplete XML file to dict mapper

    - nodes with an attribute 'active' set to 'no' are ignored
      and not transferred into the dict

    - nodes with tags ending with 'list' are transferrend into
      an item with the key = 'tag without the list' and
      a list with the subnodes as the value
    """

    def __init__(self, file):
        self.file = file
        dict.__init__(self)
        xml = ET.parse(file)
        self.config = self.nodes_to_dict(xml.getroot())

    def nodes_to_dict(self,node):

        if node.tag.endswith('list'):
            d = []
        else:
            d = {}
            for attr,value in node.items():
                if attr == 'active':
                    continue
                d[attr] = value

        for n in node:
            if n.get('active','yes') == 'yes':
                if len(n) == 0:
                    if n.text is not None and len(n.text)>0:
                        d[n.get('name',n.tag)] = n.text
                    a = {}
                    for attr,value in n.items():
                        if attr == 'active':
                            continue
                        if isinstance(d,dict):
                            d[attr] = value
                        else:
                            a[attr] = value
                    if isinstance(d,list) and len(a):
                        d.append(a)
                else:
                    if isinstance(d,dict):
                        tag = n.tag
                        if tag.endswith('list'):
                            tag = tag[:-4]
                        d[n.get('name',tag)] = self.nodes_to_dict(n)
                    else:
                        d.append(self.nodes_to_dict(n))
        return d

    def __getitem__(self, key):
        """ fetch an item """
        val = self.config.get(key, None)
        return val

    def get(self, key, default=None):
        """ our version of ``get`` """
        try:
            return self[key]
        except KeyError:
            return default

    def __repr__(self):
        return "%r" % self.config