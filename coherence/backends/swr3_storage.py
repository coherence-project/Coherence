# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2008 Frank Scholz <coherence@beebits.net>

from coherence.backend import BackendStore
from coherence.backend import BackendItem
from coherence.upnp.core import DIDLLite
from coherence.upnp.core.utils import getPage

from twisted.internet import reactor
from twisted.python.util import OrderedDict

from coherence.extern.et import parse_xml

ROOT_CONTAINER_ID = 0
MARIANNE_014_CONTAINER_ID = 100
PETER_GEDOENS_CONTAINER_ID = 101
BESCHEIDWISSER_CONTAINER_ID = 102
TIM_FRAGT_TOM_CONTAINER_ID = 103
WIE_WAR_DER_TAG_CONTAINER_ID = 104
BOERSENMAN_CONTAINER_ID = 105
GAG_DES_TAGES_CONTAINER_ID = 106
TOPTHEMA_CONTAINER_ID = 107
EVISHOW_CONTAINER_ID = 108
REUSCHS_WOCHENRUECKBLICK_CONTAINER_ID = 109
TAEGLICH_POP_CONTAINER_ID = 110


class Item(BackendItem):

    def __init__(self, parent_id, id, title, url):
        self.parent_id = parent_id
        self.id = id
        self.location = url
        self.name = title
        self.duration = None
        self.size = None
        self.mimetype = 'audio/mpeg'
        self.description = None

        self.item = None

    def get_item(self):
        if self.item == None:
            self.item = DIDLLite.AudioItem(self.id, self.parent_id, self.name)
            self.item.description = self.description

            res = DIDLLite.Resource(self.location, 'http-get:*:%s:*' % self.mimetype)
            res.duration = self.duration
            res.size = self.size
            self.item.res.append(res)
        return self.item

class Container(BackendItem):

    def __init__(self, id, store, parent_id, title):
        self.url = store.urlbase+str(id)
        self.parent_id = parent_id
        self.id = id
        self.name = title
        self.mimetype = 'directory'
        self.update_id = 0
        self.children = []

        self.item = DIDLLite.Container(self.id, self.parent_id, self.name)
        self.item.childCount = 0

        self.sorted = False

    def add_child(self, child):
        id = child.id
        if isinstance(child.id, basestring):
            _,id = child.id.split('.')
        self.children.append(child)
        self.item.childCount += 1
        self.sorted = False

    def get_children(self, start=0, end=0):
        if self.sorted == False:
            def childs_sort(x,y):
                r = cmp(x.name,y.name)
                return r

            self.children.sort(cmp=childs_sort)
            self.sorted = True
        if end != 0:
            return self.children[start:end]
        return self.children[start:]

    def get_child_count(self):
        return len(self.children)

    def get_path(self):
        return self.url

    def get_item(self):
        return self.item

    def get_name(self):
        return self.name

    def get_id(self):
        return self.id


