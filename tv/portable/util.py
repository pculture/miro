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
import urllib
import socket
import logging
from miro import filetypes
import traceback
import subprocess
from StringIO import StringIO
from clock import clock

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

MAX_TORRENT_SIZE = 500 * (2**10) # 500k

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
        if ((os.path.basename(stack[i][0]) == 'signals.py'
             and stack[i][2] in ('system.failed', 'system.failed_exn'))):
            stack = stack[:i+1]
            break

    # remove trap_call calls
    stack = [i for i in stack if 'trap_call' in i]
    return stack


CONFIG_LINE_RE = re.compile(r"^([^ ]+) *= *([^\r\n]*)[\r\n]*$")

def read_simple_config_file(path):
    """Parse a configuration file in a very simple format and return contents
    as a dict.

    Each line is either whitespace or "Key = Value".  Whitespace is ignored
    at the beginning of Value, but the remainder of the line is taken
    literally, including any whitespace.

    Note: There is no way to put a newline in a value.
    """
    ret = {}

    filep = open(path, "rt")
    for line in filep.readlines():
        # Skip blank lines
        if not line.strip():
            continue

        # Otherwise it'd better be a configuration setting
        match = CONFIG_LINE_RE.match(line)
        if not match:
            print ("WARNING: %s: ignored bad configuration directive '%s'" %
                   (path, line))
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
    filep = open(path, "wt")

    for k, v in data.iteritems():
        filep.write("%s = %s\n" % (k, v))

    filep.close()

def query_revision():
    """Called at build-time to ask git for the revision of this
    checkout.

    Returns the (url, revision) on success and None on failure.
    """
    url = "unknown"
    revision = "unknown"
    try:
        proc = subprocess.Popen(["git", "config", "--list"],
                             stdout=subprocess.PIPE)
        info = proc.stdout.read().splitlines()
        proc.stdout.close()
        origline = "remote.origin.url"
        info = [m for m in info if m.startswith(origline)]
        if info:
            url = info[0][len(origline)+1:].strip()

        proc = subprocess.Popen(["git", "rev-parse", "HEAD"],
                             stdout=subprocess.PIPE)
        info = proc.stdout.read()
        proc.stdout.close()
        revision = info[0:8]
        return (url, revision)
    except StandardError, exc:
        print "Exception thrown when querying revision: %s" % exc
    return (url, revision)

