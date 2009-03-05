#!/bin/bash

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
