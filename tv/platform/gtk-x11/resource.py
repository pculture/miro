import os
import re
import sys
import config
import prefs

resource_root = os.environ.get('DEMOCRACY_RESOURCE_ROOT',
        '/usr/share/democracy/resources/')
resource_root = os.path.abspath(resource_root)

# Note: some of these functions are probably not absolutely correct in
# the face of funny characters in the input paths. In particular,
# url() doesn't DTRT when the path contains spaces. But they should be
# sufficient for resolving resources, since we have control over the
# filenames.

# Find the full path to a resource data file. 'relative_path' is
# expected to be supplied in Unix format, with forward-slashes as
# separators. 
def path(relative_path):
    return os.path.join(resource_root, relative_path)

# As path(), but return a file: URL instead.
def url(relative_path):
    return 'file://%s' % path(relative_path)

def iconCacheUrl(relative_path):
    """Like url, but for icon cache files.  These probably don't live in the
    resources directory because we need write access to them.
    """
    iconCacheDir = config.get(prefs.ICON_CACHE_DIRECTORY)
    return "file://%s" % os.path.join(iconCacheDir, relative_path)
