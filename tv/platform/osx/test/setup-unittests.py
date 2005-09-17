from distutils.core import setup
from distutils.extension import Extension
import py2app
import os
import sys
import shutil
from Pyrex.Distutils import build_ext

# The name of this platform.
platform = 'osx'

# Find the top of the source tree and set search path
root = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])),
                    '..', '..', '..')

# GCC3.3 on OS X 10.3.9 doesn't like ".."'s in the path
root = os.path.normpath(root)
sys.path[0:0]=['%s/platform/%s' % (root, platform), '%s/platform' % root, '%s/portable' % root,'%s/platform/%s/test' % (root, platform), '%s/portable/test' % root]

# Only now may we import things from our own tree
import vlchelper.info

# Get a list of additional resource files to include
resourceFiles = ['../Resources/%s' % x for x in os.listdir('../Resources')]
resourceFiles.append('English.lproj')

py2app_options = dict(
    resources='%s/resources' % root, 
    plist='../Info.plist',
    iconfile='%s/platform/%s/check.icns' % (root, platform),
)

setup(
    app=['unittests.py'],
    data_files= resourceFiles,
# NEEDS XXXX
#    ext_modules = [vlchelper.info.getExtension(root)],
    options=dict(
        py2app=py2app_options,
    ),
    ext_modules=[
        #Add extra_compile_args to change the compile options
        Extension("database",["%s/portable/database.pyx" % root]),
        Extension("template",["%s/portable/template.pyx" % root]),
        Extension("fasttypes",["%s/portable/fasttypes.cpp" % root],
                  extra_objects=["/usr/local/lib/libboost_python-1_33.a"],
                  include_dirs=["/usr/local/include/boost-1_33/"])
        ],
    cmdclass = {'build_ext': build_ext}
)

# NEEDS: Hack: Copy VLC libraries into bundle so they are at the place
# that the OS X VLC build process told the dynamic linker told them
# they would be. There should be a cleaner way to do
# this. Furthermore, although the rule was taken from VLC's makefile,
# it probably copies more libraries than we actually need.
#
# In an ideal world, VLC would put the actual paths on the local
# machine into the objects, and py2app would rewrite those paths to be
# bundle relative during its normal dependency scan.
#
# Also copy modules into the bundle. This is a little less than ideal
# as well.
#
# IMPORTANT: Note well that we don't *remove* any files left over from
# the previous build that disappeared in this one. So, before building
# a distribution bundle, you should be sure to 'clean'.

VLC_LIBRARY_SUBDIR = 'extras/contrib/vlc-lib'
BUNDLE_LIB_DIRECTORY = 'Contents/MacOS/lib'
BUNDLE_MODULE_DIRECTORY = 'Contents/MacOS'

if 'py2app' in sys.argv and False: ## NEEDS XXXX
    # Create symlinks or copy files?
    alias = '-A' in sys.argv
    
    # NEEDS: We guess where the bundle was built. Horrible.
    bundleRoot = 'dist/DTV.app'
    for i in range(0,len(sys.argv)-1):
        if sys.argv[i] == '--dist-dir':
            bundleRoot = '%s/DTV.app' % sys.argv[i+1]

    # list of (sourcePath, destinationPath) tuples of files to copy or link
    manifest = []

    # Make list of libraries to copy, and compute their VLC-mangled names.
    vlcLibDir = "%s/%s" % (vlchelper.info.getVLCRoot(root), VLC_LIBRARY_SUBDIR)
    bundleLibDir = "%s/%s" % (bundleRoot, BUNDLE_LIB_DIRECTORY)
    if not os.access(bundleLibDir, os.F_OK):
        os.makedirs(bundleLibDir)
    for file in os.listdir(vlcLibDir):
        src = os.path.abspath('%s/%s' % (vlcLibDir, file))
        dest = '%s/vlc_%s' % (bundleLibDir, os.path.basename(file))
        manifest.append((src, dest))

    # Find the modules to copy.
    bundleModuleDir = "%s/%s" % (bundleRoot, BUNDLE_MODULE_DIRECTORY)
    for module in vlchelper.info.getModuleList(root):
        src = os.path.abspath('%s/%s.dylib' % (vlchelper.info.getVLCRoot(root), module))
        dest = '%s/%s.dylib' % (bundleModuleDir, module)
        manifest.append((src, dest))

    # Copy or link the files.
    for (src, dest) in manifest:
        # Make sure the destination directory exists.
        if not os.access(os.path.dirname(dest), os.F_OK):
            os.makedirs(os.path.dirname(dest))

        # Delete the file if it exists.
        try:
            os.unlink(dest)
        except OSError:
            pass

        # Copy or link the file.
        if alias:
            os.symlink(src, dest)
        else:
            # NEEDS: frob permissions?
            shutil.copy(src, dest)
