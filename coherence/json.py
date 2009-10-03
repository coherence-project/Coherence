# -*- coding: utf-8 -*-

# HifiMedia
# for HIFIakademie.de devices

# Copyright 2009, Frank Scholz <fs@beebits.net>

import simplejson as json
from twisted.web import resource,static

from coherence import log

class JsonInterface(resource.Resource,log.Loggable):
    logCategory = 'json'

    def __init__(self, controlpoint):
        self.controlpoint = controlpoint
        self.controlpoint.coherence.add_web_resource('json',
                                        self)
        self.children = {}

    def getChildWithDefault(self, path, request):
        self.warning('getChildWithDefault, %s, %s, %s %s' % (request.method, path, request.uri, request.client))
        if request.method == 'GET':
            if path == 'devices':
                return self.list_devices(request)


    def list_devices(self,request):
        devices = []
        for device in self.controlpoint.get_devices():
            devices.append(device.as_dict())
        return static.Data(json.dumps(devices),'application/json')