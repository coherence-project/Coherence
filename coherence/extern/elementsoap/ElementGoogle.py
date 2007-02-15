#
# ElementSOAP
# $Id: ElementGoogle.py 2924 2006-11-19 22:24:22Z fredrik $
#
# a simple Google client
#
# history:
# 2003-11-17 fl   created
# 2003-11-23 fl   use decode_element to handle responses
#
# Copyright (c) 2003 by Fredrik Lundh.  All rights reserved.
#
# fredrik@pythonware.com
# http://www.pythonware.com
#

##
# This module implements a client for Google's Web API.
# <p>
# For more information on this API, see
# <a href='http://www.google.com/apis/'>http://www.google.com/apis/</a>.
##

from ElementSOAP import SoapService, SoapRequest, SoapElement
from ElementSOAP import decode, decode_element

##
# Google service client.  To talk to the Google Web API, create an
# instance of this class, and call the appropriate methods.  This
# class will forward you calls to the Google server.
#
# @param key Google license key.
# @param url Optional service URL.  The default is the standard
#    Google endpoint.

class GoogleService(SoapService):

    url = "http://api.google.com/search/beta2"

    def __init__(self, key, url=None):
        self.__key = key
        SoapService.__init__(self, url)

    ##
    # Searches Google.
    #
    # @param query The query string.
    # @param start First result to return.
    # @param maxResult Maximum number of results to return (max 10).
    # @return An element structure containing the result set.
    # @throws SoapError If the server doesn't like the request.

    def doGoogleSearch(self, query, start=0, maxResults=10):
        action = "urn:GoogleSearchAction"
        request = SoapRequest("{urn:GoogleSearch}doGoogleSearch")
        SoapElement(request, "key", "string", self.__key)
        SoapElement(request, "q", "string", query)
        SoapElement(request, "start", "int", str(start))
        SoapElement(request, "maxResults", "int", str(maxResults))
        SoapElement(request, "filter", "boolean", "true")
        SoapElement(request, "restrict", "string", "")
        SoapElement(request, "safeSearch", "boolean", "false")
        SoapElement(request, "lr", "string", "")
        SoapElement(request, "ie", "string", "utf-8")
        SoapElement(request, "oe", "string", "utf-8")
        return self.call(action, request).find("return")

    ##
    # Same as {@link #GoogleService.doGoogleSearch}, but returns
    # a Python object structure.
    #
    # @param query The query string.
    # @param start First result to return.
    # @param maxResult Maximum number of results to return (max 10).
    # @return An Python object describing the result set.
    # @throws SoapError If the server doesn't like the request.

    def pyGoogleSearch(self, query, start=0, maxResults=10):
        return decode(self.doGoogleSearch(query, start, maxResults))

    ##
    # Gets a cached version of a page.
    #
    # @param url The page URL.
    # @return A string containing the page contents.
    # @throws SoapError If the server doesn't like the request.

    def doGetCachedPage(self, url):
        action = "urn:GoogleSearchAction"
        request = SoapRequest("{urn:GoogleSearch}doGetCachedPage")
        SoapElement(request, "key", "string", self.__key)
        SoapElement(request, "url", "string", url)
        return decode_element(self.call(action, request).find("return"))

    ##
    # Gets an alternate spelling of a word or phrase.
    #
    # @param phrase The original word or phrase.
    # @return A string containing the alternate spelling, or None.
    # @throws SoapError If the server doesn't like the request.

    def doSpellingSuggestion(self, phrase):
        action = "urn:GoogleSearchAction"
        request = SoapRequest("{urn:GoogleSearch}doSpellingSuggestion")
        SoapElement(request, "key", "string", self.__key)
        SoapElement(request, "phrase", "string", phrase)
        return decode_element(self.call(action, request).find("return"))
