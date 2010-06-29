#!/bin/bash

mkdir requirements
cd requirements

echo "Instructions for installing" > README.txt
echo "===========================" >> README.txt
echo "" >> README.txt
echo "Instructions are at:" >> README.txt
echo "https://develop.participatoryculture.org/trac/democracy/wiki/WindowsBuildDocs" >> README.txt


echo "Fetching Python 2.6.5"
wget "http://python.org/ftp/python/2.6.5/python-2.6.5.msi"

echo "Fetching Py2exe 0.6.9"
wget "http://downloads.sourceforge.net/project/py2exe/py2exe/0.6.9/py2exe-0.6.9.win32-py2.6.exe?use_mirror=superb-sea2"

echo "Fetching Pyrex 0.9.9"
wget "http://www.cosc.canterbury.ac.nz/greg.ewing/python/Pyrex/Pyrex-0.9.9.tar.gz"

echo "Fetching NullSoft Installer 2.46"
wget "http://downloads.sourceforge.net/project/nsis/NSIS%202/2.46/nsis-2.46-setup.exe?use_mirror=softlayer"

echo "Fetching PyGTK 2.16"
wget "http://ftp.gnome.org/pub/GNOME/binaries/win32/pygtk/2.16/pygtk-2.16.0.win32-py2.6.exe"

echo "Fetching PyGobject 2.20.0"
wget "http://ftp.acc.umu.se/pub/GNOME/binaries/win32/pygobject/2.20/pygobject-2.20.0.win32-py2.6.exe"

echo "Fetching PyCairo 1.8.6"
wget "http://ftp.acc.umu.se/pub/GNOME/binaries/win32/pycairo/1.8/pycairo-1.8.6.win32-py2.6.exe"

echo "Fetching PyCurl 7.19.0.win32-py2.6"
wget "http://www.lfd.uci.edu/~gohlke/pythonlibs/pycurl-ssl-7.19.0.win32-py2.6.exe"
