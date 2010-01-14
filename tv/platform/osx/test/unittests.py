# Miro - an RSS based video player application
# Copyright (C) 2005-2010 Participatory Culture Foundation
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

import os
import sys
import unittest

# Add extra stuff to the search path that will let us find our source
# directories when we have built a development bundle with py2app -A.
platform = 'osx'
root = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])),
                    '..', '..', '..')
root = os.path.normpath(root)
sys.path[0:0]=['%s/platform/%s' % (root, platform), '%s/platform' % root, '%s/portable' % root, '%s/portable/test' % root, '%s/platform/%s/test' % (root, platform)]

import fasttypes
from miro.databasetest import *
from miro.templatetest import *
from fasttypestest import *

unittest.main()

