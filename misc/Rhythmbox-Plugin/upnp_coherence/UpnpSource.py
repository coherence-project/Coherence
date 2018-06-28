# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php
#
# Copyright 2011, Caleb Callaway <enlightened-despot@gmail.com>
# Copyright 2007-2010 Frank Scholz <dev@coherence-project.org>
# Copyright 2007, James Livingston  <doclivingston@gmail.com>

import rb
import rhythmdb
import gobject
import gtk
import re

from coherence import log
from coherence.upnp.core import DIDLLite


class UpnpSource(rb.BrowserSource, log.Loggable):

    logCategory = 'rb_media_store'

    __gproperties__ = {
        'plugin': (rb.Plugin, 'plugin', 'plugin', gobject.PARAM_WRITABLE | gobject.PARAM_CONSTRUCT_ONLY),
        'client': (gobject.TYPE_PYOBJECT, 'client', 'client', gobject.PARAM_WRITABLE | gobject.PARAM_CONSTRUCT_ONLY),
        'udn': (gobject.TYPE_PYOBJECT, 'udn', 'udn', gobject.PARAM_WRITABLE | gobject.PARAM_CONSTRUCT_ONLY),
    }

    def __init__(self):
        rb.BrowserSource.__init__(self)
        self.__db = None
        self.__activated = False
        self.container_watch = []

    def do_set_property(self, property, value):
        if property.name == 'plugin':
            self.__plugin = value
        elif property.name == 'client':
            self.__client = value
            self.props.name = self.__client.device.get_friendly_name()
        elif property.name == 'udn':
            self.__udn = value
        elif property.name == 'entry-type':
            self.__entry_type = value
        else:
            raise AttributeError('unknown property %s' % property.name)

    def do_selected (self):
        if not self.__activated:
            print "activating upnp source"
            self.__activated = True

            shell = self.get_property('shell')
            self.__db = shell.get_property('db')
            self.__entry_type = self.get_property('entry-type')

            self.load_db()
            self.__client.content_directory.subscribe_for_variable('ContainerUpdateIDs', self.state_variable_change)
            self.__client.content_directory.subscribe_for_variable('SystemUpdateID', self.state_variable_change)

    def do_get_status(self):
        if (self.browse_count > 0):
            return ('Loading contents of %s' % self.props.name, None, 0)
        else:
            qm = self.get_property("query-model")
            return (qm.compute_status_normal("%d song", "%d songs"), None, 2.0)

    def load_db(self):
        self.browse_count = 0
        self.load_children(0)

    def load_children(self, id):
        self.browse_count += 1
        d = self.__client.content_directory.browse(id, browse_flag='BrowseDirectChildren', process_result=False, backward_compatibility=False)
        d.addCallback(self.process_media_server_browse, self.__udn)
        d.addErrback(self.err_back)

    def err_back(self, *args, **kw):
        self.info("Browse action failed: %s" % str(args))
        self.browse_count -= 1

    def state_variable_change(self, variable, udn=None):
        self.info('%(name)r changed from %(old_value)r to %(value)r',
                  vars(variable))

        if variable.old_value == '':
            return

        if variable.name == 'SystemUpdateID':
            self.load_db(0)
        elif variable.name == 'ContainerUpdateIDs':
            changes = variable.value.split(',')
            while len(changes) > 1:
                container = changes.pop(0).strip()
                update_id = changes.pop(0).strip()
                if container in self.container_watch:
                    self.info("we have a change in %r, container needs a reload", container)
                    self.load_db(container)

    def process_media_server_browse(self, results, udn):
        self.browse_count -= 1

        didl = DIDLLite.DIDLElement.fromString(results['Result'])
        for item in didl.getItems():
            self.info("process_media_server_browse %r %r", item.id, item)
            if item.upnp_class.startswith('object.container'):
                self.load_children(item.id)
            if item.upnp_class.startswith('object.item.audioItem'):

                url = None
                duration = None
                size = None
                bitrate = None

                for res in item.res:
                    remote_protocol, remote_network, remote_content_format, remote_flags = res.protocolInfo.split(':')
                    self.info("%r %r %r %r", remote_protocol, remote_network, remote_content_format, remote_flags)
                    if remote_protocol == 'http-get':
                        url = res.data
                        duration = res.duration
                        size = res.size
                        bitrate = res.bitrate
                        break

                if url is not None and item.refID is None:
                    self.info("url %r %r", url, item.title)

                    entry = self.__db.entry_lookup_by_location(url)
                    if entry == None:
                        entry = self.__db.entry_new(self.__entry_type, url)

                    self.__db.set(entry, rhythmdb.PROP_TITLE, item.title)
                    try:
                        if item.artist is not None:
                            self.__db.set(entry, rhythmdb.PROP_ARTIST, item.artist)
                    except AttributeError:
                        pass
                    try:
                        if item.album is not None:
                            self.__db.set(entry, rhythmdb.PROP_ALBUM, item.album)
                    except AttributeError:
                        pass
                    try:
                        if item.genre is not None:
                            self.__db.set(entry, rhythmdb.PROP_GENRE, item.genre)
                    except AttributeError:
                        pass
                    try:
                        self.info("%r %r", item.title, item.originalTrackNumber)
                        if item.originalTrackNumber is not None:
                            self.__db.set(entry, rhythmdb.PROP_TRACK_NUMBER, int(item.originalTrackNumber))
                    except AttributeError:
                        pass

                    if duration is not None:
                        #match duration via regular expression.
                        #in case RB ever supports fractions of a second, here's the full regexp:
                        #"(\d+):([0-5][0-9]):([0-5][0-9])(?:\.(\d+))?(?:\.(\d+)\/(\d+))?"
                        self.info("duration: %r" % (duration))
                        match = re.match("(\d+):([0-5][0-9]):([0-5][0-9])", duration)
                        if match is not None:
                            h = match.group(1)
                            m = match.group(2)
                            s = match.group(3)
                            seconds = int(h) * 3600 + int(m) * 60 + int(s)
                            self.info("duration parsed as %r:%r:%r (%r seconds)" % (h, m, s, seconds))
                            self.__db.set(entry, rhythmdb.PROP_DURATION, seconds)

                    if size is not None:
                        try:
                            self.__db.set(entry, rhythmdb.PROP_FILE_SIZE, int(size))
                        except AttributeError:
                            pass
                    if bitrate is not None:
                        try:
                            self.__db.set(entry, rhythmdb.PROP_BITRATE, int(bitrate))
                        except AttributeError:
                            pass

                    self.__db.commit()

gobject.type_register(UpnpSource)
