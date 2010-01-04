# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# a Shoutcast radio media server for the Coherence UPnP Framework
# (heavily revamped from the existing IRadio plugin)

# Copyright 2007, Frank Scholz <coherence@beebits.net>
# Copyright 2009-2010, Jean-Michel Sizun <jmDOTsizunATfreeDOTfr>

from twisted.internet import defer,reactor
from twisted.python.failure import Failure
from twisted.web import server

from coherence.upnp.core import utils

from coherence.upnp.core import DIDLLite
from coherence.upnp.core.DIDLLite import classChooser, Resource, DIDLElement

import coherence.extern.louie as louie

from coherence.extern.simple_plugin import Plugin

from coherence import log
from coherence.backend import BackendItem, BackendStore, Container, LazyContainer, AbstractBackendStore

from urlparse import urlsplit

SHOUTCAST_WS_URL = 'http://www.shoutcast.com/sbin/newxml.phtml'

genre_families = {
    # genre hierarchy created from http://forums.winamp.com/showthread.php?s=&threadid=303231
    "Alternative" : ["Adult Alternative", "Britpop", "Classic Alternative", "College", "Dancepunk", "Dream Pop", "Emo", "Goth", "Grunge", "Indie Pop", "Indie Rock", "Industrial", "Lo-Fi", "Modern Rock", "New Wave", "Noise Pop", "Post-Punk", "Power Pop", "Punk", "Ska", "Xtreme"],
    "Blues" : ["Acoustic Blues", "Chicago Blues", "Contemporary Blues", "Country Blues", "Delta Blues", "Electric Blues", "Cajun/Zydeco" ],
    "Classical" : [ "Baroque", "Chamber", "Choral", "Classical Period", "Early Classical", "Impressionist", "Modern", "Opera", "Piano", "Romantic", "Symphony" ],
    "Country" : ["Alt-Country", "Americana", "Bluegrass", "Classic Country", "Contemporary Bluegrass", "Contemporary Country", "Honky Tonk", "Hot Country Hits", "Western" ],
    "Easy Listening" : ["Exotica", "Light Rock", "Lounge", "Orchestral Pop", "Polka", "Space Age Pop" ],
    "Electronic" : ["Acid House", "Ambient", "Big Beat", "Breakbeat", "Dance", "Demo", "Disco", "Downtempo", "Drum and Bass", "Electro", "Garage", "Hard House", "House", "IDM", "Remixes", "Jungle", "Progressive", "Techno", "Trance", "Tribal", "Trip Hop" ],
    "Folk" : ["Alternative Folk", "Contemporary Folk", "Folk Rock", "New Acoustic", "Traditional Folk", "World Folk" ],
    "Themes" : ["Adult", "Best Of", "Chill", "Experimental", "Female", "Heartache", "LGBT", "Love/Romance", "Party Mix", "Patriotic", "Rainy Day Mix", "Reality", "Sexy", "Shuffle", "Travel Mix", "Tribute", "Trippy", "Work Mix" ],
    "Rap" : ["Alternative Rap", "Dirty South", "East Coast Rap", "Freestyle", "Hip Hop", "Gangsta Rap", "Mixtapes", "Old School", "Turntablism", "Underground Hip-Hop", "West Coast Rap"],
    "Inspirational" : ["Christian", "Christian Metal", "Christian Rap", "Christian Rock", "Classic Christian", "Contemporary Gospel", "Gospel", "Praise/Worship", "Sermons/Services", "Southern Gospel", "Traditional Gospel"  ],
    "International" : ["African", "Afrikaans", "Arabic", "Asian", "Brazilian", "Caribbean", "Celtic", "European", "Filipino", "Greek", "Hawaiian/Pacific", "Hindi", "Indian", "Japanese", "Jewish",  "Klezmer", "Mediterranean", "Middle Eastern", "North American", "Polskie", "Polska", "Soca", "South American", "Tamil", "Worldbeat", "Zouk" ],
    "Jazz" : ["Acid Jazz", "Avant Garde", "Big Band", "Bop", "Classic Jazz", "Cool Jazz", "Fusion", "Hard Bop", "Latin Jazz", "Smooth Jazz", "Swing", "Vocal Jazz", "World Fusion" ],
    "Latin" : ["Bachata", "Banda", "Bossa Nova", "Cumbia", "Latin Dance", "Latin Pop", "Latin Rap/Hip-Hop", "Latin Rock", "Mariachi", "Merengue", "Ranchera", "Reggaeton", "Regional Mexican", "Salsa", "Tango", "Tejano", "Tropicalia"],
    "Metal" : ["Black Metal", "Classic Metal", "Extreme Metal", "Grindcore", "Hair Metal", "Heavy Metal", "Metalcore", "Power Metal", "Progressive Metal", "Rap Metal" ],
    "New Age" : ["Environmental", "Ethnic Fusion", "Healing", "Meditation", "Spiritual" ],
    "Decades" : ["30s", "40s", "50s", "60s", "70s", "80s", "90s"],
    "Pop" : ["Adult Contemporary", "Barbershop", "Bubblegum Pop", "Dance Pop", "Idols", "Oldies", "JPOP", "Soft Rock", "Teen Pop", "Top 40", "World Pop" ],
    "R&B/Urban" : ["Classic R&B", "Contemporary R&B", "Doo Wop", "Funk", "Motown", "Neo-Soul", "Quiet Storm", "Soul", "Urban Contemporary", "Reggae", "Contemporary Reggae", "Dancehall", "Dub", "Pop-Reggae", "Ragga", "Rock Steady", "Reggae Roots"],
    "Rock" : ["Adult Album Alternative", "British Invasion", "Classic Rock", "Garage Rock", "Glam", "Hard Rock", "Jam Bands", "Piano Rock", "Prog Rock", "Psychedelic", "Rock & Roll", "Rockabilly", "Singer/Songwriter", "Surf"],
    "Seasonal/Holiday" : ["Anniversary", "Birthday", "Christmas", "Halloween", "Hanukkah", "Honeymoon", "Valentine", "Wedding", "Winter"],
    "Soundtracks" : ["Anime", "Bollywood", "Kids", "Original Score", "Showtunes", "Video Game Music"],
    "Talk" : ["Comedy", "Community", "Educational", "Government", "News", "Old Time Radio", "Other Talk", "Political", "Public Radio", "Scanner", "Spoken Word", "Sports", "Technology", "Hardcore", "Eclectic", "Instrumental" ],
    "Misc" : [],
}

