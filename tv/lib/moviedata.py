# Miro - an RSS based video player application
# Copyright (C) 2005, 2006, 2007, 2008, 2009, 2010, 2011
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
import mutagen
import struct

from miro import app
from miro import prefs
from miro import signals
from miro import util
from miro import fileutil
from miro import filetypes
from miro import coverart
from miro import models
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

TAG_MAP = {
    'album': ('album', 'talb', 'wm/albumtitle', u'\uFFFDalb'),
    'album_artist': ('albumartist', 'album artist', 'tpe2'),
    'artist': ('artist', 'tpe1', 'tpe2', 'tpe3', 'author', 'albumartist',
        'composer', u'\uFFFDart', 'album artist'),
    'drm': ('itunmovi',),
    'title': ('tit2', 'title', u'\uFFFDnam'),
    'track': ('trck', 'tracknumber'),
    'album_tracks': (),
    'year': ('tdrc', 'tyer', 'date', 'year'),
    'genre': ('genre', 'tcon', 'providerstyle', u'\uFFFDgen'),
    'cover-art': ('\uFFFDart', 'apic', 'covr'),
}
TAG_TYPES = {
    'album': unicode, 'album_artist': unicode, 'artist': unicode, 'drm': bool,
    'title': unicode, 'track': int, 'album_tracks': int, 'year': int,
    'genre': unicode,
}
NOFLATTEN_TAGS = ('cover-art',)

