import os
import objc
from Foundation import *

# Find the full path to a resource data file.
def path(relative_path):
    return os.path.join(NSBundle.mainBundle().resourcePath(), 'resources', relative_path)
