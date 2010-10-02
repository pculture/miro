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

"""miro.extensionmanager -- Extension manager that loads and manages
extensions.
"""

import traceback
import logging
import os
import sys
import ConfigParser
import glob
from miro import config
from miro import prefs

class Extension:
    def __init__(self):
        self.loadpriority = 50
        self.name = "Unknown"
        self.version = "0.0"
        self.ext_module = None

    def __repr__(self):
        return "%s (%s)" % (self.name, self.version)

def get_extensions(ext_dir):
    """Finds all ``.miroext`` files in extension directories.  Pulls
    the following information from the ``.miroext`` files:

    * main.name (string)
    * main.version (string)
    * extension.module (string)
    * extension.loadpriority (int)
    """
    if not os.path.isdir(ext_dir):
        # skip directories that don't exist
        return []

    # go through all the extension directories and get a listing of
    # files.  we're looking for files ending with .miroext
    extensions = []
    files = os.listdir(ext_dir)
    files = [os.path.join(ext_dir, m) for m in files
             if m.endswith(".miroext")]

    for f in files:
        if not os.path.isfile(f):
            logging.debug("%s is not a file; skipping", f)
            continue

        cf = ConfigParser.RawConfigParser()
        try:
            cf.read(f)
            e = Extension()
            e.loadpriority = cf.getint("extension", "loadpriority")
            e.name = cf.get("main", "name")
            e.version = cf.get("main", "version")
            e.ext_module = cf.get("extension", "module")
            
            extensions.append(e)
        except (ConfigParser.NoSectionError, 
                ConfigParser.NoOptionError, 
                ConfigParser.ParsingError), err:
            logging.warning("Extension file %s is malformed.\n%s", 
                            f, traceback.format_exc())

    return extensions

class ExtensionManager(object):
    def __init__(self, ext_dirs):
        self.ext_dirs = ext_dirs

    def load_extensions(self):
        extensions = []
        for d in self.ext_dirs:
            try:
                d = d % {
                    "supportdir": config.get(prefs.SUPPORT_DIRECTORY)
                    }
            except KeyError:
                logging.exception("bad extension directory '%s'", d)
                continue

            logging.info("Loading extensions in %s", d)
            exts = get_extensions(d)
            if exts:
                sys.path.insert(0, d)
                extensions.extend(exts)

        print sys.path

        # this sorts all of the extensions collected by load priority
        extensions.sort(key=lambda ext: ext.loadpriority)

        for mem in extensions:
            logging.info("extension manager: loading: %r", mem)
            try:
                __import__(mem.ext_module)
            except ImportError, ie:
                logging.exception("Extension %r failed to import", mem)
                continue

            try:
                initialize = getattr(sys.modules[mem.ext_module], "initialize")
                initialize()
            except StandardError, e:
                logging.exception("Extension %r failed to initialize", mem)
