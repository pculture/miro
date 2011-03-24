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

"""gtkdirectorywatch -- GTK implementation of DirectoryWatcher."""

import os
import gio
import glib
import gtk

from miro import directorywatch
from miro import eventloop
from miro.plat.utils import utf8_to_filename

class GTKDirectoryWatcher(directorywatch.DirectoryWatcher):
    def startup(self, directory):
        self._monitors = {}
        # Note: we are in the event loop thread here use idle_add to move into
        # the frontend thread
        glib.idle_add(self._add_directory, gio.File(directory))

    def _add_directory(self, f):
        monitor = f.monitor_directory()
        monitor.connect('changed', self._on_directory_changed)
        self._monitors[f.get_path()] = monitor
        f.monitor_directory()
        glib.idle_add(self._add_subdirectories, f, priority=glib.PRIORITY_LOW)

    def _add_subdirectories(self, f):
        for child_info in f.enumerate_children('standard::*'):
            file_type = child_info.get_attribute_uint32('standard::type')
            if file_type == gio.FILE_TYPE_DIRECTORY:
                child = f.get_child(child_info.get_name())
                glib.idle_add(self._add_directory, child,
                        priority=glib.PRIORITY_LOW)

    def _on_directory_changed(self, monitor, file_, other, event):
        if event == gio.FILE_MONITOR_EVENT_CREATED:
            self._on_file_added(file_)
        elif event == gio.FILE_MONITOR_EVENT_DELETED:
            self._on_file_deleted(file_)

    def _on_file_added(self, f):
        info = f.query_info('standard::*')
        file_type = info.get_attribute_uint32('standard::type')
        if file_type == gio.FILE_TYPE_REGULAR:
            # use add_idle() to pass things over to the backend thread
            # FIXME: there should be a cleaner way to do this
            eventloop.add_idle(self.emit, "emit added signal",
                    args=("added", utf8_to_filename(f.get_path()),))
        elif file_type == gio.FILE_TYPE_DIRECTORY:
            self._add_directory(f)

    def _on_file_deleted(self, f):
        path = f.get_path()
        if path in self._monitors:
            # file is one of the things we were monitoring.  Looks like it's a
            # directory
            del self._monitors[path]
        else:
            # Assume that if we weren't monitoring it, it was a regular file.
            # This isn't always true, but it's not a big deal if we send a
            # delete event for a path that we don't have a FileItem for.

            # use add_idle() to pass things over to the backend thread
            # FIXME: there should be a cleaner way to do this
            eventloop.add_idle(self.emit, "emit deleted signal",
                    args=("deleted", utf8_to_filename(path)))
