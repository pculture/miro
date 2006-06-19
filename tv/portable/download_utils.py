from os import access, F_OK
from urlparse import urlparse

def parseURL(url):
    (scheme, host, path, params, query, fragment) = urlparse(url)
    # Filter invalid URLs with duplicated ports (http://foo.bar:123:123/baz)
    # which seem to be part of #441.
    if host.count(':') > 1:
        host = host[0:host.rfind(':')]

    if ':' in host:
        host, port = host.split(':')
        try:
            port = int(port)
        except:
            print "DTV: parseURL: WARNING: invalid port for %s" % url
            if scheme == 'https':
                port = 443
            else:
                port = 80
    else:
        host = host
        if scheme == 'https':
            port = 443
        else:
            port = 80

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
    return filename.replace("\\","").replace("/","").replace(":","").replace("*","").replace("?","").replace("\"","").replace("<","").replace(">","").replace("|","")

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
        insertPoint = len(parts)-1
        parts[insertPoint:insertPoint] = [str(count)]
        newname = '.'.join(parts)
        while access(newname,F_OK):
            count += 1
            parts[insertPoint] = str(count)
            newname = '.'.join(parts)
    return newname
