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
from contextlib import contextmanager

from miro import app
from miro import prefs
from miro import signals
from miro import util
from miro import fileutil
from miro.plat.utils import (movie_data_program_info,
                             thread_body)
from miro.errors import Shutdown

# Time in seconds that we wait for the utility to execute.  If it goes
# longer than this, we assume it's hung and kill it.
MOVIE_DATA_UTIL_TIMEOUT = 30

# Time to sleep while we're polling the external movie command
SLEEP_DELAY = 0.1

DURATION_RE = re.compile("Miro-Movie-Data-Length: (\d+)")
TYPE_RE = re.compile("Miro-Movie-Data-Type: (audio|video|other)")
THUMBNAIL_SUCCESS_RE = re.compile("Miro-Movie-Data-Thumbnail: Success")
TRY_AGAIN_RE = re.compile("Miro-Try-Again: True")

class State(object):
    """Enum for tracking what we've looked at.

    None indicates that we haven't looked at the file at all;
    non-true values indicate that we haven't run MDP.
    """
    UNSEEN = None
    SKIPPED = 0
    RAN = 1
    FAILED = 2

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
        self.thumbnail_path = self._make_thumbnail_path()
        self._program_info = None

    def _make_thumbnail_path(self):
        # add a random string to the filename to ensure it's unique.
        # Two videos can have the same basename if they're in
        # different directories.
        video_base = os.path.basename(self.video_path)
        filename = '%s.%s.png' % (video_base, util.random_string(5))
        return os.path.join(self.image_directory('extracted'), filename)

    @property
    def program_info(self):
        if not self._program_info:
            self._program_info = self._calc_program_info()
        return self._program_info

    def _calc_program_info(self):
        videopath = fileutil.expand_filename(self.video_path)
        thumbnailpath = fileutil.expand_filename(self.thumbnail_path)
        command_line, env = movie_data_program_info(videopath, thumbnailpath)
        return command_line, env

    @classmethod
    def image_directory(cls, subdir):
        dir_ = os.path.join(app.config.get(prefs.ICON_CACHE_DIRECTORY), subdir)
        try:
            fileutil.makedirs(dir_)
        except OSError:
            pass
        return dir_

class ProcessHung(StandardError): pass

