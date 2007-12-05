#!/bin/sh

bash setup_sandbox.sh

SANDBOX_ROOT=../../../sandbox
PYTHON_VERSION=2.4
PYTHON_ROOT=$SANDBOX_ROOT/Library/Frameworks/Python.framework/Versions/$PYTHON_VERSION
PYTHON=$PYTHON_ROOT/bin/python$PYTHON_VERSION

$PYTHON setup.py py2app -O2 --dist-dir . --force-update $@

find Miro.app -name ".DS_Store" -exec rm {} \;
find Miro.app -name "info.nib" -exec rm {} \;
find Miro.app -name "classes.nib" -exec rm {} \;
find Miro.app -name "*.so" -exec strip -S {} \;

echo Done.
