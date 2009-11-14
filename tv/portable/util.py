# Miro - an RSS based video player application
# Copyright (C) 2005-2009 Participatory Culture Foundation
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

"""``miro.util`` -- Utility functions.

This module contains self-contained utility functions.  It shouldn't import
any other Miro modules.
"""

import os
import random
import re
try:
    from hashlib import sha1 as sha
except ImportError:
    from sha import sha
import string
import sys
import urllib
import socket
import logging
from miro import filetypes
import threading
import traceback
import subprocess
from StringIO import StringIO


# Should we print out warning messages.  Turn off in the unit tests.
chatter = True

PREFERRED_TYPES = [
    'application/x-bittorrent',
    'application/ogg', 'video/ogg', 'audio/ogg',
    'video/mp4', 'video/quicktime', 'video/mpeg',
    'video/x-xvid', 'video/x-divx', 'video/x-wmv',
    'video/x-msmpeg', 'video/x-flv']

PREFERRED_TYPES_ORDER = dict((type, i) for i, type in
        enumerate(PREFERRED_TYPES))


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

    # remove trap_call calls
    stack = [i for i in stack if 'trap_call' in i]
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

def query_revision():
    """Called at build-time to ask git for the revision of this
    checkout.

    Returns the (url, revision) on success and None on failure.
    """
    url = "unknown"
    revision = "unknown"
    try:
        p = subprocess.Popen(["git", "config", "--list"], stdout=subprocess.PIPE)
        info = p.stdout.read().splitlines()
        p.stdout.close()
        origline = "remote.origin.url"
        info = [m for m in info if m.startswith(origline)]
        if info:
            url = info[0][len(origline)+1:].strip()

        p = subprocess.Popen(["git", "rev-parse", "HEAD"], stdout=subprocess.PIPE)
        info = p.stdout.read()
        p.stdout.close()
        revision = info[0:8]
        return (url, revision)
    except (SystemExit, KeyboardInterrupt):
        raise
    except Exception, e:
        print "Exception thrown when querying revision: %s" % e
    return None

class AutoFlushingStream:
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


class AutoLoggingStream(StringIO):
    """Create a stream that intercepts write calls and sends them to the log.
    """
    def __init__(self, logging_callback, prefix):
        StringIO.__init__(self)
        # We init from StringIO to give us a bunch of stream-related methods,
        # like closed() and read() automatically.
        self.logging_callback = logging_callback
        self.prefix = prefix

    def write(self, data):
        if isinstance(data, unicode):
            data = data.encode('ascii', 'backslashreplace')
        if data.endswith("\n"):
            data = data[:-1]
        if data:
            self.logging_callback(self.prefix + data)

def make_dummy_socket_pair():
    """Create a pair of sockets connected to each other on the local
    interface.  Used to implement SocketHandler.wakeup().

    On Unixish systems, port 0 will pick the next available port.
    But that appears to have problems on Windows possibly with
    firewall software.  So if we hit a socketerror with port 0, we
    try ports between 50000 and 65500.
    """
    port = 0
    while 1:
        try:
            dummy_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            dummy_server.bind(("127.0.0.1", port))
            dummy_server.listen(1)
            server_address = dummy_server.getsockname()
            first = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            first.connect(server_address)
            second, address = dummy_server.accept()
            dummy_server.close()
            return first, second
        except socket.error:
            # if we hit this, then it's hopeless--give up
            if port > 65500:
                raise
            # bump us into ephemeral ports if we need to try a bunch
            if port == 0:
                port = 50000
            port += 10

def get_torrent_info_hash(path):
    import libtorrent as lt
    f = open(path, 'rb')
    try:
        data = f.read()
        metainfo = lt.bdecode(data)
        try:
            infohash = metainfo['info']
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            raise ValueError("%s is not a valid torrent" % path)
        infohash = sha(lt.bencode(infohash)).digest()
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

def gather_media_files(path):
    """Gather media files on the disk in a directory tree.
    This is used by the first time startup dialog.

    path -- absolute file path to search
    """
    from miro import prefs
    from miro import config
    parsed = 0
    found = []
    short_app_name = config.get(prefs.SHORT_APP_NAME)
    for root, dirs, files in os.walk(path):
        for f in files:
            parsed = parsed + 1
            if filetypes.is_video_filename(f):
                found.append(os.path.join(root, f))

        if short_app_name in dirs:
            dirs.remove(short_app_name)

        if parsed > 1000:
            adjusted_parsed = int(parsed / 100.0) * 100
        elif parsed > 100:
            adjusted_parsed = int(parsed / 10.0) * 10
        else:
            adjusted_parsed = parsed

        yield adjusted_parsed, found

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
# Uncomment for memory usage printouts on Linux.
#    print message
#    os.system("ps huwwwp %d" % (os.getpid(),))

def db_mem_usage_test():
    from miro import models
    from miro.database import DDBObject
    last_usage = get_mem_usage()
    logging.info("baseline memory usage: %s", last_usage)
    for name in dir(models):
        ddb_object_class = getattr(models, name)
        try:
            if not issubclass(ddb_object_class, DDBObject):
                continue
        except TypeError:
            continue
        if name == 'FileItem':
            # Item and FileItem share a db table, so we only need to load one
            continue

        # make sure each object is loaded in memory and count the total
        count = len(list(ddb_object_class.make_view()))
        current_usage = get_mem_usage()
        class_usage = current_usage-last_usage
        if count == 0:
            count = 1 # prevent zero division errors
        logging.info("memory usage for %s: %s (%d bytes per object)",
                ddb_object_class.__name__, class_usage,
                class_usage * 1024 / count)
        last_usage = current_usage
    logging.info("total memory usage: %s", last_usage)
    logging.info("feed count: %s", models.Feed.make_view().count())
    logging.info("item count: %s", models.Item.make_view().count())

