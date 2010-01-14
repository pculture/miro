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

import threading
import os
import urllib
import statvfs
import logging
import logging.handlers
import sys
import time
import errno
import signal
import locale
import subprocess

from objc import NO, YES, nil
from Foundation import *
from AppKit import *

from miro import prefs
from miro import config
from miro.util import returns_unicode, returns_binary, check_u, check_b
from miro.plat.filenames import (os_filename_to_filename_type,
                                 filename_type_to_os_filename, FilenameType)
from miro.plat.frontends.widgets.threads import on_ui_thread

# We need to define samefile for the portable code.  Lucky for us, this is
# very easy.
from os.path import samefile

_locale_initialized = False

dlTask = None

def get_pyobjc_major_version():
    import objc
    version = objc.__version__
    version = version.split('.')
    return int(version[0])

###############################################################################
#### Helper method used to get the free space on the disk where downloaded ####
#### movies are stored                                                     ####
###############################################################################

def get_available_bytes_for_movies():
    pool = NSAutoreleasePool.alloc().init()
    fm = NSFileManager.defaultManager()
    movies_dir = config.get(prefs.MOVIES_DIRECTORY)
    if not os.path.exists(movies_dir):
        try:
            os.makedirs(movies_dir)
        except IOError:
            del pool
            return -1
    info = fm.fileSystemAttributesAtPath_(filenameToUnicode(movies_dir))
    if info:
        available = info[NSFileSystemFreeSize]
    else:
        available = -1
    del pool
    return available

def locale_initialized():
    return _locale_initialized

def initialize_locale():
    global _locale_initialized

    pool = NSAutoreleasePool.alloc().init()
    languages = list(NSUserDefaults.standardUserDefaults()["AppleLanguages"])
    try:
        pos = languages.index('en')
        languages = languages[:pos+1]
    except:
        pass

    if os.environ.get("MIRO_LANG"):
        os.environ["LANGUAGE"] = os.environ["MIRO_LANG"]
        os.environ["LANG"] = locale.normalize(os.environ["MIRO_LANG"])
    else:
        os.environ["LANGUAGE"] = ':'.join(languages)
        os.environ["LANG"] = locale.normalize(languages[0])

    _locale_initialized = True
    del pool

def setup_logging (inDownloader=False):
    if inDownloader:
        level = logging.INFO
        logging.basicConfig(level=level, format='%(levelname)-8s %(message)s')
        handler = logging.StreamHandler(sys.stdout)
        logging.getLogger('').addHandler(handler)
        logging.getLogger('').setLevel(level)
    else:
        level = logging.WARN
        if config.get(prefs.APP_VERSION).endswith("git"):
            level = logging.DEBUG
        logging.basicConfig(level=level, format='%(levelname)-8s %(message)s')
        rotater = logging.handlers.RotatingFileHandler(config.get(prefs.LOG_PATHNAME), mode="w", maxBytes=100000, backupCount=5)
        formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s')
        rotater.setFormatter(formatter)
        logging.getLogger('').addHandler(rotater)
        logging.getLogger('').setLevel(level)
        rotater.doRollover()

@returns_binary
def utf8_to_filename(filename):
    if not isinstance(filename, str):
        raise ValueError("filename is not a str")
    return filename

# Takes in a unicode string representation of a filename and creates a
# valid byte representation of it attempting to preserve extensions
#
# This is not guaranteed to give the same results every time it is run,
# not is it garanteed to reverse the results of filenameToUnicode
@returns_binary
def unicodeToFilename(filename, path = None):
    check_u(filename)
    if path:
        check_b(path)
    else:
        path = os.getcwd()

    # Keep this a little shorter than the max length, so we can run
    # nextFilename
    MAX_LEN = os.statvfs(path)[statvfs.F_NAMEMAX]-5

    filename.replace('/','_').replace("\000","_").replace("\\","_").replace(":","_").replace("*","_").replace("?","_").replace("\"","_").replace("<","_").replace(">","_").replace("|","_")

    newFilename = filename.encode('utf-8','replace')
    while len(newFilename) > MAX_LEN:
        filename = shortenFilename(filename)
        newFilename = filename.encode('utf-8','replace')

    return newFilename

