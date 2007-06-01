from xpcom import components
import os, sys
import re
import urllib

import config
import prefs

# Strategy: ask the directory service for
# NS_XPCOM_CURRENT_PROCESS_DIR, the directory "associated with this
# process," which is read to mean the root of the Mozilla
# installation. Use a fixed offset from this path.

# Another copy appears in components/pybridge.py, in the bootstrap
# code; if you change this function, change that one too.
def appRoot():
    # This reports the path to xulrunner.exe -- admittedly a little
    # misleading. In general, this will be in a 'xulrunner'
    # subdirectory underneath the actual application root directory.
    klass = components.classes["@mozilla.org/file/directory_service;1"]
    service = klass.getService(components.interfaces.nsIProperties)
    file = service.get("XCurProcD", components.interfaces.nsIFile)
    return file.path

def resourceRoot():
    return os.path.join(appRoot(), '..', 'resources')

# Note: some of these functions are probably not absolutely correct in
# the face of funny characters in the input paths. In particular,
# url() doesn't DTRT when the path contains spaces. But they should be
# sufficient for resolving resources, since we have control over the
# filenames.

# Find the full path to a resource data file. 'relative_path' is
# expected to be supplied in Unix format, with forward-slashes as
# separators. The output, though, uses the native platform separator.
def path(relative_path):
    abspath = os.path.abspath(os.path.join(resourceRoot(), relative_path))
    return abspath.replace("/", "\\")

def url(relative_path):
    return u"file://" + urllib.quote(path(relative_path).encode('utf_8'),safe="\\:~")

def absoluteUrl(absolute_path):
    """Like url, but without adding the resource directory.
    """
    return u"file://" + urllib.quote(absolute_path.encode('utf_8'),safe="\\:~")
