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

"""fontinfo.py.  Get info about system fonts."""

import ctypes
import os
import logging
from miro.plat import specialfolders

class FT_FaceRec(ctypes.Structure):
    _fields_ = [
            ('num_faces', ctypes.c_long),
            ('face_index', ctypes.c_long),
            ('face_flags', ctypes.c_long),
            ('style_flags', ctypes.c_long),
            ('num_glyphs', ctypes.c_long),
            ('family_name', ctypes.c_char_p),
            ('style_name', ctypes.c_char_p),

            # There's many more fields, but this is all we need
    ]
FT_FACE = ctypes.POINTER(FT_FaceRec)

freetype = library = None
_font_cache = {} # maps path -> font name

def init():
    global freetype
    global library

    freetype = ctypes.cdll.LoadLibrary("freetype6")
    library = ctypes.c_void_p()
    rv = freetype.FT_Init_FreeType(ctypes.byref(library))
    if rv != 0:
        logging.warn("Couldn't load freetype: %s", rv)

def check_init():
    if freetype is None:
        raise AssertionError("init() not called")

def _get_font_info(path):
    face = FT_FACE()
    rv = freetype.FT_New_Face(library, path, 0, ctypes.byref(face))
    if rv == 0:
        name = "%s %s" % (face.contents.family_name, face.contents.style_name)
        freetype.FT_Done_Face(face)
        return name
    else:
        raise ValueError("Couldn't load freetype font: %s (error: %s)" % (path,
                rv))

def get_font_info(path):
    global _font_cache

    check_init()
    try:
        return _font_cache[path]
    except KeyError:
        _font_cache[path] = _get_font_info(path)
        return _font_cache[path]

def get_all_font_info():
    check_init()
    font_dir = specialfolders.get_special_folder("Fonts")
    infos = {}
    for filename in os.listdir(font_dir):
        if not (filename.lower().endswith('.ttf') or 
                filename.lower().endswith('.ttc')):
            continue
        path = os.path.join(font_dir, filename)
        try:
            name = get_font_info(path)
        except ValueError, e:
            logging.info(e)
            continue
        if name not in infos:
            infos[name] = path
    names = infos.keys()
    names.sort()
    return [(name, infos[name]) for name in names]
