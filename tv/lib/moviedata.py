# Miro - an RSS based video player application
# Copyright (C) 2006, 2006, 2007, 2008, 2009, 2010, 2011
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

from miro.eventloop import as_idle
import os.path
import re
import subprocess
import tempfile
import time
import traceback
import threading
import Queue
import logging

from miro import app
from miro import prefs
from miro import signals
from miro import util
from miro import fileutil
from miro import filetypes
from miro import models
from miro import filetags
from miro.filetags import METADATA_VERSION
from miro.fileobject import FilenameType
from miro.plat.utils import (kill_process, movie_data_program_info,
                             thread_body)

# Time in seconds that we wait for the utility to execute.  If it goes
# longer than this, we assume it's hung and kill it.
MOVIE_DATA_UTIL_TIMEOUT = 120

# Time to sleep while we're polling the external movie command
SLEEP_DELAY = 0.1

DURATION_RE = re.compile("Miro-Movie-Data-Length: (\d+)")
TYPE_RE = re.compile("Miro-Movie-Data-Type: (audio|video|other)")
THUMBNAIL_SUCCESS_RE = re.compile("Miro-Movie-Data-Thumbnail: Success")
TRY_AGAIN_RE = re.compile("Miro-Try-Again: True")

class MovieDataInfo(object):
    """Little utility class to keep track of data associated with each
    movie.  This is:

    * The item.
    * The path to the video.
    * Path to the thumbnail we're trying to make.
    * List of commands that we're trying to run, and their environments.
    """
    def __init__(self, item):
        self.item = item
        self.video_path = item.get_filename()
        if self.video_path is None:
            self._program_info = None
            return
        # add a random string to the filename to ensure it's unique.
        # Two videos can have the same basename if they're in
        # different directories.
        thumbnail_filename = '%s.%s.png' % (os.path.basename(self.video_path),
                                            util.random_string(5))
        self.thumbnail_path = os.path.join(self.image_directory('extracted'),
                                           thumbnail_filename)
        if hasattr(app, 'in_unit_tests'):
            self._program_info = None

    def _get_program_info(self):
        try:
            return self._program_info
        except AttributeError:
            self._calc_program_info()
            return self._program_info

    def _calc_program_info(self):
        videopath = fileutil.expand_filename(self.video_path)
        thumbnailpath = fileutil.expand_filename(self.thumbnail_path)
        command_line, env = movie_data_program_info(videopath, thumbnailpath)
        self._program_info = (command_line, env)

    program_info = property(_get_program_info)

    @classmethod
    def image_directory(cls, subdir):
        dir_ = os.path.join(app.config.get(prefs.ICON_CACHE_DIRECTORY), subdir)
        try:
            fileutil.makedirs(dir_)
        except OSError:
            pass
        return dir_

