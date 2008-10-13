#
# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2007,2008 Frank Scholz <coherence@beebits.net>

from coherence.extern.et import ET, indent

class ConfigMixin(object):

    def nodes_to_dict(self,node):

        if node.tag.endswith('list'):
            return  ConfigList(node)
        else:
            return ConfigDict(node)


class ConfigList(list,ConfigMixin):

    def __init__(self,node):
        self.name = node.tag
        list.__init__(self)
        self.from_element(node)

    def to_element(self):
        root = ET.Element(self.name)
        for v in self:
            if isinstance(v, (dict,list)):
                root.append(v.to_element())
        return root

    def from_element(self,node):
        for n in node:
            if n.get('active','yes') == 'yes':
                if len(n) == 0:
                    a = {}
                    for attr,value in n.items():
                        if attr == 'active':
                            continue
                        a[attr] = value
                    if len(a):
                        self.append(a)
                else:
                    self.append(self.nodes_to_dict(n))

class ConfigDict(dict,ConfigMixin):

    def __init__(self,node):
        self.name = node.tag
        dict.__init__(self)
        self.from_element(node)

    def to_element(self):
        root = ET.Element(self.name)
        for key, value in self.items():
            if isinstance(value, (dict,list)):
                root.append(value.to_element())
            else:
                s = ET.SubElement(root,key)
                if isinstance(value, basestring):
                    s.text = value
                else:
                    s.text = str(value)
        return root

    def from_element(self, node):
        for attr,value in node.items():
            if attr == 'active':
                continue
            self[attr] = value

        for n in node:
            if n.get('active','yes') == 'yes':
                if len(n) == 0:
                    if n.text is not None and len(n.text)>0:
                        self[n.get('name',n.tag)] = n.text
                    for attr,value in n.items():
                        if attr == 'active':
                            continue
                        self[attr] = value
                else:
                    tag = n.tag
                    #if tag.endswith('list'):
                    #    tag = tag[:-4]
                    self[n.get('name',tag)] = self.nodes_to_dict(n)

    #def __setitem__(self, key, value):
    #    self.config[key] = value

    #def __getitem__(self, key):
    #    """ fetch an item """
    #    value = self.config.get(key, None)
    #    return value

    #def __delitem__(self, key):
    #    del self.config[key]

    #def get(self, key, default=None):
    #    try:
    #        return self[key]
    #    except KeyError:
    #        return default

    #def items(self):
    #    """ """
    #    return self.config.items()

    #def keys(self):
    #    """ """
    #    return self.config.keys()

    #def values(self):
    #    """ """
    #    return self.config.values()

    #def __repr__(self):
    #    return "%r" % self.config

class Config(ConfigDict):
    """
    an incomplete XML file to dict and vice versa mapper

    - nodes with an attribute 'active' set to 'no' are ignored
      and not transferred into the dict

    - nodes with tags ending with 'list' are transferrend into
      an item with the key = 'tag' and a list with the subnodes
      as the value

    at the moment we parse the xml file and create dicts or lists out
    of the nodes, but maybe it is much easier to keep the xml structure
    as it is and simulate the dict/list access behavior on it?

    """

    def __init__(self, file):
        self.file = file
        dict.__init__(self)
        try:
            xml = ET.parse(file)
        except SyntaxError, msg:
            raise SyntaxError, msg
        except IOError, msg:
            raise IOError, msg
        except Exception, msg:
            raise SyntaxError, msg

        xmlroot = xml.getroot()
        self.name = xmlroot.tag
        self.from_element(xmlroot)

    def save(self,file=None):
        if file == None:
            file = self.file
        e = ET.Element(self.name)
        for key, value in self.items():
            if isinstance(value, (dict,list)):
                e.append(value.to_element())
            else:
                s = ET.SubElement(e,key)
                if isinstance(value, basestring):
                    s.text = value
                else:
                    s.text = str(value)
        indent(e)
        db = ET.ElementTree(e)
        db.write(file, encoding='utf-8')


if __name__ == '__main__':

    import sys

    config = Config(sys.argv[1])
    print config
    config['serverport'] = 55555
    config['test'] = 'test'
    config['logging']['level'] = 'info'
    del config['controlpoint']
    #del config['logging']['level']
    print config
    config.save('/tmp/t')