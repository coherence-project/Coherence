# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2007, Frank Scholz <coherence@beebits.net>

"""

Covers by Amazon

methods to retrieve covers/album art via the
Amazon E-Commerce WebService v4
http://docs.amazonwebservices.com/AWSECommerceService/2007-04-04/DG/

The licence agreement says something about only
one request per second, so we need to serialize
and delay the calls a bit.

The AWSAccessKeyId supplied is _only_ for the use
in conjunction with Coherence, http://coherence.beebits.net

If you use this library in your own software please
apply for your own key @ http://www.amazon.com/webservices

"""

import urllib

from twisted.internet import reactor
from twisted.web import client

from coherence.upnp.core.utils import parse_xml

aws_key = '1XHSE4FQJ0RK0X3S9WR2'

aws_server = { 'de': 'de',
               'jp': 'jp',
               'ca': 'ca',
               'uk': 'co.uk',
               'fr': 'fr'}

aws_base_query = '/onca/xml?Service=AWSECommerceService' \
                 '&AWSAccessKeyId=%s' % aws_key

aws_artist_query = '&Operation=ItemSearch' \
                   '&SearchIndex=Music'

aws_asin_query = '&Operation=ItemLookup'

aws_response_group = '&ResponseGroup=Images'

aws_ns = 'http://webservices.amazon.com/AWSECommerceService/2005-10-05'

aws_image_size = { 'large': 'LargeImage',
                   'medium': 'MediumImage',
                   'small': 'SmallImage'}

class WorkQueue(object):

    _instance_ = None  # Singleton

    def __new__(cls, *args, **kwargs):
        obj = getattr(cls,'_instance_',None)
        if obj is not None:
            return obj
        else:
            obj = super(WorkQueue, cls).__new__(cls, *args, **kwargs)
            cls._instance_ = obj
            obj.max_workers = kwargs.get('max_workers', 10)
            obj.queue = []
            obj.workers = []
            return obj

    def __init__(self, method, *args, **kwargs):
        self.queue.append((method,args,kwargs))
        self.queue_run()

    def queue_run(self):
        if len(self.queue) == 0:
            return
        if len(self.workers) >= self.max_workers:
            #print "WorkQueue - all workers busy"
            return
        work = self.queue.pop()
        d = work[0](*work[1],**work[2])
        self.workers.append(d)
        d.addCallback(self.remove_from_workers, d)
        d.addErrback(self.remove_from_workers, d)

    def remove_from_workers(self, result, d):
        self.workers.remove(d)
        reactor.callLater(1,self.queue_run)  # a very,very weak attempt

class CoverGetter(object):

    """
    retrieve a cover image for a given ASIN or a ARTIST/TITLE combo
    parameters are:

        filename: where to save a received image
                  TODO: let filename be NONE and
                        store the image in memory
        callback: a method to call with the filename as a parameter
                  after the image request and save was successful
                  can be:
                  - only a callable
                  - a tuple with a callable,
                      - optional an argument or a tuple of arguments
                      - optional a dict with keyword arguments

        locale:   which Amazon Webservice Server to use, defaults to .com
        image_size: request the cover as large|medium|small image
                    resolution seems to be in pixels for
                    large: 500x500, medium: 160x160 and small: 75x75
        asin: the Amazon Store Identification Number
        artist: the artists name
        title: the album title
    """

    def __init__(self, filename, callback=None,
                       locale=None,
                       image_size='large',
                       title=None, artist=None, asin=None):
        self.filename = filename
        self.callback = callback
        self.server = 'http://ecs.amazonaws.%s' % aws_server.get(locale,'com')
        self.image_size = image_size
        if asin != None:
            query = aws_asin_query + '&ItemId=%s' % urllib.quote(asin)
        elif (artist is not None and title is not None):
            query = aws_artist_query + '&Artist=%s&Title=%s' % (urllib.quote(artist),
                                                                urllib.quote(title))
        else:
            raise KeyError, "Please supply either asin or artist and title arguments"
        url = self.server+aws_base_query+aws_response_group+query
        WorkQueue(self.send_request, url)

    def send_request(self,url,*args,**kwargs):
        #print "send_request", url
        d= client.getPage(url)
        d.addCallback(self.got_response)
        d.addErrback(self.got_error, url)
        return d

    def got_image(self, result):
        #print "got_image, saved to", self.filename
        if self.callback is not None:
            #print "got_image", self.callback
            if isinstance(self.callback,tuple):
                if len(self.callback) == 3:
                    c,a,kw = self.callback
                    if not isinstance(a,tuple):
                        a = (a,)
                    a=(self.filename,) + a
                    c(*a,**kw)
                if len(self.callback) == 2:
                    c,a = self.callback
                    if isinstance(a,dict):
                        c(self.filename,**a)
                    else:
                        if not isinstance(a,tuple):
                            a = (a,)
                        a=(self.filename,) + a
                        c(*a)
                if len(self.callback) == 1:
                    c = self.callback
                    c(self.filename)
            else:
                self.callback(self.filename)

    def got_response(self, result):
        #print x
        result = parse_xml(result, encoding='utf-8')
        image_tag = result.find('.//{%s}%s' % (aws_ns,aws_image_size.get(self.image_size,'large')))
        if image_tag != None:
            image_url = image_tag.findtext('{%s}URL' % aws_ns)
            d = client.downloadPage( image_url, self.filename)
            d.addCallback(self.got_image)
            d.addErrback(self.got_error, image_url)

    def got_error(self, failure, url):
        print "got_error", failure, url

if __name__ == '__main__':

    def got_it(filename, *args, **kwargs):
        print "Mylady, it is an image and its name is", filename, args, kwargs

    def got_it2(filename, **kwargs):
        print "Mylady, it is an image and its name is", filename, args, kwargs

    reactor.callWhenRunning(CoverGetter,"cover.jpg",callback=(got_it, ("a", 1), {'test':1}),asin='B000NJLNPO')
    reactor.callWhenRunning(CoverGetter,"cover.jpg",callback=(got_it, {'test':2}),artist='Beyonce',title="B'Day [Deluxe]")

    reactor.run()
