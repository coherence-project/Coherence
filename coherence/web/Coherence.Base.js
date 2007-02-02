// Licensed under the MIT license
// http://opensource.org/licenses/mit-license.php
//
// Copyright 2007, Frank Scholz <coherence@beebits.net>

// import Nevow.Athena

// import MochiKit
// import MochiKit.DOM

if(typeof(Coherence) == "undefined") {
    Coherence = {};
}

//MochiKit.LoggingPane.createLoggingPane()

Coherence.Base = Nevow.Athena.Widget.subclass('Coherence.Base');
Coherence.Base.activeTab = 0;

Coherence.Base.methods(

function setTab(self, tab, active) {
    log("setTab " + tab.id + " " + active);
    if( active == 'on') {
        if( Coherence.Base.activeTab != 0) {
            Coherence.Base.activeTab.style.color ='#FFFFFF'
            Coherence.Base.activeTab.style.backgroundColor ='#404040'
            $(Coherence.Base.activeTab.id.split('-')[0]+'-container').style.visibility = 'hidden'
        }
        tab.style.color ='#000000'
        tab.style.backgroundColor ='#C0C0C0'
        log("set " + tab.id.split('-')[0]+'-container' + " " + 'visible');
        $(tab.id.split('-')[0]+'-container').style.visibility = 'visible'
        Coherence.Base.activeTab = tab
    }
    else
    {
        tab.style.color ='#FFFFFF'
        tab.style.backgroundColor ='#404040'
        $(tab.id.split('-')[0]+'-container').style.visibility = 'hidden'
        Coherence.Base.activeTab = 0
    }
},

function clickTab(self, Event) {
    log("clickTab " + Event.target.id);
    if( Event.target.className != 'coherence_menu_item')
        return;
    if( Coherence.Base.activeTab == Event.target)
        return;
    Coherence.Base.prototype.setTab(Event.target, 'on');
},

function addTab(self, tab) {
    log('addTab '+tab['title']);
    if( $('coherence_menu_box').build_done == 'no')
        return;

    appendChildNodes($('coherence_menu_box'),
        DIV({'id':tab['title']+'-tab','class':'coherence_menu_item'}, tab['title']
        )
    )
    $(tab['title']+'-tab').addEventListener("click", Coherence.Base.prototype.clickTab, false);
    //appendChildNodes($('coherence_body'),
    //    DIV({'id':tab['title']+'-container','class':'coherence_container'}
    //    )
    //)
    if(tab['active'] == 'yes') {
        log('addTab set active '+tab['title']);
        Coherence.Base.prototype.setTab($(tab['title']+'-tab'), 'on');
    }
    // MochiKit.Visual.roundElement( $(channel+'-box'));
},

function buildMenu(self, result) {
    log('buildMenu ' + result.length);
    $('coherence_menu_box').build_done = 'yes'
    for(var i=0; i<result.length;++i) {
        log('buildMenu ' + i + ' ' + result[i]);
        Coherence.Base.prototype.addTab(result[i]);
    }
},

function __init__(self, node) {
    Coherence.Base.upcall(self, '__init__', node);
    $('coherence_menu_box').build_done = 'no'
    var d = self.callRemote('going_live');
    d.addCallback(Coherence.Base.prototype.buildMenu);
}

);
