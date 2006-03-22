#!/bin/sh
PYTHON=`which python2.4`

$PYTHON distutils/setup.py install --root=./dist && PYTHONPATH=dist/usr/lib/python2.4/site-packages/ $PYTHON dist/usr/bin/democracyplayer
