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

from miro.xhtmltools import urlencode
from miro.plat.utils import (unicode_to_filename, PlatformFilenameType)

# FilenameType is currently a transitional object and as such is incomplete.
# You should NOT use its urlize functionality for anything other than DAAP
# objects.  In particular, the file_handler() is not supposed to work well now.
#
# One problem in Miro is filename handling is a bit iffy at the moment, 
# transforming from string to unicode and then back maybe several times 
# is not good practice and error prone.  What we need is a file object
# which encapsulates all this information.
#
# Ground rules: all interactions with the filesystem should uninterpreted
# byte string (other than subject to OS/file system limitations).  This
# means 'str' type.
#
# For all internal manipulation, it should be in unicode.  So, the moment
# you read in something, display something or grab a new filename from the
# user it's unicode.  If you need to keep the filename around for writing
# later, you should make the unicode a copy, so you don't lose any info
# between conversions.
#
# When you write, if you only have a unicode copy or the file has been
# renamed in the meantime, use the unicode copy and convert back to string
# to interact with the filesystem.  If no file rename has occurred, use
# the original 'str'.
#
# That's how it should happen.  We'll get there...
# Interesting reading: http://docs.python.org/howto/unicode.html
# We kind of, sort of, but not really do what they describe there, which is
# where all this filename iffiness is coming from.
class FilenameType(PlatformFilenameType):
    """FilenameType: the file representation for a given platform.
    It defaults to local files but can be specified to be remote files by
    passing an appropriate url handler.

    It defaults to file for legacy support, a lot of places depend on this.

    Note to platform implementors: the PlatformFileType must be a string-type
    basetype, so either unicode or str.  Nothing else.

    NOTE: This is a transitional object.  You should NOT use its urlize()
    functionality other than for DAAP at the moment.
    """
    base_type = PlatformFilenameType
    def __new__(cls, s):
        return PlatformFilenameType.__new__(cls, s)

    def __init__(self, string):
        self.args = []
        self.handler = self.file_handler    # Default to file handler.

    def file_handler(self, path):
        return 'file://' + urlencode(path)

    def set_urlize_handler(self, handler, args):
        self.handler = handler
        self.args = args

    def urlize(self):
        return self.handler(self, *self.args)
