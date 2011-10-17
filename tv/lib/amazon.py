# Miro - an RSS based video player application
# Copyright (C) 2005, 2006, 2007, 2008, 2009, 2010, 2011
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

"""Functions for downloading stuff from Amazon's MP3 Store.
"""

# NOTE: This file is not run through gettext because gettext kicks up an
# error.

import base64
import urlparse
from xml.dom import minidom

from miro import app
from miro import httpclient
from miro import fileutil
try:
    import pyDes as des
except ImportError:
    from miro import des

# keys courtesy of Steven C. Colbert's pymazon
AMAZON_DES_KEY = '\x29\xAB\x9D\x18\xB2\x44\x9E\x31'
AMAZON_DES_IV = '\x5E\x72\xD7\x9A\x11\xB3\x4F\xEE'

def decrypt_amz(data):
    decrypter = des.des(AMAZON_DES_KEY,
                        des.CBC,
                        AMAZON_DES_IV)
    return decrypter.decrypt(data)

def is_amazon_url(url):
    parts = urlparse.urlparse(url)
    return ((parts.path.endswith('.amz') or
             parts.path.endswith('.m3u')))

def is_amazon_content_type(content_type):
    """
    Returns True if this is a content type from Amazon.
    """
    return content_type.startswith(('audio/x-amzxml',
                                    'audio/x-mpegurl'))

def download_file(url, handle_unknown_callback):
    """
    Deals with turning an .amz file into some real downloads.
    """
    def unknown():
        handle_unknown_callback(url)
    def callback(data):
        _amazon_callback(data, unknown)

    if url.startswith('file://'):
        path = url[7:]
        try:
            _amz_callback(file(path).read())
        finally:
            fileutil.remove(path)
        return
    options = httpclient.TransferOptions(url)
    options.requires_cookies = True
    transfer = httpclient.CurlTransfer(options, callback,
                                       handle_unknown_callback)
    transfer.start()

def _amazon_callback(data, unknown):
    if data['status'] != 200:
        unknown()
        return

    if not is_amazon_content_type(data.get('content-type')):
        unknown()
        return

    if data['content-type'].startswith('audio/x-amzxml'): # .amz file:
        _amz_callback(data['body'])
    elif data['content-type'].startswith('audio/x-mpegurl'): # .m3u file:
        _m3u_callback(data['body'])

def _amz_callback(data):
    content = decrypt_amz(base64.b64decode(data)).rstrip('\x00\x08')

    dom = minidom.parseString(content)

    from miro.singleclick import _build_entry, download_video

    for track in dom.documentElement.getElementsByTagName('track'):
        url = None
        additional = {}
        for node in track.childNodes:
            if node.nodeType != node.TEXT_NODE:
                key = node.nodeName
                value = node.childNodes[0].nodeValue
                if key == 'location':
                    url = value
                elif key == 'title':
                    additional['title'] = value
                elif key == 'image':
                    additional['thumbnail'] = value
                elif key == 'duration':
                    additional['length'] = int(value) / 1000
        if url is None:
            app.controller.failed_soft("_amz_callback",
                                       "could not find URL for track",
                                       with_exception=False)
        else:
            entry = _build_entry(url, 'audio/mp3', additional)
            download_video(entry)

def _m3u_callback(data):
    from miro.singleclick import _build_entry, download_video

    for line in data.split('\n'):
        line = line.strip()
        if line.startswith('#'): # comment
            continue
        elif line:
            entry = _build_entry(line.decode('utf8'), 'audio/mp3')
            download_video(entry)
