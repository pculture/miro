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

"""
Holds utility methods that are platform-specific.
"""

import ctypes
import _winreg
import os
import logging
from logging.handlers import RotatingFileHandler
import subprocess
import sys
import urllib
import sqlite3

from miro import app
from miro import prefs
from miro.gtcache import gettext as _
from miro.importmedia import import_itunes_path
from miro.plat import config as plat_config
from miro.plat import prelogger
from miro.plat import proxyfind
from miro.plat import resources
from miro.plat import specialfolders
from miro.plat.popen import Popen
from miro.plat.renderers import gst_extractor
from miro.util import returns_unicode, check_u
from miro.util import AutoLoggingStream
from miro import fileutil

_locale_initialized = False
PlatformFilenameType = unicode

def dirfilt(root, dirs):
    """
    Platform hook to filter out any directories that should not be
    descended into, root and dirs corresponds as per os.walk().
    """
    return dirs

def samefile(path1, path2):
    return get_long_path_name(path1) == get_long_path_name(path2)

def get_long_path_name(path):
    buf = ctypes.create_unicode_buffer(260)
    GetLongPathName = ctypes.windll.kernel32.GetLongPathNameW
    rv = GetLongPathName(path, buf, 260)
    if rv == 0 or rv > 260:
        return path
    else:
        return buf.value

def get_available_bytes_for_movies():
    movies_dir = fileutil.expand_filename(
        app.config.get(prefs.MOVIES_DIRECTORY))
    free_space = ctypes.c_ulonglong(0)
    available_space = ctypes.c_ulonglong(0)
    total_space = ctypes.c_ulonglong(0)
    rv = ctypes.windll.kernel32.GetDiskFreeSpaceExW(
        unicode(movies_dir),
        ctypes.byref(available_space), ctypes.byref(total_space),
        ctypes.byref(free_space))
    if rv == 0:
        print "GetDiskFreeSpaceExW failed, returning bogus value!"
        return 100 * 1024 * 1024 * 1024
    return available_space.value

########################################################################
# Windows specific locale                                              #
########################################################################
# see Language Identifier Constants and Strings (Windows):
# http://msdn.microsoft.com/en-us/library/dd318693%28VS.85%29.aspx
_langs = {
    0x401: "ar",
    0x404: "zh_TW", # Chinese traditional
    0x405: "cs",
    0x406: "da",
    0x407: "de",
    0x408: "el",
    0x409: "en",
    0x40b: "fi",
    0x40c: "fr",
    0x40d: "he",
    0x40e: "hu",
    0x410: "it",
    0x411: "jp",
    0x412: "ko",
    0x413: "nl",
    0x414: "nb",
    0x415: "pl",
    0x416: "pt_BR",
    0x419: "ru",
    0x41d: "sv",
    0x41f: "tr",
    0x804: "zh_CN", # Chinese simplified
    0x816: "pt",
    0xc0a: "es",
}

def _get_locale():
    # allows you to override the language using the MIRO_LANGUAGE
    # environment variable
    if os.environ.get("MIRO_LANGUAGE"):
        return os.environ["MIRO_LANGUAGE"]

    # see GetUserDefaultUILanguage Function:
    # http://msdn.microsoft.com/en-us/library/dd318137%28VS.85%29.aspx
    #
    # see User Interface Language Management (Windows):
    # http://msdn.microsoft.com/en-us/library/dd374098%28VS.85%29.aspx
    code = ctypes.windll.kernel32.GetUserDefaultUILanguage()
    try:
        return _langs[code]
    except KeyError:
        # we don't know the language for this code
        logging.warning("Don't know what locale to choose for code '%s' (%s)",
                        code, hex(code))
    return None

def locale_initialized():
    return _locale_initialized

def initialize_locale():
    global _locale_initialized
    lang = _get_locale()
    if lang is not None:
        os.environ["LANGUAGE"] = lang
    _locale_initialized = True

