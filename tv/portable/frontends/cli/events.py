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

import threading
import Queue

from miro import signals
from miro import messages
from miro.frontends.cli.util import print_box

class EventHandler:
    def __init__(self):
        self.startup_failure = None
        self.startup_event = threading.Event()
        self.dialog_queue = Queue.Queue()
        self.message_handler = CliMessageHandler(self.handle_startup_success, self.handle_startup_failure)

    def connect_to_signals(self):
        messages.FrontendMessage.install_handler(self.message_handler)

        signals.system.connect('error', self.handle_error)
        signals.system.connect('update-available', self.handle_update_available)
        signals.system.connect('new-dialog', self.handle_dialog)
        signals.system.connect('shutdown', self.on_backend_shutdown)

    def handle_update_available(self, obj, item):
        print "There is a Miro Update available!"

    def handle_dialog(self, obj, dialog):
        self.dialog_queue.put(dialog)

    def handle_startup_failure(self, summary, description):
        print "Startup failure."
        self.startup_failure = (summary, description)
        self.startup_event.set()

    def handle_startup_success(self):
        print "Startup success."
        self.startup_event.set()

    def handle_download_complete(self, obj, item):
        print_box('Download Complete: %s' % item)

    def handle_error(self, obj, report):
        print_box('ERROR')
        print
        print report
        print

    def on_backend_shutdown(self, obj):
        print
        print 'Shutting down...'

class CliMessageHandler(messages.MessageHandler):
    def __init__(self, startup_success, startup_failure):
        messages.MessageHandler.__init__(self)
        self.on_startup_success = startup_success
        self.on_startup_failure = startup_failure

    def call_handler(self, method, message):
        method(message)

    def handle_startup_failure(self, message):
        self.on_startup_failure(message.summary, message.description)

    def handle_startup_success(self, message):
        self.on_startup_success()
