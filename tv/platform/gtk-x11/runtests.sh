#!/bin/sh
PYTHON=`which python2.4`
export DEMOCRACY_RESOURCE_ROOT=dist/usr/share/democracy/resources/
$PYTHON setup.py install --root=./dist && PYTHONPATH=dist/usr/lib/python2.4/site-packages/ $PYTHON dist/usr/bin/democracyplayer --unittest $*
