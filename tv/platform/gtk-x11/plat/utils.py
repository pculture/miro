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

import errno
import signal
import os
import statvfs
import threading
from miro import config
from miro import prefs
import logging
import locale
import urllib
import sys
import time
from miro.util import returnsUnicode, returnsBinary, checkU, checkB, call_command
import miro
from miro.plat import options

FilenameType = str

# We need to define samefile for the portable code.  Lucky for us, this is
# very easy.
from os.path import samefile


# this is used in portable/gtcache.py
localeInitialized = True


def get_available_bytes_for_movies():
    """Helper method used to get the free space on the disk where downloaded
    movies are stored
    """
    d = config.get(prefs.MOVIES_DIRECTORY)

    if not os.path.exists(d):
        return 0

    statinfo = os.statvfs(dir_)
    return statinfo.f_frsize * statinfo.f_bavail


backend_thread = None

def set_backend_thread():
    global backend_thread
    backend_thread = threading.currentThread()

def confirm_backend_thread():
    if backend_thread is not None and backend_thread != threading.currentThread():
        import traceback
        print "backend function called from thread %s" % threading.currentThread()
        traceback.print_stack()

ui_thread = None

def set_ui_thread():
    global ui_thread
    ui_thread = threading.currentThread()

def confirm_ui_thread():
    if ui_thread is not None and ui_thread != threading.currentThread():
        import traceback
        print "ui function called from thread %s" % threading.currentThread()
        traceback.print_stack()


# gettext understands *NIX locales, so we don't have to do anything
def initializeLocale():
    pass

def setup_logging(inDownloader=False):
    if inDownloader:
        if os.environ.get('MIRO_FRONTEND') == 'cli':
            level = logging.WARN
        else:
            level = logging.INFO
        logging.basicConfig(level=level,
                            format='%(levelname)-8s %(message)s',
                            stream=sys.stdout)
    else:
        logging.basicConfig(level=logging.DEBUG,
                            format='%(asctime)s %(levelname)-8s %(message)s',
                            filename=config.get(prefs.LOG_PATHNAME),
                            filemode="w")
        console = logging.StreamHandler(sys.stdout)
        if config.get(prefs.APP_VERSION).endswith("svn"):
            level = logging.DEBUG
        elif options.frontend != 'cli':
            level = logging.INFO
        else:
            level = logging.WARN
        console.setLevel(level)

        formatter = logging.Formatter('%(levelname)-8s %(message)s')
        console.setFormatter(formatter)

        logging.getLogger('').addHandler(console)

@returnsBinary
def unicodeToFilename(filename, path=None):
    """Takes in a unicode string representation of a filename (NOT a file
    path) and creates a valid byte representation of it attempting to preserve
    extensions.

    Note: This is not guaranteed to give the same results every time it is run,
    nor is it garanteed to reverse the results of filenameToUnicode.
    """
    @returnsUnicode
    def shortenFilename(filename):
        checkU(filename)
        first, last = os.path.splitext(filename)

        if first:
            return u"".join(first[:-1], last)

        return last[:-1]

    checkU(filename)
    if path:
        checkB(path)
    else:
        path = os.getcwd()

    # Keep this a little shorter than the max length, so we can run
    # nextFilename
    max_len = os.statvfs(path)[statvfs.F_NAMEMAX]-5

    for mem in ("/", "\000", "\\", ":", "*", "?", "\"", "<", ">", "|", "&"):
        filename = filename.replace(mem, "_")

    def encodef(filename):
        try:
            return filename.encode(locale.getpreferredencoding())
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            return filename.encode('ascii', 'replace')

    new_filename = encodef(filename)

    while len(new_filename) > max_len:
        filename = shortenFilename(filename)
        new_filename = encodef(filename)

    return new_filename

@returnsUnicode
def filenameToUnicode(filename, path=None):
    """Given a filename in raw bytes, return the unicode representation

    Note: This is not guaranteed to give the same results every time it is run,
    not is it garanteed to reverse the results of unicodeToFilename.
    """
    if path:
        checkB(path)
    checkB(filename)
    try:
        return filename.decode(locale.getpreferredencoding())
    except (SystemExit, KeyboardInterrupt):
        raise
    except:
        return filename.decode('ascii', 'replace')

# Takes filename given by the OS and turn it into a FilenameType
def osFilenameToFilenameType(filename):
    return FilenameType(filename)

# Takes an array of filenames given by the OS and turn them into a FilenameTypes
def osFilenamesToFilenameTypes(filenames):
    return [osFilenameToFilenameType(filename) for filename in filenames]

# Takes a FilenameType and turn it into something the OS accepts.
def filenameTypeToOSFilename(filename):
    return filename

@returnsUnicode
def makeURLSafe(s, safe='/'):
    """Takes in a byte string or a unicode string and does the right thing
    to make a URL
    """
    if isinstance(s, str):
        # quote the byte string
        return urllib.quote(s, safe=safe).decode('ascii')
    else:
        try:
            return urllib.quote(s.encode(locale.getpreferredencoding()), safe=safe).decode('ascii')
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            return s.decode('ascii', 'replace')

@returnsBinary
def unmakeURLSafe(s):
    """Undoes makeURLSafe (assuming it was passed a filenameType)
    """
    # unquote the byte string
    checkU(s)
    return urllib.unquote(s.encode('ascii'))

_convert_path_cache = None

@returnsBinary
def findConvert():
    global _convert_path_cache

    if _convert_path_cache != None:
        return _convert_path_cache

    search_path = os.environ.get('PATH', os.defpath)
    for d in search_path.split(os.pathsep):
        convert_path = os.path.join(d, 'convert')
        if os.path.exists(convert_path):
            _convert_path_cache = convert_path
    return _convert_path_cache

def pidIsRunning(pid):
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError, err:
        return err.errno == errno.EPERM

def killProcess(pid):
    if pid is None:
        return
    if pidIsRunning(pid):
        try:
            os.kill(pid, signal.SIGTERM)
            for i in xrange(100):
                time.sleep(.01)
                if not pidIsRunning(pid):
                    return
            os.kill(pid, signal.SIGKILL)
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            logging.exception("error killing download daemon")

def launchDownloadDaemon(oldpid, env):
    # Use UNIX style kill
    if oldpid is not None and pidIsRunning(oldpid):
        killProcess(oldpid)

    environ = os.environ.copy()
    environ['MIRO_FRONTEND'] = options.frontend
    environ.update(env)
    miro_path = os.path.dirname(miro.__file__)
    dl_daemon_path = os.path.join(miro_path, 'dl_daemon')

    # run the Miro_Downloader script
    script = os.path.join(dl_daemon_path, 'Democracy_Downloader.py')
    os.spawnlpe(os.P_NOWAIT, "python", "python", script, environ)

def exit(return_code):
    sys.exit(return_code)

def set_properties(props):
    for p, val in props:
        logging.info("Setting preference: %s -> %s", p.alias, val)
        config.set(p, val)

def movie_data_program_info(moviePath, thumbnailPath):
    raise NotImplementedError()
