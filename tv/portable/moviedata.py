# Miro - an RSS based video player application
# Copyright (C) 2005-2007 Participatory Culture Foundation
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

from fasttypes import LinkedList
from eventloop import asIdle
from platformutils import FilenameType
import os.path
import app

RUNNING_MAX = 3

class MovieDataUpdater:
    def __init__ (self):
        self.vital = LinkedList()
        self.runningCount = 0
        self.inShutdown = False

    def requestUpdate (self, item):
        if self.inShutdown:
            return
        filename = item.getVideoFilename()
        if not filename or not os.path.isfile(filename):
            return
        if item.downloader and not item.downloader.isFinished():
            return
        if self.runningCount < RUNNING_MAX:
            self.update(item)
        else:
            self.vital.prepend(item)

    @asIdle
    def updateFinished (self, item, movie_data):
        if item.idExists():
            item.duration = movie_data["duration"]
            item.screenshot = movie_data["screenshot"]
            item.updating_movie_info = False
            item.signalChange()

        self.runningCount -= 1

        if self.inShutdown:
            return

        while self.runningCount < RUNNING_MAX and len (self.vital) > 0:
            next = self.vital.pop()
            self.update (next)

    def update (self, item):
        if item.updating_movie_info:
            return
        if hasattr(app.controller, 'videoDisplay'):
            item.updating_movie_info = True
            movie_data = {"duration": -1, "screenshot": FilenameType("")}
            self.runningCount += 1
            app.controller.videoDisplay.fillMovieData (item.getVideoFilename(), movie_data, lambda: self.updateFinished (item, movie_data))

    @asIdle
    def shutdown (self):
        self.inShutdown = True

movieDataUpdater = MovieDataUpdater()
