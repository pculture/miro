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

"""util.py -- Utility functions.

This module contains self-contained utility functions.  It shouldn't import
any other Miro modules.
"""

import os
import random
import re
import sha
import string
import urllib
import socket
import logging
from miro import filetypes
import threading
import traceback
import subprocess


# Should we print out warning messages.  Turn off in the unit tests.
chatter = True

PREFERRED_TYPES = [
    'application/x-bittorrent',
    'application/ogg', 'video/ogg', 'audio/ogg',
    'video/mp4', 'video/quicktime', 'video/mpeg',
    'video/x-xvid', 'video/x-divx', 'video/x-wmv',
    'video/x-msmpeg', 'video/x-flv']


def get_nice_stack():
    """Get a stack trace that's a easier to read that the full one."""
    stack = traceback.extract_stack()
    # We don't care about the unit test lines
    while (len(stack) > 0
            and os.path.basename(stack[0][0]) == 'unittest.py'
            or (isinstance(stack[0][3], str)
                and stack[0][3].startswith('unittest.main'))):
        stack = stack[1:]

    # remove after the call to signals.system.failed
    for i in xrange(len(stack)):
        if (os.path.basename(stack[i][0]) == 'signals.py'
                and stack[i][2] in ('system.failed', 'system.failed_exn')):
            stack = stack[:i+1]
            break

    # remove trapCall calls
    stack = [i for i in stack if 'trapCall' in i]
    return stack

_config_line_re = re.compile(r"^([^ ]+) *= *([^\r\n]*)[\r\n]*$")

def read_simple_config_file(path):
    """Parse a configuration file in a very simple format and return contents
    as a dict.

    Each line is either whitespace or "Key = Value".  Whitespace is ignored
    at the beginning of Value, but the remainder of the line is taken
    literally, including any whitespace.

    Note: There is no way to put a newline in a value.
    """
    ret = {}

    f = open(path, "rt")
    for line in f.readlines():
        # Skip blank lines
        if not line.strip():
            continue

        # Otherwise it'd better be a configuration setting
        match = _config_line_re.match(line)
        if not match:
            print "WARNING: %s: ignored bad configuration directive '%s'" % (path, line)
            continue
        
        key = match.group(1)
        value = match.group(2)
        if key in ret:
            print "WARNING: %s: ignored duplicate directive '%s'" % (path, line)
            continue

        ret[key] = value

    return ret

def write_simple_config_file(path, data):
    """Given a dict, write a configuration file in the format that
    read_simple_config_file reads.
    """
    f = open(path, "wt")

    for k, v in data.iteritems():
        f.write("%s = %s\n" % (k, v))
    
    f.close()

def query_revision(fn):
    """Called at build-time to ask Subversion for the revision number of
    this checkout.  Going to fail without Cygwin. Yeah, oh well.  Pass the
    file or directory you want to use as a reference point.

    Returns the (url, revision) on success and None on failure.
    """
    try:
        # first try straight-up svn
        p = subprocess.Popen(["svn", "info", fn], stdout=subprocess.PIPE)
        info = p.stdout.read()
        p.stdout.close()
        url_match = re.search("URL: (.*)", info)
        # FIXME - this doesn't work on non English systems because the word
        # we're looking for will be in another language!
        revision_match = re.search("Revision: (.*)", info)

        # if that doesn't work, try git over svn.
        if not url_match:
            p = subprocess.Popen(["git", "svn", "info"], stdout=subprocess.PIPE)
            info = p.stdout.read()
            p.stdout.close()
            url_match = re.search("URL: (.*)", info)
            revision_match = re.search("Revision: (.*)", info)

        url = url_match.group(1).strip()
        revision = revision_match.group(1).strip()
        return (url, revision)
    except KeyboardInterrupt:
        raise
    except Exception, e:
        print "Exception thrown when querying revision: %s" % e

def failed_exn(when, **kwargs):
    """Shortcut for 'failed' with the exception flag.
    """
    failed(when, withExn=True, **kwargs)

def failed(when, withExn=False, details=None):
    """Puts up a dialog with debugging information encouraging the user to
    file a ticket.  (Also print a call trace to stderr or whatever, which
    hopefully will end up on the console or in a log.) 'when' should be
    something like "when trying to play a video."  The user will see
    it.

    If 'withExn' is true, last-exception information will be printed to.

    If 'detail' is true, it will be included in the report and the
    the console/log, but not presented in the dialog box flavor text.
    """
    logging.warn("util.failed is deprecated.  Use system.signals.failed\n"
            "stack:\n%s" % ''.join(traceback.format_stack()))
    from miro import signals
    signals.system.failed(when, withExn, details)

