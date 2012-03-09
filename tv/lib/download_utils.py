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

# FIXME - seems unneeded
# from os import access, F_OK
from urlparse import urlparse
from urllib import unquote
import errno
import os.path
import re
import logging
import sys

from miro import filetypes
from miro import util

from miro.util import check_f, check_u, returns_filename, returns_file
from miro.plat.utils import unicode_to_filename, unmake_url_safe
from miro.fileutil import expand_filename

# next_free_filename and friends used to be defined in this module, but
# they've been moved to the utils module.  For now, we import into this module
# too so that the old code will continue to work.
# FIXME: refactor code so we import next_free_filename from util.py
from miro.util import next_free_filename, next_free_directory

URI_PATTERN = re.compile(r'^([^?]*/)?([^/?]*)/*(\?(.*))?$')

# filename limits this is mostly for windows where we have a 255 character
# limit on entire pathname
MAX_FILENAME_LENGTH = 100 
MAX_FILENAME_EXTENSION_LENGTH = 50

def fix_file_urls(url):
    """Fix file urls that start with file:// instead of file:///.

    Note: this breaks for file urls that include a hostname, but we
    never use those and it's not so clear what that would mean
    anyway--file urls is an ad-hoc spec as I can tell.
    """
    if url.startswith('file://'):
        if not url.startswith('file:///'):
            url = 'file:///%s' % url[len('file://'):]
        url = url.replace('\\', '/')
    return url

def default_port(scheme):
    if scheme == 'https':
        return 443
    elif scheme == 'http':
        return 80
    elif scheme == 'rtsp':
        return 554
    elif scheme == 'file':
        return None
    else:
        if util.chatter:
            logging.warn("Assuming port 80 for scheme: %s", scheme)
    return 80

def parse_url(url, split_path=False):
    url = fix_file_urls(url)
    (scheme, host, path, params, query, fragment) = \
             util.unicodify(list(urlparse(url)))

    # Filter invalid URLs with duplicated ports
    # (http://foo.bar:123:123/baz) which seem to be part of #441.
    if host.count(':') > 1:
        host = host[0:host.rfind(':')]

    if scheme == '' and util.chatter:
        logging.warn("%r has no scheme", url)

    if ':' in host:
        host, port = host.split(':')
        try:
            port = int(port)
        except ValueError:
            logging.warn("invalid port for %r", url)
            port = default_port(scheme)
    else:
        port = default_port(scheme)

    host = host.lower()
    scheme = scheme.lower()

    path = path.replace('|', ':') 

    # Windows drive names are often specified as "C|\foo\bar"
    if path == '' or not path.startswith('/'):
        path = '/' + path
    elif scheme.startswith("file") and re.match(r'/[a-zA-Z]:', path):
        # fixes "file:///C:/foo" paths
        path = path[1:]
    full_path = path
    if split_path:
        return scheme, host, port, full_path, params, query

    if params:
        full_path += ';%s' % params
    if query:
        full_path += '?%s' % query
    return scheme, host, port, full_path

def get_file_url_path(url):
    scheme, host, port, path = parse_url(url)
    if scheme != 'file':
        raise ValueError("%r is not a file URL" % url)
    return unmake_url_safe(path)

def check_filename_extension(filename, content_type):
    """If a filename doesn't have an extension, this tries to find a
    suitable one based on the HTTP content-type info and add it if one
    is available.
    """
    check_f(filename)
    if content_type is not None and not filetypes.is_allowed_filename(filename):
        guessed_ext = filetypes.guess_extension(content_type)
        if guessed_ext is not None:
            filename += guessed_ext
    return filename

@returns_filename
def filename_from_url(url, clean=False):
    """Returns a reasonable filename for saving the given url.
    """
    check_u(url)
    try:
        match = URI_PATTERN.match(url)
        if match is None:
            # This code path will never be executed.
            return unicode_to_filename(url)
        filename = match.group(2)
        query = match.group(4)
        if not filename:
            ret = query
        elif not query:
            ret = filename
        else:
            root, ext = os.path.splitext(filename)
            ret = u"%s-%s%s" % (root, query, ext)
        ret = unquote(ret)
        if ret is None:
            ret = u'unknown'
        if clean:
            return clean_filename(ret)
        else:
            return unicode_to_filename(ret)
    except (TypeError, KeyError, AttributeError, UnicodeDecodeError):
        return unicode_to_filename(u'unknown')

@returns_filename
def clean_filename(filename):
    """Given either a filename or a unicode "filename" return a valid
    clean version of it.
    """
    for char in (':', '?', '<', '>', '|', '*', '\\', '/', '"', '\'', '%'):
        filename = filename.replace(char, '')
    if len(filename) == 0:
        return unicode_to_filename(u'_')
    if len(filename) > MAX_FILENAME_LENGTH:
        base, ext = os.path.splitext(filename)
        ext = ext[:MAX_FILENAME_EXTENSION_LENGTH]
        base = base[:MAX_FILENAME_LENGTH-len(ext)]
        filename = base + ext
    if isinstance(filename, str):
        return unicode_to_filename(filename.decode('ascii', 'replace'))
    else:
        return unicode_to_filename(filename)

def filter_directory_name(name):
    """Filter out all non alpha-numeric characters from a future directory
    name so we can create a corresponding directory on disk without bumping
    into platform specific pathname limitations.
    """
    return re.sub(r'[^a-zA-Z0-9]', '-', name)
