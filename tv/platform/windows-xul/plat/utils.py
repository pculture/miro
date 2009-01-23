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

"""
Holds utility methods that are platform-specific.
"""

import ctypes
import _winreg
from miro import config
from miro import prefs
import os
import logging
import logging.handlers
from miro.plat import resources
import subprocess
import sys
import urllib
from miro.util import (returnsUnicode, returnsBinary, checkU, checkB, call_command,
        AutoflushingStream)
from miro import fileutil

localeInitialized = False
FilenameType = unicode

def samefile(path1, path2):
    return getLongPathName(path1) == getLongPathName(path2)

def getLongPathName(path):
    buf = ctypes.create_unicode_buffer(260) 
    GetLongPathName = ctypes.windll.kernel32.GetLongPathNameW
    rv = GetLongPathName(path, buf, 260)
    if rv == 0 or rv > 260:
        return path
    else:
        return buf.value

def get_available_bytes_for_movies():
    moviesDir = fileutil.expand_filename(config.get(prefs.MOVIES_DIRECTORY))
    freeSpace = ctypes.c_ulonglong(0)
    availableSpace = ctypes.c_ulonglong(0)
    totalSpace = ctypes.c_ulonglong(0)
    rv = ctypes.windll.kernel32.GetDiskFreeSpaceExW(unicode(moviesDir),
            ctypes.byref(availableSpace), ctypes.byref(totalSpace),
            ctypes.byref(freeSpace)) 
    if rv == 0:
        print "GetDiskFreeSpaceExW failed, returning bogus value!"
        return 100 * 1024 * 1024 * 1024
    return availableSpace.value

#############################################################################
# Windows specific locale                                                   #
#############################################################################
_langs = {
0x401: "ar",
0x416: "pt_BR",
0x804: "zh_CN", # Chinese simplified
0x404: "zh_TW", # Chinese traditional
0x405: "cs",
0x406: "da",
0x413: "nl",
#0x409: "en",  # This is the default. Don't bother with gettext in that case
0x40b: "fi",
0x40c: "fr",
0x407: "de",
0x408: "el",
0x40d: "he",
0x40e: "hu",
0x410: "it",
0x411: "jp",
0x412: "ko",
0x414: "nb",
0x415: "pl",
0x816: "pt",
0x419: "ru",
0xc0a: "es",
0x41D: "sv",
0x41f: "tr",
}

def _getLocale():
    code = ctypes.windll.kernel32.GetUserDefaultUILanguage()
    try:
        return _langs[code]

    # Hmmmmm, we don't know the language for this code
    except:
        return None

def initializeLocale():
    global localeInitialized
    lang = _getLocale()
    if lang:
        os.environ["LANGUAGE"] = lang
    localeInitialized = True

_loggingSetup = False
def setup_logging(inDownloader=False):
    global _loggingSetup
    if _loggingSetup:
        return

    if inDownloader:
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s %(levelname)-8s %(message)s',
                            stream=sys.stderr)
    else:
        logger = logging.getLogger('')
        logger.setLevel(logging.DEBUG)

        rotater = logging.handlers.RotatingFileHandler(config.get(prefs.LOG_PATHNAME), mode="w", maxBytes=500000, backupCount=5)
        rotater.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s')
        rotater.setFormatter(formatter)
        logging.getLogger('').addHandler(rotater)
        logging.info("=================================================")


    # Disable the xpcom log handlers.  This just means the log handler we
    # install at the root level will handle it instead.  The xpcom one
    # generates errors when it writes to stderr.
    xpcomLogger = logging.getLogger('xpcom')
    for handler in xpcomLogger.handlers[:]:
        xpcomLogger.removeHandler(handler)
    _loggingSetup = True

