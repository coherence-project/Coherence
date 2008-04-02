// Licensed under the MIT license
// http://opensource.org/licenses/mit-license.php
//
// Copyright 2007, Frank Scholz <coherence@beebits.net>

// import Nevow.Athena

// import MochiKit

if(typeof(Coherence) == "undefined") {
    Coherence = {};
}

Coherence.Logging = Nevow.Athena.Widget.subclass('Coherence.Logging');

Coherence.Logging.methods(

function buildLogPanel(self, result) {
    Divmod.debug("logging",'buildLogPanel ');
    //for(var i=0; i<result.length;++i) {
    //    Divmod.debug("logging",'buildLogPanel ' + i + ' ' + result[i]);
    //}
},

function __init__(self, node) {
    Divmod.debug("logging",'Coherence.Logging __init__');
    Coherence.Logging.upcall(self, '__init__', node);
    var d = self.callRemote('going_live');
    d.addCallback(function (result) { self.buildLogPanel(result); });
    Divmod.debug("logging",'Coherence.Logging __init__ done');
}

);