@returns_unicode
def shortenFilename(filename):
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
        return u"%s.%s" % (firstpart[:-1],lastpart)
    else:
        return filename[:-1]

# Given a filename in raw bytes, return the unicode representation
#
# Since this is not guaranteed to give the same results every time it is run,
# not is it garanteed to reverse the results of unicodeToFilename
@returns_unicode
def filenameToUnicode(filename, path = None):
    if path:
        check_b(path)
    check_b(filename)
    return filename.decode('utf-8','replace')

@returns_unicode
def make_url_safe(string, safe='/'):
    """Takes in a byte string or a unicode string and does the right thing
    to make a URL
    """
    if type(string) == str:
        # quote the byte string
        return urllib.quote(string, safe=safe).decode('ascii')
    else:
        return urllib.quote(string.encode('utf-8','replace'), safe=safe).decode('ascii')

@returns_binary
def unmake_url_safe(string):
    """Undoes make_url_safe (assuming it was passed a filenameType)
    """
    # unquote the byte string
    check_u(string)
    return urllib.unquote(string.encode('ascii'))

# Load the image at source_path, resize it to [width, height] (and use
# letterboxing if source and destination ratio are different) and save it to
# dest_path
def resizeImage(source_path, dest_path, width, height):
    source_path = filename_type_to_os_filename(source_path)
    source = NSImage.alloc().initWithContentsOfFile_(source_path)
    jpegData = getResizedJPEGData(source, width, height)
    if jpegData is not None:
        dest_path = filename_type_to_os_filename(dest_path)
        destinationFile = open(dest_path, "w")
        try:
            destinationFile.write(jpegData)
        finally:
            destinationFile.close()

# Returns a resized+letterboxed version of image source as JPEG data.
def getResizedJPEGData(source, width, height):
    if source is None:
        return None

    sourceSize = source.size()
    sourceRatio = sourceSize.width / sourceSize.height
    destinationSize = NSSize(width, height)
    destinationRatio = destinationSize.width / destinationSize.height

    if sourceRatio > destinationRatio:
        size = NSSize(destinationSize.width, destinationSize.width / sourceRatio)
        pos = NSPoint(0, (destinationSize.height - size.height) / 2.0)
    else:
        size = NSSize(destinationSize.height * sourceRatio, destinationSize.height)
        pos = NSPoint((destinationSize.width - size.width) / 2.0, 0)

    destination = NSImage.alloc().initWithSize_(destinationSize)
    try:
        destination.lockFocus()
        NSGraphicsContext.currentContext().setImageInterpolation_(NSImageInterpolationHigh)
        NSColor.blackColor().set()
        NSRectFill(((0,0), destinationSize))
        source.drawInRect_fromRect_operation_fraction_((pos, size), ((0,0), sourceSize), NSCompositeSourceOver, 1.0)
    finally:
        destination.unlockFocus()

    tiffData = destination.TIFFRepresentation()
    imageRep = NSBitmapImageRep.imageRepWithData_(tiffData)
    properties = {NSImageCompressionFactor: 0.8}
    jpegData = imageRep.representationUsingType_properties_(NSJPEGFileType, properties)
    jpegData = str(jpegData.bytes())

    return jpegData

# Returns the major version of the OS we are currently running on
def getMajorOSVersion():
    versionInfo = os.uname()
    versionInfo = versionInfo[2].split('.')
    return int(versionInfo[0])

def pid_is_running(pid):
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError, err:
        return err.errno == errno.EPERM

def kill_process(pid):
    if pid is None:
        return
    if pid_is_running(pid):
        try:
            os.kill(pid, signal.SIGTERM)
            for i in xrange(100):
                time.sleep(.01)
                if not pid_is_running(pid):
                    return
            os.kill(pid, signal.SIGKILL)
        except:
            logging.exception ("error killing process")