class AutoflushingStream:
    """Converts a stream to an auto-flushing one.  It behaves in exactly the
    same way, except all write() calls are automatically followed by a
    flush().
    """
    def __init__(self, stream):
        self.__dict__['stream'] = stream

    def write(self, data):
        if isinstance(data, unicode):
            data = data.encode('ascii', 'backslashreplace')
        self.stream.write(data)
        self.stream.flush()

    def __getattr__(self, name):
        return getattr(self.stream, name)

    def __setattr__(self, name, value):
        return setattr(self.stream, name, value)

def make_dummy_socket_pair():
    """Create a pair of sockets connected to each other on the local
    interface.  Used to implement SocketHandler.wakeup().
    """
    dummy_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    dummy_server.bind(('127.0.0.1', 0))
    dummy_server.listen(1)
    server_address = dummy_server.getsockname()
    first = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    first.connect(server_address)
    second, address = dummy_server.accept()
    dummy_server.close()
    return first, second

def get_torrent_info_hash(path):
    import miro.libtorrent as lt
    f = open(path, 'rb')
    try:
        data = f.read()
        metainfo = lt.bdecode(data)
        infohash = sha.sha(lt.bencode(metainfo['info'])).digest()
        return infohash
    finally:
        f.close()

class ExponentialBackoffTracker:
    """Utility class to track exponential backoffs."""
    def __init__(self, baseDelay):
        self.baseDelay = self.currentDelay = baseDelay
    def nextDelay(self):
        rv = self.currentDelay
        self.currentDelay *= 2
        return rv
    def reset(self):
        self.currentDelay = self.baseDelay

def gather_videos(path, progress_callback):
    """Gather movie files on the disk.  Used by the startup dialog.
    """
    from miro import prefs
    from miro import config
    keepGoing = True
    parsed = 0
    found = []
    try:
        for root, dirs, files in os.walk(path):
            for f in files:
                parsed = parsed + 1
                if filetypes.isVideoFilename(f):
                    found.append(os.path.join(root, f))
                if parsed > 1000:
                    adjustedParsed = int(parsed / 100.0) * 100
                elif parsed > 100:
                    adjustedParsed = int(parsed / 10.0) * 10
                else:
                    adjustedParsed = parsed
                keepGoing = progress_callback(adjustedParsed, len(found))
                if not keepGoing:
                    found = None
                    raise
            if config.get(prefs.SHORT_APP_NAME) in dirs:
                dirs.remove(config.get(prefs.SHORT_APP_NAME))
    except (SystemExit, KeyboardInterrupt):
        raise
    except:
        pass
    return found

def formatSizeForUser(bytes, zeroString="", withDecimals=True, kbOnly=False):
    """Format an int containing the number of bytes into a string suitable for
    printing out to the user.  zeroString is the string to use if bytes == 0.
    """
    from miro.gtcache import gettext as _
    if bytes > (1 << 30) and not kbOnly:
        value = (bytes / (1024.0 * 1024.0 * 1024.0))
        if withDecimals:
            # we do the string composing this way so as to make it easier
            # on translators.
            return _("%(size)sGB", {"size": "%1.1f" % value})
        else:
            return _("%(size)sGB", {"size": "%d" % value})
    elif bytes > (1 << 20) and not kbOnly:
        value = (bytes / (1024.0 * 1024.0))
        if withDecimals:
            return _("%(size)sMB", {"size": "%1.1f" % value})
        else:
            return _("%(size)sMB", {"size": "%d" % value})
    elif bytes > (1 << 10):
        value = (bytes / 1024.0)
        if withDecimals:
            return _("%(size)sKB", {"size": "%1.1f" % value})
        else:
            return _("%(size)sKB", {"size": "%d" % value})
    elif bytes > 1:
        value = bytes
        if withDecimals:
            return _("%(size)sB", {"size": "%1.1f" % value})
        else:
            return _("%(size)sB", {"size": "%d" % value})
    else:
        return zeroString

def clampText(text, maxLength=20):
    if len(text) > maxLength:
        return text[:maxLength-3] + '...'
    else:
        return text

def print_mem_usage(message):
    pass
# Uncomment for memory usage printouts on linux.
#    print message
#    os.system("ps huwwwp %d" % (os.getpid(),))

class TooManySingletonsError(Exception):
    pass

