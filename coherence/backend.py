# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2007, Frank Scholz <coherence@beebits.net>

from coherence.extern.simple_plugin import Plugin

from coherence import log

class Backend(log.Loggable,Plugin):

    """ the base class for all backends
    """

    logCategory = 'backend'


class BackendItem(log.Loggable):

    """ the base class for all MediaServer backend items
    """

    logCategory = 'backend_item'


class BackendStore(Backend):

    """ the base class for all MediaServer backend stores
    """

    logCategory = 'backend_store'
    wmc_mapping = {'4':'4', '5':'5', '6':'6','7':'7','14':'14','F':'F',
                   '11':'11','16':'16','B':'B','C':'C','D':'D',
                   '13':'13', '17':'17',
                   '8':'8', '9':'9', '10':'10', '15':'15', 'A':'A', 'E':'E'}

    def __init__(self):
        self.wmc_mapping.update({'4':lambda: self._get_all_items(0),
                                 '8':lambda: self._get_all_items(0),
                                 'B':lambda: self._get_all_items(0),
                                })

    def _get_all_items(self,id):
        items = []
        item = self.get_by_id(id)
        if item is not None:
            containers = [item]
            while len(containers)>0:
                container = containers.pop()
                if container.mimetype not in ['root', 'directory']:
                    continue
                for child in container.get_children(0,0):
                    if child.mimetype in ['root', 'directory']:
                        containers.append(child)
                    else:
                        items.append(child)
        return items