#!/bin/sh

# The Bittorent library will put its support files in the folder pointed by
# the environment variable APPDATA, which is defined in the Info.plist of the
# Democracy application. However, environment variables defined in the Info.plist of
# an application bundle are only set for applications launched through Launch
# Services. Since we launch it here through command line, we manually set it
# to a similar default value.

export APPDATA=`echo ~/Library/Application Support/DTV`

# And now build and launch the test app.

/usr/bin/env python2.4 setup-unittests.py py2app --dist-dir . -A && Democracy.app/Contents/MacOS/Democracy
