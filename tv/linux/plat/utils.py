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

import errno
import signal
import os
import statvfs
import threading
from miro import app
from miro import prefs
import logging
import logging.handlers
import locale
import urllib
import sys
import time
from miro.util import returns_unicode, returns_binary, check_u, check_b
import miro
from miro.plat import options

from miro.gtcache import gettext as _

FilenameType = str

# We need to define samefile for the portable code.  Lucky for us, this is
# very easy.
from os.path import samefile

# this is used in lib/gtcache.py
_locale_initialized = False

def dirfilt(root, dirs):
    """
    Platform hook to filter out any directories that should not be
    descended into, root and dirs corresponds as per os.walk().
    """
    return dirs

def get_available_bytes_for_movies():
    """Helper method used to get the free space on the disk where downloaded
    movies are stored.

    If it errors out, returns 0.

    :returns: free disk space on drive for MOVIES_DIRECTORY as an int
    Returns an integer
    """
    movie_dir = app.config.get(prefs.MOVIES_DIRECTORY)

    if not os.path.exists(movie_dir):
        # FIXME - this is a bogus value.  need to "do the right thing"
        # here.
        return 0

    statinfo = os.statvfs(movie_dir)
    return statinfo.f_frsize * statinfo.f_bavail

def locale_initialized():
    """Returns whether or not the locale has been initialized.

    :returns: True or False regarding whether initialize_locale has been
        called.
    """
    return _locale_initialized

def initialize_locale():
    """Initializes the locale.
    """
    # gettext understands *NIX locales, so we don't have to do anything
    global _locale_initialized
    _locale_initialized = True

def setup_logging(in_downloader=False):
    """Sets up logging using the Python logging module.

    :param in_downloader: True if this is being called from the
        downloader daemon, False otherwise.
    """
    if in_downloader:
        if 'MIRO_IN_UNIT_TESTS' in os.environ:
            level = logging.WARN
        elif os.environ.get('MIRO_DEBUGMODE', "") == "True":
            level = logging.DEBUG
        else:
            level = logging.INFO
        logging.basicConfig(level=level,
                            format='%(asctime)s %(levelname)-8s %(message)s',
                            stream=sys.stdout)
        pathname = os.environ.get("DEMOCRACY_DOWNLOADER_LOG")
        if not pathname:
            return
    else:
        if app.debugmode:
            level = logging.DEBUG
        else:
            level = logging.INFO
        logging.basicConfig(level=level,
                            format='%(asctime)s %(levelname)-8s %(message)s')
        pathname = app.config.get(prefs.LOG_PATHNAME)

    try:
        rotater = logging.handlers.RotatingFileHandler(
            pathname, mode="w", maxBytes=100000,
            backupCount=5)
    except IOError:
        # bug 13338.  sometimes there's a file there and it causes
        # RotatingFileHandler to flip out when opening it.  so we
        # delete it and then try again.
        os.remove(pathname)
        rotater = logging.handlers.RotatingFileHandler(
            pathname, mode="w", maxBytes=100000,
            backupCount=5)
            
    formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s')
    rotater.setFormatter(formatter)
    logging.getLogger('').addHandler(rotater)
    rotater.doRollover()

@returns_binary
def utf8_to_filename(filename):
    """Converts a utf-8 encoded string to a FilenameType.
    """
    if not isinstance(filename, str):
        raise ValueError("filename is not a str")
    return filename

@returns_unicode
def shorten_fn(filename):
    check_u(filename)
    first, last = os.path.splitext(filename)

    if first:
        return u"".join([first[:-1], last])

    return unicode(last[:-1])

def encode_fn(filename):
    try:
        return filename.encode(locale.getpreferredencoding())
    except (SystemExit, KeyboardInterrupt):
        raise
    except:
        return filename.encode('ascii', 'replace')

@returns_binary
def unicode_to_filename(filename, path=None):
    """Takes in a unicode string representation of a filename (NOT a
    file path) and creates a valid byte representation of it
    attempting to preserve extensions.

    .. Note::

       This is not guaranteed to give the same results every time it
       is run, nor is it guaranteed to reverse the results of
       filename_to_unicode.
    """
    check_u(filename)
    if path:
        check_b(path)
    else:
        path = os.getcwd()

    # keep this a little shorter than the max length, so we can
    # add a number to the end
    max_len = os.statvfs(path)[statvfs.F_NAMEMAX] - 5

    for mem in ("/", "\000", "\\", ":", "*", "?", "\"", "'", "<", ">", "|", "&", "\r", "\n"):
        filename = filename.replace(mem, "_")

    new_filename = encode_fn(filename)

    while len(new_filename) > max_len:
        filename = shorten_fn(filename)
        new_filename = encode_fn(filename)

    return new_filename

@returns_unicode
def filename_to_unicode(filename, path=None):
    """Given a filename in raw bytes, return the unicode representation

    .. Note::

       This is not guaranteed to give the same results every time it
       is run, not is it guaranteed to reverse the results of
       unicode_to_filename.
    """
    if path:
        check_b(path)
    check_b(filename)
    try:
        return filename.decode(locale.getpreferredencoding())
    except (SystemExit, KeyboardInterrupt):
        raise
    except:
        return filename.decode('ascii', 'replace')

