// Licensed under the MIT license
// http://opensource.org/licenses/mit-license.php
//
// Copyright 2007, Frank Scholz <coherence@beebits.net>

// import Nevow.Athena

// import MochiKit


if(typeof(Coherence) == "undefined") {
    Coherence = {};
}

Coherence.Devices = Nevow.Athena.Widget.subclass('Coherence.Devices');

Coherence.Devices.methods(

function addDevice(self, device) {
    Divmod.debug("device",'addDevice '+device['name']);
    // self.nodeById('Devices-container')
    appendChildNodes(self.nodeById('Devices-container'),
        DIV({'id':device['usn']}, device['name']
        )
    )
},

function removeDevice(self, usn) {
    Divmod.debug("device",'removeDevice '+usn);
    self.nodeById('Devices-container').removeChild($(usn));
},


function listDevices(self, result) {
    Divmod.debug("device",'listDevices ' + result.length);
    for(var i=0; i<result.length;++i) {
        Divmod.debug("device",'listDevices ' + i + ' ' + result[i]);
        self.addDevice(result[i]);
    }
},

function __init__(self, node) {
    Divmod.debug("device",'Coherence.Devices __init__');
    Coherence.Devices.upcall(self, '__init__', node);
    var d = self.callRemote('going_live');
    d.addCallback(function (result) { self.listDevices(result); });
    Divmod.debug("device",'Coherence.Devices __init__ done');
 }

);