class SWR3Store(BackendStore):

    implements = ['MediaServer']

    def __init__(self, server, *args, **kwargs):
        self.name = kwargs.get('name', 'SWR3')
        self.refresh = int(kwargs.get('refresh', 1)) * (60 *60)
        self.urlbase = kwargs.get('urlbase','')
        if( len(self.urlbase)>0 and
            self.urlbase[len(self.urlbase)-1] != '/'):
            self.urlbase += '/'
        self.server = server
        self.next_id = 1000
        self.update_id = 0
        self.last_updated = None
        self.store = {}

        self.store[ROOT_CONTAINER_ID] = \
                        Container(ROOT_CONTAINER_ID,self,-1, self.name)

        self.store[MARIANNE_014_CONTAINER_ID] = \
                        Container(MARIANNE_014_CONTAINER_ID,self,ROOT_CONTAINER_ID, u'Mariane 014 - Die Landärztin')
        self.store[MARIANNE_014_CONTAINER_ID].description = u"""Hier kommt die Rettung aller Landwirte: Comedy-Star Anke Engelke ist „Die Landärztin“ – exklusiv bei SWR3. """ \
                                                            u"""Als Marianne 014 eilt sie auf geilen Fahrzeugen von einem heißen Notarzt-Einsatz zum nächsten."""
        self.store[ROOT_CONTAINER_ID].add_child(self.store[MARIANNE_014_CONTAINER_ID])

        self.store[PETER_GEDOENS_CONTAINER_ID] = \
                        Container(PETER_GEDOENS_CONTAINER_ID,self,ROOT_CONTAINER_ID, u'Peter Gedöns aus Bonn')
        self.store[PETER_GEDOENS_CONTAINER_ID].description = u"""Sascha Zeus fürchtet seinen Anruf in der SWR3-Morningshow – doch immer wieder meldet er """ \
                                                             u"""sich per Telefon: Peter Gedöns aus Bonn. Er ist einfach immer schlecht gelaunt und hat """ \
                                                             u"""immer ein paar wüste Beschimpfungen parat."""
        self.store[ROOT_CONTAINER_ID].add_child(self.store[PETER_GEDOENS_CONTAINER_ID])

        self.store[BESCHEIDWISSER_CONTAINER_ID] = \
                        Container(BESCHEIDWISSER_CONTAINER_ID,self,ROOT_CONTAINER_ID, u'Der SWR3-Bescheidwisser')
        self.store[BESCHEIDWISSER_CONTAINER_ID].description = u"""Die Welt ist voller kleiner Wunder. Können wir Blicke spüren? """ \
                                                              u"""Was rettet uns, wenn wir uns verschlucken? Warum können wir auf der ganzen Welt Geld abheben? """ \
                                                              u"""SWR3-Reporter Andreas Hain klärt Phänomene des Alltags auf."""
        self.store[ROOT_CONTAINER_ID].add_child(self.store[BESCHEIDWISSER_CONTAINER_ID])

        self.store[TIM_FRAGT_TOM_CONTAINER_ID] = \
                        Container(TIM_FRAGT_TOM_CONTAINER_ID,self,ROOT_CONTAINER_ID, u'Tim fragt Tom')
        self.store[TIM_FRAGT_TOM_CONTAINER_ID].description = u"""Die Welt ist kompliziert – nicht nur für Kinder. In der SWR3-Serie „Tim fragt Tom“ """ \
                                                             u"""erklärt der ARD-Tagesthemen-Moderator Tom Buhrow dem 12-jährigen Tim schwierige Begriffe aus den Nachrichten."""
        self.store[ROOT_CONTAINER_ID].add_child(self.store[TIM_FRAGT_TOM_CONTAINER_ID])

        self.store[WIE_WAR_DER_TAG_CONTAINER_ID] = \
                        Container(WIE_WAR_DER_TAG_CONTAINER_ID,self,ROOT_CONTAINER_ID, u'Wie war der Tag, Liebling?')
        self.store[WIE_WAR_DER_TAG_CONTAINER_ID].description = u"""SWR3-Moderator Kristian Thees hat früher mit Anke Engelke zusammen Radio gemacht """ \
                                                               u"""und ruft sie jetzt regelmäßig aus seiner Sendung an. Worüber die beiden dann plaudern, """ \
                                                               u"""hört ihr im SWR3-Podcast „Wie war der Tag, Liebling?“"""
        self.store[ROOT_CONTAINER_ID].add_child(self.store[WIE_WAR_DER_TAG_CONTAINER_ID])

        self.store[BOERSENMAN_CONTAINER_ID] = \
                        Container(BOERSENMAN_CONTAINER_ID,self,ROOT_CONTAINER_ID, u'SWR3-Börsenman')
        self.store[BOERSENMAN_CONTAINER_ID].description = u"""Ob Aktie des Tages, allgemeine Trends oder Börsengossip: """ \
                                                          u"""Jeden Tag gibt es eine neue Story vom SWR3 Börsenman. """ \
                                                          u"""Frisch vom Parkett auf SWR3 und hier zum Nachhören für zuhause und unterwegs."""
        self.store[ROOT_CONTAINER_ID].add_child(self.store[BOERSENMAN_CONTAINER_ID])

        self.store[GAG_DES_TAGES_CONTAINER_ID] = \
                        Container(GAG_DES_TAGES_CONTAINER_ID,self,ROOT_CONTAINER_ID, u'SWR3-Gag des Tages')
        self.store[GAG_DES_TAGES_CONTAINER_ID].description = u"""Die SWR3-Witzküche arbeitet unentwegt an eurer guten Laune und liefert""" \
                                                             u"""euch mit dem SWR3-Gag des Tages die besten Comix im Abo: Sachen, die Lachen """ \
                                                             u"""machen – zum Nachkichern und Mitnehmen."""
        self.store[ROOT_CONTAINER_ID].add_child(self.store[GAG_DES_TAGES_CONTAINER_ID])

        self.store[TOPTHEMA_CONTAINER_ID] = \
                        Container(TOPTHEMA_CONTAINER_ID,self,ROOT_CONTAINER_ID, u'SWR3-Topthema')
        self.store[TOPTHEMA_CONTAINER_ID].description = u"""Das SWR3 Topthema ist der tägliche Info-Schwerpunkt in der SWR3-Nachmittagsshow """ \
                                                        u"""– immer gegen 17 Uhr 40 in SWR3 und auf SWR3.de. Damit seid ihr in vier Minuten """ \
                                                        u"""bestens informiert über die wichtigen Themen."""
        self.store[ROOT_CONTAINER_ID].add_child(self.store[TOPTHEMA_CONTAINER_ID])

        self.store[EVISHOW_CONTAINER_ID] = \
                        Container(EVISHOW_CONTAINER_ID,self,ROOT_CONTAINER_ID, u'SWR3-Evishow – die Interviews')
        self.store[EVISHOW_CONTAINER_ID].description = u"""SWR3-Moderatorin Evi Seibert angelt sich die angesagtesten Promis der Woche. """ \
                                                       u"""Sie weiß, wie sie ihre Gäste zum Plaudern bringt. Die Interviews aus ihrer """ \
                                                       u"""witzig-charmanten Show (Sonntags, 9-12 Uhr) gibt's hier als Podcast."""
        self.store[ROOT_CONTAINER_ID].add_child(self.store[EVISHOW_CONTAINER_ID])

        self.store[REUSCHS_WOCHENRUECKBLICK_CONTAINER_ID] = \
                        Container(REUSCHS_WOCHENRUECKBLICK_CONTAINER_ID,self,ROOT_CONTAINER_ID, u'Reuschs rigoroser Wochenrückblick')
        self.store[REUSCHS_WOCHENRUECKBLICK_CONTAINER_ID].description = u"""Eine ganze Woche im Schnelldurchlauf, und dabei bringt er zusammen, """ \
                                                                        u"""was zusammen gehört – oder auch nicht: Jeden Freitag läuft in SWR3 der """ \
                                                                        u"""rigorose Wochenrückblick von Stefan Reusch, und jede Woche gibt's ihn auch als Podcast."""
        self.store[ROOT_CONTAINER_ID].add_child(self.store[REUSCHS_WOCHENRUECKBLICK_CONTAINER_ID])

        self.store[TAEGLICH_POP_CONTAINER_ID] = \
                        Container(TAEGLICH_POP_CONTAINER_ID,self,ROOT_CONTAINER_ID, u'Täglich Pop')
        self.store[TAEGLICH_POP_CONTAINER_ID].description = u"""SWR3: Täglich Pop - jeden Tag neue Stories rund um eure Stars. Was geschah heute vor zwei Jahren?""" \
                                                            u"""SWR3-Musikredakteur Matthias Kugler traegt Tag für Tag die interessantesten Facts""" \
                                                            u"""und die besten Stories für euch zusammen."""
        self.store[ROOT_CONTAINER_ID].add_child(self.store[TAEGLICH_POP_CONTAINER_ID])

        self.init_completed()

        self.update_data("http://www.swr3.de/rdf-feed/podcast/marianne014.xml.php",self.store[MARIANNE_014_CONTAINER_ID])
        self.update_data("http://www.swr3.de/rdf-feed/podcast/gedoens.xml.php",self.store[PETER_GEDOENS_CONTAINER_ID])
        self.update_data("http://www.swr3.de/rdf-feed/podcast/bescheid.xml.php",self.store[BESCHEIDWISSER_CONTAINER_ID])
        self.update_data("http://www.swr3.de/rdf-feed/podcast/timtom.xml.php",self.store[TIM_FRAGT_TOM_CONTAINER_ID])
        self.update_data("http://www.swr3.de/rdf-feed/podcast/wwdtl.xml.php",self.store[WIE_WAR_DER_TAG_CONTAINER_ID])
        self.update_data("http://www.swr3.de/rdf-feed/podcast/boersenman.xml.php",self.store[BOERSENMAN_CONTAINER_ID])
        self.update_data("http://www.swr3.de/rdf-feed/podcast/gag.xml.php",self.store[GAG_DES_TAGES_CONTAINER_ID])
        self.update_data("http://www.swr3.de/rdf-feed/podcast/tt.xml.php",self.store[TOPTHEMA_CONTAINER_ID])
        self.update_data("http://www.swr3.de/rdf-feed/podcast/evishow.xml.php",self.store[EVISHOW_CONTAINER_ID])
        self.update_data("http://www.swr3.de/rdf-feed/podcast/reusch.xml.php",self.store[REUSCHS_WOCHENRUECKBLICK_CONTAINER_ID])
        self.update_data("http://www.swr3.de/rdf-feed/podcast/taepo.xml.php",self.store[TAEGLICH_POP_CONTAINER_ID])

    def get_next_id(self):
        self.next_id += 1
        return self.next_id

    def get_by_id(self,id):
        if isinstance(id, basestring):
            id = id.split('@',1)
            id = id[0]
        try:
            return self.store[int(id)]
        except (ValueError,KeyError):
            pass
        return None

    def upnp_init(self):
        if self.server:
            self.server.connection_manager_server.set_variable( \
                0, 'SourceProtocolInfo', ['http-get:*:audio/mpeg:DLNA.ORG_PN=MP3;DLNA.ORG_OP=11;DLNA.ORG_FLAGS=01700000000000000000000000000000',
                                          'http-get:*:audio/mpeg:*'])

    def update_data(self,rss_url,container):

        def fail(f):
            print "fail", f
            return f

        dfr = getPage(rss_url)
        dfr.addCallback(parse_xml, encoding="ISO-8859-1")
        dfr.addErrback(fail)
        dfr.addCallback(self.parse_data,container)
        dfr.addErrback(fail)
        dfr.addBoth(self.queue_update,rss_url,container)
        return dfr

    def parse_data(self,xml_data,container):
        root = xml_data.getroot()
        for podcast in root.findall("./channel/item"):
            item = Item(container.id, self.get_next_id(), unicode(podcast.find("./title").text), podcast.find("./link").text)
            container.add_child(item)
            item.description = unicode(podcast.find("./description").text)
            enclosure = podcast.find("./enclosure")
            item.size = int(enclosure.attrib['length'])
            item.mimetype = enclosure.attrib['type']
            #item.date = podcast.find("./pubDate")


        self.update_id += 1
        #if self.server:
        #    self.server.content_directory_server.set_variable(0, 'SystemUpdateID', self.update_id)
        #    value = (ROOT_CONTAINER_ID,self.container.update_id)
        #    self.server.content_directory_server.set_variable(0, 'ContainerUpdateIDs', value)

    def queue_update(self, error_or_failure,rss_url,container):
        reactor.callLater(self.refresh, self.update_data,rss_url,container)