synonym_genres = {
  # TODO: extend list with entries from "Misc" which are clearly the same
  "24h" : ["24h", "24hs"],
  "80s" : ["80s", "80er"],
  "Acid Jazz" : ["Acid", "Acid Jazz"],
  "Adult" : ["Adult", "Adulto"],
  "Alternative" : ["Alt", "Alternativa", "Alternative", "Alternativo"],
  "Francais" : ["Francais", "French"],
  "Heavy Metal" : ["Heavy Metal", "Heavy", "Metal"],
  "Hip Hop" : ["Hip", "Hop", "Hippop", "Hip Hop"],
  "Islam" : [ "Islam", "Islamic"],
  "Italy" : ["Italia", "Italian", "Italiana", "Italo", "Italy"],
  "Latina" : ["Latin", "Latina", "Latino" ],
}
useless_title_content =[ 
    # TODO: extend list with title expressions which are clearly useless
    " - [SHOUTcast.com]"
]
useless_genres = [
    # TODO: extend list with entries from "Misc" which are clearly useless
    "genres", "go", "here",
    "Her", "Hbwa"
]


class PlaylistStreamProxy(utils.ReverseProxyUriResource, log.Loggable):
    """ proxies audio streams published as M3U playlists (typically the case for shoutcast streams) """
    logCategory = 'PlaylistStreamProxy'

    stream_url = None
    
    def __init__(self, uri):
        self.stream_url = None
        utils.ReverseProxyUriResource.__init__(self, uri)


    def requestFinished(self, result):
        """ self.connection is set in utils.ReverseProxyResource.render """
        self.debug("ProxyStream requestFinished")
        if self.connection is not None:
            self.connection.transport.loseConnection()

    def render(self, request):

        if self.stream_url is None:
            def got_playlist(result):
                if result is None:
                    self.warning('Error to retrieve playlist - nothing retrieved')
                    return requestFinished(result)
                result = result[0].split('\n')
                for line in result:
                    if line.startswith('File1='):
                        self.stream_url = line[6:]
                        break
                if self.stream_url is None:
                    self.warning('Error to retrieve playlist - inconsistent playlist file')
                    return requestFinished(result)
                #self.resetUri(self.stream_url)
                request.uri = self.stream_url
                return self.render(request)
            
            def got_error(error):
                self.warning('Error to retrieve playlist - unable to retrieve data')
                self.warning(error)
                return None
                
            playlist_url = self.uri           
            d = utils.getPage(playlist_url, timeout=20)
            d.addCallbacks(got_playlist, got_error)
            return server.NOT_DONE_YET
             
        self.info("this is our render method",request.method, request.uri, request.client, request.clientproto)
        self.info("render", request.getAllHeaders())
        if request.clientproto == 'HTTP/1.1':
            self.connection = request.getHeader('connection')
            if self.connection:
                tokens = map(str.lower, self.connection.split(' '))
                if 'close' in tokens:
                    d = request.notifyFinish()
                    d.addBoth(self.requestFinished)
        else:
            d = request.notifyFinish()
            d.addBoth(self.requestFinished)
        return utils.ReverseProxyUriResource.render(self, request)

        
