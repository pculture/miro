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
)

setup(
    app=['unittests.py'],
    data_files= resourceFiles,
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
