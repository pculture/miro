import os
import sys
import unittest

# Add extra stuff to the search path that will let us find our source
# directories when we have built a development bundle with py2app -A.
platform = 'osx'
root = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])),
                    '..', '..', '..')
root = os.path.normpath(root)
sys.path[0:0]=['%s/platform/%s' % (root, platform), '%s/platform' % root, '%s/portable' % root, '%s/portable/test' % root, '%s/platform/%s/test' % (root, platform)]

from databasetest import *
from templatetest import *

unittest.main()

