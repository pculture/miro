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

    def guess_mediatype(self, item_):
        """Guess the mediatype of a file. Needs to be quick, as it's executed by
        the requesting thread in request_update(), and nothing will break if it
        isn't always accurate - so just checks filename.
        """
        filename = item_.get_filename()
        if filetypes.is_video_filename(filename):
            mediatype = 'video'
        elif filetypes.is_audio_filename(filename):
            mediatype = 'audio'
        else:
            mediatype = 'other'
        return mediatype

    def update_progress(self, mediatype, device, add_or_remove):
        if device:
            target = (u'device', '%s-%s' % (device.id, mediatype))
        elif mediatype in ('audio', 'video'):
            target = (u'library', mediatype)
        else: # mediatype 'other'
            return

        if add_or_remove > 0: # add
            self.total.setdefault(target, 0)
            self.total[target] += add_or_remove

        self.remaining.setdefault(target, 0)
        self.remaining[target] += add_or_remove

        if not self.remaining[target]:
            self.total[target] = 0

        update = models.messages.MetadataProgressUpdate(target,
            self.remaining[target], None, self.total[target])
        update.send_to_frontend()

    def process_with_movie_data_program(self,
            mdi, duration, mediatype, metadata, cover_art):
        screenshot_worked = False
        screenshot = None

        command_line, env = mdi.program_info
        stdout = self.run_movie_data_program(command_line, env)

        if TRY_AGAIN_RE.search(stdout):
            # if the moviedata program tells us to try again, we move
            # along without updating the item at all
            if mdi.item in self.retrying:
                # but don't retry indefinitely
                self.update_finished(
                    mdi.item, -1, screenshot, mediatype, metadata, cover_art)
            else:
                self.retrying.add(mdi.item)
            return

        if duration == -1 or not duration:
            duration = self.parse_duration(stdout)
        mediatype = self.parse_type(stdout) or 'other'
        if THUMBNAIL_SUCCESS_RE.search(stdout):
            screenshot_worked = True
        if ((screenshot_worked and
             fileutil.exists(mdi.thumbnail_path))):
            screenshot = mdi.thumbnail_path
        else:
            # All the programs failed, maybe it's an audio
            # file?  Setting it to "" instead of None, means
            # that we won't try to take the screenshot again.
            screenshot = FilenameType("")

        logging.debug("moviedata: mdp %s %s %s", duration, screenshot,
                      mediatype)
        self.update_finished(
            mdi.item, duration, screenshot, mediatype, metadata, cover_art)

    def thread_loop(self):
        while not self.in_shutdown:
            self.emit('begin-loop')
            if self.queue.empty():
                self.emit('queue-empty')
            _discard_, mdi = self.queue.get(block=True)
            if mdi is None or mdi.program_info is None:
                # shutdown() was called or there's no moviedata
                # implemented.
                self.emit('end-loop')
                break
            duration = -1
            metadata = {}
            cover_art = FilenameType("")
            item_ = mdi.item
            file_info = filetags.read_metadata(item_.get_filename())
            (mime_mediatype, duration, metadata, cover_art) = file_info
            if duration > -1 and mime_mediatype != u'video':
                mediatype = 'audio'
                screenshot = item_.screenshot or FilenameType("")
                if cover_art is None:
                    logging.debug("moviedata: mutagen %s %s", duration, mediatype)
                else:
                    logging.debug("moviedata: mutagen %s %s %s",
                                  duration, cover_art, mediatype)

                self.update_finished(item_, duration, screenshot, mediatype,
                                     metadata, cover_art)
            else:
                try:
                    self.process_with_movie_data_program(
                        mdi, duration, mime_mediatype, metadata, cover_art)
                except StandardError:
                    if self.in_shutdown:
                        break
                    signals.system.failed_exn(
                        "When running external movie data program")
                    self.update_finished(item_, -1, None, None, metadata,
                                         cover_art)
            self.emit('end-loop')

    def run_movie_data_program(self, command_line, env):
        start_time = time.time()
        pipe = subprocess.Popen(command_line, stdout=subprocess.PIPE,
                stdin=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
                startupinfo=util.no_console_startupinfo())
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
        return pipe.stdout.read()

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
    def update_finished(self, item, duration, screenshot, mediatype, metadata,
                        cover_art):
        self.in_progress.remove(item.id)
        progress_mediatype = self.guess_mediatype(item)
        if hasattr(item, 'device'):
            device = item.device
        else:
            device = None
        self.update_progress(progress_mediatype, device, -1)
        if item.id_exists():
            if not duration:
                # duration == None is how we know it's not parsed yet
                duration = -1
            item.duration = duration
            item.screenshot = screenshot
            item.cover_art = cover_art
            item.album = metadata.get('album', None)
            item.album_artist = metadata.get('album_artist', None)
            item.artist = metadata.get('artist', None)
            item.title_tag = metadata.get('title', None)
            item.track = metadata.get('track', None)
            item.year = metadata.get('year', None)
            item.genre = metadata.get('genre', None)
            item.has_drm = metadata.get('drm', False)
            item.metadata_version = METADATA_VERSION
            if mediatype is not None:
                item.file_type = unicode(mediatype)
                item.media_type_checked = True
            item.signal_change()

    def request_update(self, item):
        if self.in_shutdown:
            return
        filename = item.get_filename()
        if not filename or not fileutil.isfile(filename):
            return
        if item.downloader and not item.downloader.is_finished():
            return
        if item.id in self.in_progress:
            return

        self.in_progress.add(item.id)
        mediatype = self.guess_mediatype(item)
        priority = self.media_order.index(mediatype)
        self.queue.put((priority, MovieDataInfo(item)))
        if hasattr(item, 'device'):
            device = item.device
        else:
            device = None
        self.update_progress(mediatype, device, 1)

    def shutdown(self):
        self.in_shutdown = True
        # wake up our thread
        self.queue.put((-1000, None))
        if self.thread is not None:
            self.thread.join()

movie_data_updater = MovieDataUpdater()
