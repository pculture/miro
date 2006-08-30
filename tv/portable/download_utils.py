from os import access, F_OK
from urlparse import urlparse
import os.path
import re
import urllib
import util

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

# Returns a filename minus nasty characters
def cleanFilename(filename):
    if not os.path.supports_unicode_filenames:
        filename = filename.encode('ascii', 'ignore')
    stripped = filename.replace("\\","").replace("/","").replace(":","").replace("*","").replace("?","").replace("\"","").replace("<","").replace(">","").replace("|","")
    if stripped == '':
        # What can we do here?  This seems as good as anything.
        return '_' 
    else:
        return stripped

##
# Finds a filename that's unused and similar the the file we want
# to download
def nextFreeFilename(name):
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

def shortenFilename(name):
    if len(name) < 200:
        return name
    (path, basename) = os.path.split(name)
    split = basename.rsplit(".", 1)
    if len(split[0]) > 100:
        split[0] = split[0][:100]
    if len(split) > 1 and len(split[1]) > 100:
        split[1] = split[1][:100]
    basename = ".".join(split)
    name = os.path.join (path, basename)
    return name
