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

"""
Contains the search box 
(the widget on the bottom of the left side with the video search field).
"""

from miro import app
from miro.frontends.widgets import style
from miro.frontends.widgets import widgetutil
from miro.plat.frontends.widgets import widgetset

class SearchBox(style.LowerBox):
    
    def __init__(self):
        style.LowerBox.__init__(self)
        self.search_field = widgetset.VideoSearchTextEntry()
        self.search_field.connect('validate', self.on_search)
        self.add(widgetutil.align_middle(self.search_field, 0, 0, 16, 16))

    def on_search(self, obj):
        app.search_manager.set_search_info(obj.selected_engine().name, obj.get_text())
        app.tab_list_manager.select_search()
        app.search_manager.perform_search()