def get_mem_usage():
    return int(call_command('ps', '-o', 'rss', 'hp', str(os.getpid())))

class TooManySingletonsError(Exception):
    pass

def getSingletonDDBObject(view):
    view.confirm_db_thread()
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
        """Increments the value by 1."""
        self.lock.acquire()
        try:
            self.value += 1
        finally:
            self.lock.release()

    def dec(self):
        """Decrements the value by 1."""
        self.lock.acquire()
        try:
            self.value -= 1
        finally:
            self.lock.release()

    def getvalue(self):
        """Returns the current value."""
        self.lock.acquire()
        try:
            return self.value
        finally:
            self.lock.release()

def setup_logging():
    """Adds TIMING and JSALERT logging levels.
    """
    logging.addLevelName(15, "STACK TRACE")
    logging.stacktrace = lambda msg, *args, **kargs: logging.log(15, "%s\n%s" % ("".join(traceback.format_stack()), msg) , *args, **kargs)

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

    You can pass in a handleerror argument which defaults to
    ``"xmlcharrefreplace"``.  This will increase the string size as it
    converts unicode characters that don't have ascii equivalents into
    escape sequences.  If you don't want to increase the string length, use
    ``"replace"`` which will use ? for unicode characters that don't have
    ascii equivalents.

    .. note::

       This is not the inverse of unicodify!
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
    None.  On windows, it's some win32 silliness.
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
    return PREFERRED_TYPES_ORDER.get(enclosure.get('type'), sys.maxint)

def _get_enclosure_size(enclosure):
    if 'filesize' in enclosure and enclosure['filesize'].isdigit():
        return int(enclosure['filesize'])
    else:
        return -1

def _get_enclosure_bitrate(enclosure):
    if 'bitrate' in enclosure and enclosure['bitrate'].isdigit():
        return int(enclosure['bitrate'])
    else:
        return None

def cmp_enclosures(enclosure1, enclosure2):
    """
    Returns:
      -1 if enclosure1 is preferred, 1 if enclosure2 is preferred, and
      zero if there is no preference between the two of them
    """
    # meda:content enclosures have an isDefault which we should pick
    # since it's the preference of the feed
    if enclosure1.get("isDefault"):
        return -1
    if enclosure2.get("isDefault"):
        return 1

    # let's try sorting by preference
    enclosure1_index = _get_enclosure_index(enclosure1)
    enclosure2_index = _get_enclosure_index(enclosure2)
    if enclosure1_index < enclosure2_index:
        return -1
    elif enclosure2_index < enclosure1_index:
        return 1

    # next, let's try sorting by bitrate..
    enclosure1_bitrate = _get_enclosure_bitrate(enclosure1)
    enclosure2_bitrate = _get_enclosure_bitrate(enclosure2)
    if enclosure1_bitrate > enclosure2_bitrate:
        return -1
    elif enclosure2_bitrate > enclosure1_bitrate:
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

    enclosures = [e for e in enclosures if filetypes.is_video_enclosure(e)]
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
    """Strips html from text while maintaining links and newline-like HTML
    bits.

    This class resets itself after every ``strip`` call, so you can re-use
    the class if you want.  However, this class is not threadsafe.
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
        """Takes a string ``s`` and returns the stripped version.
        """
        if "<" not in s:
            return (s.strip(), [])

        s = s.replace("\r\n", "\n")
        s = self.__unaryre.sub("<\\1 />", s)

        try:
            self.feed(s)
            self.close()
        except:
            pass

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
        if ref.startswith('x'):
            charnum = int(ref[1:], 16)
        else:
            charnum = int(ref)
        self.__add(unichr(charnum))

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
    indices, for example:

    >>> m = Matrix(5, 5)
    >>> m[3, 4] = "foo"
    >>> m
    None, None, None, None, None
    None, None, None, None, None
    None, None, None, None, None
    None, None, None, None, None
    None, None, None, 'foo', None
    """

    def __init__(self, columns, rows, initial_value=None):
        self.columns = columns
        self.rows = rows
        self.data = [ initial_value ] * (columns * rows)

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

def entity_replace(text):
    replacements = [
            ('&#39;', "'"),
            ('&apos;', "'"),
            ('&#34;', '"'),
            ('&quot;', '"'),
            ('&#38;', '&'),
            ('&amp;', '&'),
            ('&#60;', '<'),
            ('&lt;', '<'),
            ('&#62;', '>'),
            ('&gt;', '>'),
    ] # FIXME: have a more general, charset-aware way to do this.
    for src, dest in replacements:
        text = text.replace(src, dest)
    return text

_lower_translate = string.maketrans(string.ascii_uppercase,
        string.ascii_lowercase)

def ascii_lower(str):
    """Converts a string to lower case, using a simple translations of ASCII
    characters.

    This method is not locale-dependant, which is useful in some cases.
    Normally str.lower() should be used though.
    """
    return str.translate(_lower_translate)
