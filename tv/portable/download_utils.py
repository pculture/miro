from os import access, F_OK
from urlparse import urlparse
import os.path
import re
import urllib
import mimetypes
import util
from util import checkF, checkU, returnsFilename
from platformutils import unicodeToFilename

# The mimetypes module does not know about FLV, let's enlighten him.
mimetypes.add_type('video/flv', '.flv')
mimetypes.add_type('video/x-flv', '.flv')

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
    elif scheme == 'file':
        return None
    else:
        if util.chatter:
            print "WARNING: Assuming port 80 for scheme: %s" % scheme
        return 80

def parseURL(url):
    url = fixFileURLS(url)
    (scheme, host, path, params, query, fragment) = urlparse(url)
    # Filter invalid URLs with duplicated ports (http://foo.bar:123:123/baz)
    # which seem to be part of #441.
    if host.count(':') > 1:
        host = host[0:host.rfind(':')]

    if scheme == '' and util.chatter:
        print "WARNING: %s has no scheme" % url

    if ':' in host:
        host, port = host.split(':')
        try:
            port = int(port)
        except:
            print "DTV: parseURL: WARNING: invalid port for %s" % url
            port = defaultPort(scheme)
    else:
        port = defaultPort(scheme)

    host = host.lower()
    scheme = scheme.lower()

    if path == '' or path[0] != '/':
        path = '/' + path
    fullPath = path
    if params:
        fullPath += ';%s' % params
    if query:
        fullPath += '?%s' % query
    return scheme, host, port, fullPath

# If a filename doesn't have an extension, this tries to find a suitable one
# based on the HTTP content-type info and add it if one is available.
def checkFilenameExtension(filename, httpInfo):
    checkF(filename)
    _, ext = os.path.splitext(filename)
    if ext == '' and 'content-type' in httpInfo:
        guessedExt = mimetypes.guess_extension(httpInfo['content-type'])
        if guessedExt is not None:
            filename += guessedExt
    return filename

##
# Finds a filename that's unused and similar the the file we want
# to download
@returnsFilename
def nextFreeFilename(name):
    checkF(name)
    if not access(name,F_OK):
        return name
    parts = name.split('.')
    count = 1
    if len(parts) == 1:
        newname = "%s.%s" % (name, count)
        while access(newname,F_OK):
            count += 1
            newname = "%s.%s" % (name, count)
    else:
        parts[-1:-1] = [str(count)]
        newname = '.'.join(parts)
        while access(newname,F_OK):
            count += 1
            parts[-2] = str(count)
            newname = '.'.join(parts)
    return newname

##
# Returns a reasonable filename for saving the given url
@returnsFilename
def filenameFromURL(url):
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
            ret = u"%s-%s" % (filename, query)
        if ret is None:
            ret = u'unknown'
        return unicodeToFilename(ret)
    except:
        return unicodeToFilename(u'unknown')

# Given either a filename or a unicode "filename" return a valid clean
# version of it
@returnsFilename
def cleanFilename(filename):
    if type(filename) == str:
        return unicodeToFilename(filename.decode('ascii','replace'))
    else:
        return unicodeToFilename(filename)

# Saves data, returns filename, doesn't write over existing files.
def saveData (target, suggested_basename, data):
    try:
        os.makedirs(target)
    except:
        pass

    filename = os.path.join (target, suggested_basename)

    try:
        # Write to a temp file.
        tmp_filename = filename + ".part"
#        tmp_filename = shortenFilename (tmp_filename)
        tmp_filename = nextFreeFilename (tmp_filename)
        output = file (tmp_filename, 'wb')
        output.write(data)
        output.close()
    except IOError:
        try:
            os.remove (tmp_filename)
        except:
            pass
        raise

#    filename = shortenFilename (filename)
    filename = nextFreeFilename (filename)
    needsSave = True
    try:
        os.remove (filename)
    except:
        pass

    os.rename (tmp_filename, filename)

    return filename
