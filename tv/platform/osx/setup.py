import os
import sys
import string
import py2app
import plistlib

from glob import glob
from distutils.core import setup
from Pyrex.Distutils import build_ext
from distutils.extension import Extension

# Find the top of the source tree and set search path
# GCC3.3 on OS X 10.3.9 doesn't like ".."'s in the path so we normalize it

root = os.path.dirname(os.path.abspath(sys.argv[0]))
root = os.path.join(root, '..', '..')
root = os.path.normpath(root)
sys.path[0:0]=['%s/portable' % root]

# Only now may we import things from our own tree

import template_compiler
template_compiler.compileAllTemplates(root)

# Look for the Boost library in various common places.
# - we assume that both the library and the include files are installed in the
#   same directory sub-hierarchy.
# - we look for library and include directory in:
#   - the standard '/usr/local' tree
#   - Darwinports' standard '/opt/local' tree
#   - Fink's standard '/sw' tree

boostLib = None
boostIncludeDir = None
boostSearchDirs = ('/usr/local', '/opt/local', '/sw')

for rootDir in boostSearchDirs:
    libItems = glob(os.path.join(rootDir, 'lib/libboost_python-1_3*.a'))
    incItems = glob(os.path.join(rootDir, 'include/boost-1_3*/'))
    if len(libItems) == 1 and len(incItems) == 1:
        boostLib = libItems[0]
        boostIncludeDir = incItems[0]

if boostLib is None or boostIncludeDir is None:
    print 'Boost library could not be found, interrupting build.'
    sys.exit(1)
else:
    print 'Boost library found (%s)' % boostLib


import util
revision = util.queryRevision(root)
if revision is None:
    revision = 'unknown'
else:
    revision = '%s' % revision

# Inject the revision number into app.config.template to get app.config.
# NEEDS: Very sloppy. The new file is just dropped in the source tree
# next to the old one.
appConfigPath = os.path.join(root, 'resources', 'app.config')
s = open("%s.template" % appConfigPath, "rt").read()
s = string.Template(s).safe_substitute(APP_REVISION = revision, APP_PLATFORM = 'osx')
f = open(appConfigPath, "wt")
f.write(s)
f.close()

# Update the Info property list.

def updatePListEntry(plist, key, conf):
    entry = plist[key]
    plist[key] = string.Template(entry).safe_substitute(conf)

conf = util.readSimpleConfigFile(appConfigPath)
infoPlist = plistlib.readPlist(u'Info.plist')

updatePListEntry(infoPlist, u'CFBundleGetInfoString', conf)
updatePListEntry(infoPlist, u'CFBundleIdentifier', conf)
updatePListEntry(infoPlist, u'CFBundleName', conf)
updatePListEntry(infoPlist, u'CFBundleShortVersionString', conf)
updatePListEntry(infoPlist, u'CFBundleVersion', conf)
updatePListEntry(infoPlist, u'NSHumanReadableCopyright', conf)

print "Building Democracy Player v%s (%s)" % (conf['appVersion'], conf['appRevision'])

# Get a list of additional resource files to include

resourceFiles = ['Resources/%s' % x for x in os.listdir('Resources')]
resourceFiles.append('English.lproj')

py2app_options = dict(
    plist = infoPlist,
    resources = '%s/resources' % root, 
    iconfile = '%s/platform/osx/Democracy.icns' % root,
    packages = ['dl_daemon']
)

setup(
    app = ['Democracy.py'],
    data_files = resourceFiles,
    options = dict(py2app = py2app_options),
    ext_modules = [
        Extension("idletime",["%s/platform/osx/idletime.c" % root]),
        Extension("database",["%s/portable/database.pyx" % root]),
        Extension("fasttypes",["%s/portable/fasttypes.cpp" % root],
                  extra_objects=[boostLib],
                  include_dirs=[boostIncludeDir])
        ],
    cmdclass = dict(build_ext = build_ext)
)