class MovieDataUpdater(signals.SignalEmitter):
    def __init__ (self):
        signals.SignalEmitter.__init__(self, 'begin-loop', 'end-loop',
                'queue-empty')
        self.in_shutdown = False
        self.in_progress = set()
        self.queue = Queue.Queue()
        self.thread = None
        self.watchdog = None
        self.pipe = None
        self.cmd_begin_gate = threading.Event()
        self.cmd_end_gate = threading.Event()

    def start_thread(self):
        self.thread = threading.Thread(name='Movie Data Thread',
                                       target=thread_body,
                                       args=[self.thread_loop])
        self.thread.setDaemon(True)
        self.thread.start()

        self.watchdog = threading.Thread(target=thread_body,
                             args=[self.watcher],
                             name='moviedata watchdog timer')
        self.watchdog.setDaemon(True)
        self.watchdog.start()

    def process_with_movie_data_program(self, mdi):
        command_line, env = mdi.program_info
        try:
            stdout = self.run_movie_data_program(command_line, env)
        except StandardError:
            # check whether it's actually a Shutdown error, then raise
            if self.in_shutdown:
                raise Shutdown
            raise

        if not stdout:
            logging.debug("moviedata: error--no stdout: %s", stdout)

        if TRY_AGAIN_RE.search(stdout):
            # FIXME: we should try again at some point, but right now we just
            # ignore this
            pass

        duration = self.parse_duration(stdout)
        if os.path.splitext(mdi.video_path)[1] == '.flv':
            # bug #17266.  if the extension is .flv, we ignore the mediatype
            # we just got from the movie data program.  this is
            # specifically for .flv files which the movie data
            # extractors have a hard time with.
            mediatype = u'video'
        else:
            mediatype = self.parse_type(stdout)
        screenshot = self.parse_screenshot(stdout, mdi)

        # bz:17364/bz:18072 HACK: need to avoid UnicodeDecodeError -
        # until we do a proper pathname cleanup.  Used to be a %s with a
        # encode to utf-8 but then 18072 came up.  It seems that this
        # can either be a str OR a unicode.  I don't really feel
        # like dealing with this right now, so just use %r.
        logging.debug("moviedata: mdp %s %s %s %r", duration, screenshot,
                mediatype, mdi.video_path)
        return duration, screenshot, mediatype

    @contextmanager
    def looping(self):
        """Simple contextmanager to ensure that whatever happens in a
        thread_loop, we signal begin/end properly.
        """
        self.emit('begin-loop')
        try:
            yield
        finally:
            self.emit('end-loop')

    def thread_loop(self):
        try:
            while not self.in_shutdown:
                with self.looping():
                    self.process_item()
        except Shutdown:
            pass

    def process_item(self):
        try:
            mdi = self.queue.get(block=False)
        except Queue.Empty:
            self.emit('queue-empty')
            mdi = self.queue.get(block=True)
        # IMPORTANT: once we have popped an MDI off the queue, its mdp_state
        # *must* be set (by update_finished or update_failed) unless we shut
        # down before we could process it
        if mdi is None:
            raise Shutdown
        try:
            results = self.process_with_movie_data_program(mdi)
        except ProcessHung:
            self.update_failed(mdi.item)
            # this kind of error is expected; just a warning
            logging.warning("Movie data process hung, killing it. File was: %r",
                    mdi.video_path)
        except StandardError:
            self.update_failed(mdi.item)
            signals.system.failed_exn(
                "When running external movie data program for %r" %
                mdi.video_path)
        else:
            self.update_finished(mdi.item, *results)
        if hasattr(app, 'metadata_progress_updater'): # hack for unittests
            app.metadata_progress_updater.path_processed(mdi.video_path)

    def watcher(self):
        while True:
            self.cmd_begin_gate.wait()
            if self.in_shutdown:
                break
            self.cmd_begin_gate.clear()
            # OK to wait indefinitely: run_movie_data_program() sits on
            # on a timed wait so when the gate clears and finds the
            # external program still active it will kill it, and this will
            # resolve.  Then everything proceeds as normal.
            self.pipe.wait()
            self.cmd_end_gate.set()

    def run_movie_data_program(self, command_line, env):
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
        self.pipe = pipe
        # Fire up the watchdog
        self.cmd_begin_gate.set()
        self.cmd_end_gate.wait(MOVIE_DATA_UTIL_TIMEOUT)
        # Pipe should be gone by now.  Reset for safety
        self.pipe = None
        if pipe.poll() is None and not self.in_shutdown:
            logging.warning("Movie data process hung, killing it")
            self.kill_process(pipe)
            # when the process is killed the end command gate will be
            # set, so wait again here for it to clear.
            self.cmd_end_gate.wait()
            self.cmd_end_gate.clear()
            raise ProcessHung

        if self.in_shutdown:
            if pipe.poll() is None:
                logging.warning("Movie data process running after shutdown, "
                                "killing it")
                self.kill_process(pipe)
            # no need to clear command gates here - shutting down anyway
            raise Shutdown

        # We now know this is normal external movie data program termination.
        # The self.pipe.wait() in the watchdog must have succeeded so
        # clear the end command gate.
        self.cmd_end_gate.clear()
        # FIXME: should we do anything with stderr?
        movie_data_stdout.seek(0)
        return movie_data_stdout.read()

    def kill_process(self, pipe):
        try:
            pipe.kill()
            pipe.wait()
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
            return None

    def parse_type(self, stdout):
        type_match = TYPE_RE.search(stdout)
        if type_match:
            return unicode(type_match.group(1))
        else:
            return None

    def parse_screenshot(self, stdout, mdi):
        if (THUMBNAIL_SUCCESS_RE.search(stdout) and
                fileutil.exists(mdi.thumbnail_path)):
            return mdi.thumbnail_path
        else:
            return None

    @as_idle
    def update_failed(self, item):
        self.in_progress.remove(item.id)
        if item.id_exists():
            item.mdp_state = State.FAILED
            if item.has_drm:
                #17442#c7, part2: if mutagen called it potentially DRM'd and we
                # couldn't read it, we consider it DRM'd; files that we consider
                # DRM'd initially go in "Other"
                item.file_type = u'other'
            item.signal_change()

    @as_idle
    def update_finished(self, item, duration, screenshot, mediatype):
        self.in_progress.remove(item.id)
        if item.id_exists():
            item.mdp_state = State.RAN
            item.screenshot = screenshot
            if duration is not None:
                item.duration = duration
                if duration != -1:
                    # if mutagen thought it might have DRM but we got a
                    # duration, override mutagen's guess
                    item.has_drm = False
            if item.has_drm:
                #17442#c7, part2: if mutagen called it potentially DRM'd and we
                # couldn't read it, we consider it DRM'd; files that we consider
                # DRM'd initially go in "Other"
                item.file_type = u'other'
            elif mediatype is not None:
                item.file_type = mediatype
            item.signal_change()

    def update_skipped(self, item):
        item.mdp_state = State.SKIPPED
        item.signal_change()

    def request_update(self, item):
        if (hasattr(app, 'in_unit_tests') and
                not hasattr(app, 'testing_mdp')):
            # kludge for skipping MDP in non-MDP unittests
            return
        if self.in_shutdown:
            return
        if item.id in self.in_progress:
            logging.warn("Not adding in-progess item (%s)", item.id)
            return

        if self._should_process_item(item):
            self.in_progress.add(item.id)
            self.queue.put(MovieDataInfo(item))
        else:
            self.update_skipped(item)
            app.metadata_progress_updater.path_processed(item.get_filename())

    def _should_process_item(self, item):
        if item.has_drm:
            # mutagen can only identify files that *might* have drm, so we
            # always need to check that
            return True
        # Only run the movie data program for video items, audio items that we
        # don't know the duration for, or items that do not have "other"
        # filenames that mutagen could not determine type for.
        return (item.file_type == u'video' or
                (item.file_type == u'audio' and item.duration is None) or
                item.file_type is None)

    def shutdown(self):
        self.in_shutdown = True
        # wake up our thread
        self.queue.put(None)
        # Wake up the command gates.  Begin gate wakes up the
        # watchdog and tells it to quit.
        #
        # End gate wakes up run_movie_data_program() if it was
        # blocked on a moviedata.  It will have detection code for
        # the quit scenario.
        self.cmd_begin_gate.set()
        self.cmd_end_gate.set()
        if self.thread is not None:
            self.thread.join()

movie_data_updater = MovieDataUpdater()
