###############################################################################
#### Helper method used to get the free space on the disk where downloaded ####
#### movies are stored                                                     ####
###############################################################################

import ctypes
import _winreg
import config
import prefs
import os
import logging
import sys
import urllib
from util import returnsUnicode, returnsBinary, checkU, checkB

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
    moviesDir = config.get(prefs.MOVIES_DIRECTORY)
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

def setupLogging (inDownloader=False):
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(levelname)-8s %(message)s',
                        stream = sys.stdout)

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
    checkU(string)
    return urllib.quote(string.encode('utf_16'), safe=safe).decode('ascii')

# Undoes makeURLSafe
@returnsUnicode
def unmakeURLSafe(string):
    checkU(string)
    return urllib.unquote(string.encode('ascii')).decode('utf_16')

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
    import shutil
    shutil.copyfile(source_path, dest_path)