class IRadioItem(BackendItem):
    logCategory = 'iradio'

    def __init__(self, station_id, title, stream_url, mimetype):
        self.station_id = station_id
        self.name = title
        self.mimetype = mimetype
        self.stream_url = stream_url
        
        self.location = PlaylistStreamProxy(self.stream_url)
        
        self.item = None


    def replace_by (self, item):
        # do nothing: we suppose the replacement item is the same
        return
    
    def get_item(self):
        if self.item == None:
            upnp_id = self.get_id()
            upnp_parent_id = self.parent.get_id()
            self.item = DIDLLite.AudioBroadcast(upnp_id, upnp_parent_id, self.name)
            res = Resource(self.url, 'http-get:*:%s:%s' % (self.mimetype,
                                                           ';'.join(('DLNA.ORG_PN=MP3',
                                                                     'DLNA.ORG_CI=0',
                                                                     'DLNA.ORG_OP=01',
                                                                     'DLNA.ORG_FLAGS=01700000000000000000000000000000'))))
            res.size = 0 #None
            self.item.res.append(res)
        return self.item

    def get_path(self):
        self.url = self.store.urlbase + str(self.storage_id)
        return self.url

    def get_id(self):
        return self.storage_id
    
    
class IRadioStore(AbstractBackendStore):

    logCategory = 'iradio'

    implements = ['MediaServer']

    genre_parent_items = {} # will list the parent genre for every given genre
    
    def __init__(self, server, **kwargs):
        AbstractBackendStore.__init__(self,server,**kwargs)
 
        self.name = kwargs.get('name','iRadioStore')
        self.refresh = int(kwargs.get('refresh',60))*60

        self.shoutcast_ws_url = self.config.get('genrelist',SHOUTCAST_WS_URL)
        
        # set root item
        root_item = Container(None, self.name)
        self.set_root_item(root_item)

        # set root-level genre family containers
        # and populate the genre_parent_items dict from the family hierarchy information
        for family, genres in genre_families.items():
            family_item = self.append_genre(root_item, family)           
            if family_item is not None:
                self.genre_parent_items[family] = root_item
                for genre in genres:
                    self.genre_parent_items[genre] = family_item
        
        # retrieve asynchronously the list of genres from the souhtcast server
        # genres not already attached to a family will be attached to the "Misc" family           
        self.retrieveGenreList_attemptCount = 0
        deferredRoot = self.retrieveGenreList()
        # self.init_completed() # will be fired when the genre list is retrieved

    def append_genre(self, parent, genre):
        if genre in useless_genres:
            return None
        if synonym_genres.has_key(genre):
            same_genres = synonym_genres[genre]
        else:
            same_genres = [genre]
        title = genre.encode('utf-8')     
        family_item = LazyContainer(parent, title, genre, self.refresh, self.retrieveItemsForGenre, genres=same_genres, per_page=1)
        # we will use a specific child items sorter
        # in order to get the sub-genre containers first
        def childs_sort(x,y):
            if x.__class__ == y.__class__:
                return cmp(x.name,y.name) # same class, we compare the names
            else:
                # the IRadioItem is deemed the lowest item class,
                # other classes are compared by name (as usual)
                if isinstance(x, IRadioItem):
                        return 1
                elif isinstance(y, IRadioItem):
                    return -1
                else:
                    return cmp(x.name,y.name)
        family_item.sorting_method = childs_sort
        
        parent.add_child(family_item, external_id=genre)
        return family_item

    def __repr__(self):
        return self.__class__.__name__


    def upnp_init(self):
        self.current_connection_id = None

        self.wmc_mapping = {'4': self.get_root_id()}

        if self.server:
            self.server.connection_manager_server.set_variable(0, 'SourceProtocolInfo',
                                                                    ['http-get:*:audio/mpeg:*',
                                                                     'http-get:*:audio/x-scpls:*'],
                                                                     default=True)


    # populate a genre container (parent) with the sub-genre containers
    # and corresponding IRadio (list retrieved from the shoutcast server)
    def retrieveItemsForGenre (self, parent, genres, per_page=1, offset=0, page=0):
        genre = genres[page]
        if page < len(genres)-1:
            parent.childrenRetrievingNeeded = True
        url = '%s?genre=%s' % (self.shoutcast_ws_url, genre)

        if genre_families.has_key(genre):
            family_genres = genre_families[genre]
            for family_genre in family_genres:
                self.append_genre(parent, family_genre)
        
        def got_page(result):
            self.info('connection to ShoutCast service successful for genre %s' % genre)
            result = utils.parse_xml(result, encoding='utf-8')
            tunein = result.find('tunein')
            if tunein != None:
                tunein = tunein.get('base','/sbin/tunein-station.pls')
            prot,host_port,path,_,_ = urlsplit(self.shoutcast_ws_url)
            tunein = prot + '://' + host_port + tunein

            stations = {}
            for stationResult in result.findall('station'):
                mimetype = stationResult.get('mt')
                station_id = stationResult.get('id')
                bitrate = stationResult.get('br')
                name = stationResult.get('name').encode('utf-8')
                # remove useless substrings (eg. '[Shoutcast.com]' ) from title
                for substring in useless_title_content:
                    name = name.replace(substring, "")
                lower_name = name.lower()
                url = '%s?id=%s' % (tunein, stationResult.get('id'))
                
                sameStation = stations.get(lower_name)
                if sameStation == None or bitrate>sameStation['bitrate']:
                    station = {'name':name,                                               
                               'station_id':station_id,
                               'mimetype':mimetype,
                               'id':station_id,
                               'url':url,
                               'bitrate':bitrate }
                    stations[lower_name] = station
            
            for station in stations.values():
                station_id = station.get('station_id')
                name = station.get('name')
                url =  station.get('url')
                mimetype = station.get('mimetype')
                item = IRadioItem(station_id, name, url, mimetype)
                parent.add_child(item, external_id = station_id)
            
            return True


        def got_error(error):
            self.warning("connection to ShoutCast service failed: %s" % url)
            self.debug("%r", error.getTraceback())
            parent.childrenRetrievingNeeded = True # we retry
            return Failure("Unable to retrieve stations for genre" % genre)
            
        d = utils.getPage(url)
        d.addCallbacks(got_page, got_error)
        return d
    

    # retrieve the whole list of genres from the shoutcast server
    # to complete the population of the genre families classification
    # (genres not previously classified are put into the "Misc" family)
    # ...and fire mediaserver init completion
    def retrieveGenreList(self):
 
        def got_page(result):
            if self.retrieveGenreList_attemptCount == 0:
                self.info("Connection to ShoutCast service successful for genre listing")
            else:
                self.warning("Connection to ShoutCast service successful for genre listing after %d attempts." % self.retrieveGenreList_attemptCount)
            result = utils.parse_xml(result, encoding='utf-8')
            
            genres = {}
            main_synonym_genre = {}
            for main_genre, sub_genres in synonym_genres.items():
                genres[main_genre] = sub_genres
                for genre in sub_genres:
                    main_synonym_genre[genre] = main_genre
                    
            for genre in result.findall('genre'):
                name = genre.get('name')
                if name not in main_synonym_genre:
                    genres[name] = [name]
                    main_synonym_genre[name] = name

            for main_genre, sub_genres in genres.items():
                if not self.genre_parent_items.has_key(main_genre):
                    genre_families["Misc"].append(main_genre)
            
            self.init_completed()                

        def got_error(error):
            self.warning("connection to ShoutCast service for genre listing failed - Will retry! %r", error)
            self.debug("%r", error.getTraceback())
            self.retrieveGenreList_attemptCount += 1
            reactor.callLater(5, self.retrieveGenreList)
        
        d = utils.getPage(self.shoutcast_ws_url)
        d.addCallback(got_page)
        d.addErrback(got_error)
        return d
  
    

