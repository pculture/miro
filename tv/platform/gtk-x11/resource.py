import os
import re
import sys

def appRoot():
    if hasattr(sys, "frozen"):
        path = sys.executable
    else:
        path = sys.argv[0]
    return os.path.dirname(os.path.join(os.getcwdu(), path))

# Note: some of these functions are probably not absolutely correct in
# the face of funny characters in the input paths. In particular,
# url() doesn't DTRT when the path contains spaces. But they should be
# sufficient for resolving resources, since we have control over the
# filenames.

# Find the full path to a resource data file. 'relative_path' is
# expected to be supplied in Unix format, with forward-slashes as
# separators. The output, though, uses the native platform separator.
def path(relative_path):
    root = appRoot()
    if len(root) > 0:
        rootParts = re.split(r'/', appRoot())
    else:
        rootParts = []
    rootParts.append('..')
    rootParts.append('..')
    myParts = re.split(r'/', relative_path)
    return os.path.normpath('/'.join(rootParts + ['resources'] + myParts))

# As path(), but return a file: URL instead.
def url(relative_path):
    root = appRoot()
    if len(root) > 0:
        rootParts = re.split(r'/', appRoot())
    else:
        rootParts = []
    rootParts.append('..')
    rootParts.append('..')
    myParts = re.split(r'/', relative_path)
    return "file://" + os.path.normpath('/'.join(rootParts + ['resources'] + myParts))

