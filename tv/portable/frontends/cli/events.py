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

import threading
import Queue

from miro import signals
from miro.frontends.cli.util import print_box

class EventHandler:
    def __init__(self):
        self.startup_failure = None
        self.startup_event = threading.Event()
        self.dialog_queue = Queue.Queue()

    def connect_to_signals(self):
        signals.system.connect('error', self.handleError)
        signals.system.connect('download-complete', self.handleDownloadComplete)
        signals.system.connect('startup-success', self.handleStartupSuccess)
        signals.system.connect('startup-failure', self.handleStartupFailure)
        signals.system.connect('new-dialog', self.handleDialog)
        signals.system.connect('shutdown', self.onBackendShutdown)

    def handleDialog(self, obj, dialog):
        self.dialog_queue.put(dialog)

    def handleStartupFailure(self, obj, summary, description):
        self.startup_failure = (summary, description)
        self.startup_event.set()

    def handleStartupSuccess(self, obj):
        self.startup_event.set()

    def handleDownloadComplete(self, obj, item):
        print_box('Download Complete: %s' % item)

    def handleError(self, obj, report):
        print_box('ERROR')
        print
        print report
        print

    def onBackendShutdown(self, obj):
        print
        print 'Shutting down...'

