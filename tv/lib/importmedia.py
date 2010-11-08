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

"""``miro.importmedia`` -- functions for importing from other music jukeboxes.
"""

import os
import urllib

import xml.sax
import xml.sax.handler
import xml.sax.saxutils

ITUNES_XML_FILE = "iTunes Music Library.xml"

class iTunesMusicLibraryContentHandler(xml.sax.handler.ContentHandler):
    """A very specific content handler for handling the iTunes music 
       library file.

       We only care about snarfing the music path then we bail out.
       This is done by getting the value <key>Music Folder</key>
       which will appear as <string>...</string>.
    """

    MUSIC_FOLDER_KEYNAME = "Music Folder"

    def __init__(self):
        self.element_name = None
        self.in_music_folder_key = False
        self.music_path = None

    def startElement(self, name, attrs):
        self.element_name = name

    def characters(self, content):
        if self.element_name == 'key' and content == self.MUSIC_FOLDER_KEYNAME:
            self.in_music_folder_key = True
            return
        if self.in_music_folder_key and self.element_name == 'string':
            # Must convert to string content - otherwise we get into unicode
            # troubles when we unquote the URI escapes.
            self.music_path = str(content)
            self.in_music_folder_key = False
            return
        # Wasn't followed with a <string> as expected...
        self.in_music_folder_key = False

def file_path_xlat(path):
    """Convert iTunes path to what we can handle."""
    try:
        file_url_bits = "file://localhost"
        if not path.startswith(file_url_bits):
            return None
        path = urllib.url2pathname(path[len(file_url_bits):])
        return path
    # bad path catchall
    except StandardError:
        return None

def import_itunes_path(path):
    """Look for a specified iTunes Music Library.xml file from the specified
       path.  Returns the path of the music library as specified in the
       iTunes settings or None if it cannot find the xml file, or does not
       contain the path for some reason."""
    music_path = None
    try:
        parser = xml.sax.make_parser()
        handler = iTunesMusicLibraryContentHandler()
        parser.setContentHandler(handler)
        # Tell xml.sax that we don't want to parse external entities, as it
        # will stall when no network is installed.
        parser.setFeature(xml.sax.handler.feature_external_ges, False)
        parser.setFeature(xml.sax.handler.feature_external_pes, False)
        parser.parse(os.path.join(path, ITUNES_XML_FILE))
        music_path = file_path_xlat(handler.music_path)
        return music_path
    except IOError:
        pass
    return music_path

