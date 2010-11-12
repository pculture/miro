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

from miro import app
from miro import prefs
from miro.gtcache import gettext as _
from miro.importmedia import import_itunes_path
from miro.util import returns_unicode, returns_binary, check_u, check_b
from miro.plat.filenames import (os_filename_to_filename_type,
                                 filename_type_to_os_filename, FilenameType)
from miro.plat.frontends.widgets.threads import on_ui_thread

# We need to define samefile for the portable code.  Lucky for us, this is
# very easy.
from os.path import samefile

_locale_initialized = False

dlTask = None

def dirfilt(root, dirs):
    """
    Platform hook to filter out any directories that should not be
    descended into, root and dirs corresponds as per os.dirwalk() and
    same semantics for these objects apply.
    """
    removelist = []
    ws = NSWorkspace.sharedWorkspace()
    for d in dirp:
        if ws.isFilePackageAtPath_(os.path.join(root, d)):
            removelist.append(d)
    for x in removelist:
        dirs.remove(x)
    return dirs

###############################################################################
#### Helper method used to get the free space on the disk where downloaded ####
#### movies are stored                                                     ####
###############################################################################

def get_available_bytes_for_movies():
    pool = NSAutoreleasePool.alloc().init()
    fm = NSFileManager.defaultManager()
    movies_dir = app.config.get(prefs.MOVIES_DIRECTORY)
    if not os.path.exists(movies_dir):
        try:
            os.makedirs(movies_dir)
        except IOError:
            del pool
            return -1
    info = fm.fileSystemAttributesAtPath_(filename_to_unicode(movies_dir))
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

    # XXX: FIXME - fixup the language environment variables.  Mac OS X returns
    # a list of these, mostly which we can use in setting the environment but
    # not always.  We do a manual fixup, for these edge cases there is no
    # 1:1 mapping and we do a best guess so we should try to find a better way
    # to do this.
    #
    # TODO:
    # some have Latn/Cyrl variants and I am not sure what to do here.  Seems
    # it is okay to just drop the variant and things will be okay.
    # es (Spanish) has a 419 variant, what's this?
    # Some may have iso639 codes only, what to do here? (not sure if this
    # list is complete)
    # nap - Neapolitan
    # gsw - Swiss German
    # scn - Sicilian
    # haw - Hawaiian
    # kok - Konkani
    # chr - Cherokee
    # tlh - Klingon (why??)
    def rewritelang(lang):
        # rewrite Chinese.
        if lang == 'zh-Hant':
            return 'zh_TW'
        if lang == 'zh-Hans':
            return 'zh_CN'
        # rewrite special case for Spanish.
        if '419' in lang:
            lang = 'es'
        # Rewrite cyrl/latn.
        if 'Cyrl' in lang or 'Latn' in lang:
            lang = lang[:2]
        # iso639 codes only - what to do here?
        if len(lang) == 3:
            pass
        # generic rewrite: e.g. fr-CA -> fr_CA
        return lang.replace('-', '_')

    languages = [rewritelang(x) for x in languages]
    if os.environ.get("MIRO_LANG"):
        os.environ["LANGUAGE"] = os.environ["MIRO_LANG"]
        os.environ["LANG"] = os.environ["MIRO_LANG"]
    else:
        os.environ["LANGUAGE"] = ':'.join(languages)

    _locale_initialized = True
    del pool

def setup_logging (in_downloader=False):
    if in_downloader:
        log_name = os.environ.get("DEMOCRACY_DOWNLOADER_LOG")
        level = logging.INFO
    else:
        log_name = app.config.get(prefs.LOG_PATHNAME)
        if app.config.get(prefs.APP_VERSION).endswith("git"):
            level = logging.DEBUG
        else:
            level = logging.WARN

    logging.basicConfig(level=level, format='%(levelname)-8s %(message)s')
    rotater = logging.handlers.RotatingFileHandler(
        log_name, mode="w", maxBytes=100000, backupCount=5)
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
# not is it guaranteed to reverse the results of filename_to_unicode
@returns_binary
def unicode_to_filename(filename, path = None):
    check_u(filename)
    if path:
        check_b(path)
    else:
        path = os.getcwd()

    # Keep this a little shorter than the max length, so we can run
    # nextFilename
    MAX_LEN = os.statvfs(path)[statvfs.F_NAMEMAX]-5

    for mem in ("/", "\000", "\\", ":", "*", "?", "'", "\"", "<", ">", "|", "&", "\r", "\n"):
        filename = filename.replace(mem, "_")

    new_filename = filename.encode('utf-8','replace')
    while len(new_filename) > MAX_LEN:
        filename = shortenFilename(filename)
        new_filename = filename.encode('utf-8','replace')

    return new_filename

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
# not is it guaranteed to reverse the results of unicode_to_filename.
@returns_unicode
def filename_to_unicode(filename, path = None):
    if path:
        check_b(path)
    check_b(filename)
    return filename.decode('utf-8', 'replace')

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

    env['DEMOCRACY_DOWNLOADER_LOG'] = app.config.get(prefs.DOWNLOADER_LOG_PATHNAME)
    env['VERSIONER_PYTHON_PREFER_32_BIT'] = "yes"
    env["MIRO_APP_VERSION"] = app.config.get(prefs.APP_VERSION)
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

