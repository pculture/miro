#!/bin/bash
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


OS_VERSION=$(uname -r | cut -c 1)

if [ $OS_VERSION == "9" ]; then
    SANDBOX_ROOT=$(pushd ../../../sandbox >/dev/null; pwd; popd >/dev/null)
    PYTHON=$SANDBOX_ROOT/Library/Frameworks/Python.framework/Versions/2.5/bin/python2.5
else
    PYTHON_VERSION=2.4
    PYTHON_ROOT=/Library/Frameworks/Python.framework/Versions/$PYTHON_VERSION
    PYTHON=$PYTHON_ROOT/bin/python$PYTHON_VERSION
fi

TMP_SCRIPT=`mktemp patch_objc_module.XXXXXXXX`

cat <<EOF >$TMP_SCRIPT
import os
import objc

objc_module_path = os.path.dirname(objc.__file__)
dyld_py_path = os.path.join(objc_module_path, '_dyld.py')

if os.path.exists(dyld_py_path):
    patched_dyld_py_path = dyld_py_path + ".patched"
    command = 'sed "s/expanduser(u\\\\"\\\\(.*\\\\)\\\\")/expanduser(\\\\"\\\1\\\\").decode(sys.getfilesystemencoding())/" %s > %s' % (dyld_py_path, patched_dyld_py_path)

    print command
    os.system(command)

    os.remove(dyld_py_path)
    os.rename(patched_dyld_py_path, dyld_py_path)

    dyld_pyc_path = os.path.join(objc_module_path, '_dyld.pyc')
    if os.path.exists(dyld_pyc_path):
        os.remove(dyld_pyc_path)
else:
    print "ERROR: could not find the pyobc-core _dyld module to patch."
EOF

$PYTHON $TMP_SCRIPT
rm $TMP_SCRIPT

echo Done.
