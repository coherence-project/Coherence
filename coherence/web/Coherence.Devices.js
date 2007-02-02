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

Coherence.Devices = Nevow.Athena.Widget.subclass('Coherence.Devices');

Coherence.Devices.methods(

function addDevice(self, device) {
    log('addDevice '+device['name']);
    appendChildNodes($('Devices-container'),
        DIV({'id':device['usn']}, device['name']
        )
    )
},

function removeDevice(self, usn) {
    log('removeDevice '+usn);
    $('Devices-container').removeChild($(usn));
},


function listDevices(self, result) {
    log('listDevices ' + result.length);
    for(var i=0; i<result.length;++i) {
        log('listDevices ' + i + ' ' + result[i]);
        Coherence.Devices.prototype.addDevice(result[i]);
    }
},

function __init__(self, node) {
    log('Coherence.Devices __init__');
    Coherence.Devices.upcall(self, '__init__', node);
    var d = self.callRemote('going_live');
    d.addCallback(self.listDevices);
}

);
