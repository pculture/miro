from xpcom import components
import os, sys
import re

# Strategy: ask the directory service for
# NS_XPCOM_CURRENT_PROCESS_DIR, the directory "associated with this
# process," which is read to mean the root of the Mozilla
# installation. Use a fixed offset from this path.

def appRoot():
    klass = components.classes["@mozilla.org/file/directory_service;1"]
    service = klass.getService(components.interfaces.nsIProperties)
    file = service.get("XCurProcD", components.interfaces.nsIFile)
    return file.path

def resourceRoot():
    if 'RUNXUL_RESOURCES' in os.environ:
	# We're being run it test mode by our 'runxul' distutils
	# command.
	return os.environ['RUNXUL_RESOURCES']
    # NEEDS: is this really how we want to lay out the directories?
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
    rootParts = re.split(r'\\', resourceRoot())
    myParts = re.split(r'/', relative_path)
    return '\\'.join(rootParts + myParts)

# As path(), but return a file: URL instead.
def url(relative_path):
    rootParts = re.split(r'\\', resourceRoot())
    myParts = re.split(r'/', relative_path)
    return "file:///" + '/'.join(rootParts + myParts)
