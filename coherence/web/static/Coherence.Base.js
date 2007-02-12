// Licensed under the MIT license
// http://opensource.org/licenses/mit-license.php
//
// Copyright 2007, Frank Scholz <coherence@beebits.net>

// import Nevow.Athena

// import MochiKit

if(typeof(Coherence) == "undefined") {
    Coherence = {};
}

Coherence.Base = Nevow.Athena.Widget.subclass('Coherence.Base');
Coherence.Base.activeTab = 0;
Coherence.Base.build_done = 'no';

Coherence.Base.methods(

function setTab(self, tab, active) {
    Divmod.debug("base", "setTab " + tab.id + " " + active);
    log('tab_item ' + tab.id.split('-')[0]+'-'+tab.id.split('-')[1]+'-container');
    tab_item = $(tab.id.split('-')[0]+'-'+tab.id.split('-')[1]+'-container')
    log('tab_item ' + tab_item);
    if( active == 'on') {
        if( Coherence.Base.activeTab != 0) {
            Coherence.Base.activeTab.style.color ='#FFFFFF'
            Coherence.Base.activeTab.style.backgroundColor ='#404040'
            c = $(Coherence.Base.activeTab.id.split('-')[0]+'-'+Coherence.Base.activeTab.id.split('-')[1]+'-container')
            c.style.visibility = 'hidden'
        }
        tab.style.color ='#000000'
        tab.style.backgroundColor ='#C0C0C0'
        log("set " + tab.id.split('-')[0]+'-'+tab.id.split('-')[1]+'-container' + " " + 'visible');
        tab_item.style.visibility = 'visible'
        Coherence.Base.activeTab = tab
    }
    else
    {
        tab.style.color ='#FFFFFF'
        tab.style.backgroundColor ='#404040'
        tab_item.style.visibility = 'hidden'
        Coherence.Base.activeTab = 0
    }
},

function clickTab(self, Event) {
    Divmod.debug("base", "clickTab " + Event.target.id);
    if( Event.target.className != 'coherence_menu_item')
        return;
    if( Coherence.Base.activeTab == Event.target)
        return;
    Coherence.Base.prototype.setTab(Event.target, 'on');
},

function addTab(self, tab) {
    Divmod.debug("base", 'addTab '+tab['title']+' '+tab['athenaid']);
    if( Coherence.Base.build_done == 'no') {
        Divmod.debug("base", 'Base.build_done == no');
        return;
    }
    appendChildNodes(self.nodeById('coherence_menu_box'),
        DIV({'id':tab['athenaid']+'-'+tab['title']+'-tab','class':'coherence_menu_item'}, tab['title']
        )
    )
    $(tab['athenaid']+'-'+tab['title']+'-tab').addEventListener("click", Coherence.Base.prototype.clickTab, false);
    //self.nodeById(tab['title']+'-tab').addEventListener("click", Coherence.Base.prototype.clickTab, false);
    if(tab['active'] == 'yes') {
        Divmod.debug("base", 'addTab set active '+tab['title']);
        self.setTab($(tab['athenaid']+'-'+tab['title']+'-tab'), 'on');
    }
    // MochiKit.Visual.roundElement( $(channel+'-box'));
},

function buildMenu(self, result) {
    Divmod.debug("base", 'buildMenu ' + result.length);
    Coherence.Base.build_done = 'yes'
    for(var i=0; i<result.length;++i) {
        Divmod.debug("base", 'buildMenu ' + i + ' ' + result[i]);
        self.addTab(result[i]);

    }
},

function __init__(self, node) {
    Divmod.debug("base",'Coherence.Base __init__');
    Coherence.Base.upcall(self, '__init__', node);
    var d = self.callRemote('going_live');
    d.addCallback(function (result) { self.buildMenu(result); });
    Divmod.debug("base",'Coherence.Base __init__ done');
}

);
