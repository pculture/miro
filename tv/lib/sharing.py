# Miro - an RSS based video player application
# Copyright (C) 2010 Participatory Culture Foundation
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
import threading

from miro import app
from miro import config
from miro import eventloop
from miro import prefs

import libdaap

class NullBackend(object):
    def get_files(self):
        return []

class SharingManager(object):
    def __init__(self):
        self.sharing = False
        self.discoverable = False
        self.config_watcher = config.ConfigWatcher(
            lambda func, *args: eventloop.add_idle(func, 'config watcher',
                 args=args))
        self.callback_handle = self.config_watcher.connect('changed',
                               self.on_config_changed)
        # Enable sharing if necessary.
        self.twiddle_sharing()

    def on_config_changed(self, obj, key, value):
        # We actually know what's changed but it's so simple let's not bother.
        self.twiddle_sharing()

    def twiddle_sharing(self):
        sharing = app.config.get(prefs.SHARE_MEDIA)
        discoverable = app.config.get(prefs.SHARE_DISCOVERABLE)

        if sharing != self.sharing:
            if sharing:
                self.enable_sharing()
            else:
                self.disable_discover()
                self.disable_sharing()

        # Short-circuit: if we have just disabled the share, then we don't
        # need to check the discoverable bits since it is not relevant, and
        # would already have been disabled anyway.
        if not self.sharing:
            return

        if discoverable != self.discoverable:
            if discoverable:
                self.enable_discover()
            else:
                self.disable_discover()

    def enable_discover(self):
        name = app.config.get(prefs.SHARE_NAME)
        self.mdns_ref = libdaap.install_mdns(name)
        self.discoverable = True

    def disable_discover(self):
        self.discoverable = False
        libdaap.uninstall_mdns(self.mdns_ref)
        del self.mdns_ref

    def server_thread(self):
        name = app.config.get(prefs.SHARE_NAME)
        backend = NullBackend()
        self.server = libdaap.make_daap_server(backend, name=name)
        libdaap.runloop(self.server)

    def enable_sharing(self):
        self.thread = threading.Thread(target=self.server_thread,
                                       name='DAAP Server Thread')
        self.thread.start()
        self.sharing = True

    def disable_sharing(self):
        self.sharing = False
        self.server.shutdown()
        self.thread.join()
        del self.thread
        del self.server

