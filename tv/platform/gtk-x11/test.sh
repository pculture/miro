#!/bin/sh
PYTHON=`which python2.4`
PREFIX=/usr
export DEMOCRACY_SHARE_ROOT=dist/$PREFIX/share/
export DEMOCRACY_RESOURCE_ROOT=dist/usr/share/democracy/resources/
$PYTHON setup.py install --root=./dist --prefix=$PREFIX && PYTHONPATH=dist/$PREFIX/lib/python2.4/site-packages/ $PYTHON dist/$PREFIX/bin/democracyplayer "$@"
