#!/bin/sh

bash setup_sandbox.sh

SANDBOX_ROOT=../../../sandbox
PYTHON_VERSION=2.4
PYTHON_ROOT=$SANDBOX_ROOT/Library/Frameworks/Python.framework/Versions/$PYTHON_VERSION
PYTHON=$PYTHON_ROOT/bin/python$PYTHON_VERSION

$PYTHON setup.py py2app --dist-dir . -A $@ && Miro.app/Contents/MacOS/Miro
