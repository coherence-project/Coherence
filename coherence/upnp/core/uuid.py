# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php
#
# Copyright 2005, Tim Potter <tpot@samba.org>
# Copyright 2006, Frank Scholz <coherence@beebits.net>
# Copyright 2013, Hartmut Goebel <h.goebel@crazy-compilers.com>
#

from __future__ import absolute_import

from uuid import uuid4


class UUID:

    def __init__(self):
        self.uuid = 'uuid:' + str(uuid4())

    def __repr__(self):
        return self.uuid
