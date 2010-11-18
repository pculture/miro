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

"""app.py -- Stores singleton objects.

App.py is a respository for high-level singleton objects.  Most of these
objects get set in startup.py, but some get set in frontend code as well.
"""

# handles high-level control of Miro
controller = None

# list of active renderers
renderers = []

# database object
db = None

# stores ItemInfo objects so we can quickly fetch them
item_info_cache = None

# command line arguments for thumbnailer (linux)
movie_data_program_info = None

# configuration data
config = None

# low-level parser for the "app.config" file
configfile = None

# manages the known devices
device_manager = None

# platform-specific device tracker
device_tracker = None

# signal emiters for when config data changes
backend_config_watcher = None
frontend_config_watcher = None
downloader_config_watcher = None

# debugmode adds a bunch of computation that's useful for development
# and debugging.  initalized to None; set to True/False depending on
# mode
debugmode = None

# widget frontend adds these
# --------------------------

# application object
widgetapp = None

# handles the right-hand display
display_manager = None

# handles the tab display
tab_list_manager = None

# manages ItemListControllers
item_list_controller_manager = None

# manages search state
search_manager = None

# remembers inline search terms
inline_search_memory = None

# tracks channel/item updates from the backend
info_updater = None

# manages the menu system
menu_manager = None

# manages playback
playback_manager = None

# manages watched folders
watched_folder_manager = None

# keeps track of frontend states
frontend_states_memory = None

# gtk/windows video renderer
video_renderer = None

# gtk/windows audio renderer
audio_renderer = None

# gtk/windows item type sniffer
get_item_type = None


# cli frontend adds these
# -----------------------

# event handler
cli_events = None
