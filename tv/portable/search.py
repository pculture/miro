# Miro - an RSS based video player application
# Copyright (C) 2005-2009 Participatory Culture Foundation
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

import re

QUOTEKILLER = re.compile(r'(?<!\\)"')
SLASHKILLER = re.compile(r'\\.')

SEARCHOBJECTS = {}

def match(searchString, comparisons):
    searchString = searchString.lower()
    comparisons = [c.lower() for c in comparisons]
    if not SEARCHOBJECTS.has_key(searchString):
        SEARCHOBJECTS[searchString] = BooleanSearch(searchString)
    return SEARCHOBJECTS[searchString].match(comparisons)

class BooleanSearch:
    def __init__ (self, s):
        self.string = s
        self.parse_string()
        self.rules = []

    def parse_string(self):
        inquote = False
        i = 0
        while i < len (self.string) and self.string[i] == ' ':
            i += 1
        laststart = i
        self.rules = []
        while (i < len(self.string)):
            i = laststart
            while (i < len(self.string)):
                if self.string[i] == '"':
                    inquote = not inquote
                if not inquote and self.string[i] == ' ':
                    break
                if self.string[i] == '\\':
                    i += 1
                i += 1
            if inquote:
                self.rules.append(self.process(self.string[laststart:]))
            else:
                self.rules.append(self.process(self.string[laststart:i]))
            while i < len (self.string) and self.string[i] == ' ':
                i += 1
            laststart = i

    def process(self, substring):
        positive = True
        if substring[0] == '-':
            substring = substring[1:]
            positive = False
        substring = QUOTEKILLER.sub("", substring)
        substring = SLASHKILLER.sub(lambda x: x.group(0)[1], substring)
        #print substring
        return [positive, substring]

    def match(self, comparisons):
        for rule in self.rules:
            matched = False
            for comparison in comparisons:
                if rule[1] in comparison:
                    matched = True
                    break
            if rule[0] != matched:
                return False
        return True

    def as_string(self):
        return self.string
