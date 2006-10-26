# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006, Frank Scholz <coherence@beebits.net>
#

class UUID:

    def __init__(self):
        self.uuid = self.generateuuid()

    def generateuuid(self):
        import random
        import string
        return ''.join([ 'uuid:'] + map(lambda x: random.choice(string.letters), xrange(20)))
        
    def __repr__(self):
        print self.uuid
