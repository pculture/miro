#!/bin/sh

# Miro - an RSS based video player application
# Copyright (C) 2005-2008 Participatory Culture Foundation
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
#
# In addition, as a special exception, the copyright holders give
# permission to link the code of portions of this program with the OpenSSL
# library.
#
# You must obey the GNU General Public License in all respects for all of
# the code used other than OpenSSL. If you modify file(s) with this
# exception, you may extend this exception to your version of the file(s),
# but you are not obligated to do so. If you do not wish to do so, delete
# this exception statement from your version. If you delete this exception
# statement from all source files in the program, then also delete it here.

PYTHON=`which python`
PYTHON_VERSION=`python -c 'import sys; info=sys.version_info; print "%s.%s" % (info[0], info[1])'`
PREFIX=/usr
export MIRO_SHARE_ROOT=dist/$PREFIX/share/
export MIRO_RESOURCE_ROOT=dist/$PREFIX/share/miro/resources/

# NOTE: The first part of this LD_LIBRARY_PATH _must_ match what setup.py
# picks out and puts in dist/usr/bin/miro .  If you're having problems
# running miro with ./run.sh, then make sure you've got the LD_LIBRARY_PATH
# portion matching.
#
# This line probably doesn't need to be here since we call "miro" which sets
# the LD_LIBRARY_PATH correctly anyhow.
#
# export LD_LIBRARY_PATH=/usr/lib/firefox${LD_LIBRARY_PATH:+:}${LD_LIBRARY_PATH}

$PYTHON setup.py install --root=./dist --prefix=$PREFIX && PATH=dist/$PREFIX/bin:$PATH PYTHONPATH=dist/$PREFIX/lib/python$PYTHON_VERSION/site-packages/ dist/$PREFIX/bin/miro "$@"
