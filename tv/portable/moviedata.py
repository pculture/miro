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

from eventloop import asIdle
from platformutils import FilenameType
import os.path
import re
import subprocess
import time
import traceback
import threading
import Queue

import app
import eventloop
import logging
import config
import prefs
import util

durationRE = re.compile("Miro-Movie-Data-Length: (\d+)")
thumbnailRE = re.compile("Miro-Movie-Data-Thumbnail: Success")

class MovieDataUpdater:
    def __init__ (self):
        self.inShutdown = False
        self.queue = Queue.Queue()
        self.thread = None

    def startThread(self):
        self.thread = threading.Thread(name='Movie Data Thread',
                target=self.threadLoop)
        self.thread.setDaemon(True)
        self.thread.start()

    def threadLoop(self):
        while not self.inShutdown:
            movieDataInfo = self.queue.get(block=True)
            if movieDataInfo is None:
                # shutdown() was called()
                break
            try:
                self.runMovieDataProgram(**movieDataInfo)
            except:
                if self.inShutdown:
                    break
                util.failedExn("When running external movie data program")

    def runMovieDataProgram(self, item, thumbnailPath, commandLine, env):
        duration = -1
        screenshot = None
        pipe = subprocess.Popen(commandLine, stdout=subprocess.PIPE,
                stdin=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
                startupinfo=util.no_console_startupinfo())
        while pipe.poll() is None and not self.inShutdown:
            time.sleep(0.1)

        if self.inShutdown:
            if pipe.poll() is None:
                logging.info("Movie data process still going, trying to kill it")
                try:
                    app.delegate.killProcess(pipe.pid)
                except:
                    logging.warn("Error trying to kill the movie data process:\n%s", traceback.format_exc())
                else:
                    logging.info("Movie data process killed")
            return

        stdout = pipe.stdout.read()
        if thumbnailRE.search(stdout):
            screenshot = thumbnailPath
        durationMatch = durationRE.search(stdout)
        if durationMatch:
            duration = int(durationMatch.group(1))
        self.updateFinished(item, duration, screenshot)

    @asIdle
    def updateFinished (self, item, duration, screenshot):
        if item.idExists():
            item.duration = duration
            item.screenshot = screenshot
            item.updating_movie_info = False
            item.signalChange()


    def requestUpdate (self, item):
        if self.inShutdown:
            return
        filename = item.getVideoFilename()
        if not filename or not os.path.isfile(filename):
            return
        if item.downloader and not item.downloader.isFinished():
            return
        if item.updating_movie_info:
            return
        if not hasattr(app.delegate, 'movieDataProgramInfo'):
            return

        item.updating_movie_info = True
        videoPath = item.getVideoFilename()
        thumbnailFilename = os.path.basename(videoPath) + ".png"
        thumbnailPath = os.path.join(self.thumbnailDirectory(),
                thumbnailFilename)
        commandLine, env = app.delegate.movieDataProgramInfo(videoPath,
                thumbnailPath)
        movieDataInfo = {'item': item, 'thumbnailPath': thumbnailPath,
                'commandLine': commandLine, 'env': env}
        self.queue.put(movieDataInfo)

    def thumbnailDirectory(self):
        dir = os.path.join(config.get(prefs.ICON_CACHE_DIRECTORY),
                "extracted")
        try:
            os.makedirs(dir)
        except:
            pass
        return dir

    def shutdown (self):
        self.inShutdown = True
        self.queue.put(None) # wake up our thread
        if self.thread is not None:
            self.thread.join()

movieDataUpdater = MovieDataUpdater()
