#!/usr/bin/python

import logging 
import sys
import re
import time
import tempfile
import subprocess
import os.path

from miro import app
from miro import util
from miro import prefs
from miro import fileutil
from miro.plat.utils import movie_data_program_info
from miro.descriptions import File, DataSource, DataSourceStatus, Record
from miro.descriptions import CoverArt, MediaType, Duration

# Time in seconds that we wait for the utility to execute.  If it goes
# longer than this, we assume it's hung and kill it.
MOVIE_DATA_UTIL_TIMEOUT = 30

# Time to sleep while we're polling the external movie command
SLEEP_DELAY = 0.1

DURATION_RE = re.compile("Miro-Movie-Data-Length: (\d+)")
TYPE_RE = re.compile("Miro-Movie-Data-Type: (audio|video|other)")
THUMBNAIL_SUCCESS_RE = re.compile("Miro-Movie-Data-Thumbnail: Success")
TRY_AGAIN_RE = re.compile("Miro-Try-Again: True")

class MovieDataInfo(object):
    """Little utility class to keep track of data associated with each
    movie.  This is:

    * The path to the video.
    * Path to the thumbnail we're trying to make.
    * List of commands that we're trying to run, and their environments.
    """
    def __init__(self, path):
        self.video_path = path
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

class MovieDataUpdater(object):
    _mdp = None
    _status = None

    @classmethod
    def get_datasource(cls):
        if cls._mdp is None:
            cls._mdp = DataSource.with_values(
                    name=u'mdp', version=1, priority=90)
            cls._status = DataSourceStatus.with_values(
                    datasource=cls._mdp, description_type='File')
        return cls._mdp

    @classmethod
    def run_movie_data_program(cls, command_line, env):
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
        while pipe.poll() is None:
            time.sleep(SLEEP_DELAY)
            if time.time() - start_time > MOVIE_DATA_UTIL_TIMEOUT:
                logging.warning("Movie data process hung, killing it")
                MovieDataUpdater.kill_process(pipe)
                raise ProcessHung
        # FIXME: should we do anything with stderr?
        movie_data_stdout.seek(0)
        return movie_data_stdout.read()

    @staticmethod
    def parse_duration(stdout):
        duration_match = DURATION_RE.search(stdout)
        if duration_match:
            return int(duration_match.group(1))
        else:
            return None

    @staticmethod
    def parse_type(stdout):
        type_match = TYPE_RE.search(stdout)
        if type_match:
            return MediaType.TYPES.index(type_match.group(1))

    @staticmethod
    def parse_screenshot(stdout, mdi):
        if (THUMBNAIL_SUCCESS_RE.search(stdout) and
                fileutil.exists(mdi.thumbnail_path)):
            return mdi.thumbnail_path
        else:
            return None

    @classmethod
    def process(cls, file_):
        """Yield descriptions to apply to whatever LibraryItem has the given path."""
        # create a Record to document how and when the data was acquired
        record = Record(cls.get_datasource())

        mdi = MovieDataInfo(file_.path)
        command_line, env = mdi.program_info
        stdout = cls.run_movie_data_program(command_line, env)

        if not stdout:
            logging.debug("moviedata: error--no stdout: %s", stdout)

        if TRY_AGAIN_RE.search(stdout):
            # FIXME: we should try again at some point, but right now we just
            # ignore this
            pass

        duration = MovieDataUpdater.parse_duration(stdout)
        if duration is not None:
            yield Duration.with_values(record=record, milliseconds=duration)

        if os.path.splitext(mdi.video_path)[1] == '.flv':
            # bug #17266.  if the extension is .flv, we ignore the mediatype
            # we just got from the movie data program.  this is
            # specifically for .flv files which the movie data
            # extractors have a hard time with.
            mediatype = MediaType.VIDEO
        else:
            mediatype = MovieDataUpdater.parse_type(stdout)
        if mediatype is not None:
            yield MediaType.with_values(record=record, mediatype=mediatype)

        screenshot = MovieDataUpdater.parse_screenshot(stdout, mdi)
        if screenshot is not None:
            yield CoverArt.with_values(record=record, path=screenshot)

app.metadata_manager.add_provider(
        MovieDataUpdater.get_datasource(), File, MovieDataUpdater.process)
