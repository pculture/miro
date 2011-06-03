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

"""Functions for downloading from eMusic."""

from miro import app
from miro import httpclient
from miro import fileutil

import StringIO

import urlparse
from xml.dom import minidom

def is_emusic_url(url):
    parts = urlparse.urlparse(url)
    return parts.path.endswith('.emx')
            
def download_file(url, handle_unknown_callback):
    """
    Deals with turning an .amz file into some real downloads.
    """
    if url.startswith('file://'):
        path = url[7:]
        try:
            _download_emx_files(path)
        finally:
            fileutil.remove(path)
        return

    def callback(data):
        _emx_callback(data, handle_unknown_callback)

    options = httpclient.TransferOptions(url)
    options.requires_cookies = True
    transfer = httpclient.CurlTransfer(options, callback,
                                       handle_unknown_callback)
    transfer.start()

def _emx_callback(data, unknown):
    if data['status'] != 200:
        return unknown(data['original-url'])
    if data['content-type'].startswith('text/html'):
        return unknown(data['original-url'])

    _download_emx_files(StringIO(data['body']))

def _download_emx_files(file_):
    dom = minidom.parse(file_)

    from miro.singleclick import _build_entry, download_video

    for track in dom.documentElement.getElementsByTagName('TRACK'):
        url = None
        additional = {}
        for node in track.childNodes:
            if node.nodeType != node.TEXT_NODE:
                key = node.nodeName
                if node.childNodes:
                    value = node.childNodes[0].nodeValue
                else:
                    value = None
                if key == 'TRACKURL':
                    url = value
                elif key == 'TITLE':
                    additional['title'] = value
                elif key == 'ALBUMARTLARGE':
                    additional['thumbnail'] = value
                elif key == 'ALBUMART' and 'thumbnail' not in additional:
                    additional['thumbnail'] = value
                elif key == 'DURATION':
                    additional['length'] = int(value)
        if url is None:
            app.controller.failed_soft("_emx_callback",
                                       "could not find URL for track",
                                       with_exception=False)
        else:
            entry = _build_entry(url, 'audio/mp3', additional)
            download_video(entry)
