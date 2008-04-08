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

import os
import sys

from glob import glob

if len(sys.argv) == 2:
    nib = "Resources/English.lproj/%s.nib" % sys.argv[1]
    if not os.path.exists(nib):
        print "Unknown nib file: %s" % nib
        sys.exit()
    else:
        nibs = [nib]
else:
    nibs = glob("Resources/English.lproj/*.nib")

for lproj in glob("Resources/*.lproj"):
    lang = os.path.basename(lproj)[:-6]
    if lang == "English":
        continue
    if os.path.exists ("Resources/%s.lproj/translated.strings" % (lang)):
        print "working on %s ..." % lang
        for nib in nibs:
            name = os.path.basename (nib)[:-4]
            exists = os.path.exists ("Resources/%s.lproj/%s.nib" % (lang, name))
            if exists:
                nib = "Resources/%s.lproj/temp.%s.nib" % (lang, name)
            else:
                nib = "Resources/%s.lproj/%s.nib" % (lang, name)
            os.system ("nibtool -8 Resources/English.lproj/%s.nib -d Resources/%s.lproj/translated.strings -W %s" % (name, lang, nib))
            if exists:
                os.system ("mv Resources/%s.lproj/temp.%s.nib/* Resources/%s.lproj/%s.nib/" % (lang, name, lang, name))
                os.system ("rmdir Resources/%s.lproj/temp.%s.nib" % (lang, name))
