import os

import prefs
import config
import urllib
import platformcfg

# Find the full path to a resource data file. 'relative_path' is
# expected to be supplied in Unix format, with forward-slashes as
# separators. The output, though, uses the native platform separator.
def path(relative_path):
    rsrcpath = os.path.join(platformcfg.getBundleResourcePath(), u'resources', relative_path)
    return os.path.abspath(rsrcpath)

# As path(), but return a file: URL instead.
def url(relative_path):
    return u"file://" + urllib.quote(path(relative_path).encode('utf-8'))

def absoluteUrl(absolute_path):
    """Like url, but without adding the resource directory.
    """
    return u"file://" + urllib.quote(absolute_path)
