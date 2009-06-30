# Miro - an RSS based video player application
# Copyright (C) 2005-2009 Participatory Culture Foundation
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

# NOTE: if you change VIDEO_EXTENSIONS or AUDIO_EXTENSIONS, consider writing a
# database update so that the file_type attribute of the item table gets fixed

VIDEO_EXTENSIONS = ['.mov', '.wmv', '.mp4', '.m4v', '.ogv', '.anx', '.mpg', '.avi', '.flv', '.mpeg', '.divx', '.xvid', '.rmvb', '.mkv', '.m2v', '.ogm']
AUDIO_EXTENSIONS = ['.mp3', '.m4a', '.wma', '.mka', '.flac', '.ogg']
FEED_EXTENSIONS = ['.xml', '.rss', '.atom']

UNSUPPORTED_MIMETYPES = ("video/3gpp", "video/vnd.rn-realvideo", "video/x-ms-asf")

MIMETYPES_EXT_MAP = {
    'video/quicktime':  ['.mov'],
    'video/mpeg':       ['.mpeg', '.mpg', '.m2v'],
    'video/mp4':        ['.mp4', '.m4v'],
    'video/mpeg4':      ['.mp4', '.m4v'],
    'video/flv':        ['.flv'],
    'video/x-flv':      ['.flv'],
    'video/x-ms-wmv':   ['.wmv'],
    'video/x-msvideo':  ['.avi'],
    'video/x-matroska': ['.mkv'],
    'application/ogg':  ['.ogg'],
    'video/ogg':        ['.ogv'],

    'audio/flac':       ['.flac'],
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

def is_allowed_filename(filename):
    """
    Pass a filename to this method and it will return a boolean
    saying if the filename represents video, audio or torrent.
    """
    return is_video_filename(filename) or is_audio_filename(filename) or is_torrent_filename(filename)

def is_playable_filename(filename):
    """
    Pass a filename to this method and it will return a boolean
    saying if the filename represents video or audio.
    """
    return is_video_filename(filename) or is_audio_filename(filename)

def is_video_filename(filename):
    """
    Pass a filename to this method and it will return a boolean
    saying if the filename represents a video file.
    """
    filename = filename.lower()
    for ext in VIDEO_EXTENSIONS:
        if filename.endswith(ext):
            return True
    return False

def is_audio_filename(filename):
    """
    Pass a filename to this method and it will return a boolean
    saying if the filename represents an audio file.
    """
    filename = filename.lower()
    for ext in AUDIO_EXTENSIONS:
        if filename.endswith(ext):
            return True
    return False

def is_media_filename(filename):
    """Check if a filename is a video or audio filename"""
    return is_video_filename(filename) or is_audio_filename(filename)

def is_torrent_filename(filename):
    """
    Pass a filename to this method and it will return a boolean
    saying if the filename represents a torrent file.
    """
    filename = filename.lower()
    return filename.endswith('.torrent')

def is_feed_filename(filename):
    """
    Pass a filename to this method and it will return a boolean saying if the
    filename possibly represents an Atom or RSS feed URL.
    """
    filename = filename.lower()
    for ext in FEED_EXTENSIONS:
        if filename.endswith(ext):
            return True
    return False

def is_video_enclosure(enclosure):
    """
    Pass an enclosure dictionary to this method and it will return a boolean
    saying if the enclosure is a video or not.
    """
    return (_has_video_type(enclosure) or
            _has_video_extension(enclosure, 'url') or
            _has_video_extension(enclosure, 'href'))

def _has_video_type(enclosure):
    return ('type' in enclosure and
            (enclosure['type'].startswith(u'video/') or
             enclosure['type'].startswith(u'audio/') or
             enclosure['type'] == u"application/ogg" or
             enclosure['type'] == u"application/x-annodex" or
             enclosure['type'] == u"application/x-bittorrent" or
             enclosure['type'] == u"application/x-shockwave-flash") and
            (enclosure['type'] not in UNSUPPORTED_MIMETYPES))

def _has_video_extension(enclosure, key):
    from miro import download_utils
    if key in enclosure:
        elems = download_utils.parseURL(enclosure[key], split_path=True)
        return is_allowed_filename(elems[3])
    return False

def is_feed_content_type(contentType):
    """Is a content-type for a RSS feed?"""

    feedTypes = [ u'application/rdf+xml', u'application/atom+xml',
            u'application/rss+xml', u'application/podcast+xml', u'text/xml',
            u'application/xml', 
        ]
    for type in feedTypes:
        if contentType.startswith(type):
            return True
    return False

def is_maybe_feed_content_type(contentType):
    """Could the content type contain a feed?
    """
    return contentType.startswith(u"text/")

def is_maybe_rss(body):
    """Sniffs the body to determine whether it's a feed or not.

    this is very loosely taken from Firefox nsFeedSniffer.cpp and ideas in
    http://blogs.msdn.com/rssteam/articles/PublishersGuide.aspx
    """
    if len(body) > 512:
        body = body[0:512]

    for mem in ( "<rss", "<feed", "<rdf:RDF" ):
        if body.find(mem) != -1:
            return True
    return False

def is_maybe_rss_url(url):
    return (url.startswith("http") and
            (url.startswith("http://feeds.feedburner.com") or "rss" in url))

def guess_extension(mimetype):
    """
    Pass a mime type to this method and it will return a corresponding file
    extension, or None if it doesn't know about the type.
    """
    possibleExtensions = MIMETYPES_EXT_MAP.get(mimetype)
    if possibleExtensions is None:
        return None
    return possibleExtensions[0]

def guess_mime_type(filename):
    """
    Pass a filename to this method and it will return a corresponding mime type,
    or 'video/unknown' if the filename has a known video extension but no 
    corresponding mime type, or None if it doesn't know about the file extension.
    """
    root, ext = os.path.splitext(filename)
    possibleTypes = EXT_MIMETYPES_MAP.get(ext)
    if possibleTypes is None:
        if is_video_filename(filename):
            return 'video/unknown'
        elif is_audio_filename(filename):
            return 'audio/unknown'
        else:
            return None
    return possibleTypes[0]
