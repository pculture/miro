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

from miro.eventloop import asIdle
import os.path
import re
import subprocess
import time
import traceback
import threading
import Queue

from miro import app
import logging
from miro import config
from miro import prefs
from miro import signals
from miro import util
from miro import fileutil
from miro.plat.utils import FilenameType, killProcess

MOVIE_DATA_UTIL_TIMEOUT = 60
# Time in seconds that we wait for the utility to execute.  If it goes longer
# than this, we assume it's hung and kill it.
SLEEP_DELAY = 0.1
# Time to sleep while we're polling the external movie command

durationRE = re.compile("Miro-Movie-Data-Length: (\d+)")
thumbnailSuccessRE = re.compile("Miro-Movie-Data-Thumbnail: Success")
thumbnailRE = re.compile("Miro-Movie-Data-Thumbnail: (Success|Failure)")

def thumbnailDirectory():
    dir_ = os.path.join(config.get(prefs.ICON_CACHE_DIRECTORY), "extracted")
    try:
        fileutil.makedirs(dir_)
    except:
        pass
    return dir_

class MovieDataInfo:
    """Little utility class to keep track of data associated with each movie.
    This is:

    * The item.
    * The path to the video.
    * Path to the thumbnail we're trying to make.
    * List of commands that we're trying to run, and their environments.
    """

    def __init__(self, item):
        self.item = item
        self.videoPath = item.getVideoFilename()
        # add a random string to the filename to ensure it's unique.  Two
        # videos can have the same basename if they're in different
        # directories.
        thumbnailFilename = '%s.%s.png' % (os.path.basename(self.videoPath),
                util.random_string(5))
        self.thumbnailPath = os.path.join(thumbnailDirectory(),
                thumbnailFilename)
        self.programInfo = []
        for renderer in app.renderers:
            try:
                commandLine, env = renderer.movieDataProgramInfo(
                        fileutil.expand_filename(self.videoPath), fileutil.expand_filename(self.thumbnailPath))
            except NotImplementedError:
                pass
            else:
                self.programInfo.append((commandLine, env))

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
                duration = -1
                screenshotWorked = False
                screenshot = None
                for commandLine, env in movieDataInfo.programInfo:
                    stdout = self.runMovieDataProgram(commandLine, env)
                    if duration == -1:
                        duration = self.parseDuration(stdout)
                    if thumbnailSuccessRE.search(stdout):
                        screenshotWorked = True
                    if duration != -1 and screenshotWorked:
                        break
                if (screenshotWorked and 
                        fileutil.exists(movieDataInfo.thumbnailPath)):
                    screenshot = movieDataInfo.thumbnailPath
                else:
                    # All the programs failed, maybe it's an audio file?
                    # Setting it to "" instead of None, means that we won't
                    # try to take the screenshot again.
                    screenshot = FilenameType("")
                self.updateFinished(movieDataInfo.item, duration, screenshot)
            except:
                if self.inShutdown:
                    break
                signals.system.failedExn("When running external movie data program")
                self.updateFinished(movieDataInfo.item, -1, None)

    def runMovieDataProgram(self, commandLine, env):
        start_time = time.time()
        pipe = subprocess.Popen(commandLine, stdout=subprocess.PIPE,
                stdin=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
                startupinfo=util.no_console_startupinfo())
        while pipe.poll() is None and not self.inShutdown:
            time.sleep(SLEEP_DELAY)
            if time.time() - start_time > MOVIE_DATA_UTIL_TIMEOUT:
                logging.info("Movie data process hung, killing it")
                self.killProcess(pipe.pid)
                return ''

        if self.inShutdown:
            if pipe.poll() is None:
                logging.info("Movie data process running after shutdown, killing it")
                self.killProcess(pipe.pid)
            return ''
        return pipe.stdout.read()

    def killProcess(self, pid):
        try:
            killProcess(pid)
        except:
            logging.warn("Error trying to kill the movie data process:\n%s", traceback.format_exc())
        else:
            logging.info("Movie data process killed")

    def outputValid(self, stdout):
        return (thumbnailRE.search(stdout) is not None and
                durationRE.search(stdout) is not None)

    def parseDuration(self, stdout):
        durationMatch = durationRE.search(stdout)
        if durationMatch:
            return int(durationMatch.group(1))
        else:
            return -1

    @asIdle
    def updateFinished(self, item, duration, screenshot):
        if item.idExists():
            item.duration = duration
            item.screenshot = screenshot
            item.updating_movie_info = False
            item.signalChange()

    def requestUpdate(self, item):
        if self.inShutdown:
            return
        filename = item.getVideoFilename()
        if not filename or not fileutil.isfile(filename):
            return
        if item.downloader and not item.downloader.isFinished():
            return
        if item.updating_movie_info:
            return

        item.updating_movie_info = True
        self.queue.put(MovieDataInfo(item))

    def shutdown(self):
        self.inShutdown = True
        self.queue.put(None) # wake up our thread
        if self.thread is not None:
            self.thread.join()

movieDataUpdater = MovieDataUpdater()
