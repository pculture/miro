# Miro - an RSS based video player application
# Copyright (C) 2011
# Participatory Culture Foundation
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
#
# In addition, as a special exception, the copyright holders give
# permission to link the code of portions of this program with the OpenSSL
# library.
#
# You must obey the GNU General Public License in all respects for all of
# the code used other than OpenSSL. If you modify file(s) with this
# exception, you may extend this exception to your version of the file(s),
# but you are not obligated to do so. If you do not wish to do so, delete
# this exception statement from your version. If you delete this exception
# statement from all source files in the program, then also delete it here.

"""``miro.echonest`` -- Query Echonest"""

import collections
import logging
import os.path
import urllib
from xml.dom import minidom

from miro import filetags
from miro import httpclient
from miro import util
from miro import eventloop
from miro import trapcall

# TODO: get a API keys for PCF
ECHO_NEST_API_KEY = "ZAHBN7QAMJFJLABY6"
SEVEN_DIGITAL_API_KEY = "7d35gcbnycah"

try:
    import simplejson as json
except ImportError:
    import json

class CodegenError(StandardError):
    """ENMFP or echoprint failed to process a file."""

class ResponseParsingError(StandardError):
    """Error parsing an echonest/7digital response."""

def exec_codegen(codegen_info, media_path, callback, errback):
    """Run an echonest codegen in a worker thread.

    This method should work for both ENMFP and echoprint.

    On success, callback(media_path, echonest_code) will be called.

    On error, errback(media_path, exception) will be called.
    """
    codegen_path = codegen_info['path']
    codegen_env = codegen_info.get('env')
    def thread_function():
        stdout = util.call_command(codegen_path, media_path, env=codegen_env)
        results = json.loads(stdout)
        # not sure why the code generator always returns a 1-element list, but
        # it does
        results = results[0]
        if 'error' in results:
            raise CodegenError(results['error'])
        # NOTE: both codegens return some metadata that we can use, but
        # mutagen can get the same data so let's just pay attention to the
        # code.
        return results['code']

    def thread_callback(code):
        callback(media_path, code)

    def thread_errback(error):
        errback(media_path, error)

    logging.debug("Invoking echonest codegen on %s", media_path)
    eventloop.call_in_thread(thread_callback, thread_errback, thread_function,
                             'exec echonest codegen')

def query_echonest(path, cover_art_dir, code, version, metadata, callback,
                   errback):
    """Send a query to echonest to indentify a song.

    After the query is complete, we will either call callback(path,
    metadata_dict) or errback(path, exception_obj)

    :param path: path for the song
    :param cover_art_dir: directory to write cover art to
    :param code: echonest code from ENMFP or echoprint
    :param version: code version (3.15 for ENMFP or 4.11 for echoprint)
    :param metadata: dict of metadata from ID3 tags.
    :param callback: function to call on success
    :param error: function to call on error
    """
    _EchonestQuery(path, cover_art_dir, code, version, metadata, callback,
                   errback)

