# Miro - an RSS based video player application
# Copyright (C) 2010 Participatory Culture Foundation
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


"""The file object encapsulates data about the filename object.
"""

import logging
import os
import shutil

from miro.plat.utils import PlatformFilenameType

class FilenameType(PlatformFilenameType):
    """FilenameType: the file representation for a given platform.
    It defaults to local files but can be specified to be remote files by
    passing an appropriate url handler.

    It defaults to file for legacy support, a lot of places depend on this.

    Note to platform implementors: the PlatformFileType must be a string-type
    basetype, so either unicode or str.  Nothing else.

    NOTE: This is a transitional object.  You should NOT use it for anything
    other than DAAP at the moment.
    """
    base_type = PlatformFilenameType
    args = []

    def file_handler(self, path):
        return 'file://' + path

    handler = file_handler

    def set_handler(self, handler, args):
        self.handler = handler
        self.args = args

    def urlize(self):
        return self.handler(self, *self.args)
