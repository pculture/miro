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
from miro.platform import options

FilenameType = str

# We need to define samefile for the portable code.  Lucky for us, this is
# very easy.
from os.path import samefile

###############################################################################
#### Helper method used to get the free space on the disk where downloaded ####
#### movies are stored                                                     ####
###############################################################################

def getAvailableBytesForMovies():
    dir = config.get(prefs.MOVIES_DIRECTORY)
    # Create the download directory if it doesn't already exist.
    try:
        os.makedirs(dir)
    except:
        pass
    
    statinfo = os.statvfs (dir)
    return statinfo.f_frsize * statinfo.f_bavail

main_thread = None
localeInitialized = True

def setMainThread():
    global main_thread
    main_thread = threading.currentThread()

def confirmMainThread():
    global main_thread
    if main_thread is not None and main_thread != threading.currentThread():
        import traceback
        print "UI function called from thread %s" % (threading.currentThread(),)
        traceback.print_stack()

# Gettext understands *NIX locales, so we don't have to do anything
def initializeLocale():
    pass

def setupLogging (inDownloader=False):
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
        console = logging.StreamHandler (sys.stdout)
        if options.frontend != 'cli':
            level = logging.INFO
        else:
            level = logging.WARN
        console.setLevel(level)
    
        formatter = logging.Formatter('%(levelname)-8s %(message)s')
        console.setFormatter(formatter)

        logging.getLogger('').addHandler(console)

# Takes in a unicode string representation of a filename and creates a
# valid byte representation of it attempting to preserve extensions
#
# This is not guaranteed to give the same results every time it is run,
# not is it garanteed to reverse the results of filenameToUnicode
@returnsBinary
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
        checkB(path)
    else:
        path = os.getcwd()

    # Keep this a little shorter than the max length, so we can run
    # nextFilename
    MAX_LEN = os.statvfs(path)[statvfs.F_NAMEMAX]-5
    
    filename.replace('/','_').replace("\000","_").replace("\\","_").replace(":","_").replace("*","_").replace("?","_").replace("\"","_").replace("<","_").replace(">","_").replace("|","_")
    try:
        newFilename = filename.encode(locale.getpreferredencoding())
    except:
        newFilename = filename.encode('ascii','replace')
    while len(newFilename) > MAX_LEN:
        filename = shortenFilename(filename)
        try:
            newFilename = filename.encode(locale.getpreferredencoding())
        except:
            newFilename = filename.encode('ascii','replace')

    return newFilename

# Given a filename in raw bytes, return the unicode representation
#
# SinceThis is not guaranteed to give the same results every time it is run,
# not is it garanteed to reverse the results of unicodeToFilename
@returnsUnicode
def filenameToUnicode(filename, path = None):
    if path:
        checkB(path)
    checkB(filename)
    try:
        return filename.decode(locale.getpreferredencoding())
    except:
        return filename.decode('ascii','replace')

# Takes filename given by the OS and turn it into a FilenameType
def osFilenameToFilenameType(filename):
    return FilenameType(filename)

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
    if type(string) == str:
        # quote the byte string
        return urllib.quote(string, safe = safe).decode('ascii')
    else:
        try:
            return urllib.quote(string.encode(locale.getpreferredencoding()), safe = safe).decode('ascii')
        except:
            return string.decode('ascii','replace')
    
# Undoes makeURLSafe (assuming it was passed a filenameType)
@returnsBinary
def unmakeURLSafe(string):
    # unquote the byte string
    checkU(string)
    return urllib.unquote(string.encode('ascii'))

@returnsBinary
def findConvert():
    global _convert_path_cache
    try:
        return _convert_path_cache
    except NameError:
        _convert_path_cache = None
        search_path = os.environ.get('PATH', os.defpath)
        for d in search_path.split(os.pathsep):
            convert_path = os.path.join(d, 'convert')
            if os.path.exists(convert_path):
                _convert_path_cache = convert_path
        return _convert_path_cache

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
    convert_path = findConvert()
    if convert_path == None:
        return
    # From the "Pad Out Image" recipe at
    # http://www.imagemagick.org/Usage/thumbnails/
    border_width = max(width, height) / 2
    # sometimes convert complains because our output filename doesn't match a
    # known image filetype.  It still converts the image though, so don't
    # worry about it.
    call_command(convert_path,  source_path, 
            "-strip",
            "-resize", "%dx%d>" % (width, height), 
            "-gravity", "center", "-bordercolor", "black",
            "-border", "%s" % border_width,
            "-crop", "%dx%d+0+0" % (width, height),
            "+repage", dest_path,
            ignore_stderr=True)

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
        except:
            logging.exception ("error killing download daemon")

def launchDownloadDaemon(oldpid, env):
    # Use UNIX style kill
    if oldpid is not None and pidIsRunning(oldpid):
        killProcess(oldpid)

    environ = os.environ.copy()
    environ['MIRO_FRONTEND'] = options.frontend
    environ.update(env)
    miroPath = os.path.dirname(miro.__file__)
    dlDaemonPath = os.path.join(miroPath, 'dl_daemon')

    # run the Miro_Downloader script
    script = os.path.join(dlDaemonPath,  'Democracy_Downloader.py')
    os.spawnlpe(os.P_NOWAIT, "python", "python", script, environ)

def exit(returnCode):
    sys.exit(returnCode)
