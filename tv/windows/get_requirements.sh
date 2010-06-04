#!/bin/bash

mkdir requirements
cd requirements

echo "Instructions for installing" > README
echo "===========================" >> README
echo "" >> README
echo "Instructions are at:" >> README
echo "https://develop.participatoryculture.org/trac/democracy/wiki/WindowsBuildDocs" >> README

echo "Fetching Python 2.5"
wget "http://www.python.org/ftp/python/2.5/python-2.5.msi"

echo "Fetching sqlitedll-3_5_2.zip"
wget "http://www.sqlite.org/sqlitedll-3_5_2.zip"

echo "Fetching Psyco r70200"
svn co -r70200 http://codespeak.net/svn/psyco/dist/ psyco

echo "Fetching Py2exe 0.6.9"
wget "http://internap.dl.sourceforge.net/sourceforge/py2exe/py2exe-0.6.9.win32-py2.5.exe"

echo "Fetching NullSoft Installer 2.46"
wget "http://downloads.sourceforge.net/project/nsis/NSIS%202/2.46/nsis-2.46-setup.exe?use_mirror=softlayer"

echo "Fetching PyGTK 2.12.1"
wget "http://ftp.gnome.org/pub/GNOME/binaries/win32/pygtk/2.12/pygtk-2.12.1-3.win32-py2.5.exe"

echo "Fetching PyGobject 2.14.2"
wget "http://ftp.gnome.org/pub/GNOME/binaries/win32/pygobject/2.14/pygobject-2.14.2-2.win32-py2.5.exe"

echo "PyCairo 1.4.12"
wget "http://ftp.gnome.org/pub/GNOME/binaries/win32/pycairo/1.4/pycairo-1.4.12-2.win32-py2.5.exe"