class MovieDataUpdater(signals.SignalEmitter):
    def __init__ (self):
        signals.SignalEmitter.__init__(self, 'begin-loop', 'end-loop',
                'queue-empty')
        self.in_shutdown = False
        self.in_progress = set()
        self.queue = Queue.PriorityQueue()
        self.thread = None
        self.media_order = ['audio', 'video', 'other']
        self.total = {}
        self.remaining = {}
        self.retrying = set()

    def start_thread(self):
        self.thread = threading.Thread(name='Movie Data Thread',
                                       target=thread_body,
                                       args=[self.thread_loop])
        self.thread.setDaemon(True)
        self.thread.start()

    def process_with_movie_data_program(self, mdi):
        screenshot_worked = False
        screenshot = None

        command_line, env = mdi.program_info
        stdout = self.run_movie_data_program(command_line, env)

        if TRY_AGAIN_RE.search(stdout):
            # FIXME: we should try again at some point, but right now we just
            # ignore this
            return

        duration = self.parse_duration(stdout)
        mediatype = self.parse_type(stdout) or 'other'
        if THUMBNAIL_SUCCESS_RE.search(stdout):
            screenshot_worked = True
        if ((screenshot_worked and
             fileutil.exists(mdi.thumbnail_path))):
            screenshot = mdi.thumbnail_path

        logging.debug("moviedata: mdp %s %s %s %s", duration, screenshot,
                mediatype, mdi.video_path)
        self.update_finished(mdi.item, duration, screenshot, mediatype)

    def thread_loop(self):
        while not self.in_shutdown:
            self.emit('begin-loop')
            if self.queue.empty():
                self.emit('queue-empty')
            mdi = self.queue.get(block=True)
            if mdi is None or mdi.program_info is None:
                # shutdown() was called or there's no moviedata
                # implemented.
                self.emit('end-loop')
                break
            try:
                self.process_with_movie_data_program(mdi)
            except StandardError:
                if self.in_shutdown:
                    break
                signals.system.failed_exn(
                    "When running external movie data program")
            app.metadata_progress_updater.path_processed(
                    mdi.video_path)
            self.emit('end-loop')

    def run_movie_data_program(self, command_line, env):
        start_time = time.time()
        # create tempfiles to catch output for the movie data program.  Using
        # a pipe fails if the movie data program outputs enough to fill up the
        # buffers (see #17059)
        movie_data_stdout = tempfile.TemporaryFile()
        movie_data_stderr = tempfile.TemporaryFile()
        pipe = subprocess.Popen(command_line, stdout=movie_data_stdout,
                stdin=subprocess.PIPE, stderr=movie_data_stderr, env=env,
                startupinfo=util.no_console_startupinfo())
        # close stdin since we won't write to it.
        pipe.stdin.close()
        while pipe.poll() is None and not self.in_shutdown:
            time.sleep(SLEEP_DELAY)
            if time.time() - start_time > MOVIE_DATA_UTIL_TIMEOUT:
                logging.warning("Movie data process hung, killing it")
                self.kill_process(pipe.pid)
                return ''

        if self.in_shutdown:
            if pipe.poll() is None:
                logging.warning("Movie data process running after shutdown, "
                                "killing it")
                self.kill_process(pipe.pid)
            return ''
        # FIXME: should we do anything with stderr?
        movie_data_stdout.seek(0)
        return movie_data_stdout.read()

    def kill_process(self, pid):
        try:
            kill_process(pid)
        except OSError:
            logging.warning("Error trying to kill the movie data process:\n%s",
                            traceback.format_exc())
        else:
            logging.warning("Movie data process killed")

    def parse_duration(self, stdout):
        duration_match = DURATION_RE.search(stdout)
        if duration_match:
            return int(duration_match.group(1))
        else:
            return -1

    def parse_type(self, stdout):
        type_match = TYPE_RE.search(stdout)
        if type_match:
            return type_match.group(1)
        else:
            return None

    @as_idle
    def update_finished(self, item, duration, screenshot, mediatype):
        self.in_progress.remove(item.id)
        if item.id_exists():
            item.screenshot = screenshot
            if duration is not None:
                item.duration = duration
            if mediatype is not None:
                item.file_type = unicode(mediatype)
                item.media_type_checked = True
            item.signal_change()

    def request_update(self, item):
        if self.in_shutdown:
            return
        if item.id in self.in_progress:
            logging.warn("Not adding in-progess item (%s)", item.id)
            return

        if self._should_process_item(item):
            self.in_progress.add(item.id)
            self.queue.put(MovieDataInfo(item))
        else:
            app.metadata_progress_updater.path_processed(item.get_filename())

    def _duration_unknown(self, item):
        # FIXME: we should just be using 1 value for unknown.  I think that
        # should be None
        return item.duration is None or item.duration < 0

    def _should_process_item(self, item):
        # don't process non-video/audio files
        if filetypes.is_other_filename(item.get_filename()):
            return False
        # Only run the movie data program for video items, or audio items that
        # we don't know the duration for.
        return self._duration_unknown(item) or item.file_type == u'video'

    def shutdown(self):
        self.in_shutdown = True
        # wake up our thread
        self.queue.put(None)
        if self.thread is not None:
            self.thread.join()

movie_data_updater = MovieDataUpdater()
