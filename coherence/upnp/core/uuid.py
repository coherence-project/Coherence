# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php
#
# Copyright 2005, Tim Potter <tpot@samba.org>
# Copyright 2006, Frank Scholz <coherence@beebits.net>
#
#
# uses uuid4 method from http://zesty.ca/python/uuid.html
# Copyright 2006, Ka-Ping Yee <ping@zesty.ca>
#

try: 
   from uuid import uuid4
except ImportError:
    try:
        from coherence.extern.uuid.uuid import uuid4
    except ImportError:
        print 'fallback: define own uuid4'
        def uuid4():
            import random
            import string
            return ''.join(map(lambda x: random.choice(string.letters), xrange(20)))

class UUID:

    def __init__(self):
        self.uuid = 'uuid:' + str(uuid4())

    def __repr__(self):
        return self.uuid
