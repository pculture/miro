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

"""app.py -- Stores singleton objects.

App.py is a respository for high-level singleton objects.  Most of these
objects get set in startup.py, but some get set in frontend code as well.

Here is the list of objects that app currently stores:

controller -- Handle High-level control of Miro
selection -- Handles selected objects
renderers -- List of active renderers
db -- Database object

The widget frontend adds:

widgetapp -- Application object
display_manger -- Handles the right-hand display.
tab_list_manager -- Handles the tab lists and selection.
item_list_controller_manager -- Manages ItemListControllers
renderer -- Video rendering object (or None if the platform code can't
        initialize a suitable renderer)
search_manager -- Manages the search state
inline_search_memory -- Remembers inline search terms
"""

renderers = []
# NOTE: we could set controller, db, etc. to None here, but it seems better
# not do.  This way if we call "from miro.app import controller" before the
# controller singleton is created, then we will immediately get an error.
