#!/bin/sh
PYTHON=`which python2.4`

$PYTHON distutils/setup.py install --root=./dist && PYTHONPATH=./dist/lib/python2.4/site-packages $PYTHON dist/usr/bin/democracyplayer