# increment this after adding to TAG_MAP or changing read_metadata() in a way
# that will increase data identified (will not change values already extracted)
METADATA_VERSION = 5

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
        if mediatype not in ('audio', 'video'):
            # I don't think it's useful to show progress for "Other" items
            return
        target = device or mediatype
        if device is None:
            full_target = (u'library', target)
        else:
            full_target = (u'device', target)

        self.total.setdefault(target, 0)
        if add_or_remove > 0: # add
            self.total[target] += add_or_remove
        total = self.total[target]

        self.remaining.setdefault(target, 0)
        self.remaining[target] += add_or_remove
        remaining = self.remaining[target]

        news = None
        if remaining == 0:
            news = models.messages.MetadataProgressFinish(full_target)
        else:
            news = models.messages.MetadataProgressUpdate(full_target,
                   remaining, None, total)
        if news is not None:
            news.send_to_frontend()

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
            file_info = self.read_metadata(item_)
            (mime_mediatype, duration, metadata, cover_art) = file_info
            if duration > -1 and mime_mediatype is not 'video':
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
                    if mediatype is None:
                        mediatype = 'other'
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

                    self.update_finished(item_, duration, screenshot,
                                         mediatype, metadata, cover_art)
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

    def _mediatype_from_mime(self, mimes):
        audio = False
        other = False
        for mime in mimes:
            ext = filetypes.guess_extension(mime)
            if ext in filetypes.VIDEO_EXTENSIONS:
                return 'video'
            if ext in filetypes.AUDIO_EXTENSIONS:
                audio = True
            if ext in filetypes.OTHER_EXTENSIONS:
                other = True
        if audio:
            return 'audio'
        elif other:
            return 'other'
        else:
            return None

    def _str_or_object_to_unicode(self, thing):
        """Whatever thing is, get a unicode out of it at all costs."""
        if not isinstance(thing, basestring):
            if hasattr(thing, '__unicode__'):
                # object explicitly supports unicode. yay!
                thing = unicode(thing)
            else:
                # unicode(thing) would die if thing had funky chars,
                # but unicode(thing, errors=FOO) can't be used for objects
                thing = str(thing)
        if not isinstance(thing, unicode):
            # at this point, thing has to be descended from basestring
            thing = unicode(thing, errors='replace')
        return thing

    def _sanitize_keys(self, tags):
        """Strip useless components and strange characters from tag names
        """
        tags_cleaned = {}
        for key, value in tags.iteritems():
            key = self._str_or_object_to_unicode(key)
            if key.startswith('PRIV:'):
                key = key.split('PRIV:')[1]
            if key.startswith('TXXX:'):
                key = key.split('TXXX:')[1]
            if key.startswith('----:com.apple.iTunes:'):
                # iTunes M4V
                key = key.split('----:com.apple.iTunes:')[1]
            key = key.split(':')[0]
            if key.startswith('WM/'):
                key = key.split('WM/')[1]
            key = key.lower()
            tags_cleaned[key] = value
        return tags_cleaned

    def _sanitize_values(self, tags):
        """Flatten values into simple unicode strings
        """
        tags_cleaned = {}
        for key, value in tags.iteritems():
            while isinstance(value, list):
                if not value:
                    value = None
                    break
                value = value[0]
            if value is not None:
                value = self._str_or_object_to_unicode(value)
                tags_cleaned[key] = value.lstrip()
        return tags_cleaned

    def _special_mappings(self, data, item):
        """Handle tags that need more than a simple TAG_MAP entry
        """
        if 'purd' in data:
            data[u'year'] = data['purd'].split('-')[0]
        if 'year' in data:
            if not data['year'].isdigit():
                del data['year']
        if 'track' in data:
            track = data['track'].split('/')[0]
            if track.isdigit():
                data[u'track'] = unicode(int(track))
            else:
                del data['track']
        if 'trkn' in data:
            track = data['trkn']
            if isinstance(track, tuple):
                track = track[0]
            data[u'track'] = unicode(track)
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
        return data

    def _make_cover_art_file(self, track_path, objects):
        if not isinstance(objects, list):
            objects = [objects]

        images = []
        for image_object in objects:
            try:
               image = coverart.Image(image_object)
            except coverart.UnknownImageObjectException as e:
               logging.debug("Couldn't parse image object of type %s", e.get_type())
            else:
               images.append(image)
        if not images:
            return

        cover_image = None
        for candidate in images:
            if candidate.is_cover_art() is not False:
                cover_image = candidate
                break
        if cover_image is None:
            # no attached image is definitively cover art. use the first one.
            cover_image = images[0]

        path = cover_image.write_to_file(track_path)
        return path
    
    def read_metadata(self, item):
        mediatype = None
        duration = -1
        cover_art = None
        tags = {}
        info = {}
        data = {}

        try:
            muta = mutagen.File(item.get_filename())
            meta = muta.__dict__
        except (ArithmeticError):
            # mutagen doesn't catch these errors internally
            logging.warn("malformed file: %s", item.get_filename())
            return (mediatype, duration, data, cover_art)
        except (AttributeError, IOError):
            return (mediatype, duration, data, cover_art)
        except struct.error:
            logging.warn("read_metadata on incomplete file: %s",
                         item.get_filename())
            return (mediatype, duration, data, cover_art)

        filename = item.get_filename()
        if filetypes.is_video_filename(filename):
            mediatype = 'video'
        elif filetypes.is_audio_filename(filename):
            mediatype = 'audio'
        elif hasattr(muta, 'mime'):
            mediatype = self._mediatype_from_mime(muta.mime)

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

        tags = self._sanitize_keys(tags)
        nonflattened_tags = tags.copy()
        tags = self._sanitize_values(tags)

        for tag, sources in TAG_MAP.iteritems():
            for source in sources:
                if source in tags:
                    if tag in NOFLATTEN_TAGS:
                        data[unicode(tag)] = nonflattened_tags[source]
                    else:
                        data[unicode(tag)] = tags[source]
                    break

        data = self._special_mappings(data, item)

        if hasattr(muta, 'pictures'):
            image_data = muta.pictures
            cover_art = self._make_cover_art_file(item.get_filename(), image_data)
        elif 'cover-art' in data:
            image_data = data['cover-art']
            cover_art = self._make_cover_art_file(item.get_filename(), image_data)
            del data['cover-art']

        for tag, value in data.iteritems():
            if not isinstance(value, TAG_TYPES[tag]):
                try:
                    data[tag] = TAG_TYPES[tag](value)
                except ValueError:
                    logging.debug("Invalid type for tag %s: %s", tag, repr(value))
                    del data[tag]
        return (mediatype, duration, data, cover_art)

    def kill_process(self, pid):
        try:
            kill_process(pid)
        except OSError:
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
    def update_finished(self, item, duration, screenshot, mediatype, metadata,
                        cover_art):
        self.in_progress.remove(item.id)
        mediatype = self.guess_mediatype(item)
        if hasattr(item, 'device'):
            device = item.device
        else:
            device = None
        self.update_progress(mediatype, device, -1)
        if item.id_exists():
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
            if item.has_drm:
                mediatype = 'other'
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
