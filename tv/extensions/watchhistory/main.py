# Miro - an RSS based video player application
# Copyright (C) 2010, 2011
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

import logging
import os
import time
import csv

from miro import app
from miro import api

my_logger = logging.getLogger('watchhistory')

class WatchHistory():
    def __init__(self):
        self.csv_writer = None
        self.item_info = None
        api.signals.system.connect(
            'startup-success', self.handle_startup_success)

    def handle_startup_success(self, obj):
        my_logger.info("startup")
        # open log file
        logfile = os.path.join(api.get_support_directory(), "watched.csv")
        fp = open(logfile, "ab")
        self.csv_writer = csv.writer(fp)

        # connect to will-play
        app.playback_manager.connect('selecting-file', self.handle_select_file)
        app.playback_manager.connect('will-play', self.handle_will_play)

    def handle_select_file(self, obj, item_info):
        self.item_info = item_info

    def handle_will_play(self, obj, duration):
        if self.csv_writer and self.item_info:
            row = [
                time.ctime(),
                self.item_info.name,

                self.item_info.duration]
            self.csv_writer.writerow(row)
            # we wipe out self.item_info because will-play gets called
            # whenver someone starts watching an item (which we want
            # to log), but also whenever someone pauses and plays an
            # item (which we don't want to log)
            self.item_info = None
