import os
import sys

#import test.domtest
#print "Your DTV session has been hijacked for Mozilla testing."
#test.domtest.main()

# Add extra stuff to the search path that will let us find our source
# directories when we have built a development bundle with py2app -A.
platform = 'gtk-x11'
root = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), '..', '..')
sys.path[0:0]=['%s/platform/%s' % (root, platform), '%s/platform' % root, '%s/portable' % root]

import app
app.main()
