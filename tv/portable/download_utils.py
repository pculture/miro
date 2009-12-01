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

from os import access, F_OK
from urlparse import urlparse
from urllib import unquote
import os.path
import re
import logging

from miro import filetypes
from miro import util
from miro import fileutil

from miro.util import checkF, checkU, returnsFilename
from miro.plat.utils import unicodeToFilename, unmake_url_safe
from miro.fileutil import expand_filename

URIPattern = re.compile(r'^([^?]*/)?([^/?]*)/*(\?(.*))?$')

# filename limits this is mostly for windows where we have a 255 character
# limit on entire pathname
MAX_FILENAME_LENGTH = 100 
MAX_FILENAME_EXTENSION_LENGTH = 50

def fixFileURLS(url):
    """Fix file URLS that start with file:// instead of file:///.  Note: this
    breaks for file URLS that include a hostname, but we never use those and
    it's not so clear what that would mean anyway -- file URLs is an ad-hoc
    spec as I can tell.."""
    if url.startswith('file://'):
        if not url.startswith('file:///'):
            url = 'file:///%s' % url[len('file://'):]
        url = url.replace('\\', '/')
    return url

def defaultPort(scheme):
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
            logging.warn("Assuming port 80 for scheme: %s" % scheme)
    return 80

def parseURL(url, split_path=False):
    url = fixFileURLS(url)
    (scheme, host, path, params, query, fragment) = util.unicodify(list(urlparse(url)))
    # Filter invalid URLs with duplicated ports (http://foo.bar:123:123/baz)
    # which seem to be part of #441.
    if host.count(':') > 1:
        host = host[0:host.rfind(':')]

    if scheme == '' and util.chatter:
        logging.warn("%r has no scheme" % url)

    if ':' in host:
        host, port = host.split(':')
        try:
            port = int(port)
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            logging.warn("invalid port for %r" % url)
            port = defaultPort(scheme)
    else:
        port = defaultPort(scheme)

    host = host.lower()
    scheme = scheme.lower()

    path = path.replace('|', ':') 
    # Windows drive names are often specified as "C|\foo\bar"

    if path == '' or not path.startswith('/'):
        path = '/' + path
    elif scheme.startswith("file") and re.match(r'/[a-zA-Z]:', path):
        # fixes "file:///C:/foo" paths
        path = path[1:]
    fullPath = path
    if split_path:
        return scheme, host, port, fullPath, params, query
    else:
        if params:
            fullPath += ';%s' % params
        if query:
            fullPath += '?%s' % query
        return scheme, host, port, fullPath

def getFileURLPath(url):
    scheme, host, port, path = parseURL(url)
    if scheme != 'file':
        raise ValueError("%r is not a file URL" % url)
    return unmake_url_safe(path)

def checkFilenameExtension(filename, contentType):
    """If a filename doesn't have an extension, this tries to find a suitable
    one based on the HTTP content-type info and add it if one is available.
    """
    checkF(filename)
    if contentType is not None and not filetypes.is_allowed_filename(filename):
        guessedExt = filetypes.guess_extension(contentType)
        if guessedExt is not None:
            filename += guessedExt
    return filename

@returnsFilename
def nextFreeFilename(name):
    """Finds a filename that's unused and similar the the file we want
    to download
    """
    checkF(name)
    if not access(expand_filename(name), F_OK):
        return name
    parts = name.split('.')
    count = 1
    if len(parts) == 1:
        newname = "%s.%s" % (name, count)
        while access(expand_filename(newname), F_OK):
            count += 1
            newname = "%s.%s" % (name, count)
    else:
        parts[-1:-1] = [str(count)]
        newname = '.'.join(parts)
        while access(expand_filename(newname), F_OK):
            count += 1
            parts[-2] = str(count)
            newname = '.'.join(parts)
    return newname

@returnsFilename
def filenameFromURL(url, clean=False):
    """Returns a reasonable filename for saving the given url
    """
    checkU(url)
    try:
        match = URIPattern.match(url)
        if match is None:
            # This code path will never be executed.
            return unicodeToFilename(url)
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
            return cleanFilename(ret)
        else:
            return unicodeToFilename(ret)
    except (SystemExit, KeyboardInterrupt):
        raise
    except:
        return unicodeToFilename(u'unknown')

@returnsFilename
def cleanFilename(filename):
    """Given either a filename or a unicode "filename" return a valid clean
    version of it
    """
    for char in ( ':', '?', '<', '>', '|', '*', '\\', '/', '"', '\'', '%'):
        filename = filename.replace(char, '')
    if len(filename) == 0:
        return unicodeToFilename(u'_')
    if len(filename) > MAX_FILENAME_LENGTH:
        base, ext = os.path.splitext(filename)
        ext = ext[:MAX_FILENAME_EXTENSION_LENGTH]
        base = base[:MAX_FILENAME_LENGTH-len(ext)]
        filename = base + ext
    if type(filename) == str:
        return unicodeToFilename(filename.decode('ascii', 'replace'))
    else:
        return unicodeToFilename(filename)

def saveData(target, suggested_basename, data):
    """Saves data, returns filename, doesn't write over existing files.
    """
    try:
        fileutil.makedirs(target)
    except (SystemExit, KeyboardInterrupt):
        raise
    except:
        pass

    filename = os.path.join(target, suggested_basename)

    try:
        # Write to a temp file.
        tmp_filename = filename + ".part"
        tmp_filename = nextFreeFilename(tmp_filename)
        output = file(tmp_filename, 'wb')
        output.write(data)
        output.close()
    except IOError:
        try:
            fileutil.remove(tmp_filename)
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            pass
        raise

    filename = nextFreeFilename(filename)
    needsSave = True
    try:
        fileutil.remove(filename)
    except (SystemExit, KeyboardInterrupt):
        raise
    except:
        pass

    fileutil.rename(tmp_filename, filename)

    return filename

def filterDirectoryName(name):
    """Filter out all non alpha-numeric characters from a future directory
    name so we can create a corresponding directory on disk without bumping
    into platform specific pathname limitations.
    """
    return re.sub(r'[^a-zA-Z0-9]', '-', name)
