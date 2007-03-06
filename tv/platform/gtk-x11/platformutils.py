# Democracy Player - an RSS based video player application
# Copyright (C) 2005-2006 Participatory Culture Foundation
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

import os
import statvfs
import threading
import config
import prefs
import logging
import locale
import urllib
import sys
from util import returnsUnicode, returnsBinary, checkU, checkB

# We need to define samefile for the portable code.  Lucky for us, this is
# very easy.
from os.path import samefile

###############################################################################
#### Helper method used to get the free space on the disk where downloaded ####
#### movies are stored                                                     ####
###############################################################################

def getAvailableBytesForMovies():
    statinfo = os.statvfs (config.get(prefs.MOVIES_DIRECTORY))
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
        logging.basicConfig(level=logging.INFO,
                            format='%(levelname)-8s %(message)s',
                            stream=sys.stdout)
    else:
        logging.basicConfig(level=logging.DEBUG,
                            format='%(asctime)s %(levelname)-8s %(message)s',
                            filename=config.get(prefs.LOG_PATHNAME),
                            filemode="w")
        console = logging.StreamHandler (sys.stdout)
        console.setLevel(logging.INFO)
    
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

# Takes in a byte string or a unicode string and does the right thing
# to make a URL
@returnsUnicode
def makeURLSafe(string):
    if type(string) == str:
        # quote the byte string
        return urllib.quote(string).decode('ascii')
    else:
        try:
            return urllib.quote(string.encode(locale.getpreferredencoding())).decode('ascii')
        except:
            return string.decode('ascii','replace')
    
