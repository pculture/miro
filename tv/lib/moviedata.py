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

from miro.eventloop import as_idle
import os.path
import re
import subprocess
import time
import traceback
import threading
import Queue
import logging
import mutagen

from miro import app
from miro import prefs
from miro import signals
from miro import util
from miro import fileutil
from miro.plat.utils import (FilenameType, kill_process,
                             movie_data_program_info, thread_body)

# Time in seconds that we wait for the utility to execute.  If it goes
# longer than this, we assume it's hung and kill it.
MOVIE_DATA_UTIL_TIMEOUT = 120

# Time to sleep while we're polling the external movie command
SLEEP_DELAY = 0.1

DURATION_RE = re.compile("Miro-Movie-Data-Length: (\d+)")
TYPE_RE = re.compile("Miro-Movie-Data-Type: (audio|video|other)")
THUMBNAIL_SUCCESS_RE = re.compile("Miro-Movie-Data-Thumbnail: Success")
TRY_AGAIN_RE = re.compile("Miro-Try-Again: True")

def thumbnail_directory():
    dir_ = os.path.join(app.config.get(prefs.ICON_CACHE_DIRECTORY),
                        "extracted")
    try:
        fileutil.makedirs(dir_)
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        pass
    return dir_

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
        self.thumbnail_path = os.path.join(thumbnail_directory(),
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

class MovieDataUpdater(signals.SignalEmitter):
    def __init__ (self):
        signals.SignalEmitter.__init__(self, 'begin-loop', 'end-loop',
                'queue-empty')
        self.in_shutdown = False
        self.queue = Queue.Queue()
        self.thread = None

    def start_thread(self):
        self.thread = threading.Thread(name='Movie Data Thread',
                                       target=thread_body,
                                       args=[self.thread_loop])
        self.thread.setDaemon(True)
        self.thread.start()

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
            duration = -1
            metadata = {}
            (mime_mediatype, duration, metadata) = self.read_metadata(mdi.item)
            if duration > -1 and mime_mediatype is not 'video':
                mediatype = 'audio'
                screenshot = mdi.item.screenshot or FilenameType("")
                logging.debug("moviedata: %s %s", duration, mediatype)

                self.update_finished(mdi.item, duration, screenshot, mediatype,
                        metadata)
            else:
                try:
                    screenshot_worked = False
                    screenshot = None

                    command_line, env = mdi.program_info
                    stdout = self.run_movie_data_program(command_line, env)

                    # if the moviedata program tells us to try again, we move
                    # along without updating the item at all
                    if TRY_AGAIN_RE.search(stdout):
                        continue

                    if duration == -1:
                        duration = self.parse_duration(stdout)
                    mediatype = self.parse_type(stdout)
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
                    logging.debug("moviedata: %s %s %s", duration, screenshot,
                                  mediatype)

                    self.update_finished(mdi.item, duration, screenshot,
                                         mediatype, metadata)
                except StandardError:
                    if self.in_shutdown:
                        break
                    signals.system.failed_exn(
                        "When running external movie data program")
                    self.update_finished(mdi.item, -1, None, None, metadata)
            self.emit('end-loop')

    def run_movie_data_program(self, command_line, env):
        start_time = time.time()
        pipe = subprocess.Popen(command_line, stdout=subprocess.PIPE,
                stdin=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
                startupinfo=util.no_console_startupinfo())
        while pipe.poll() is None and not self.in_shutdown:
            time.sleep(SLEEP_DELAY)
            if time.time() - start_time > MOVIE_DATA_UTIL_TIMEOUT:
                logging.info("Movie data process hung, killing it")
                self.kill_process(pipe.pid)
                return ''

        if self.in_shutdown:
            if pipe.poll() is None:
                logging.info("Movie data process running after shutdown, "
                             "killing it")
                self.kill_process(pipe.pid)
            return ''
        return pipe.stdout.read()

    def read_metadata(self, item):
        mediatype = None
        duration = -1
        tags = {}
        info = {}
        data = {}

        try:
            muta = mutagen.File(item.filename)
            meta = muta.__dict__
        except (AttributeError, IOError):
            return (mediatype, duration, data)

        if hasattr(muta, 'mime'):
            for mime in muta.mime:
                category = mime.split('/')[0]
                if category in ('audio', 'video'):
                    mediatype = category
                    break

        tags = meta['tags']
        if hasattr(tags, '__dict__') and '_DictProxy__dict' in tags.__dict__:
            tags = tags.__dict__['_DictProxy__dict']
        tags = tags or {}

        if 'info' in meta:
            info = meta['info'].__dict__
        if 'fps' in info or 'gsst' in tags:
            mediatype = 'video'
        if 'length' in info:
            duration = int(info['length'] * 1000)
        else:
            try:
                dur = meta['seektable'].__dict__['seekpoints'].pop()[1]
                duration = int(dur / 100)
            except (KeyError, AttributeError, TypeError, IndexError):
                pass

        TAG_MAP = {
                'album': ('ALBUM', 'TALB', 'WM/AlbumTitle'),
                'artist': ('ARTIST', 'TPE1', 'TPE2', 'TPE3', 'Author',
                    'WM/AlbumArtist', 'WM/Composer'),
                'title': ('TIT2', 'Title'),
                'track': ('TRCK', 'TRACKNUMBER', 'WM/TrackNumber'),
                'year': ('TDRC', 'TYER', 'DATE', 'WM/Year'),
                'genre': ('GENRE', 'TCON', 'WM/Genre', 'WM/ProviderStyle'),
                }

        for tag, sources in TAG_MAP.items():
            for source in sources:
                if source in tags:
                    value = tags[source]
                    while isinstance(value, list):
                        if not value:
                            value = None
                            break
                        value = value[0]
                    if value:
                        data[unicode(tag)] = unicode(value)
                        break

        if 'year' in data:
            if not data['year'].isdigit():
                del data['year']
        if 'track' in data:
            track = data['track'].split('/')[0]
            if track.isdigit():
                data[u'track'] = unicode(int(track))
            else:
                del data['track']
        if 'track' not in data:
            num = ''
            full_path = item.get_url() or item.get_filename()
            filename = os.path.basename(full_path)
            
            for char in filename:
                if not char.isdigit():
                    break
                num += char
            if num.isdigit():
                num = int(num)
                if num > 0:
                    while num > 100:
                        num -= 100
                    data[u'track'] = unicode(num)
        return (mediatype, duration, data)

    def kill_process(self, pid):
        try:
            kill_process(pid)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            logging.warn("Error trying to kill the movie data process:\n%s",
                         traceback.format_exc())
        else:
            logging.info("Movie data process killed")

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
    def update_finished(self, item, duration, screenshot, mediatype, metadata):
        if item.id_exists():
            item.duration = duration
            item.screenshot = screenshot
            item.metadata = metadata
            item.updating_movie_info = False
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
        if item.updating_movie_info:
            return

        item.updating_movie_info = True
        self.queue.put(MovieDataInfo(item))

    def shutdown(self):
        self.in_shutdown = True
        # wake up our thread
        self.queue.put(None)
        if self.thread is not None:
            self.thread.join()

movie_data_updater = MovieDataUpdater()
