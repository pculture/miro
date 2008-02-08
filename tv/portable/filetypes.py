# Miro - an RSS based video player application
# Copyright (C) 2005-2008 Participatory Culture Foundation
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

import os

VIDEO_EXTENSIONS = ['.mov', '.wmv', '.mp4', '.m4v', '.ogg', '.anx', '.mpg', '.avi', '.flv', '.mpeg', '.divx', '.xvid', '.rmvb', '.mkv', '.m2v', '.ogm']
AUDIO_EXTENSIONS = ['.mp3', '.m4a', '.wma', '.mka']

MIMETYPES_EXT_MAP = {
    'video/quicktime':  ['.mov'],
    'video/mpeg':       ['.mpeg', '.mpg', '.m2v'],
    'video/mp4':        ['.mp4', '.m4v'],
    'video/flv':        ['.flv'],
    'video/x-flv':      ['.flv'],
    'video/x-ms-wmv':   ['.wmv'],
    'video/x-msvideo':  ['.avi'],
    'video/x-matroska': ['.mkv'],
    'application/ogg':  ['.ogg'],

    'audio/mpeg':       ['.mp3'],
    'audio/mp4':        ['.m4a'],
    'audio/x-ms-wma':   ['.wma'],
    'audio/x-matroska': ['.mka'],
    
    'application/x-bittorrent': ['.torrent']
}

EXT_MIMETYPES_MAP = {}
for (mimetype, exts) in MIMETYPES_EXT_MAP.iteritems():
    for ext in exts:
        if ext not in EXT_MIMETYPES_MAP:
            EXT_MIMETYPES_MAP[ext] = list()
        EXT_MIMETYPES_MAP[ext].append(mimetype)

def isAllowedFilename(filename):
    """
    Pass a filename to this method and it will return a boolean
    saying if the filename represents video, audio or torrent.
    """
    return isVideoFilename(filename) or isAudioFilename(filename) or isTorrentFilename(filename)

def isVideoFilename(filename):
    """
    Pass a filename to this method and it will return a boolean
    saying if the filename represents a video file.
    """
    filename = filename.lower()
    for ext in VIDEO_EXTENSIONS:
        if filename.endswith(ext):
            return True
    return False

def isAudioFilename(filename):
    """
    Pass a filename to this method and it will return a boolean
    saying if the filename represents an audio file.
    """
    filename = filename.lower()
    for ext in AUDIO_EXTENSIONS:
        if filename.endswith(ext):
            return True
    return False

def isTorrentFilename(filename):
    """
    Pass a filename to this method and it will return a boolean
    saying if the filename represents a torrent file.
    """
    filename = filename.lower()
    return filename.endswith('.torrent')

def isVideoEnclosure(enclosure):
    """
    Pass an enclosure dictionary to this method and it will return a boolean
    saying if the enclosure is a video or not.
    """
    return (_hasVideoType(enclosure) or
            _hasVideoExtension(enclosure, 'url') or
            _hasVideoExtension(enclosure, 'href'))

def _hasVideoType(enclosure):
    return ('type' in enclosure and
            (enclosure['type'].startswith(u'video/') or
             enclosure['type'].startswith(u'audio/') or
             enclosure['type'] == u"application/ogg" or
             enclosure['type'] == u"application/x-annodex" or
             enclosure['type'] == u"application/x-bittorrent" or
             enclosure['type'] == u"application/x-shockwave-flash"))

def _hasVideoExtension(enclosure, key):
    from miro import download_utils
    if key in enclosure:
        elems = download_utils.parseURL(enclosure[key], split_path=True)
        return isAllowedFilename(elems[3])
    return False

def isFeedContentType(contentType):
    """Is a content-type for a RSS feed?"""

    feedTypes = [ u'application/rdf+xml', u'application/atom+xml',
            u'application/rss+xml', u'application/podcast+xml', u'text/xml',
            u'application/xml', 
        ]
    for type in feedTypes:
        if contentType.startswith(type):
            return True
    return False

def guessExtension(mimetype):
    """
    Pass a mime type to this method and it will return a corresponding file
    extension, or None if it doesn't know about the type.
    """
    possibleExtensions = MIMETYPES_EXT_MAP.get(mimetype)
    if possibleExtensions is None:
        return None
    return possibleExtensions[0]

def guessMimeType(filename):
    """
    Pass a filename to this method and it will return a corresponding mime type,
    or 'video/unknown' if the filename has a known video extension but no 
    corresponding mime type, or None if it doesn't know about the file extension.
    """
    root, ext = os.path.splitext(filename)
    possibleTypes = EXT_MIMETYPES_MAP.get(ext)
    if possibleTypes is None:
        if isVideoFilename(filename):
            return 'video/unknown'
        elif isAudioFilename(filename):
            return 'audio/unknown'
        else:
            return None
    return possibleTypes[0]
