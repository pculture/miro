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

def iconCacheUrl(relative_path):
    """Like url, but for icon cache files.  These probably don't live in the
    resources directory because we need write access to them.
    """
    iconCacheDir = config.get(prefs.ICON_CACHE_DIRECTORY)
    return u"file://" + os.path.join(iconCacheDir, relative_path)