def exit_miro(return_code):
    NSApplication.sharedApplication().stop_(nil)

###############################################################################

def movie_data_program_info(movie_path, thumbnail_path):
    main_bundle = NSBundle.mainBundle()
    bundle_path = main_bundle.bundlePath()
    rsrc_path = main_bundle.resourcePath()
    script_path = os.path.join(rsrc_path, 'qt_extractor.py')
    options = main_bundle.infoDictionary().get('PyOptions')
    env = None
    if options['alias'] == 1:
        py_exe_path = os.path.join(os.path.dirname(main_bundle.executablePath()), 'python')
        env = {'PYTHONPATH': ':'.join(sys.path), 'MIRO_BUNDLE_PATH': main_bundle.bundlePath()}
    else:
        py_version = main_bundle.infoDictionary().get('PythonInfoDict').get('PythonShortVersion')
        py_exe_path = os.path.join(main_bundle.privateFrameworksPath(), "Python.framework", "Versions", py_version, "bin", 'python')
        env = {'PYTHONHOME': rsrc_path, 'MIRO_BUNDLE_PATH': main_bundle.bundlePath()}
    # XXX
    # Unicode kludge.  This wouldn't be a problem once we switch to Python 3.
    # Only need to do conversion on the py_exe_path and script_path - 
    # movie_path and thumbnail_path are Python 2 strings.
    py_exe_path = py_exe_path.encode('utf-8')
    script_path = script_path.encode('utf-8')
    # ... et tu, environment variables.
    for k in env.keys():
        try:
            check_b(env[k])
        except:
            env[k] = env[k].encode('utf-8')
    return ((py_exe_path, script_path, movie_path, thumbnail_path), env)

###############################################################################

def get_ffmpeg_executable_path():
    bundle_path = NSBundle.mainBundle().bundlePath()
    # XXX Unicode kludge.  This wouldn't be a problem once we switch to 
    # Python 3.
    path = os.path.join(bundle_path, "Contents", "Helpers", "ffmpeg")
    return path.encode('utf-8')

def customize_ffmpeg_parameters(default_parameters):
    return default_parameters

def get_ffmpeg2theora_executable_path():
    bundle_path = NSBundle.mainBundle().bundlePath()
    # Unicode kludge.  This wouldn't be a problem once we switch to Python 3.
    path = os.path.join(bundle_path, "Contents", "Helpers", "ffmpeg2theora")
    return path.encode('utf-8')

def customize_ffmpeg2theora_parameters(default_parameters):
    return default_parameters
    
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
    if isinstance(qttime, tuple):
        return(value, qttime[1], qttime[2])
    else:
        qttime.timeValue = value
        return qttime

###############################################################################

def get_logical_cpu_count():
    try:
        import multiprocessing
        return multiprocessing.cpu_count()
    except ImportError, e:
        try:
            ncpus = os.sysconf("SC_NPROCESSORS_ONLN")
            if isinstance(ncpus, int) and ncpus > 0:
                return ncpus
        except:
            return int(os.popen2("sysctl -n hw.ncpu")[1].read())
    return 1

###############################################################################

def begin_thread_loop(context_object):
    if hasattr(context_object, 'autorelease_pool'):
        finish_thread_loop(context_object)
    context_object.autorelease_pool = NSAutoreleasePool.alloc().init()

def finish_thread_loop(context_object):
    del context_object.autorelease_pool

def get_plat_media_player_name_path():
    itunespath = os.path.join(os.path.expanduser("~"), "Music", "iTunes")
    return (_("iTunes"), import_itunes_path(itunespath))