class _EchonestQuery(object):
    """Functor object that does the work for query_echonest.

    Since we use a couple deferred calls, it's simpler to work with an object
    than nesting everything inside a function.
    """
    # cache album names for 7digital release ids
    seven_digital_cache = {}

    def __init__(self, path, cover_art_dir, code, version, metadata, callback,
                 errback):
        self.metadata = {}
        self.cover_art_url = None
        self.cover_art_filename = None
        self.path = path
        self.cover_art_dir = cover_art_dir
        self.seven_digitial_ids_to_query = collections.deque()
        self.seven_digital_results = []
        self.callback = callback
        self.errback = errback
        self.code = code
        if code is not None:
            self.query_echonest_with_code(code, version, metadata)
        else:
            self.query_echonest_with_tags(metadata)

    def invoke_callback(self):
        trapcall.trap_call('query_echonest callback', self.callback,
                           self.path, self.metadata)

    def invoke_errback(self, error):
        trapcall.trap_call('query_echonest errback', self.errback,
                           self.path, error)

    def query_echonest_with_code(self, code, version, metadata):
        post_vars = {
            'api_key': ECHO_NEST_API_KEY,
            'bucket': ['tracks', 'id:7digital'],
            'query': self._make_echonest_query(code, version, metadata),
        }
        url = 'http://developer.echonest.com/api/v4/song/identify?'
        httpclient.grab_url(url,
                            self.echonest_callback, self.echonest_errback,
                            post_vars=post_vars)

    def query_echonest_with_tags(self, metadata):
        url_data = [
            ('api_key', ECHO_NEST_API_KEY),
            ('bucket', 'tracks'),
            ('bucket', 'id:7digital'),
        ]
        for key in ('title', 'artist'):
            if key in metadata:
                url_data.append((key, metadata[key].encode('utf-8')))
        url = ('http://developer.echonest.com/api/v4/song/search?' +
                urllib.urlencode(url_data))
        httpclient.grab_url(url, self.echonest_callback,
                            self.echonest_errback)

    def _make_echonest_query(self, code, version, metadata):
        echonest_metadata = {'version': version}
        if 'title' in metadata:
            echonest_metadata['title'] = metadata['title']
        if 'artist' in metadata:
            echonest_metadata['artist'] = metadata['artist']
        if 'album' in metadata:
            # echonest uses "release" instead of album
            echonest_metadata['release'] = metadata['album']
        if 'duration' in metadata:
            # convert millisecs to secs for echonest
            echonest_metadata['duration'] = metadata['duration'] // 1000
        return json.dumps({
            'code': code,
            'metadata': echonest_metadata,
        })

    def echonest_callback(self, data):
        try:
            self._handle_echonest_callback(data['body'])
        except StandardError, e:
            logging.warn("Error handling echonest response:\n%s",
                         data['body'], exc_info=True)
            self.invoke_errback(ResponseParsingError())

    def _handle_echonest_callback(self, echonest_reply):
        response = json.loads(echonest_reply)['response']
        status_code = response['status']['code']
        # TODO: check status code
        songs = response['songs']
        if len(songs) != 1:
            if self.code is not None:
                query_type = "Echonest code"
            else:
                query_type = "Metadata to echonest"
            if len(songs) == 0:
                logging.warn("%s matched no songs", query_type)
            else:
                logging.warn("%s Echonest code matched multiple songs",
                             query_type)
            # What can we do here?  Just return an empty metadata dict to our
            # callback
            self.invoke_callback()
            return

        song = songs[0]
        self.metadata['title'] = song['title'].decode('utf-8')
        self.metadata['artist'] = song['artist_name'].decode('utf-8')
        self.metadata['echonest_id'] = song['id'].decode('utf-8')

        tracks = song.get('tracks', [])
        if len(tracks) != 1:
            # No 7digital releases or too many Return the metadata we have
            self.invoke_callback()
        else:
            # No find all release ids, then start fetching them
            track = tracks[0]
            foreign_release_id = track['foreign_release_id']
            if not foreign_release_id.startswith("7digital:release:"):
                raise ResponseParsingError("Invalid foreign_release_id: %s" %
                                           foreign_release_id)
            release_id = foreign_release_id[len('7digital:release:'):]
            self.query_7digital(release_id)

    def echonest_errback(self, error):
        self.invoke_errback(error)

    def query_7digital(self, release_id):
        if release_id not in self.seven_digital_cache:
            self.release_id = release_id
            seven_digital_url = self._make_7digital_url(release_id)
            httpclient.grab_url(seven_digital_url,
                                self.seven_digital_callback,
                                self.seven_digital_errback)
        else:
            self.handle_7digital_cache_hit(release_id)

    def handle_7digital_cache_hit(self, release_id):
        album = self.seven_digital_cache[release_id]
        self.metadata['album'] = album
        cover_art_filename = filetags.calc_cover_art_filename(album)
        cover_art_path = os.path.join(self.cover_art_dir,
                                       cover_art_filename)
        if os.path.exists(cover_art_path):
            self.metadata['cover_art_path'] = cover_art_path
        self.invoke_callback()

    def _make_7digital_url(self, release_id):
        # data in all query strings
        url_data = [
            ('oauth_consumer_key', SEVEN_DIGITAL_API_KEY),
            ('imageSize', '350'),
            ('releaseid', str(release_id)),
        ]
        return ('http://api.7digital.com/1.2/release/details?' +
                urllib.urlencode(url_data))

    def seven_digital_callback(self, data):
        try:
            self._handle_7digital_callback(data['body'])
        except StandardError, e:
            logging.exception("Error handling 7digital response")
            # we can still invoke our callback with the data from echonest
        if (self.cover_art_url and self.cover_art_filename):
            self.grab_url_dest = os.path.join(self.cover_art_dir,
                                              self.cover_art_filename)
            if os.path.exists(self.grab_url_dest):
                self.metadata['cover_art_path'] = self.grab_url_dest
                self.invoke_callback()
            else:
                self.fetch_cover_art()
        else:

            self.invoke_callback()

    def _handle_7digital_callback(self, seven_digital_reply):
        doc = minidom.parseString(seven_digital_reply)
        def find_text_for_tag(tag_name):
            return doc.getElementsByTagName(tag_name)[0].firstChild.data

        if len(doc.getElementsByTagName('error')) == 0:
            album = find_text_for_tag('title')
            self.cover_art_url = find_text_for_tag('image')
            self.cover_art_filename = filetags.calc_cover_art_filename(album)
            self.metadata['album'] = album
            self.seven_digital_cache[self.release_id] = album
            # Note: we don't need to cache the cover art URL, because we only
            # have to download that once per album
        else:
            error = doc.getElementsByTagName('error')[0]
            code = error.getAttribute("code"),
            msg = find_text_for_tag('errorMessage')
            logging.warn("7digital returned an error: %s -- %s", code, msg)

    def seven_digital_errback(self, error):
        logging.warn("Error connecting to 7digital: %s", error)
        # we can still invoke our callback with the data from echonest
        self.invoke_callback()

    def fetch_cover_art(self):
        httpclient.grab_url(self.cover_art_url,
                            self.cover_art_callback,
                            self.cover_art_errback,
                            write_file=self.grab_url_dest)

    def cover_art_callback(self, data):
        # we don't care about the data sent back, since grab_url wrote our
        # file for us
        self.metadata['cover_art_path'] = self.grab_url_dest
        self.metadata['created_cover_art'] = True
        self.invoke_callback()

    def cover_art_errback(self, error):
        logging.warn("Error fetching cover art (%s)", self.cover_art_url)
        # we can still invoke our callback with the data from echonest
        self.invoke_callback()