@returnsUnicode
def unicodeToFilename(filename, path = None):
    """Takes in a unicode string representation of a filename and creates a
    valid byte representation of it attempting to preserve extensions

    This is not guaranteed to give the same results every time it is run,
    not is it garanteed to reverse the results of filenameToUnicode
    """
    @returnsUnicode
    def shortenFilename(filename):
        checkU(filename)
        # Find the first part and the last part
        pieces = filename.split(u".")
        lastpart = pieces[-1]
        if len(pieces) > 1:
            firstpart = u".".join(pieces[:-1])
        else:
            firstpart = u""
        # If there's a first part, use that, otherwise shorten what we have
        if len(firstpart) > 0:
            return u"%s.%s" % (firstpart[:-1],lastpart)
        else:
            return filename[:-1]

    checkU(filename)
    if path:
        checkU(path)
    else:
        path = os.getcwd()

    # Keep this a little shorter than the max length, so we can run
    # nextFilename
    MAX_LEN = 200
    
    filename.replace('/','_').replace("\000","_").replace("\\","_").replace(":","_").replace("*","_").replace("?","_").replace("\"","_").replace("<","_").replace(">","_").replace("|","_")

    newFilename = filename
    while len(newFilename) > MAX_LEN:
        newFilename = shortenFilename(newFilename)

    return newFilename

@returnsUnicode
def filenameToUnicode(filename, path = None):
    """Given a filename in raw bytes, return the unicode representation

    Since this is not guaranteed to give the same results every time it is run,
    not is it garanteed to reverse the results of unicodeToFilename
    """
    if path:
        checkU(path)
    checkU(filename)
    return filename

def osFilenameToFilenameType(filename):
    """Takes filename given by the OS and turn it into a FilenameType
    where FilenameType is unicode.
    """
    # the filesystem encoding for Windows is "mbcs" so we have to
    # use that for decoding--can't use the default utf8
    try:
        return filename.decode(sys.getfilesystemencoding())
    except UnicodeDecodeError, ude:
        return filename.decode("utf-8")

def osFilenamesToFilenameTypes(filenames):
    """Takes an array of filenames given by the OS and turn them into a 
    FilenameTypes
    """
    return [osFilenameToFilenameType(filename) for filename in filenames]

def filenameTypeToOSFilename(filename):
    """Takes a FilenameType and turn it into something the OS accepts.
    """
    return filename

@returnsUnicode
def makeURLSafe(string, safe = '/'):
    """Takes in a byte string or a unicode string and does the right thing
    to make a URL
    """
    checkU(string)
    return urllib.quote(string.encode('utf_8'), safe=safe).decode('ascii')

@returnsUnicode
def unmakeURLSafe(string):
    """Undoes makeURLSafe
    """
    checkU(string)
    return urllib.unquote(string.encode('ascii')).decode('utf_8')

def killProcess(pid):
    # Kill the old process, if it exists
    if pid is not None:
        # This isn't guaranteed to kill the process, but it's likely the
        # best we can do
        # See http://support.microsoft.com/kb/q178893/
        # http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/347462
        PROCESS_TERMINATE = 1
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
        ctypes.windll.kernel32.TerminateProcess(handle, -1)
        ctypes.windll.kernel32.CloseHandle(handle)

def launchDownloadDaemon(oldpid, env):
    killProcess(oldpid)
    for key, value in env.items():
        os.environ[key] = value
    os.environ['DEMOCRACY_DOWNLOADER_LOG'] = \
            config.get(prefs.DOWNLOADER_LOG_PATHNAME)
    # Start the downloader.  We use the subprocess module to turn off the
    # console.  One slightly awkward thing is that the current process
    # might not have a valid stdin/stdout/stderr, so we create a pipe to
    # it that we never actually use.

    # Note that we use "Miro" instead of the app name here, so custom
    # versions will work

    # Note that the application filename has to be in double-quotes otherwise
    # it kicks up "%1 is not a valid Win32 application" errors on some Windows
    # machines.  Why it only happens on some is a mystery of the universe.
    # Bug #9274.
    downloaderPath = '"%s"' % os.path.join(resources.appRoot(),
            "Miro_Downloader.exe") 
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    subprocess.Popen(downloaderPath, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, 
            stdin=subprocess.PIPE,
            startupinfo=startupinfo)

def exit(returnCode):
    """Python's sys.exit isn't sufficient in a Windows application. It's not
    clear why.
    """
    ctypes.windll.kernel32.ExitProcess(returnCode)

def movie_data_program_info(movie_path, thumbnail_path):
    appname = config.get(prefs.SHORT_APP_NAME)
    exe_path = os.path.join(resources.appRoot(), '%s_MovieData.exe' % appname)
    cmd_line = (exe_path, movie_path, thumbnail_path)
    env = None
    return (cmd_line, env)