def getSingletonDDBObject(view):
    view.confirmDBThread()
    viewLength = view.len()
    if viewLength == 1:
        view.resetCursor()
        return view.next()
    elif viewLength == 0:
        raise LookupError("Can't find singleton in %s" % repr(view))
    else:
        msg = "%d objects in %s" % (viewLength, len(view))
        raise TooManySingletonsError(msg)

class ThreadSafeCounter:
    """Implements a counter that can be access by multiple threads."""
    def __init__(self, initialValue=0):
        self.value = initialValue
        self.lock = threading.Lock()

    def inc(self):
        self.lock.acquire()
        try:
            self.value += 1
        finally:
            self.lock.release()

    def dec(self):
        self.lock.acquire()
        try:
            self.value -= 1
        finally:
            self.lock.release()

    def getvalue(self):
        self.lock.acquire()
        try:
            return self.value
        finally:
            self.lock.release()

def setup_logging():
    logging.addLevelName(25, "TIMING")
    logging.timing = lambda msg, *args, **kargs: logging.log(25, msg, *args, **kargs)
    logging.addLevelName(26, "JSALERT")
    logging.jsalert = lambda msg, *args, **kargs: logging.log(26, msg, *args, **kargs)

class MiroUnicodeError(StandardError):
    """Returned when input to a template function isn't unicode
    """
    pass

def checkU(text):
    """Raise an exception if input isn't unicode
    """
    if text is not None and not isinstance(text, unicode):
        raise MiroUnicodeError(u"text %r is not a unicode string (type:%s)" % (text, type(text)))

def returnsUnicode(func):
    """Decorator that raised an exception if the function doesn't return unicode
    """
    def checkFunc(*args, **kwargs):
        result = func(*args, **kwargs)
        if result is not None:
            checkU(result)
        return result
    return checkFunc

def checkB(text):
    """Raise an exception if input isn't a binary string
    """
    if text is not None and not isinstance(text, str):
        raise MiroUnicodeError, (u"text \"%s\" is not a binary string" % text)

def returnsBinary(func):
    """Decorator that raised an exception if the function doesn't return unicode
    """
    def checkFunc(*args, **kwargs):
        result = func(*args, **kwargs)
        if result is not None:
            checkB(result)
        return result
    return checkFunc

def checkURL(text):
    """Raise an exception if input isn't a URL type
    """
    if not isinstance(text, unicode):
        raise MiroUnicodeError, (u"url \"%s\" is not unicode" % text)
    try:
        text.encode('ascii')
    except (SystemExit, KeyboardInterrupt):
        raise
    except:
        raise MiroUnicodeError, (u"url \"%s\" contains extended characters" % text)

def returnsURL(func):
    """Decorator that raised an exception if the function doesn't return a filename
    """
    def checkFunc(*args, **kwargs):
        result = func(*args, **kwargs)
        if result is not None:
            checkURL(result)
        return result
    return checkFunc

def checkF(text):
    """Returns exception if input isn't a filename type
    """
    from miro.plat.utils import FilenameType
    if text is not None and not isinstance(text, FilenameType):
        raise MiroUnicodeError, (u"text %r is not a valid filename type" %
                                     text)

def returnsFilename(func):
    """Decorator that raised an exception if the function doesn't return a filename
    """
    def checkFunc(*args, **kwargs):
        result = func(*args, **kwargs)
        if result is not None:
            checkF(result)
        return result
    return checkFunc

def unicodify(d):
    """Turns all strings in data structure to unicode.
    """
    if isinstance(d, dict):
        for key in d.keys():
            d[key] = unicodify(d[key])
    elif isinstance(d, list):
        for key in range(len(d)):
            d[key] = unicodify(d[key])
    elif isinstance(d, str):
        d = d.decode('ascii', 'replace')
    return d

def stringify(u, handleerror="xmlcharrefreplace"):
    """Takes a possibly unicode string and converts it to a string string.
    This is required for some logging especially where the things being
    logged are filenames which can be Unicode in the Windows platform.

    Note that this is not the inverse of unicodify.

    You can pass in a handleerror argument which defaults to "xmlcharrefreplace".
    This will increase the string size as it converts unicode characters that
    don't have ascii equivalents into escape sequences.  If you don't want to
    increase the string length, use "replace" which will use ? for unicode
    characters that don't have ascii equivalents.
    """
    if isinstance(u, unicode):
        return u.encode("ascii", handleerror)
    if not isinstance(u, str):
        return str(u)
    return u

