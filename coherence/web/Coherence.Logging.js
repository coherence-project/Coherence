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

Coherence.Logging = Nevow.Athena.Widget.subclass('Coherence.Logging');

Coherence.Logging.methods(

function buildLogPanel(self, result) {
    log('buildLogPanel ' + result.length);
    for(var i=0; i<result.length;++i) {
        log('buildLogPanel ' + i + ' ' + result[i]);
    }
},

function __init__(self, node) {
    Coherence.Logging.upcall(self, '__init__', node);
    var d = self.callRemote('going_live');
    log('Coherence.Logging __init__');

    d.addCallback(Coherence.Logging.prototype.buildLogPanel);
}

);
