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

from miro import app
from miro import prefs
from miro import signals
from miro import util
from miro import fileutil
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

VIDEO_EXTENSIONS = ('.m4v','.mp4','.mpg')
TAG_MAP = {
    'album': ('album', 'talb', 'wm/albumtitle', u'\uFFFDalb'),
    'artist': ('artist', 'tpe1', 'tpe2', 'tpe3', 'author', 'albumartist',
        'composer', u'\uFFFDart'),
    'title': ('tit2', 'title', u'\uFFFDnam'),
    'track': ('trck', 'tracknumber'),
    'year': ('tdrc', 'tyer', 'date', 'year'),
    'genre': ('genre', 'tcon', 'providerstyle', u'\uFFFDgen'),
    'cover-art': ('\uFFFDart', 'apic', 'covr'),
}
NOFLATTEN_TAGS = ('cover-art',)


def image_directory(subdir):
    dir_ = os.path.join(app.config.get(prefs.ICON_CACHE_DIRECTORY), subdir)
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
        self.thumbnail_path = os.path.join(image_directory('extracted'),
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

class UnknownImageObjectException(Exception):
    """Image uses this when mutagen gives us something strange.
    """
    pass

class Image(object):
    """Utility class to represent a cover art image.
    Normalizes mutagen's various image objects into one class
    so that we can use them all the same way.
    """
    JPEG_EXTENSION = 'jpg'
    PNG_EXTENSION = 'png'
    # keep images of unknown formats; maybe we can use them later:
    UNKNOWN_EXTENSION = 'bin'
    MIME_EXTENSION_MAP = {
        'image/jpeg': JPEG_EXTENSION,
        'image/jpg': JPEG_EXTENSION,
        'image/png': PNG_EXTENSION,
    }
    def __init__(self, image_object):
        self.is_cover_art = True
        self.extension = Image.UNKNOWN_EXTENSION
        self.data = None
        if isinstance(image_object, mutagen.id3.APIC):
            self._parse_APIC(image_object)
        elif isinstance(image_object, mutagen.mp4.MP4Cover):
            self._parse_MP4(image_object)
        else:
            raise UnknownImageObjectException()

    def _parse_APIC(self, apic):
        COVER_ART_TYPE = 3
        if apic.type is not COVER_ART_TYPE:
            self.is_cover_art = False
        mime = apic.mime.lower()
        if not '/' in mime:
            # some files arbitrarily drop the 'image/' component
            mime = "image/{0}".format(mime)
        if mime in Image.MIME_EXTENSION_MAP:
            self.extension = Image.MIME_EXTENSION_MAP[mime]
        else:
            logging.warn("Unknown image mime type: %s", mime)
        self.data = apic.data

    def _parse_MP4(self, mp4):
        MP4_EXTENSION_MAP = {
            mutagen.mp4.MP4Cover.FORMAT_JPEG: Image.JPEG_EXTENSION,
            mutagen.mp4.MP4Cover.FORMAT_PNG: Image.PNG_EXTENSION,
        }
        if mp4.imageformat in MP4_EXTENSION_MAP:
            self.extension = MP4_EXTENSION_MAP[mp4.imageformat]
        else:
            logging.warn("Unknown MP4 image type code: %s", mp4.imageformat)
        self.data = str(mp4)

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
            cover_art = FilenameType("")
            file_info = self.read_metadata(mdi.item)
            (mime_mediatype, duration, metadata, cover_art) = file_info
            if duration > -1 and mime_mediatype is not 'video':
                mediatype = 'audio'
                screenshot = mdi.item.screenshot or FilenameType("")
                logging.debug("moviedata: mutagen %s %s", duration, mediatype)

                self.update_finished(mdi.item, duration, screenshot, mediatype,
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

                    self.update_finished(mdi.item, duration, screenshot,
                                         mediatype, metadata, cover_art)
                except StandardError:
                    if self.in_shutdown:
                        break
                    signals.system.failed_exn(
                        "When running external movie data program")
                    self.update_finished(mdi.item, -1, None, None, metadata,
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
        for mime in mimes:
            category = mime.split('/')[0]
            if category == 'video':
                return category
        for mime in mimes:
            category = mime.split('/')[0]
            if category == 'audio':
                return category
        return None

    def _sanitize_keys(self, tags):
        """Strip useless components and strange characters from tag names
        """
        tags_cleaned = {}
        for key, value in tags.items():
            if not isinstance(key, basestring):
                key = str(key)
            if isinstance(key , str):
                key = unicode(key, 'utf-8', 'replace')
            if key.startswith('PRIV:'):
                key = key.split('PRIV:')[1]
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
        for key, value in tags.items():
            while isinstance(value, list):
                if not value:
                    value = None
                    break
                value = value[0]
            if value:
                if not isinstance(value, basestring):
                    value = str(value)
                if isinstance(value, str):
                    value = unicode(value, 'utf-8', 'replace')
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

    def _make_cover_art_file(self, filename, objects):
        if not isinstance(objects, list):
            objects = [objects]

        images = []
        for image_object in objects:
            try:
               image = Image(image_object)
            except UnknownImageObjectException:
               logging.debug("Couldn't parse image object of type %s",
                             type(image_object))
            else:
               images.append(image)

        cover_image = None
        for candidate in images:
            if candidate.is_cover_art:
                cover_image = candidate
                break
        if cover_image is None:
            # no attached image is definitively cover art. use the first one.
            cover_image = images[0]

        cover_filename = "{0}.{1}.{2}".format(os.path.basename(filename),
                         util.random_string(5), image.extension)
        cover_path = os.path.join(image_directory('cover-art'), cover_filename)
        try:
            file_handle = fileutil.open_file(cover_path, 'wb')
            file_handle.write(image.data) 
        except IOError:
            logging.warn(
                "Couldn't write cover art file: {0}".format(cover_path))
            cover_path = None
        return cover_path
    
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
        except (AttributeError, IOError):
            return (mediatype, duration, data, cover_art)

        if os.path.splitext(
            item.get_filename())[1].lower() in VIDEO_EXTENSIONS:
            mediatype = 'video'
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

        for tag, sources in TAG_MAP.items():
            for source in sources:
                if source in tags:
                    if tag in NOFLATTEN_TAGS:
                        data[unicode(tag)] = nonflattened_tags[source]
                    else:
                        data[unicode(tag)] = tags[source]
                    break

        data = self._special_mappings(data, item)

        if 'cover-art' in data:
            image_data = data['cover-art']
            cover_art = self._make_cover_art_file(item.get_filename(), image_data)
            del data['cover-art']

        return (mediatype, duration, data, cover_art)

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
    def update_finished(self, item, duration, screenshot, mediatype, metadata,
                        cover_art):
        if item.id_exists():
            item.duration = duration
            item.screenshot = screenshot
            item.metadata = metadata
            item.cover_art = cover_art
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