class ApatheticRotatingFileHandler(RotatingFileHandler):
    """The whole purpose of this class is to prevent rotation errors
    from percolating up into stdout/stderr and popping up a dialog
    that's not particularly useful to users or us.
    """
    def doRollover(self):
        # If you shut down Miro then start it up again immediately
        # afterwards, then we get in this squirrely situation where
        # the log is opened by another process.  We ignore the
        # exception, but make sure we have an open file.  (bug #11228)
        try:
            RotatingFileHandler.doRollover(self)
        except WindowsError:
            if not self.stream or self.stream.closed:
                self.stream = open(self.baseFilename, "a")
            try:
                RotatingFileHandler.doRollover(self)
            except WindowsError:
                pass

    def shouldRollover(self, record):
        # if doRollover doesn't work, then we don't want to find
        # ourselves in a situation where we're trying to do things on
        # a closed stream.
        if self.stream.closed:
            self.stream = open(self.baseFilename, "a")
        return RotatingFileHandler.shouldRollover(self, record)

    def handleError(self, record):
        # ignore logging errors that occur rather than printing them to
        # stdout/stderr which isn't helpful to us
        pass

FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
def setup_logging(in_downloader=False):
    if in_downloader:
        if 'MIRO_IN_UNIT_TESTS' in os.environ:
            level = logging.WARN
        elif os.environ.get('MIRO_DEBUGMODE', '') == True:
            level = logging.DEBUG
        else:
            level = logging.INFO
        logging.basicConfig(level=level,
                            format='%(asctime)s %(levelname)-8s %(message)s',
                            stream=sys.stderr)
        pathname = os.environ.get("DEMOCRACY_DOWNLOADER_LOG")
        if not pathname:
            return
    else:
        if app.debugmode:
            level = logging.DEBUG
        else:
            level = logging.INFO
        logging.basicConfig(level=level,
                            format=FORMAT)
        pathname = app.config.get(prefs.LOG_PATHNAME)

    rotater = ApatheticRotatingFileHandler(
        pathname, mode="a", maxBytes=100000, backupCount=5)

    formatter = logging.Formatter(FORMAT)
    rotater.setLevel(level)
    rotater.setFormatter(formatter)
    logger = logging.getLogger('')
    logger.addHandler(rotater)
    rotater.doRollover()
    try:
        for record in prelogger.remove():
            logger.handle(record)
    except ValueError:
        logging.debug("No records from prelogger.")

    if app.debugmode:
        stdouthandler = logging.StreamHandler(sys.stdout)
        stdouthandler.setLevel(level)
        stdouthandler.setFormatter(formatter)
        logger.addHandler(stdouthandler)
    else:
        sys.stdout = AutoLoggingStream(logging.warn, '(from stdout) ')
        sys.stderr = AutoLoggingStream(logging.error, '(from stderr) ')

    logging.info("Logging set up to %s at level %s", pathname, level)

@returns_unicode
def utf8_to_filename(filename):
    if not isinstance(filename, str):
        raise ValueError("filename is not a str")
    return filename.decode('utf-8', 'replace')

@returns_unicode
def unicode_to_filename(filename, path=None):
    """Takes in a unicode string representation of a filename and
    creates a valid byte representation of it attempting to preserve
    extensions

    This is not guaranteed to give the same results every time it is
    run, not is it garanteed to reverse the results of
    filename_to_unicode
    """
    @returns_unicode
    def shorten_filename(filename):
        check_u(filename)
        # Find the first part and the last part
        pieces = filename.split(u".")
        lastpart = pieces[-1]
        if len(pieces) > 1:
            firstpart = u".".join(pieces[:-1])
        else:
            firstpart = u""
        # If there's a first part, use that, otherwise shorten what we have
        if len(firstpart) > 0:
            return u"%s.%s" % (firstpart[:-1], lastpart)
        else:
            return filename[:-1]

    check_u(filename)
    if path:
        check_u(path)
    else:
        path = os.getcwd()

    # Keep this a little shorter than the max length, so we can run
    # nextFilename
    MAX_LEN = 200

    badchars = ('/', '\000', '\\', ':', '*', '?', "'", '"',
                '<', '>', '|', "\n", "\r")
    for mem in badchars:
        filename = filename.replace(mem, "_")

    new_filename = filename
    while len(new_filename) > MAX_LEN:
        new_filename = shorten_filename(new_filename)

    return new_filename

