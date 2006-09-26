#!/usr/bin/env python

# Written by Bram Cohen
# see LICENSE.txt for license information

from distutils.core import setup
import py2exe

setup(windows=[{'script': 'btdownloadgui.py', "icon_resources": [(1, "bittorrent.ico")]}])
