# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2007, Frank Scholz <coherence@beebits.net>

from coherence.extern.simple_plugin import Plugin

from coherence import log


class BackendItem(log.Loggable):

    """ the base class for all backend store items
    """

    logCategory = 'backend_item'


class BackendStore(log.Loggable,Plugin):

    """ the base class for all backend store items
    """

    logCategory = 'backend_store'