@returns_unicode
def filename_to_unicode(filename, path=None):
    """Given a filename in raw bytes, return the unicode
    representation.

    Since this is not guaranteed to give the same results every time
    it is run, not is it garanteed to reverse the results of
    unicode_to_filename.
    """
    if path:
        check_u(path)
    check_u(filename)
    return filename

@returns_unicode
def make_url_safe(string, safe='/'):
    """Takes in a byte string or a unicode string and does the right
    thing to make a URL
    """
    check_u(string)
    return urllib.quote(string.encode('utf_8'), safe=safe).decode('ascii')

@returns_unicode
def unmake_url_safe(string):
    """Undoes make_url_safe.
    """
    check_u(string)
    return urllib.unquote(string.encode('ascii')).decode('utf_8')

def kill_process(pid):
    """Kill the old process, if it exists.
    """
    if pid is not None:
        # This isn't guaranteed to kill the process, but it's likely
        # the best we can do See
        # http://support.microsoft.com/kb/q178893/
        # http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/347462
        try:
            PROCESS_TERMINATE = 1
            handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_TERMINATE, False, pid)
            ctypes.windll.kernel32.TerminateProcess(handle, -1)
            ctypes.windll.kernel32.CloseHandle(handle)
        except ValueError:
            logging.exception("problem killing process")

def launch_download_daemon(oldpid, env):
    kill_process(oldpid)

    # FIXME - wtf is going on here between os.environ, env and
    # environ?
    for key, value in env.items():
        os.environ[key] = value

    environ = os.environ.copy()
    environ['DEMOCRACY_DOWNLOADER_LOG'] = app.config.get(
        prefs.DOWNLOADER_LOG_PATHNAME)
    environ['MIRO_APP_VERSION'] = app.config.get(prefs.APP_VERSION)
    if hasattr(app, 'in_unit_tests'):
        environ['MIRO_IN_UNIT_TESTS'] = '1'
    environ.update(env)

    # start the downloader.  We use the subprocess module to turn off
    # the console.  One slightly awkward thing is that the current
    # process might not have a valid stdin/stdout/stderr, so we create
    # a pipe to it that we never actually use.

    # note that we use "Miro" instead of the app name here, so custom
    # versions will work

    downloader_path = (os.path.join(resources.app_root(),
                                   "Miro_Downloader.exe"),) 
    return Popen(downloader_path, stdout=subprocess.PIPE,
                 stderr=subprocess.PIPE,
                 stdin=subprocess.PIPE,
                 env=environ)

def exit_miro(return_code):
    """Python's sys.exit isn't sufficient in a Windows
    application. It's not clear why.
    """
    try:
        # this kicks up an access violation error.  not clear why.
        ctypes.windll.kernel32.ExitProcess(return_code)
    except WindowsError:
        pass

def run_media_metadata_extractor(movie_path, thumbnail_path):
    return gst_extractor.run(movie_path, thumbnail_path)

def get_logical_cpu_count():
    try:
        import multiprocessing
        return multiprocessing.cpu_count()
    except (NotImplementedError, ImportError):
        pass

    try:
        ncpus = int(os.environ.get("NUMBER_OF_PROCESSORS"));
        if ncpus > 0:
            return ncpus
    except (TypeError, ValueError):
        pass
    return 1

def get_segmenter_executable_path():
    return os.path.join(resources.app_root(), "miro-segmenter.exe")

