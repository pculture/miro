# Miro - an RSS based video player application
# Copyright (C) 2005-2010 Participatory Culture Foundation
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
#
# In addition, as a special exception, the copyright holders give
# permission to link the code of portions of this program with the OpenSSL
# library.
#
# You must obey the GNU General Public License in all respects for all of
# the code used other than OpenSSL. If you modify file(s) with this
# exception, you may extend this exception to your version of the file(s),
# but you are not obligated to do so. If you do not wish to do so, delete
# this exception statement from your version. If you delete this exception
# statement from all source files in the program, then also delete it here.

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
