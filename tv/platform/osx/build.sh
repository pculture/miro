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

$PYTHON setup.py py2app -O2 --dist-dir . --force-update "$@"

echo Done.
