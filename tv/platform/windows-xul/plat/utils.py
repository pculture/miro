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

###############################################################################
#### Helper method used to get the free space on the disk where downloaded ####
#### movies are stored                                                     ####
###############################################################################

import ctypes
import _winreg
from miro import config
from miro import prefs
import os
import logging
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

def getAvailableBytesForMovies():
    # TODO: windows implementation
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
    except:  # Hmmmmm, we don't know the language for this code
        return None

def initializeLocale():
    global localeInitialized
    lang = _getLocale()
    if lang:
        os.environ["LANGUAGE"] = lang
    localeInitialized = True

_loggingSetup = False
def setupLogging (inDownloader=False):
    global _loggingSetup
    if _loggingSetup:
        return

    if not inDownloader:
        logFile = config.get(prefs.LOG_PATHNAME)
        logStream = open(logFile, "wt")
        sys.stdout = sys.stderr = AutoflushingStream(logStream)
    else:
        # If we're in the dwnloader sys.stdout and sys.stderr have already
        # been redirected
        logStream = sys.stderr
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(levelname)-8s %(message)s',
                        stream=logStream)
    
    # Disable the xpcom log handlers.  This just means the log handler we
    # install at the root level will handle it instead.  The xpcom one
    # generates errors when it writes to stderr.
    xpcomLogger = logging.getLogger('xpcom')
    for handler in xpcomLogger.handlers[:]:
        xpcomLogger.removeHandler(handler)
    _loggingSetup = True

# Takes in a unicode string representation of a filename and creates a
# valid byte representation of it attempting to preserve extensions
#
# This is not guaranteed to give the same results every time it is run,
# not is it garanteed to reverse the results of filenameToUnicode
@returnsUnicode
def unicodeToFilename(filename, path = None):
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

# Given a filename in raw bytes, return the unicode representation
#
# Since this is not guaranteed to give the same results every time it is run,
# not is it garanteed to reverse the results of unicodeToFilename
@returnsUnicode
def filenameToUnicode(filename, path = None):
    if path:
        checkU(path)
    checkU(filename)
    return filename

# Takes filename given by the OS and turn it into a FilenameType
# where FilenameType is unicode.
def osFilenameToFilenameType(filename):
    # the filesystem encoding for Windows is "mbcs" so we have to
    # use that for decoding--can't use the default utf8
    try:
        return filename.decode(sys.getfilesystemencoding())
    except UnicodeDecodeError, ude:
        return filename.decode("utf-8")

# Takes an array of filenames given by the OS and turn them into a FilenameTypes
def osFilenamesToFilenameTypes(filenames):
    return [osFilenameToFilenameType(filename) for filename in filenames]

# Takes a FilenameType and turn it into something the OS accepts.
def filenameTypeToOSFilename(filename):
    return filename

# Takes in a byte string or a unicode string and does the right thing
# to make a URL
@returnsUnicode
def makeURLSafe(string, safe = '/'):
    checkU(string)
    return urllib.quote(string.encode('utf_8'), safe=safe).decode('ascii')

# Undoes makeURLSafe
@returnsUnicode
def unmakeURLSafe(string):
    checkU(string)
    return urllib.unquote(string.encode('ascii')).decode('utf_8')

def resizeImage(source_path, dest_path, width, height):
    """Resize an image to a smaller size.
    
    Guidelines:

    Don't try to expand up the image.

    Don't change the aspect ratio

    The final image should be have the exact dimensions <width>X<height>.  If
    there is extra room, either because the source image was smaller
    specified, or because it had a different aspect ratio, pad out the image
    with black pixels.
    """
    convert_path = os.path.join(resources.appRoot(), 'imagemagick',
            'convert.exe')
    # From the "Pad Out Image" recipe at
    # http://www.imagemagick.org/Usage/thumbnails/
    border_width = max(width, height) / 2
    call_command(convert_path,  source_path, 
            "-strip",
            "-resize", "%dx%d>" % (width, height), 
            "-gravity", "center", "-bordercolor", "black",
            "-border", "%s" % border_width,
            "-crop", "%dx%d+0+0" % (width, height),
            "+repage", dest_path)

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

# Python's sys.exit isn't sufficient in a Windows application. It's not
# clear why.
# NEEDS: this is probably *not* what we want to do under XUL.
def exit(returnCode):
    ctypes.windll.kernel32.ExitProcess(returnCode)