def quoteUnicodeURL(url):
    """Quote international characters contained in a URL according to w3c, see:
    <http://www.w3.org/International/O-URL-code.html>
    """
    checkU(url)
    quotedChars = []
    for c in url.encode('utf8'):
        if ord(c) > 127:
            quotedChars.append(urllib.quote(c))
        else:
            quotedChars.append(c)
    return u''.join(quotedChars)

def no_console_startupinfo():
    """Returns the startupinfo argument for subprocess.Popen so that we don't
    open a console window.  On platforms other than windows, this is just
    None.  On windows, it's some win32 sillyness.
    """
    if subprocess.mswindows:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return startupinfo
    else:
        return None

def call_command(*args, **kwargs):
    """Call an external command.  If the command doesn't exit with status 0,
    or if it outputs to stderr, an exception will be raised.  Returns stdout.
    """
    ignore_stderr = kwargs.pop('ignore_stderr', False)
    if kwargs:
        raise TypeError('extra keyword arguments: %s' % kwargs)

    pipe = subprocess.Popen(args, stdout=subprocess.PIPE,
            stdin=subprocess.PIPE, stderr=subprocess.PIPE,
            startupinfo=no_console_startupinfo())
    stdout, stderr = pipe.communicate()
    if pipe.returncode != 0:
        raise OSError("call_command with %s has return code %s\nstdout:%s\nstderr:%s" % 
                (args, pipe.returncode, stdout, stderr))
    elif stderr and not ignore_stderr:
        raise OSError("call_command with %s outputed error text:\n%s" % 
                (args, stderr))
    else:
        return stdout

def random_string(length):
    return ''.join(random.choice(string.ascii_letters) for i in xrange(length))

def _get_enclosure_index(enclosure):
    try:
        return PREFERRED_TYPES.index(enclosure.get('type'))
    except ValueError:
        return None

def _get_enclosure_size(enclosure):
    if 'filesize' in enclosure and enclosure['filesize'].isdigit():
        return int(enclosure['filesize'])
    else:
        return None

def cmp_enclosures(enclosure1, enclosure2):
    """
    Returns:
      -1 if enclosure1 is preferred, 1 if enclosure2 is preferred, and
      zero if there is no preference between the two of them
    """
    # first let's try sorting by preference
    enclosure1_index = _get_enclosure_index(enclosure1)
    enclosure2_index = _get_enclosure_index(enclosure2)
    if enclosure1_index < enclosure2_index:
        return -1
    elif enclosure2_index < enclosure1_index:
        return 1

    # next, let's try sorting by filesize..
    enclosure1_size = _get_enclosure_size(enclosure1)
    enclosure2_size = _get_enclosure_size(enclosure2)
    if enclosure1_size > enclosure2_size:
        return -1
    elif enclosure2_size > enclosure1_size:
        return 1

    # at this point they're the same for all we care
    return 0

def getFirstVideoEnclosure(entry):
    """
    Find the first "best" video enclosure in a feedparser entry.
    Returns the enclosure, or None if no video enclosure is found.
    """
    try:
        enclosures = entry.enclosures
    except (KeyError, AttributeError):
        return None

    enclosures = [e for e in enclosures if filetypes.isVideoEnclosure(e)]
    if len(enclosures) == 0:
        return None

    enclosures.sort(cmp_enclosures)
    return enclosures[0]

def quoteattr(orig):
    orig = unicode(orig)
    return orig.replace(u'"', u'&quot;')


_default_encoding = "iso-8859-1" # aka Latin-1
_utf8cache = {}

def _to_utf8_bytes(s, encoding=None):
    """Takes a string and do whatever needs to be done to make it into a
    UTF-8 string. If a Unicode string is given, it is just encoded in
    UTF-8. Otherwise, if an encoding hint is given, first try to decode
    the string as if it were in that encoding; if that fails (or the
    hint isn't given), liberally (if necessary lossily) interpret it as
    _default_encoding.
    """
    try:
        return _utf8cache[(s, encoding)]
    except KeyError:
        result = None
        # If we got a Unicode string, half of our work is already done.
        if isinstance(s, unicode):
            result = s.encode('utf-8')
        elif not isinstance(s, str):
            s = str(s)
        if result is None and encoding is not None:
            # If we knew the encoding of the s, try that.
            try:
                decoded = s.decode(encoding,'replace')
            except (UnicodeDecodeError, ValueError, LookupError):
                pass
            else:
                result = decoded.encode('utf-8')
        if result is None:
            # Encoding wasn't provided, or it was wrong. Interpret provided string
            # liberally as a fixed _default_encoding (see above.)
            result = s.decode(_default_encoding, 'replace').encode('utf-8')

        _utf8cache[(s, encoding)] = result
        return _utf8cache[(s, encoding)]


