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

"""datastructures.py -- Datastructures used by Miro.
"""

class Fifo(object):
    """FIFO queue.

    Fast implentation of a first-in-first-out queue.

    Based off the code from Jeremy Fincher
    (http://code.activestate.com/recipes/68436/)
    """
    def __init__(self):
        self.back = []
        self.front = []
        self.frontpos = 0

    def enqueue(self, item):
        self.back.append(item)

    def dequeue(self):
        try:
            rv = self.front[self.frontpos]
        except IndexError:
            pass
        else:
            self.frontpos += 1
            return rv
        if self.back:
            self.front = self.back
            self.back = []
            self.frontpos = 1
            return self.front[0]
        else:
            raise ValueError("Queue Empty")

    def __len__(self):
        return len(self.front) - self.frontpos + len(self.back)
