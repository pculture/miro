import os
import objc
import config
from Foundation import *

# Find the full path to a resource data file. 'relative_path' is
# expected to be supplied in Unix format, with forward-slashes as
# separators. The output, though, uses the native platform separator.
def path(relative_path):
    return os.path.join(NSBundle.mainBundle().resourcePath(), 'resources', relative_path)

# As path(), but return a file: URL instead.
def url(relative_path):
    return "file://" + os.path.join(NSBundle.mainBundle().resourcePath(), 'resources', relative_path)

def iconCacheUrl(relative_path):
    """Like url, but for icon cache files.  These probably don't live in the
    resources directory because we need write access to them.
    """
    iconCacheDir = config.get(config.ICON_CACHE_DIRECTORY)
    return "file://%s" % os.path.join(iconCacheDir, relative_path)
