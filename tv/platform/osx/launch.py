#!/usr/bin/python

import os
import sys

# The name of this platform.
platform = 'osx'

# Find the top of the source tree and set search path
root = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), '..', '..')
sys.path[0:0]=['%s/platform/%s' % (root, platform), '%s/platform' % root, '%s/portable' % root]

import app
app.main()