@on_ui_thread
def launch_download_daemon(oldpid, env):
    kill_process(oldpid)

    env['DEMOCRACY_DOWNLOADER_LOG'] = config.get(prefs.DOWNLOADER_LOG_PATHNAME)
    env['VERSIONER_PYTHON_PREFER_32_BIT'] = "yes"
    env.update(os.environ)

    exe = NSBundle.mainBundle().executablePath()

    os_info = os.uname()
    os_version = int(os_info[2].split('.')[0])
    if os_version < 9:
        launch_path = exe
        launch_arguments = [u'download_daemon']
    else:
        arch = subprocess.Popen("arch", stdout=subprocess.PIPE).communicate()[0].strip()
        launch_path = '/usr/bin/arch'
        launch_arguments = ['-%s' % arch, exe, u'download_daemon']

    global dlTask
    dlTask = NSTask.alloc().init()
    dlTask.setLaunchPath_(launch_path)
    dlTask.setArguments_(launch_arguments)
    dlTask.setEnvironment_(env)

    controller = NSApplication.sharedApplication().delegate()
    nc = NSNotificationCenter.defaultCenter()
    nc.addObserver_selector_name_object_(controller, 'downloaderDaemonDidTerminate:', NSTaskDidTerminateNotification, dlTask)

    logging.info('Launching Download Daemon')
    dlTask.launch()

def ensureDownloadDaemonIsTerminated():
    # Calling dlTask.waitUntilExit() here could cause problems since we
    # cannot specify a timeout, so if the daemon fails to shutdown we could
    # wait here indefinitely. We therefore manually poll for a specific
    # amount of time beyond which we force quit the daemon.
    global dlTask
    if dlTask is not None:
        if dlTask.isRunning():
            logging.info('Waiting for the downloader daemon to terminate...')
            timeout = 5.0
            sleepTime = 0.2
            loopCount = int(timeout / sleepTime)
            for i in range(loopCount):
                if dlTask.isRunning():
                    time.sleep(sleepTime)
                else:
                    break
            else:
                # If the daemon is still alive at this point, it's likely to be
                # in a bad state, so nuke it.
                logging.info("Timeout expired - Killing downloader daemon!")
                dlTask.terminate()
        dlTask.waitUntilExit()
    dlTask = None

def exit(returnCode):
    NSApplication.sharedApplication().stop_(nil)

###############################################################################

def movie_data_program_info(moviePath, thumbnailPath):
    main_bundle = NSBundle.mainBundle()
    py_exe_path = os.path.join(os.path.dirname(main_bundle.executablePath()), 'python')
    rsrc_path = main_bundle.resourcePath()
    script_path = os.path.join(rsrc_path, 'qt_extractor.py')
    options = main_bundle.infoDictionary().get('PyOptions')
    env = None
    if options['alias'] == 1:
        env = {'PYTHONPATH': ':'.join(sys.path), 'MIRO_BUNDLE_PATH': main_bundle.bundlePath()}
    else:
        env = {'PYTHONHOME': rsrc_path, 'MIRO_BUNDLE_PATH': main_bundle.bundlePath()}
    return ((py_exe_path, script_path, moviePath, thumbnailPath), env)

###############################################################################

def qttime2secs(qttime):
    timeScale = qttimescale(qttime)
    if timeScale == 0:
        return 0.0
    timeValue = qttimevalue(qttime)
    return timeValue / float(timeScale)

def qttimescale(qttime):
    if isinstance(qttime, tuple):
        return qttime[1]
    else:
        return qttime.timeScale

def qttimevalue(qttime):
    if isinstance(qttime, tuple):
        return qttime[0]
    else:
        return qttime.timeValue

def qttimevalue_set(qttime, value):
    print qttime
    if isinstance(qttime, tuple):
        return(value, qttime[1], qttime[2])
    else:
        qttime.timeValue = value
        return qttime

###############################################################################
