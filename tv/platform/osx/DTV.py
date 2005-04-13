import os
import sys

# Add extra stuff to the search path that will let us find our source
# directories when we have built a development bundle with py2app -A.
platform = 'osx'
root = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), '..', '..', '..', '..', '..')
sys.path[0:0]=['%s/platform/%s' % (root, platform), '%s/platform' % root, '%s/portable' % root]

import app

app.main()

