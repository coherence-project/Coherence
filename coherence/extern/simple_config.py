# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# based on: http://code.activestate.com/recipes/573463/
# Modified by Philippe Normand

# Copyright 2008, Frank Scholz <coherence@beebits.net>

from coherence.extern.et import ET as ElementTree, indent, parse_xml

class ConfigItem(object):
    """ the base """


class Config(ConfigItem):

    def __init__(self,filename,root=None,preamble=False,element2attr_mappings=None):
        self.filename = filename
        self.element2attr_mappings = element2attr_mappings or {}
        self.db = parse_xml(open(self.filename).read())
        self.config = self.db = ConvertXmlToDict(self.db.getroot())
        self.preamble = ''
        if preamble == True:
            self.preamble = """<?xml version="1.0" encoding="utf-8"?>\n"""
        if root != None:
            try:
                self.config = self.config[root]
            except KeyError:
                pass
        self.config.save = self.save

    def tostring(self):
        root = ConvertDictToXml(self.db,self.element2attr_mappings)
        tree = ElementTree.ElementTree(root).getroot()
        indent(tree,0)
        xml = self.preamble + ElementTree.tostring(tree, encoding='utf-8')
        return xml

    def save(self, new_filename=None):
        if new_filename != None:
            self.filename = new_filename
        xml = self.tostring()
        f = open(self.filename, 'wb')
        f.write(xml)
        f.close()

    def get(self,key,default=None):
        if key in self.config:
            item = self.config[key]
            try:
                if item['active'] == 'no':
                    return default
                return item
            except (TypeError,KeyError):
                return item
        return default

    def set(self,key,value):
        self.config[key] = value


class XmlDictObject(dict,ConfigItem):
    def __init__(self, initdict=None):
        if initdict is None:
            initdict = {}
        dict.__init__(self, initdict)
        self._attrs = {}

    def __getattr__(self, item):
        value = self.__getitem__(item)
        try:
            if value['active'] == 'no':
                raise KeyError
        except (TypeError,KeyError):
            return value
        return value

    def __setattr__(self, item, value):
        if item == '_attrs':
            object.__setattr__(self, item, value)
        else:
            self.__setitem__(item, value)

    def get(self,key,default=None):
        try:
            item = self[key]
            try:
                if item['active'] == 'no':
                    return default
                return item
            except (TypeError,KeyError):
                return item
        except KeyError:
            pass

        return default

    def set(self,key,value):
        self[key] = value

    def __str__(self):
        if self.has_key('_text'):
            return self.__getitem__('_text')
        else:
            return ''

    def __repr__(self):
        return repr(dict(self))

    @staticmethod
    def Wrap(x):
        if isinstance(x, dict):
            return XmlDictObject((k, XmlDictObject.Wrap(v)) for (k, v) in x.iteritems())
        elif isinstance(x, list):
            return [XmlDictObject.Wrap(v) for v in x]
        else:
            return x

    @staticmethod
    def _UnWrap(x):
        if isinstance(x, dict):
            return dict((k, XmlDictObject._UnWrap(v)) for (k, v) in x.iteritems())
        elif isinstance(x, list):
            return [XmlDictObject._UnWrap(v) for v in x]
        else:
            return x

    def UnWrap(self):
        return XmlDictObject._UnWrap(self)

def _ConvertDictToXmlRecurse(parent, dictitem,element2attr_mappings=None):
    assert type(dictitem) is not type([])

    if isinstance(dictitem, dict):
        for (tag, child) in dictitem.iteritems():
            if str(tag) == '_text':
                parent.text = str(child)
##             elif str(tag) == '_attrs':
##                 for key, value in child.iteritems():
##                     parent.set(key, value)
            elif element2attr_mappings != None and tag in element2attr_mappings:
                    parent.set(element2attr_mappings[tag],child)
            elif type(child) is type([]):
                for listchild in child:
                    elem = ElementTree.Element(tag)
                    parent.append(elem)
                    _ConvertDictToXmlRecurse(elem, listchild,element2attr_mappings=element2attr_mappings)
            else:
                if(not isinstance(dictitem, XmlDictObject) and
                   not callable(dictitem)):
                    attrs = dictitem
                    dictitem = XmlDictObject()
                    dictitem._attrs = attrs

                if tag in dictitem._attrs:
                    parent.set(tag, child)
                elif not callable(tag) and not callable(child):
                    elem = ElementTree.Element(tag)
                    parent.append(elem)
                    _ConvertDictToXmlRecurse(elem, child,element2attr_mappings=element2attr_mappings)
    else:
        if not callable(dictitem):
            parent.text = str(dictitem)

def ConvertDictToXml(xmldict,element2attr_mappings=None):
    roottag = xmldict.keys()[0]
    root = ElementTree.Element(roottag)
    _ConvertDictToXmlRecurse(root, xmldict[roottag],element2attr_mappings=element2attr_mappings)
    return root

def _ConvertXmlToDictRecurse(node, dictclass):
    nodedict = dictclass()
##     if node.items():
##         nodedict.update({'_attrs': dict(node.items())})
    if len(node.items()) > 0:
        # if we have attributes, set them
        attrs = dict(node.items())
        nodedict.update(attrs)
        nodedict._attrs = attrs

    for child in node:
        # recursively add the element's children
        newitem = _ConvertXmlToDictRecurse(child, dictclass)
        if nodedict.has_key(child.tag):
            # found duplicate tag, force a list
            if type(nodedict[child.tag]) is type([]):
                # append to existing list
                nodedict[child.tag].append(newitem)
            else:
                # convert to list
                nodedict[child.tag] = [nodedict[child.tag], newitem]
        else:
            # only one, directly set the dictionary
            nodedict[child.tag] = newitem

    if node.text is None:
        text = ''
    else:
        text = node.text.strip()

    if len(nodedict) > 0:
        # if we have a dictionary add the text as a dictionary value (if there is any)
        if len(text) > 0:
            nodedict['_text'] = text
    else:
        # if we don't have child nodes or attributes, just set the text
        if node.text is not None:
            nodedict = node.text.strip()

    return nodedict

def ConvertXmlToDict(root,dictclass=XmlDictObject):
    return dictclass({root.tag: _ConvertXmlToDictRecurse(root, dictclass)})


def main():
    c = Config('config.xml',root='config')
    #print '%r' % c.config

    #c.save(new_filename='config.new.xml')
    print c.config['interface']

    #for plugin in c.config.pluginlist.plugin:
    #    if plugin.active != 'no':
    #        print '%r' % plugin


if __name__ == '__main__':
    main()