@returns_unicode
def make_url_safe(s, safe='/'):
    """Takes in a byte string or a unicode string and does the right thing
    to make a URL
    """
    if isinstance(s, str):
        # quote the byte string
        return urllib.quote(s, safe=safe).decode('ascii')

    try:
        return urllib.quote(s.encode(locale.getpreferredencoding()),
                            safe=safe).decode('ascii')
    except (SystemExit, KeyboardInterrupt):
        raise
    except:
        return s.decode('ascii', 'replace')

@returns_binary
def unmake_url_safe(s):
    """Undoes make_url_safe (assuming it was passed a FilenameType)
    """
    # unquote the byte string
    check_u(s)
    return urllib.unquote(s.encode('ascii'))

def _pid_is_running(pid):
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError, err:
        return err.errno == errno.EPERM

def kill_process(pid):
    """Kills the process with the given pid.
    """
    if pid is None:
        return
    if _pid_is_running(pid):
        try:
            os.kill(pid, signal.SIGTERM)
            for i in range(100):
                time.sleep(.01)
                if not _pid_is_running(pid):
                    return
            os.kill(pid, signal.SIGKILL)
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            logging.exception("error killing download daemon")

def launch_download_daemon(oldpid, env):
    """Launches the download daemon.

    :param oldpid: the pid of the previous download daemon
    :param env: the environment to launch the daemon in
    """
    # Use UNIX style kill
    if oldpid is not None and _pid_is_running(oldpid):
        kill_process(oldpid)

    environ = os.environ.copy()
    environ['MIRO_FRONTEND'] = options.frontend
    environ['DEMOCRACY_DOWNLOADER_LOG'] = app.config.get(prefs.DOWNLOADER_LOG_PATHNAME)
    environ['MIRO_APP_VERSION'] = app.config.get(prefs.APP_VERSION)
    environ['MIRO_DEBUGMODE'] = str(app.debugmode)
    if hasattr(miro.app, 'in_unit_tests'):
        environ['MIRO_IN_UNIT_TESTS'] = '1'
    environ.update(env)
    miro_path = os.path.dirname(miro.__file__)
    dl_daemon_path = os.path.join(miro_path, 'dl_daemon')

    # run the Miro_Downloader script
    script = os.path.join(dl_daemon_path, 'Democracy_Downloader.py')
    os.spawnle(os.P_NOWAIT, sys.executable, sys.executable, script, environ)

def exit_miro(return_code):
    """Exits Miro.
    """
    sys.exit(return_code)

def set_properties(props):
    """Sets a bunch of command-line specified properites.

    Linux only.

    :param props: a list of pref/value tuples
    """
    for pref, val in props:
        logging.info("Setting preference: %s -> %s", pref.alias, val)
        app.config.set(pref, val)

def movie_data_program_info(movie_path, thumbnail_path):
    """Returns the necessary information for Miro to run the media
    item info extractor program.

    The media item info extractor program takes a media item path and
    a path for where the thumbnail should go (if there is one) and
    returns information about the media item.

    Due to legacy reasons, this is called ``movie_data_program_info``,
    but it applies to audio items as well as video items.

    :returns: tuple of ``((python, script-path, movie-path, thumbnail-path),
        environment)``.  Environment is either a dict or None.
    """
    from miro import app
    return app.movie_data_program_info(movie_path, thumbnail_path)

def get_logical_cpu_count():
    """Returns the logical number of cpus on this machine.

    :returns: int
    """
    try:
        import multiprocessing
        return multiprocessing.cpu_count()
    except ImportError:
        ncpus = os.sysconf("SC_NPROCESSORS_ONLN")
        if isinstance(ncpus, int) and ncpus > 0:
            return ncpus
    return 1

def setup_ffmpeg_presets():
    # the linux distro should handle this
    pass

def get_ffmpeg_executable_path():
    """Returns the location of the ffmpeg binary.

    :returns: string
    """
    return app.config.get(options.FFMPEG_BINARY)

def customize_ffmpeg_parameters(params):
    """Takes a list of parameters and modifies it based on
    platform-specific issues.  Returns the newly modified list of
    parameters.

    :param params: list of parameters to modify

    :returns: list of modified parameters that will get passed to
        ffmpeg
    """
    return params

def get_ffmpeg2theora_executable_path():
    """Returns the location of the ffmpeg2theora binary.

    :returns: string
    """
    return app.config.get(options.FFMPEG2THEORA_BINARY)

def customize_ffmpeg2theora_parameters(params):
    """Takes a list of parameters and modifies it based on
    platform-specific issues.  Returns the newly modified list of
    parameters.

    :param params: list of parameters to modify

    :returns: list of modified parameters that will get passed to
        ffmpeg2theora
    """
    return params

def begin_thread_loop(context_object):
    # used for testing
    pass

def finish_thread_loop(context_object):
    # used for testing
    pass

# Expand me: pick up Linux media players.
def get_plat_media_player_name_path():
    return (None, None)
