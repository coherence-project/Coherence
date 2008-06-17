# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2008, Frank Scholz <coherence@beebits.net>

from coherence.ui.av_widgets import TreeWidget

import totem

class UPnPClient(totem.Plugin):

    def __init__ (self):
        totem.Plugin.__init__(self)
        self.ui = TreeWidget()
        self.ui.window.show_all()

    def activate (self, totem_object):
        totem_object.add_sidebar_page ("upnp-coherence", _("Coherence DLNA/UPnP Client"), self.ui.window)
        self.ui.cb_item_dbl_click =  totem_object.action_set_mrl_and_play

    def deactivate (self, totem_object):
        totem_object.remove_sidebar_page ("upnp-coherence")