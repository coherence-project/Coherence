# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2007, Frank Scholz <coherence@beebits.net>

import time

from twisted.python import failure
from twisted.web.xmlrpc import Proxy

from elementtree.ElementTree import fromstring

from coherence.upnp.core.utils import parse_xml

from coherence.upnp.core.DIDLLite import classChooser, Container, Resource, DIDLElement
from coherence.upnp.core.soap_proxy import SOAPProxy
from coherence.upnp.core.soap_service import errorCode

class FlickrStore:

    implements = ['MediaServer']
    vendor_value_defaults = {'ConnectionManager': {'SourceProtocolInfo': 'http-get:*:image/jpeg:*,' 
                                                                         'http-get:*:image/png:*,'
                                                                         'http-get:*:image/gif:*'}}

    def __init__(self, server, **kwargs):
        self.name = kwargs.get('name','Flickr')
        self.server = server
        self.update_id = 0
        self.flickr = Proxy('http://api.flickr.com/services/xmlrpc/')
        self.flickr_api_key = '837718c8a622c699edab0ea55fcec224'
        
    def flickr_call(self, method, **kwargs):
        def got_result(result):
            #print 'result', result.encode('utf-8')
            result = parse_xml(result, encoding='utf-8')
            return result

        def got_error(error):
            print 'error', error
            return error
        
        args = {}
        args.update(kwargs)
        args['api_key'] = self.flickr_api_key

        d = self.flickr.callRemote(method, args)
        d.addCallback(got_result)
        d.addErrback(got_error)
        return d

    def flickr_test_echo(self, name='Test'):
        d = self.flickr_call('flickr.test.echo', **kwargs)
        return d

    def flickr_interestingness(self, date=None, per_page=100):
        if date == None:
            date = time.strftime( "%Y-%m-%d", time.localtime(time.time()-86400))
        if per_page > 500:
            per_page = 500
        d = self.flickr_call('flickr.interestingness.getList', date=date, per_page=per_page)
        return d
        
    def soap_flickr_test_echo(self, value):
        client = SOAPProxy("http://api.flickr.com/services/soap/",
                            namespace=("x","urn:flickr"),
                            envelope_attrib=[("xmlns:s", "http://www.w3.org/2003/05/soap-envelope"),
                                            ("xmlns:xsi", "http://www.w3.org/1999/XMLSchema-instance"),
                                            ("xmlns:xsd", "http://www.w3.org/1999/XMLSchema")],
                            soapaction="FlickrRequest")
        d = client.callRemote( "FlickrRequest",
                                method='flickr.test.echo',
                                name=value,
                                api_key='837718c8a622c699edab0ea55fcec224')
        def got_results(result):
            print result

        d.addCallback(got_results)
        return d

        
    def upnp_Browse(self, *args, **kwargs):
        ObjectID = int(kwargs['ObjectID'])
        BrowseFlag = kwargs['BrowseFlag']
        Filter = kwargs['Filter']
        StartingIndex = int(kwargs['StartingIndex'])
        RequestedCount = int(kwargs['RequestedCount'])
        SortCriteria = kwargs['SortCriteria']
        
        def build_upnp_item(photo, id):
            title = photo.get('title').encode('utf-8')
            if len(title) == 0:
                title = u'untitled'
            
            url = u"http://farm%s.static.flickr.com/%s/%s_%s_o.jpg" % (
                        photo.get('farm').encode('utf-8'),
                        photo.get('server').encode('utf-8'),
                        photo.get('id').encode('utf-8'),
                        photo.get('secret').encode('utf-8'))
            
            UPnPClass = classChooser('image/jpeg')
            upnp_item = UPnPClass(id, 0, title)
            upnp_item.res = Resource(url, 'http-get:*:image/jpeg:*')
            upnp_item.res.size = None
            upnp_item.res = [ upnp_item.res ]
            return upnp_item
        
        def got_result(result):
            didl = DIDLElement()
            total = 0
            for photo in result.getiterator('photo'):
                if BrowseFlag == 'BrowseDirectChildren':
                    total += 1
                    didl.addItem(build_upnp_item(photo, total))
                else:
                    total = 1
                    didl.addItem(build_upnp_item(photo, total))
                    break

            r = { 'Result': didl.toString(), 'TotalMatches': total,
                  'NumberReturned': didl.numItems()}

            r['UpdateID'] = self.update_id

            return r
    
        def got_error(r):
            return failure.Failure(errorCode(701))

        d = self.flickr_interestingness(per_page=RequestedCount)
        d.addCallback(got_result)
        d.addErrback(got_error)
        return d
        
def main():

    f = FlickrStore('Flickr', None)
    
    def got_result(result):
        print "main", result
        for photo in result.getiterator('photo'):
            title = photo.get('title').encode('utf-8')
            if len(title) == 0:
                title = u'untitled'
                
            url = "http://farm%s.static.flickr.com/%s/%s_%s_o.jpg" % (
                        photo.get('farm').encode('utf-8'),
                        photo.get('server').encode('utf-8'),
                        photo.get('id').encode('utf-8'),
                        photo.get('secret').encode('utf-8'))
            print photo.get('id').encode('utf-8'), title, url
        
    #d = f.flickr_test_echo(name='Coherence')
    d = f.flickr_interestingness()
    d.addCallback(got_result)
    
    """
    dfr = f.upnp_Browse(BrowseFlag='BrowseDirectChildren',
                        RequestedCount=0,
                        StartingIndex=0,
                        ObjectID=0,
                        SortCriteria='*',
                        Filter='')
    dfr.addCallback(got_result)
    """


if __name__ == '__main__':

    from twisted.internet import reactor

    reactor.callWhenRunning(main)
    reactor.run()
