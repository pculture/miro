import os
import sys
from distutils.core import setup
import py2app
import plistlib
import string

# The name of this platform.
platform = 'osx'

def updatePListEntry(plist, key, conf):
    entry = plist[key]
    plist[key] = string.Template(entry).safe_substitute(conf)

conf = {'appVersion':'0.0','copyright':'Copyright 2006','publisher':'Participatory Culture Foundation','shortAppName':'Democracy_Downloader','longAppName':'Democracy Downloader', 'appRevision':'0'}
infoPlist = plistlib.readPlist(u'Downloader.plist')

updatePListEntry(infoPlist, u'CFBundleGetInfoString', conf)
updatePListEntry(infoPlist, u'CFBundleIdentifier', conf)
updatePListEntry(infoPlist, u'CFBundleName', conf)
updatePListEntry(infoPlist, u'CFBundleShortVersionString', conf)
updatePListEntry(infoPlist, u'CFBundleVersion', conf)
updatePListEntry(infoPlist, u'NSHumanReadableCopyright', conf)

py2app_options = dict(
    plist=infoPlist,
)

# Find the top of the source tree and set search path
root = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), '..', '..')
sys.path[0:0] = [
    os.path.join(root, 'portable', 'dl_daemon'),

    # The daemon's "platform" files are in the private directory
    os.path.join(root, 'portable', 'dl_daemon','private'),
    os.path.join(root, 'portable'),
]
root = os.path.normpath(root)

setup(
    options=dict(
        py2app=py2app_options,
    ),
    app=[os.path.join(root, 'portable', 'dl_daemon', 'Democracy_Downloader.py')]
)