def get_transcode_video_options():
    has_video_args = ['-vcodec', 'libx264', '-vpre', 'ipod320',
                      '-vpre', 'ultrafast', '-threads', '0', '-s', '480x360',
                      '-vbsf', 'h264_mp4toannexb']
    return has_video_args

def get_transcode_audio_options():
    # XXX: should we use libmp3lame?
    has_audio_args = ['-acodec', 'aac', '-strict', 'experimental',
                      '-threads', '0', '-ab', '96k']
    #has_audio_args = ['-acodec', 'libmp3lame', '-ab', '160k']
    return has_audio_args

def setup_ffmpeg_presets():
    os.environ['FFMPEG_DATADIR'] = resources.app_root()

def get_ffmpeg_executable_path():
    return os.path.join(resources.app_root(), "ffmpeg.exe")

def customize_ffmpeg_parameters(params):
    from miro.plat.specialfolders import get_short_path_name
    # look for -i input
    ind = params.index("-i")
    if ind != -1 and len(params) > ind + 2:
        params[ind+1] = get_short_path_name(params[ind+1])

    # FIXME - assumes the last item is {output}.
    # look at last item output
    params[-1] = get_short_path_name(params[-1])
    return params

def get_ffmpeg2theora_executable_path():
    return os.path.join(resources.app_root(), "ffmpeg2theora.exe")

def customize_ffmpeg2theora_parameters(params):
    from miro.plat.specialfolders import get_short_path_name
    # look for -o output
    ind = params.index("-o")
    if ind != -1 and len(params) > ind + 2:
        params[ind+1] = get_short_path_name(params[ind+1])

    # FIXME - assumes the last item is {input}.
    # look at last item input
    params[-1] = get_short_path_name(params[-1])
    return params

def begin_thread_loop(context_object):
    pass

def finish_thread_loop(context_object):
    pass

def get_cookie_path():
    """
    Returns the path to a Netscape-style cookie file for Curl to use.

    Nothing is written to this file, but we use the cookies for downloading
    from Amazon.
    """
    final_path = os.path.join(
        app.config.get(prefs.SUPPORT_DIRECTORY),
        'cookies.txt')

    sqlite_path = os.path.join(
        app.config.get(prefs.SUPPORT_DIRECTORY), 'profile',
        'cookies.sqlite')
    try:
        conn = sqlite3.connect(sqlite_path)
        cursor = conn.cursor()
        cursor = cursor.execute(
            'SELECT host, path, isSecure, expiry, name, value '
            'FROM moz_cookies')
        with file(final_path, 'w') as output:
            for (domain, path, is_secure,
                 expiry, name, value) in cursor.fetchall():
                output.write('%s\t%s\t%s\t%s\t%i\t%s\t%s\n' % (
                        domain.encode('utf8'),
                        domain[0] == '.' and 'TRUE' or 'FALSE',
                        path.encode('utf8'), is_secure and 'TRUE' or 'FALSE',
                        expiry, name.encode('utf8'), value.encode('utf8')))
        conn.close()
    except sqlite3.OperationalError:
        logging.exception('error creating cookies.txt')

    return final_path.encode('utf8') # has to be a string

def get_plat_media_player_name_path():
    music_path = specialfolders.get_special_folder("My Music")
    if music_path == None:
        # if specialfolders returns None, then My Music doesn't exist
        # so we return (None, None) indicating there's no media
        # player.

        # FIXME - can the iTunes folder be in another place?
        return (None, None)

    itunes_path = os.path.join(music_path, 'iTunes')
    return (_('iTunes'), import_itunes_path(itunes_path))

def miro_helper_program_info():
    cmd_line = (os.path.join(resources.app_root(), 'Miro_Helper.exe'),)
    env = None
    return (cmd_line, env)

def thread_body(func, *args, **kwargs):
    func(*args, **kwargs)

