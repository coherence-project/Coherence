# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006, Frank Scholz <coherence@beebits.net>

import os

from twisted.internet import reactor
from twisted.python import filepath, util
from nevow import athena, inevow, loaders, tags, static
from twisted.web import server, resource

from zope.interface import implements, Interface

import coherence.extern.louie as louie

from coherence import log

class IWeb(Interface):

    def goingLive(self):
        pass

class Web(object):

    def __init__(self, coherence):
        super(Web, self).__init__()
        self.coherence = coherence


class MenuFragment(athena.LiveElement, log.Loggable):
    logCategory = 'webui_menu_fragment'
    jsClass = u'Coherence.Base'
    fragmentName = 'coherence-menu'

    docFactory = loaders.stan(
        tags.div(render=tags.directive('liveElement'))[
            tags.div(id="coherence_menu_box",class_="coherence_menu_box")[""],
        ]
        )

    def __init__(self, page):
        super(MenuFragment, self).__init__()
        self.setFragmentParent(page)
        self.page = page
        self.coherence = page.coherence
        self.tabs = []


    def going_live(self):
        self.info("add a view to the MenuFragment")
        d = self.page.notifyOnDisconnect()
        d.addCallback( self.remove_me)
        d.addErrback( self.remove_me)
        if len(self.tabs):
            return self.tabs
        else:
            return {}
    athena.expose(going_live)

    def add_tab(self,title,active,id):
        self.info("add tab %s to the MenuFragment" % title)
        new_tab = {u'title':unicode(title),
                   u'active':unicode(active),
                   u'athenaid':u'athenaid:%d' % id}
        for t in self.tabs:
            if t[u'title'] == new_tab[u'title']:
                return
        self.tabs.append(new_tab)
        self.callRemote('addTab', new_tab)

    def remove_me(self, result):
        self.info("remove view from MenuFragment")

class DevicesFragment(athena.LiveElement, log.Loggable):
    logCategory = 'webui_device_fragment'
    jsClass = u'Coherence.Devices'
    fragmentName = 'coherence-devices'

    docFactory = loaders.stan(
        tags.div(render=tags.directive('liveElement'))[
            tags.div(id="Devices-container",class_="coherence_container")[""],
        ]
        )

    def __init__(self, page, active):
        super(DevicesFragment, self).__init__()
        self.setFragmentParent(page)
        self.page = page
        self.coherence = page.coherence
        self.active = active

    def going_live(self):
        self.info("add a view to the DevicesFragment", self._athenaID)
        self.page.menu.add_tab('Devices', self.active, self._athenaID)
        d = self.page.notifyOnDisconnect()
        d.addCallback(self.remove_me)
        d.addErrback(self.remove_me)
        devices = []
        for device in self.coherence.get_devices():
            if device is not None:
                devices.append({u'name': device.get_markup_name(),
                        u'usn':unicode(device.get_usn())})

        louie.connect(self.add_device,
                'Coherence.UPnP.Device.detection_completed', louie.Any)
        louie.connect(self.remove_device,
                'Coherence.UPnP.Device.removed', louie.Any)

        return devices

    athena.expose(going_live)

    def remove_me(self, result):
        self.info("remove view from the DevicesFragment")

    def add_device(self, device):
        self.info("DevicesFragment found device %s %s of type %s" %(
                                                device.get_usn(),
                                                device.get_friendly_name(),
                                                device.get_device_type()))
        self.callRemote('addDevice',
                {u'name': device.get_markup_name(),
                u'usn':unicode(device.get_usn())})

    def remove_device(self, usn):
        self.info("DevicesFragment remove device %s", usn)
        self.callRemote('removeDevice', unicode(usn))

    def render_devices(self, ctx, data):
        cl = []
        self.info('children: %s' % self.coherence.children)
        for child in self.coherence.children:
            device = self.coherence.get_device_with_id(child)
            if device is not None:
                cl.append( tags.li[tags.a(href='/' + child)[
                    device.get_friendly_device_type, ':',
                    device.get_device_type_version, ' ',
                    device.get_friendly_name()]])
            else:
                cl.append( tags.li[child])
        return ctx.tag[tags.ul[cl]]

