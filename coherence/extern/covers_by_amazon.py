# -*- coding: utf-8 -*-

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

The AWSAccessKeyId supplied is _ONLY_ for the use
in conjunction with Coherence, http://coherence.beebits.net

If you use this library in your own software please
apply for your own key @ http://www.amazon.com/webservices
and follow the rules of their license.

Especially you must add the following disclaimer in a place
that is reasonably viewable by the user of your application:

 PLEASE KEEP IN MIND THAT SOME OF THE CONTENT THAT WE
 MAKE AVAILABLE TO YOU THROUGH THIS APPLICATION COMES
 FROM AMAZON WEB SERVICES. ALL SUCH CONTENT IS PROVIDED
 TO YOU "AS IS." THIS CONTENT AND YOUR USE OF IT
 ARE SUBJECT TO CHANGE AND/OR REMOVAL AT ANY TIME.

Furthermore if you save any of the cover images you
have to take care that they are stored no longer than
a maximum of one month and requested then from Amazon
again.

"""

import os
import urllib
import StringIO

from twisted.internet import reactor
from twisted.internet import defer
from twisted.web import client

from et import parse_xml

aws_server = { 'de': 'de',
               'jp': 'jp',
               'ca': 'ca',
               'uk': 'co.uk',
               'fr': 'fr'}


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
            obj.max_workers = kwargs.get('max_workers', 1)
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
        d = defer.maybeDeferred(work[0], *work[1],**work[2])
        self.workers.append(d)
        d.addCallback(self.remove_from_workers, d)
        d.addErrback(self.remove_from_workers, d)

    def remove_from_workers(self, result, d):
        self.workers.remove(d)
        reactor.callLater(1,self.queue_run)  # a very,very weak attempt

class CoverGetter(object):

    """
    retrieve a cover image for a given ASIN,
                               a TITLE or
                               an ARTIST/TITLE combo

    parameters are:

        filename: where to save a received image
                  if NONE the image will be passed to the callback
        callback: a method to call with the filename
                  or the image as a parameter
                  after the image request and save was successful
                  can be:
                  - only a callable
                  - a tuple with a callable,
                      - optional an argument or a tuple of arguments
                      - optional a dict with keyword arguments
        not_found_callback: a method to call when the search at Amazon failed
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

    if the filename extension and the received image extension differ,
    the image is converted with PIL to the desired format
    http://www.pythonware.com/products/pil/index.htm

    """

    def __init__(self, filename, aws_key, callback=None, not_found_callback=None,
                       locale=None,
                       image_size='large',
                       title=None, artist=None, asin=None):
        self.aws_base_query = '/onca/xml?Service=AWSECommerceService' \
                              '&AWSAccessKeyId=%s' % aws_key

        self.filename = filename
        self.callback = callback
        self._errcall = not_found_callback
        self.server = 'http://ecs.amazonaws.%s' % aws_server.get(locale,'com')
        self.image_size = image_size

        def sanitize(s):
            if s is not None:
                s = unicode(s.lower())
                s = s.replace(unicode(u'ä'),unicode('ae'))
                s = s.replace(unicode(u'ö'),unicode('oe'))
                s = s.replace(unicode(u'ü'),unicode('ue'))
                s = s.replace(unicode(u'ß'),unicode('ss'))
                if isinstance(s,unicode):
                    s = s.encode('ascii','ignore')
                else:
                    s = s.decode('utf-8').encode('ascii','ignore')
            return s

        if asin != None:
            query = aws_asin_query + '&ItemId=%s' % urllib.quote(asin)
        elif (artist is not None or title is not None):
            query = aws_artist_query
            if artist is not None:
                artist = sanitize(artist)
                query = '&'.join((query, 'Artist=%s' % urllib.quote(artist)))
            if title is not None:
                title = sanitize(title)
                query = '&'.join((query, 'Title=%s' % urllib.quote(title)))
        else:
            raise KeyError, "Please supply either asin, title or artist and title arguments"
        url = self.server+self.aws_base_query+aws_response_group+query
        WorkQueue(self.send_request, url)

    def send_request(self,url,*args,**kwargs):
        #print "send_request", url
        d= client.getPage(url)
        d.addCallback(self.got_response)
        d.addErrback(self.got_error, url)
        return d

    def got_image(self, result, convert_from='', convert_to=''):
        #print "got_image"
        if(len(convert_from) and len(convert_to)):
            #print "got_image %d, convert to %s" % (len(result), convert_to)
            try:
                import Image

                im = Image.open(StringIO.StringIO(result))
                name,file_ext =  os.path.splitext(self.filename)
                self.filename = name + convert_to

                im.save(self.filename)
            except ImportError:
                print "we need the Python Imaging Library to do image conversion"

        if self.filename == None:
            data = result
        else:
            data = self.filename

        if self.callback is not None:
            #print "got_image", self.callback
            if isinstance(self.callback,tuple):
                if len(self.callback) == 3:
                    c,a,kw = self.callback
                    if not isinstance(a,tuple):
                        a = (a,)
                    a=(data,) + a
                    c(*a,**kw)
                if len(self.callback) == 2:
                    c,a = self.callback
                    if isinstance(a,dict):
                        c(data,**a)
                    else:
                        if not isinstance(a,tuple):
                            a = (a,)
                        a=(data,) + a
                        c(*a)
                if len(self.callback) == 1:
                    c = self.callback
                    c(data)
            else:
                self.callback(data)

    def got_response(self, result):
        convert_from = convert_to = ''
        result = parse_xml(result, encoding='utf-8')
        image_tag = result.find('.//{%s}%s' % (aws_ns,aws_image_size.get(self.image_size,'large')))
        if image_tag != None:
            image_url = image_tag.findtext('{%s}URL' % aws_ns)
            if self.filename == None:
                d = client.getPage(image_url)
            else:
                _,file_ext =  os.path.splitext(self.filename)
                if file_ext == '':
                    _,image_ext =  os.path.splitext(image_url)
                    if image_ext != '':
                        self.filename = ''.join((self.filename, image_ext))
                else:
                    _,image_ext =  os.path.splitext(image_url)
                    if image_ext != '' and file_ext != image_ext:
                        #print "hmm, we need a conversion..."
                        convert_from = image_ext
                        convert_to = file_ext
                if len(convert_to):
                    d = client.getPage(image_url)
                else:
                    d = client.downloadPage(image_url, self.filename)
            d.addCallback(self.got_image, convert_from=convert_from, convert_to=convert_to)
            d.addErrback(self.got_error, image_url)
        else:
            if self._errcall is not None:
                if isinstance(self._errcall,tuple):
                    if len(self._errcall) == 3:
                        c,a,kw = self._errcall
                        if not isinstance(a,tuple):
                            a = (a,)
                        c(*a,**kw)
                    if len(self._errcall) == 2:
                        c,a = self._errcall
                        if isinstance(a,dict):
                            c(**a)
                        else:
                            if not isinstance(a,tuple):
                                a = (a,)
                            c(*a)
                    if len(self._errcall) == 1:
                        c = self._errcall
                        c()
                else:
                    self._errcall()

    def got_error(self, failure, url):
        print "got_error", failure, url

if __name__ == '__main__':

    from twisted.python import usage

    class Options(usage.Options):
        optParameters = [['artist', 'a', '', 'artist name'],
                         ['title', 't', '', 'title'],
                         ['asin', 's', '', 'ASIN'],
                         ['filename', 'f', 'cover.jpg', 'filename'],
                    ]

    options = Options()
    try:
        options.parseOptions()
    except usage.UsageError, errortext:
        import sys
        print '%s: %s' % (sys.argv[0], errortext)
        print '%s: Try --help for usage details.' % (sys.argv[0])
        sys.exit(1)

    def got_it(filename, *args, **kwargs):
        print "Mylady, it is an image and its name is", filename, args, kwargs

    aws_key = '1XHSE4FQJ0RK0X3S9WR2'
    print options['asin'],options['artist'],options['title']
    if len(options['asin']):
        reactor.callWhenRunning(CoverGetter,options['filename'],aws_key, callback=got_it,asin=options['asin'])
    elif len(options['artist']) and len(options['title']):
        reactor.callWhenRunning(CoverGetter,options['filename'],aws_key, callback=got_it,artist=options['artist'],title=options['title'])

    reactor.run()
