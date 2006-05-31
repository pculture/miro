from os import access, F_OK
from urlparse import urlparse

# Filter invalid URLs with duplicated ports (http://foo.bar:123:123/baz) which
# seem to be part of #441.
def parseURL(url):
    (scheme, host, path, params, query, fragment) = urlparse(url)
    if host.count(':') > 1:
        host = host[0:host.rfind(':')]
    return (scheme, host, path, params, query, fragment)

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
