#!/bin/sh

# Miro - an RSS based video player application
# Copyright (C) 2005-2006 Participatory Culture Foundation
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

PYTHON=`which python`
GDB=`which gdb`
PYTHON_VERSION=`python -c 'import sys; info=sys.version_info; print "%s.%s" % (info[0], info[1])'`
PREFIX=/usr
export MIRO_SHARE_ROOT=dist/$PREFIX/share/
export MIRO_RESOURCE_ROOT=dist/$PREFIX/share/miro/resources/
export LD_LIBRARY_PATH=/usr/lib/debug:/usr/lib/firefox${LD_LIBRARY_PATH:+:}${LD_LIBRARY_PATH}

$PYTHON setup.py install --root=./dist --prefix=$PREFIX && PYTHONPATH=dist/$PREFIX/lib/python$PYTHON_VERSION/site-packages/ $GDB -ex 'set breakpoint pending on' -ex 'break gdk_x_error' -ex 'run' --args $PYTHON dist/$PREFIX/bin/miro.real --sync "$@"