_unicache = {}
_escapecache = {}

def escape(orig):
    orig = unicode(orig)
    try:
        return _escapecache[orig]
    except (SystemExit, KeyboardInterrupt):
        raise
    except:
        _escapecache[orig] = orig.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        return _escapecache[orig]

def toUni(orig, encoding=None):
    try:
        return _unicache[orig]
    except (SystemExit, KeyboardInterrupt):
        raise
    except:
        if isinstance(orig, unicode):
            # Let's not bother putting this in the cache.  Calculating
            # it is very fast, and since this is a very common case,
            # not caching here should help with memory usage.
            return orig
        elif not isinstance(orig, str):
            _unicache[orig] = unicode(orig)
        else:
            orig = _to_utf8_bytes(orig, encoding)
            _unicache[orig] = unicode(orig, 'utf-8')
        return _unicache[orig]

import sgmllib

class HTMLStripper(sgmllib.SGMLParser):
    """
    Strips html from text while maintaining links and newline-like HTML bits.
    """
    def __init__(self):
        sgmllib.SGMLParser.__init__(self)
        self.__temp = []
        self.__data = ""
        self.__pointer = 0
        self.__links = []

        # replaces one or more non-newline whitespace characters
        self.__whitespacere = re.compile("[ \\t]+", re.M)

        # replaces one or more newline characters
        self.__newlinere = re.compile("[ ]*\\n[ \\n]+", re.M)

        # <xyz/> -> <xyz /> fix--sgmllib.SGMLParser doesn't handle these right
        self.__unaryre = re.compile("\\<[ ]*([A-Za-z]+)[ ]*[/]?\\>", re.M)

    def strip(self, s):
        if "<" not in s:
            return (s.strip(), [])

        s = s.replace("\r\n", "\n")
        s = self.__unaryre.sub("<\\1 />", s)

        self.feed(s)
        self.close()

        try:
            self.__flush()
            data, links = self.__data, self.__links
            data = data.rstrip()
        finally:
            self.reset()

        return data, links

    def reset(self):
        sgmllib.SGMLParser.reset(self)
        self.__data = ""
        self.__data = []
        self.__pointer = 0
        self.__links = []

    def __clean(self, s):
        s = self.__whitespacere.sub(" ", s)
        s = self.__newlinere.sub("\n", s)
        return s

    def __add(self, s):
        self.__temp.append(s)

    def __flush(self):
        temp = self.__clean("".join(self.__temp))
        if not self.__data:
            self.__data = temp.lstrip()
        else:
            self.__data += temp
        self.__temp = []
 
    def handle_data(self, data):
        data = data.replace("\n", " ")
        self.__add(data)

    def handle_charref(self, ref):
        self.__add(unichr(int(ref)))

    def start_p(self, attributes):
        self.__add("\n")

    def end_p(self):
        self.__add("\n")

    def start_br(self, attributes):
        self.__add("\n")

    def end_br(self):
        self.__add("\n")

    def start_a(self, attributes):
        for key, val in attributes:
            if key == "href":
                href = val
                break
        else:
            return

        self.__flush()
        self.__links.append((len(self.__data), -1, href))

    def end_a(self):
        self.__flush()
        if self.__links and self.__links[-1][1] == -1:
            beg, _, url = self.__links[-1]
            self.__links[-1] = (beg, len(self.__data), url)

class Matrix(object):
    """2 Dimensional matrix.
    
    Matrix objects are accessed like a list, except tuples are used as
    indices, for example matrix[3,4] = foo
    """

    def __init__(self, columns, rows):
        self.columns = columns
        self.rows = rows
        self.data = [None] * (columns * rows)

    def __getitem__(self, key):
        return self.data[(key[0] * self.rows) + key[1]]

    def __setitem__(self, key, value):
        self.data[(key[0] * self.rows) + key[1]] = value

    def __iter__(self):
        return iter(self.data)

    def __repr__(self):
        return "\n".join([", ".join([repr(r) for r in list(self.row(i))]) for i in xrange(self.rows)])

    def remove(self, value):
        """This sets the value to None--it does NOT remove the cell from the
        Matrix because that doesn't make any sense.
        """
        i = self.data.index(value)
        self.data[i] = None

    def row(self, row):
        """Iterator that yields all the objects in a row."""
        for i in xrange(self.columns):
            yield self[i, row]

    def column(self, column):
        """Iterator that yields all the objects in a column."""
        for i in xrange(self.rows):
            yield self[column, i]
