# Miro - an RSS based video player application
# Copyright (C) 2005-2007 Participatory Culture Foundation
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

import os
import sys
import setup as core_setup
from distutils.core import setup
import py2exe

# The name of this platform.
platform = 'windows-xul'

# Find the top of the source tree and set search path
root = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), '..', '..')
root = os.path.normpath(root)
sys.path.insert(0, os.path.join(root, 'portable'))

from miro import util

templateVars = util.readSimpleConfigFile(os.path.join(root, 'resources', 'app.config'))

script_path = os.path.join(os.path.dirname(__file__), 'moviedata_util.py')

setup(
    console=[{"dest_base":("%s_MovieData"%templateVars['shortAppName']),"script":script_path}],
    zipfile=None,
)
