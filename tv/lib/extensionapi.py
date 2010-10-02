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

"""miro.extensionapi -- Extension manager that loads and manages
extensions and the API for extensions.
"""

import traceback
import logging
import os
import sys
import ConfigParser
import glob

def get_extensions(extension_directory):
    """Finds all ``.miroext`` files in extension directories.  Pulls
    the following information from the ``.miro-extension`` files:

    * main.name (string)
    * main.version (string)
    * extension.module (string)
    * extension.loadpriority (int)
    """
    # go through all the extension directories and get a listing of
    # files.  we're looking for files ending with .miroext
    extensions = []
    dirs = [os.path.join(extension_directory, m) 
            for m in os.listdir(extension_directory)]
    for d in dirs:
        if not os.path.isdir(d):
            continue

        for mem in glob.glob("%s/*.miroext"):
            cf = ConfigParser.RawConfigParser()
            try:
                fn = os.path.join(d, mem)
                cf.read(fn)
                extpri = cf.getint("extension", "loadpriority")
                name = cf.get("main", "name")
                version = cf.get("main", "version")
                extname = "%s %s" % (name, version)
                extmod = cf.get("extension", "module")

                extensions.append((extpri, extname, extmod))
            except (ConfigParser.NoSectionError, 
                    ConfigParser.NoOptionError, 
                    ConfigParser.ParsingError), err:
                logging.warning("Extension file %s is malformed.\n%s", 
                                fn, traceback.format_exc())

    return extensions

class ExtensionManager:
    def __init__(self, extension_directories):
        self.extension_directories = extension_directories

    def load_extensions(self):
        extensions = []
        for d in self.extension_directories:
            logging.info("Loading extensions in %s", d)
            exts = get_extensions(d)
            if exts:
                sys.path.append(d)
                extensions.extend(exts)

        # this sorts the extensions by load priority
        extensions.sort()

        for mem in extensions:
            logging.debug("** loading extension %s", mem[1])
            try:
                __import__(mem[2])
            except ImportError, ie:
                logging.error("Extension %s failed to import\n%s", 
                              mem[1], traceback.format_exc())
                continue

            try:
                initialize = getattr(sys.modules[mem[2]], "initialize")
                initialize()
            except StandardException, e:
                logging.error("Extension %s failed to initialize\n%s", 
                              mem[1], traceback.format_exc())
