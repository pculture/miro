#!/bin/sh
/usr/bin/env python2.4 setup.py py2app -O2 --dist-dir . --force-update $@

echo Done.
