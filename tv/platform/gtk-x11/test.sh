#!/bin/sh
PYTHON=`which python2.4`

$PYTHON setup.py install --prefix=./dist && PYTHONPATH=./dist/lib/python2.4/site-packages $PYTHON dist/bin/democracyplayer.py