class AutoFlushingStream:
    """Converts a stream to an auto-flushing one.  It behaves in
    exactly the same way, except all write() calls are automatically
    followed by a flush().
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
    """Create a stream that intercepts write calls and sends them to
    the log.
    """
    def __init__(self, logging_callback, prefix):
        StringIO.__init__(self)
        # We init from StringIO to give us a bunch of stream-related
        # methods, like closed() and read() automatically.
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
    if os.path.getsize(path) > MAX_TORRENT_SIZE:
        # file is too large, bailout.  (see #12301)
        raise ValueError("%s is not a valid torrent" % path)

    import libtorrent as lt
    f = open(path, 'rb')
    try:
        data = f.read()
        if data[0] != 'd':
            # File doesn't start with 'd', bailout  (see #12301)
            raise ValueError("%s is not a valid torrent" % path)
        metainfo = lt.bdecode(data)
        try:
            infohash = metainfo['info']
        except StandardError:
            raise ValueError("%s is not a valid torrent" % path)
        infohash = sha(lt.bencode(infohash)).digest()
        return infohash
    finally:
        f.close()

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

def format_size_for_user(nbytes, zero_string="", with_decimals=True,
                         kb_only=False):
    """Format an int containing the number of bytes into a string
    suitable for printing out to the user.

    zero_string is the string to use if bytes == 0.
    """
    from miro.gtcache import gettext as _
    if nbytes > (1 << 30) and not kb_only:
        value = (nbytes / (1024.0 * 1024.0 * 1024.0))
        if with_decimals:
            # we do the string composing this way so as to make it easier
            # on translators.
            return _("%(size)sGB", {"size": "%1.1f" % value})
        else:
            return _("%(size)sGB", {"size": "%d" % value})
    elif nbytes > (1 << 20) and not kb_only:
        value = (nbytes / (1024.0 * 1024.0))
        if with_decimals:
            return _("%(size)sMB", {"size": "%1.1f" % value})
        else:
            return _("%(size)sMB", {"size": "%d" % value})
    elif nbytes > (1 << 10):
        value = (nbytes / 1024.0)
        if with_decimals:
            return _("%(size)sKB", {"size": "%1.1f" % value})
        else:
            return _("%(size)sKB", {"size": "%d" % value})
    elif nbytes > 1:
        value = nbytes
        if with_decimals:
            return _("%(size)sB", {"size": "%1.1f" % value})
        else:
            return _("%(size)sB", {"size": "%d" % value})
    else:
        return zero_string

def clamp_text(text, max_length=20):
    if len(text) > max_length:
        return text[:max_length-3] + '...'
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
            # Item and FileItem share a db table, so we only need to
            # load one
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

def setup_logging():
    """Adds TIMING and JSALERT logging levels.
    """
    logging.addLevelName(15, "STACK TRACE")
    logging.stacktrace = lambda msg, *args, **kargs: logging.log(15, "%s\n%s" % ("".join(traceback.format_stack()), msg) , *args, **kargs)

    logging.addLevelName(25, "TIMING")
    logging.timing = lambda msg, *args, **kargs: logging.log(25, msg, *args, **kargs)
    logging.addLevelName(26, "JSALERT")
    logging.jsalert = lambda msg, *args, **kargs: logging.log(26, msg, *args, **kargs)

    logging.addLevelName(21, "DBLOG")
    logging.dblog = lambda msg, *args, **kargs: logging.log(21, msg, *args, **kargs)

class MiroUnicodeError(StandardError):
    """Returned when input to a template function isn't unicode
    """
    pass

def check_u(text):
    """Raise an exception if input isn't unicode
    """
    if text is not None and not isinstance(text, unicode):
        raise MiroUnicodeError(u"text %r is not a unicode string (type:%s)" %
                               (text, type(text)))

def returns_unicode(func):
    """Decorator that raised an exception if the function doesn't
    return unicode
    """
    def check_func(*args, **kwargs):
        result = func(*args, **kwargs)
        if result is not None:
            check_u(result)
        return result
    return check_func

def check_b(text):
    """Raise an exception if input isn't a binary string
    """
    if text is not None and not isinstance(text, str):
        raise MiroUnicodeError, (u"text \"%s\" is not a binary string" % text)

def returns_binary(func):
    """Decorator that raised an exception if the function doesn't
    return unicode
    """
    def check_func(*args, **kwargs):
        result = func(*args, **kwargs)
        if result is not None:
            check_b(result)
        return result
    return check_func

def check_f(text):
    """Returns exception if input isn't a filename type
    """
    from miro.plat.utils import FilenameType
    if text is not None and not isinstance(text, FilenameType):
        raise MiroUnicodeError, (u"text %r is not a valid filename type" %
                                 text)

def returns_filename(func):
    """Decorator that raised an exception if the function doesn't
    return a filename
    """
    def check_func(*args, **kwargs):
        result = func(*args, **kwargs)
        if result is not None:
            check_f(result)
        return result
    return check_func

def unicodify(data):
    """Turns all strings in data structure to unicode.
    """
    if isinstance(data, dict):
        for key, val in data.items():
            data[key] = unicodify(val)
    elif isinstance(data, list):
        for i, mem in enumerate(data):
            data[i] = unicodify(mem)
    elif isinstance(data, str):
        data = data.decode('ascii', 'replace')
    return data

def stringify(unicode_str, handleerror="xmlcharrefreplace"):
    """Takes a possibly unicode string and converts it to a string
    string.  This is required for some logging especially where the
    things being logged are filenames which can be Unicode in the
    Windows platform.

    You can pass in a handleerror argument which defaults to
    ``"xmlcharrefreplace"``.  This will increase the string size as it
    converts unicode characters that don't have ascii equivalents into
    escape sequences.  If you don't want to increase the string
    length, use ``"replace"`` which will use ? for unicode characters
    that don't have ascii equivalents.

    .. note::

       This is not the inverse of unicodify!
    """
    if isinstance(unicode_str, unicode):
        return unicode_str.encode("ascii", handleerror)
    if not isinstance(unicode_str, str):
        return str(unicode_str)
    return unicode_str

def quote_unicode_url(url):
    """Quote international characters contained in a URL according to
    w3c, see: <http://www.w3.org/International/O-URL-code.html>
    """
    check_u(url)
    quoted_chars = []
    for c in url.encode('utf8'):
        if ord(c) > 127:
            quoted_chars.append(urllib.quote(c))
        else:
            quoted_chars.append(c)
    return u''.join(quoted_chars)

def no_console_startupinfo():
    """Returns the startupinfo argument for subprocess.Popen so that
    we don't open a console window.  On platforms other than windows,
    this is just None.  On windows, it's some win32 silliness.
    """
    if subprocess.mswindows:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return startupinfo
    else:
        return None

def call_command(*args, **kwargs):
    """Call an external command.  If the command doesn't exit with
    status 0, or if it outputs to stderr, an exception will be raised.
    Returns stdout.
    """
    ignore_stderr = kwargs.pop('ignore_stderr', False)
    if kwargs:
        raise TypeError('extra keyword arguments: %s' % kwargs)

    pipe = subprocess.Popen(args, stdout=subprocess.PIPE,
            stdin=subprocess.PIPE, stderr=subprocess.PIPE,
            startupinfo=no_console_startupinfo())
    stdout, stderr = pipe.communicate()
    if pipe.returncode != 0:
        raise OSError("call_command with %s has return code %s\n"
                      "stdout:%s\nstderr:%s" %
                      (args, pipe.returncode, stdout, stderr))
    elif stderr and not ignore_stderr:
        raise OSError("call_command with %s outputed error text:\n%s" %
                      (args, stderr))
    else:
        return stdout

def random_string(length):
    return ''.join(random.choice(string.ascii_letters) for i in xrange(length))

def _get_enclosure_index(enc):
    maxindex = len(PREFERRED_TYPES_ORDER)
    return maxindex - PREFERRED_TYPES_ORDER.get(enc.get('type'), maxindex)

def _get_enclosure_size(enc):
    if 'filesize' in enc and enc['filesize'].isdigit():
        return int(enc['filesize'])
    else:
        return None

def _get_enclosure_bitrate(enc):
    if 'bitrate' in enc and enc['bitrate'].isdigit():
        return int(enc['bitrate'])
    else:
        return None

def cmp_enclosures(enc1, enc2):
    """Compares two enclosures looking for the best one (i.e.
    the one with the biggest values).

    Returns -1 if enclosure1 is preferred, 1 if enclosure2 is
    preferred, and zero if there is no preference between the two of
    them.
    """
    # media:content enclosures have an isDefault which we should pick
    # since it's the preference of the feed

    # if that's not there, then we sort by preference, bitrate, and
    # then size
    encdata1 = (enc1.get("isDefault"),
                _get_enclosure_index(enc1),
                _get_enclosure_bitrate(enc1),
                _get_enclosure_size(enc1))

    encdata2 = (enc2.get("isDefault"),
                _get_enclosure_index(enc2),
                _get_enclosure_bitrate(enc2),
                _get_enclosure_size(enc2))

    return cmp(encdata2, encdata1)

def get_first_video_enclosure(entry):
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


_default_encoding = "iso-8859-1" # aka Latin-1
_utf8cache = {}

def _to_utf8_bytes(s, encoding=None):
    """Takes a string and do whatever needs to be done to make it into
    a UTF-8 string. If a Unicode string is given, it is just encoded
    in UTF-8. Otherwise, if an encoding hint is given, first try to
    decode the string as if it were in that encoding; if that fails
    (or the hint isn't given), liberally (if necessary lossily)
    interpret it as _default_encoding.
    """
    try:
        return _utf8cache[(s, encoding)]
    except KeyError:
        pass

    result = None
    # If we got a Unicode string, half of our work is already done.
    if isinstance(s, unicode):
        result = s.encode('utf-8')
    elif not isinstance(s, str):
        s = str(s)
    if result is None and encoding is not None:
        # If we knew the encoding of the s, try that.
        try:
            decoded = s.decode(encoding, 'replace')
        except UnicodeDecodeError:
            pass
        else:
            result = decoded.encode('utf-8')
    if result is None:
        # Encoding wasn't provided, or it was wrong. Interpret
        # provided string liberally as a fixed _default_encoding (see
        # above.)
        result = s.decode(_default_encoding, 'replace').encode('utf-8')

    _utf8cache[(s, encoding)] = result
    return _utf8cache[(s, encoding)]

_unicache = {}
_escapecache = {}

def escape(str_):
    """Takes a string and returns a new unicode string with &, >, and
    < replaced by &amp;, &gt;, and &lt; respectively.
    """
    try:
        return _escapecache[str_]
    except KeyError:
        pass

    new_str = unicode(str_)
    for mem in [("&", "&amp;"),
                ("<", "&lt;"),
                (">", "&gt;")]:
        new_str = new_str.replace(mem[0], mem[1])
    _escapecache[str_] = new_str
    return new_str

def to_uni(orig, encoding=None):
    """Takes a stringish thing and returns the unicode version
    of it.

    If the stringish thing is already unicode, it returns it--no-op.

    If the stringish thing is a string, then it converts it to utf-8
    from the specified encoding, then turns it into a unicode.
    """
    if isinstance(orig, unicode):
        return orig

    try:
        return _unicache[orig]
    except KeyError:
        pass

    if isinstance(orig, str):
        orig = _to_utf8_bytes(orig, encoding)
        _unicache[orig] = unicode(orig, 'utf-8')
    else:
        _unicache[orig] = unicode(orig)
    return _unicache[orig]

import sgmllib

# replaces one or more non-newline whitespace characters
WHITESPACE_RE = re.compile("[ \\t]+", re.M)

# replaces one or more newline characters
NEWLINE_RE = re.compile("[ ]*\\n[ \\n]+", re.M)

# <xyz/> -> <xyz /> fix--sgmllib.SGMLParser doesn't handle these right
UNARY_RE = re.compile("\\<[ ]*([A-Za-z]+)[ ]*[/]?\\>", re.M)

class HTMLStripper(sgmllib.SGMLParser):
    """Strips html from text while maintaining links and newline-like HTML
    bits.

    This class resets itself after every ``strip`` call, so you can re-use
    the class if you want.  However, this class is not threadsafe.
    """
    def __init__(self):
        sgmllib.SGMLParser.__init__(self)
        self._temp = []
        self._data = ""
        self._pointer = 0
        self._links = []

    def strip(self, s):
        """Takes a string ``s`` and returns the stripped version.
        """
        if not isinstance(s, basestring):
            return ("", [])

        s = s.replace("\r\n", "\n")
        s = UNARY_RE.sub("<\\1 />", s)

        self.feed(s)
        self.close()

        try:
            self._flush()
            data, links = self._data, self._links
            data = data.rstrip()
        finally:
            self.reset()

        return data, links

    def reset(self):
        sgmllib.SGMLParser.reset(self)
        self._data = ""
        self._data = []
        self._pointer = 0
        self._links = []

    def _clean(self, s):
        s = WHITESPACE_RE.sub(" ", s)
        s = NEWLINE_RE.sub("\n", s)
        return s

    def _add(self, s):
        self._temp.append(s)

    def _flush(self):
        temp = self._clean("".join(self._temp))
        if not self._data:
            self._data = temp.lstrip()
        else:
            self._data += temp
        self._temp = []

    def handle_data(self, data):
        data = data.replace("\n", " ")
        self._add(data)

    def handle_charref(self, ref):
        if ref.startswith('x'):
            charnum = int(ref[1:], 16)
        else:
            charnum = int(ref)
        self._add(unichr(charnum))

    def start_p(self, attributes):
        self._add("\n")

    def end_p(self):
        self._add("\n")

    def start_br(self, attributes):
        self._add("\n")

    def end_br(self):
        self._add("\n")

    def start_a(self, attributes):
        for key, val in attributes:
            if key == "href":
                href = val
                break
        else:
            return

        self._flush()
        self._links.append((len(self._data), -1, href))

    def end_a(self):
        self._flush()
        if self._links and self._links[-1][1] == -1:
            beg, dummy, url = self._links[-1]
            self._links[-1] = (beg, len(self._data), url)

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
        return "\n".join([", ".join([repr(r)
                                     for r in list(self.row(i))])
                          for i in xrange(self.rows)])

    def remove(self, value):
        """This sets the value to None--it does NOT remove the cell
        from the Matrix because that doesn't make any sense.
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
    ]
    # FIXME: have a more general, charset-aware way to do this.
    for src, dest in replacements:
        text = text.replace(src, dest)
    return text

HTTP_HTTPS_MATCH_RE = re.compile(r"^(http|https)://[^/ ]+/[^ ]*$")

def is_url(url):
    """Returns True if this is URL-ish.
    """
    if not url:
        return False
    check_u(url)
    for c in url.encode('utf-8'):
        if ord(c) > 127:
            return False
    if HTTP_HTTPS_MATCH_RE.match(url) is not None:
        return True
    return False

LOWER_TRANSLATE = string.maketrans(string.ascii_uppercase,
                                   string.ascii_lowercase)

def ascii_lower(s):
    """Converts a string to lower case, using a simple translations of ASCII
    characters.

    This method is not locale-dependant, which is useful in some cases.
    Normally s.lower() should be used though.
    """
    return s.translate(LOWER_TRANSLATE)

class DebuggingTimer:
    def __init__(self):
        self.start_time = self.last_time = clock()

    def log_time(self, msg):
        current_time = clock()
        logging.timing("%s: %0.4f", msg, current_time - self.last_time)
        self.last_time = current_time

    def log_total_time(self):
        logging.timing("total time: %0.3f", clock() - self.start_time)
