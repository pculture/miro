#!/bin/bash

OS_VERSION=$(uname -r | cut -c 1)

if [ $OS_VERSION == "9" ]; then
    PYTHON=/usr/bin/python2.5
    SANDBOX_ROOT=$(pushd ../../../sandbox >/dev/null; pwd; popd >/dev/null)
    PYTHONPATH=$SANDBOX_ROOT/Library/Python/2.5/site-packages
    export PYTHONPATH
else
    PYTHON_VERSION=2.4
    PYTHON_ROOT=/Library/Frameworks/Python.framework/Versions/$PYTHON_VERSION
    PYTHON=$PYTHON_ROOT/bin/python$PYTHON_VERSION
fi

$PYTHON setup.py py2app --use-pythonpath --dist-dir . -A "$@" && Miro.app/Contents/MacOS/Miro
