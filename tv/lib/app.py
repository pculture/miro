# Miro - an RSS based video player application
# Copyright (C) 2005, 2006, 2007, 2008, 2009, 2010, 2011
# Participatory Culture Foundation
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

# donation manager singleton object
donate_manager = None

# database object
db = None

# BulkSQLManager for the main miro database
bulk_sql_manager = None

# DBInfo object for the main miro database
db_info = None

# configuration data
config = None

# low-level parser for the "app.config" file
configfile = None

# manages the known devices
device_manager = None

# SharingManager instance
sharing_manager = None

# SharingTracker instance
sharing_tracker = None

# platform-specific device tracker
device_tracker = None

# platform/frontend specific directory watcher
directory_watcher = None

# MetadataManager for local items
local_metadata_manager = None

# signal emiters for when config data changes
backend_config_watcher = None
frontend_config_watcher = None
downloader_config_watcher = None

# global state managers
download_state_manager = None
icon_cache_updater = None
movie_data_updater = None

# debugmode adds a bunch of computation that's useful for development
# and debugging.  initalized to None; set to True/False depending on
# mode
debugmode = None

#
# Frontend API class.  All the frontend should define a subclass of this and
# implement the methods.
#
class Frontend(object):
    def call_on_ui_thread(self, func, *args, **kwargs):
        """Call a function at a later time on the UI thread."""
        raise NotImplementedError()

    def run_choice_dialog(self, title, description, buttons):
        """Show the database error dialog and wait for a choice.

        This method should block until the choice is picked.  Depending on the
        frontend other events may still be processed or not.

        :returns: button that was choosen or None if the dialog was closed.
        """
        raise NotImplementedError()

    def quit(self):
        """Quit Miro."""
        raise NotImplementedError()

frontend = Frontend()

# name of the running frontend
frontend_name = None

# widget frontend adds these
# --------------------------

# application object
widgetapp = None

# ConnectionPoolTracker object -- Note: this object could be made thread-safe
# pretty easily, but right now it only should be used in the frontend thread.
connection_pools = None

# handles the right-hand display
display_manager = None

# handles the left-hand tabs
tabs = None

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

# manages stores
store_manager = None

# keeps track of frontend states
widget_state = None

# gtk/windows video renderer
video_renderer = None

# gtk/windows audio renderer
audio_renderer = None

# gtk/windows item type sniffer
get_item_type = None

# Tracks ItemLists that are in-use
item_list_pool = None

# cli frontend adds these
# -----------------------

# event handler
cli_events = None
