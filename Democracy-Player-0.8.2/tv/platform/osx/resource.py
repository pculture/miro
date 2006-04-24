import os
import objc
from Foundation import *

# Find the full path to a resource data file. 'relative_path' is
# expected to be supplied in Unix format, with forward-slashes as
# separators. The output, though, uses the native platform separator.
def path(relative_path):
    return os.path.join(NSBundle.mainBundle().resourcePath(), 'resources', relative_path)

# As path(), but return a file: URL instead.
def url(relative_path):
    return "file://" + os.path.join(NSBundle.mainBundle().resourcePath(), 'resources', relative_path)
