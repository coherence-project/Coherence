# Copyright (C) 2008 Jean-Michel Sizun <jm.sizun AT gmail>
#
# Copyright (C) 2008 Brent Woodruff
#   http://www.fprimex.com
#
# Copyright (C) 2004 John Sutherland <garion@twcny.rr.com>
#   http://garion.tzo.com/python/
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
#
# Change log:
#
# 16-Nov-08 - Migrated from urllib to coherence infrastructure
#
# 04-Aug-08 - Added Gallery2 compatibility
#             Changed fetch_albums and fetch_albums_prune to return dicts
#             Added docstrings
#             Created package and registered with Pypi
#
# 09-Jun-04 - Removed self.cookie='' from _doRequest to allow multiple
#             transactions for each login.
#             Fixed cut paste error in newAlbum.
#             (both patches from Yuti Takhteyev


from coherence.upnp.core.utils import getPage

import StringIO
import string

class Gallery:
    """
    The Gallery class implements the Gallery Remote protocol as documented
    here:
    http://codex.gallery2.org/Gallery_Remote:Protocol

    The Gallery project is an open source web based photo album organizer
    written in php. Gallery's web site is:
    http://gallery.menalto.com/

    This class is a 3rd party product which is not maintained by the
    creators of the Gallery project.

    Example usage:
    from galleryremote import Gallery
    my_gallery = Gallery('http://www.yoursite.com/gallery2', 2)
    my_gallery.login('username','password')
    albums = my_gallery.fetch_albums()
    """

    def __init__(self, url, version=2):
        """
        Create a Gallery for remote access.
        url - base address of the gallery
        version - version of the gallery being connected to (default 2),
                  either 1 for Gallery1 or 2 for Gallery2
        """
        self.version = version # Gallery1 or Gallery2
        if version == 1:
            self.url = url + '/gallery_remote2.php'
        else:
            # default to G2
            self.url = url + '/main.php'
        self.auth_token = None
        self.logged_in = 0
        self.cookie = ''
        self.protocol_version = '2.5'

    def _do_request(self, request):
        """
        Send a request, encoded as described in the Gallery Remote protocol.
        request - a dictionary of protocol parameters and values
        """
        if self.auth_token != None:
            request['g2_authToken'] = self.auth_token

        url = self.url
        if (len(request) > 0) :
            url += '?'
            for key,value in request.iteritems():
                url += '%s=%s&' % (key,value)
        headers = None
        if self.cookie != '':
             headers = {'Cookie' : self.cookie}

        def gotPage(result):
            data,headers = result
            response = self._parse_response( data )
            if response['status'] != '0':
                raise response['status_text']
            try:
                self.auth_token = response['auth_token']
            except:
                pass

            if headers.has_key('set-cookie'):
                cookie_info = headers['set-cookie'][-1]
                self.cookie = cookie_info.split(';')[0]

            return response

        def gotError(error):
            print "Unable to process Gallery2 request: %s" % url
            print "Error: %s" % error
            return None

        d = getPage(url, headers=headers)
        d.addCallback(gotPage)
        d.addErrback(gotError)
        return d


    def _parse_response(self, response):
        """
        Decode the response from a request, returning a request dict
        response - The response from a gallery request, encoded according
                   to the gallery remote protocol
        """
        myStr = StringIO.StringIO(response)

        for line in myStr:
            if string.find( line, '#__GR2PROTO__' ) != -1:
                break

        # make sure the 1st line is #__GR2PROTO__
        if string.find( line, '#__GR2PROTO__' ) == -1:
            raise "Bad response: \r\n" + response

        resDict = {}

        for myS in myStr:
            myS = myS.strip()
            strList = string.split(myS, '=', 2)

            try:
                resDict[strList[0]] = strList[1]
            except:
                resDict[strList[0]] = ''

        return resDict

    def _get(self, response, kwd):
        """
        """
        try:
            retval = response[kwd]
        except:
            retval = ''

        return retval

    def login(self, username, password):
        """
        Establish an authenticated session to the remote gallery.
        username - A valid gallery user's username
        password - That valid user's password
        """
        if self.version == 1:
            request = {
                'protocol_version': self.protocol_version,
                'cmd': 'login',
                'uname': username,
                'password': password
            }
        else:
            request = {
                'g2_controller' : 'remote:GalleryRemote',
                'g2_form[protocol_version]' : self.protocol_version,
                'g2_form[cmd]' : 'login',
                'g2_form[uname]': username,
                'g2_form[password]': password
            }

        def gotPage(result):
            if result is None:
                print "Unable to login as %s to gallery2  server (%s)" % (username, self.url)
                return
            self.logged_in = 1


        d = self._do_request(request)
        d.addCallbacks(gotPage)

        return d

    def fetch_albums(self):
        """
        Obtain a dict of albums contained in the gallery keyed by
        album name. In Gallery1, the name is alphanumeric. In Gallery2,
        the name is the unique identifying number for that album.
        """
        if self.version == 1:
            request = {
                'protocol_version' : self.protocol_version,
                'cmd' : 'fetch-albums'
            }
        else:
            request = {
                'g2_controller' : 'remote:GalleryRemote',
                'g2_form[protocol_version]' : self.protocol_version,
                'g2_form[cmd]' : 'fetch-albums'
            }

        d = self._do_request(request)

        def gotResponse(response):
            if response is None:
                print "Unable to retrieve list of albums!"
                return None

            albums = {}
            for x in range(1, int(response['album_count']) + 1):
                album = {}
                album['name']                   = self._get(response,'album.name.' + str(x))
                album['title']                  = self._get(response,'album.title.' + str(x))
                album['summary']                = self._get(response,'album.summary.' + str(x))
                album['parent']                 = self._get(response,'album.parent.' + str(x))
                album['resize_size']            = self._get(response,'album.resize_size.' + str(x))
                album['perms.add']              = self._get(response,'album.perms.add.' + str(x))
                album['perms.write']            = self._get(response,'album.perms.write.' + str(x))
                album['perms.del_item']         = self._get(response,'album.perms.del_item.' + str(x))
                album['perms.del_alb']          = self._get(response,'album.perms.del_alb.' + str(x))
                album['perms.create_sub']       = self._get(response,'album.perms.create_sub.' + str(x))
                album['perms.info.extrafields'] = self._get(response,'album.info.extrafields' + str(x))

                albums[album['name']] = album
            return albums

        d.addCallback(gotResponse)
        return d

    def fetch_albums_prune(self):
        """
        Obtain a dict of albums contained in the gallery keyed by
        album name. In Gallery1, the name is alphanumeric. In Gallery2,
        the name is the unique identifying number for that album.

        From the protocol docs:
        "The fetch_albums_prune command asks the server to return a list
        of all albums that the user can either write to, or that are
        visible to the user and contain a sub-album that is writable
        (including sub-albums several times removed)."
        """
        if self.version == 1:
            request = {
                'protocol_version' : self.protocol_version,
                'cmd' : 'fetch-albums-prune'
            }
        else:
            request = {
                'g2_controller' : 'remote:GalleryRemote',
                'g2_form[protocol_version]' : self.protocol_version,
                'g2_form[cmd]' : 'fetch-albums-prune'
            }

        response = self._do_request(request)

        def gotResponse(response):
            # as long as it comes back here without an exception, we're ok.
            albums = {}

            for x in range(1, int(response['album_count']) + 1):
                album = {}
                album['name']                   = self._get(response,'album.name.' + str(x))
                album['title']                  = self._get(response,'album.title.' + str(x))
                album['summary']                = self._get(response,'album.summary.' + str(x))
                album['parent']                 = self._get(response,'album.parent.' + str(x))
                album['resize_size']            = self._get(response,'album.resize_size.' + str(x))
                album['perms.add']              = self._get(response,'album.perms.add.' + str(x))
                album['perms.write']            = self._get(response,'album.perms.write.' + str(x))
                album['perms.del_item']         = self._get(response,'album.perms.del_item.' + str(x))
                album['perms.del_alb']          = self._get(response,'album.perms.del_alb.' + str(x))
                album['perms.create_sub']       = self._get(response,'album.perms.create_sub.' + str(x))
                album['perms.info.extrafields'] = self._get(response,'album.info.extrafields' + str(x))

                albums[album['name']] = album

            return albums

        d.addCallback(gotResponse)
        return d


    def add_item(self, album, filename, caption, description):
        """
        Add a photo to the specified album.
        album - album name / identifier
        filename - image to upload
        caption - string caption to add to the image
        description - string description to add to the image
        """
        if self.version == 1:
            request = {
                'protocol_version' : self.protocol_version,
                'cmd' : 'add-item',
                'set_albumName' : album,
                'userfile' : file,
                'userfile_name' : filename,
                'caption' : caption,
                'extrafield.Description' : description
            }
        else:
            request = {
                'g2_form[protocol_version]' : self.protocol_version,
                'g2_form[cmd]' : 'add-item',
                'g2_form[set_albumName]' : album,
                'g2_form[userfile]' : file,
                'g2_form[userfile_name]' : filename,
                'g2_form[caption]' : caption,
                'g2_form[extrafield.Description]' : description
            }

        file = open(filename)
        d = self._do_request(request)
        # if we get here, everything went ok.

        return d

    def album_properties(self, album):
        """
        Obtain album property information for the specified album.
        album - the album name / identifier to obtain information for
        """
        if self.version == 1:
            request = {
                'protocol_version' : self.protocol_version,
                'cmd' : 'album-properties',
                'set_albumName' : album
            }
        else:
            request = {
                'g2_controller' : 'remote:GalleryRemote',
                'g2_form[protocol_version]' : self.protocol_version,
                'g2_form[cmd]' : 'album-properties',
                'g2_form[set_albumName]' : album
            }

        d = self._do_request(request)

        def gotResponse(response):
            res_dict = {}

            if response.has_key('auto_resize'):
                res_dict['auto_resize'] = response['auto_resize']
            if response.has_key('add_to_beginning'):
                res_dict['add_to_beginning'] = response['add_to_beginning']

            return res_dict

        d.addCallback(gotResponse)
        return d


    def new_album(self, parent, name=None, title=None, description=None):
        """
        Add an album to the specified parent album.
        parent - album name / identifier to contain the new album
        name - unique string name of the new album
        title - string title of the album
        description - string description to add to the image
        """
        if self.version == 1:
            request = {
                'g2_controller' : 'remote:GalleryRemote',
                'protocol_version' : self.protocol_version,
                'cmd' : 'new-album',
                'set_albumName' : parent
            }
            if name != None:
                request['newAlbumName'] = name
            if title != None:
                request['newAlbumTitle'] = title
            if description != None:
                request['newAlbumDesc'] = description
        else:
            request = {
                'g2_controller' : 'remote:GalleryRemote',
                'g2_form[protocol_version]' : self.protocol_version,
                'g2_form[cmd]' : 'new-album',
                'g2_form[set_albumName]' : parent
            }
            if name != None:
                request['g2_form[newAlbumName]'] = name
            if title != None:
                request['g2_form[newAlbumTitle]'] = title
            if description != None:
                request['g2_form[newAlbumDesc]'] = description

        d = self._do_request(request)

        def gotResponse(response):
            return response['album_name']

        d.addCallback(d)
        return d


    def fetch_album_images(self, album):
        """
        Get the image information for all images in the specified album.
        album - specifies the album from which to obtain image information
        """
        if self.version == 1:
            request = {
                'protocol_version' : self.protocol_version,
                'cmd' : 'fetch-album-images',
                'set_albumName' : album,
                'albums_too' : 'no',
                'extrafields' : 'yes'
            }
        else:
            request = {
                'g2_controller' : 'remote:GalleryRemote',
                'g2_form[protocol_version]' : self.protocol_version,
                'g2_form[cmd]' : 'fetch-album-images',
                'g2_form[set_albumName]' : album,
                'g2_form[albums_too]' : 'no',
                'g2_form[extrafields]' : 'yes'
            }

        d = self._do_request(request)

        def gotResponse (response):
            if response is None:
                print "Unable to retrieve list of item for album %s." % album
                return None

            images = []

            for x in range(1, int(response['image_count']) + 1):
                image = {}
                image['name']                = self._get(response, 'image.name.' + str(x))
                image['title']               = self._get(response, 'image.title.' + str(x))
                image['raw_width']           = self._get(response, 'image.raw_width.' + str(x))
                image['raw_height']          = self._get(response, 'image.raw_height.' + str(x))
                image['resizedName']         = self._get(response, 'image.resizedName.' + str(x))
                image['resized_width']       = self._get(response, 'image.resized_width.' + str(x))
                image['resized_height']      = self._get(response, 'image.resized_height.' + str(x))
                image['thumbName']           = self._get(response, 'image.thumbName.' + str(x))
                image['thumb_width']         = self._get(response, 'image.thumb_width.' + str(x))
                image['thumb_height']        = self._get(response, 'image.thumb_height.' + str(x))
                image['raw_filesize']        = self._get(response, 'image.raw_filesize.' + str(x))
                image['caption']             = self._get(response, 'image.caption.' + str(x))
                image['clicks']              = self._get(response, 'image.clicks.' + str(x))
                image['capturedate.year']    = self._get(response, 'image.capturedate.year' + str(x))
                image['capturedate.mon']     = self._get(response, 'image.capturedate.mon' + str(x))
                image['capturedate.mday']    = self._get(response, 'image.capturedate.mday' + str(x))
                image['capturedate.hours']   = self._get(response, 'image.capturedate.hours' + str(x))
                image['capturedate.minutes'] = self._get(response, 'image.capturedate.minutes' + str(x))
                image['capturedate.seconds'] = self._get(response, 'image.capturedate.seconds' + str(x))
                image['description']         = self._get(response, 'image.extrafield.Description.' + str(x))

                images.append(image)

            return images

        d.addCallback(gotResponse)
        return d


    def get_URL_for_image(self, gallery2_id):
        url = '%s/main.php?g2_view=core.DownloadItem&g2_itemId=%s' % (self.url, gallery2_id)
        return url