class LoggingFragment(athena.LiveElement, log.Loggable):
    logCategory = 'webui_logging_fragment'
    jsClass = u'Coherence.Logging'
    fragmentName = 'coherence-logging'

    docFactory = loaders.stan(
        tags.div(render=tags.directive('liveElement'))[
            tags.div(id="Logging-container",class_="coherence_container")[""],
        ]
        )

    def __init__(self, page, active):
        super(LoggingFragment, self).__init__()
        self.setFragmentParent(page)
        self.page = page
        self.coherence = page.coherence
        self.active = active

    def going_live(self):
        self.info("add a view to the LoggingFragment",self._athenaID)
        self.page.menu.add_tab('Logging',self.active,self._athenaID)
        d = self.page.notifyOnDisconnect()
        d.addCallback( self.remove_me)
        d.addErrback( self.remove_me)
        return {}
    athena.expose(going_live)

    def remove_me(self, result):
        self.info("remove view from the LoggingFragment")

class WebUI(athena.LivePage, log.Loggable):
    """
    """
    logCategory = 'webui'
    jsClass = u'Coherence'

    addSlash = True
    docFactory = loaders.xmlstr("""\
<html xmlns:nevow="http://nevow.com/ns/nevow/0.1">
<head>
<nevow:invisible nevow:render="liveglue" />
<link rel="stylesheet" type="text/css" href="static/main.css" />
</head>
<body>
<div id="coherence_header"><div class="coherence_title">Coherence</div><div nevow:render="menu"></div></div>
<div id="coherence_body">
<div nevow:render="devices" />
<div nevow:render="logging" />
</div>
</body>
</html>
""")

    def __init__(self, *a, **kw):
        super(WebUI, self).__init__( *a, **kw)
        self.coherence = self.rootObject.coherence

        self.jsModules.mapping.update({
            'MochiKit': filepath.FilePath(__file__).parent().child('static').child('MochiKit.js').path})

        self.jsModules.mapping.update({
            'Coherence': filepath.FilePath(__file__).parent().child('static').child('Coherence.js').path})
        self.jsModules.mapping.update({
            'Coherence.Base': filepath.FilePath(__file__).parent().child('static').child('Coherence.Base.js').path})
        self.jsModules.mapping.update({
            'Coherence.Devices': filepath.FilePath(__file__).parent().child('static').child('Coherence.Devices.js').path})
        self.jsModules.mapping.update({
            'Coherence.Logging': filepath.FilePath(__file__).parent().child('static').child('Coherence.Logging.js').path})
        self.menu = MenuFragment(self)

    def childFactory(self, ctx, name):
        self.info('WebUI childFactory: %s' % name)
        try:
            return self.rootObject.coherence.children[name]
        except:
            ch = super(WebUI, self).childFactory(ctx, name)
            if ch is None:
                p = util.sibpath(__file__, name)
                self.info('looking for file',p)
                if os.path.exists(p):
                    ch = static.File(p)
            return ch

    def render_listmenu(self, ctx, data):
        l = []
        l.append(tags.div(id="t",class_="coherence_menu_item")[tags.a(href='/'+'devices',class_="coherence_menu_link")['Devices']])
        l.append(tags.div(id="t",class_="coherence_menu_item")[tags.a(href='/'+'logging',class_="coherence_menu_link")['Logging']])
        return ctx.tag[l]

    def render_menu(self, ctx, data):
        self.info('render_menu')
        return self.menu

    def render_devices(self, ctx, data):
        self.info('render_devices')
        f = DevicesFragment(self,'yes')
        return f

    def render_logging(self, ctx, data):
        self.info('render_logging')
        f = LoggingFragment(self,'no')
        return f
