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

def make_simple_get_set(attribute_name, change_needs_save=True):
    """Creates a simple DDBObject getter and setter for an attribute.

    This exists because for many DDBOBject attributes we have methods
    like the following::

        def get_foo(self):
            self.confirm_db_thread()
            return self.foo

        def set_foo(self, new_foo):
            self.confirm_db_thread()
            self.foo = new_foo
            self.signal_change()
    """
    def getter(self):
        self.confirm_db_thread()
        return getattr(self, attribute_name)

    def setter(self, new_value):
        self.confirm_db_thread()
        setattr(self, attribute_name, new_value)
        self.signal_change(needs_save=change_needs_save)

    return getter, setter
