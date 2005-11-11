#!/bin/sh
PYTHON=`which python2.4`

if ! [ -a $PYTHON ] ; then
    PYTHON=`which python`
fi

$PYTHON setup.py install --prefix=./dist && PYTHONPATH=./dist/lib/python2.4/site-packages $PYTHON DTV.py