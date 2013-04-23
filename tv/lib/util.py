# Miro - an RSS based video player application
# Copyright (C) 2005, 2006, 2007, 2008, 2009, 2010, 2011
# Participatory Culture Foundation
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

from hashlib import sha1 as sha
from StringIO import StringIO
import cgi
import collections
import contextlib
import itertools
import logging
import os
import random
import re
import shutil
import socket
import string
import signal
import struct
import subprocess
import sys
import tempfile
import traceback
import unicodedata
import urllib
import zipfile

from miro.clock import clock
from miro import filetypes
from miro.plat.popen import Popen

# Do NOT import libtorrent up here.  libtorrent.so is compiled with
# @executable_path-relative path dependency for the Python library
# within the Python framework.  This makes Miro.app invoke properly,
# but you cannot invoke the python command line interpreter (like
# we do with the metadata extractor) because the python executable
# has a different path to the Miro binary in Miro.app, and so when
# libtorrent tries to load Python shared library it fails.
#
# See bz:18370.

# Should we print out warning messages.  Turn off in the unit tests.
chatter = True

PREFERRED_TYPES = [
    'application/x-bittorrent',
    'application/ogg', 'video/ogg', 'audio/ogg',
    'video/mp4', 'video/quicktime', 'video/mpeg',
    'video/x-xvid', 'video/x-divx', 'video/x-wmv',
    'video/x-msmpeg', 'video/x-flv']

PREFERRED_TYPES_ORDER = dict((typ, i) for i, typ in
                             enumerate(PREFERRED_TYPES))

MAX_TORRENT_SIZE = 500 * (2**10) # 500k

def bitness():
    return struct.calcsize('L') * 8

def bits_32():
    return bitness() == 32

def bits_64():
    return bitness() == 64

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

    # remove after the call to crashreport.format_crash_report
    for i in xrange(len(stack)):
        if ((os.path.basename(stack[i][0]) == 'application.py'
            and stack[i][2] == 'handle_soft_failure')):
            stack = stack[:i]
            break

    # remove after the call to controller.failed_soft
    for i in xrange(len(stack)):
        if ((os.path.basename(stack[i][0]) == 'controller.py'
            and stack[i][2] == 'failed_soft')):
            stack = stack[:i]
            break

    # remove trap_call calls
    stack = [i for i in stack if 'trap_call' not in i]
    return stack

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

_use_ipv6 = None
def use_ipv6():
    """Should we use ipv6 for networking?"""

    global _use_ipv6
    if _use_ipv6 is None:
        if socket.has_ipv6:
            try:
                socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
                _use_ipv6 = True
            except socket.error:
                _use_ipv6 = False
        else:
            _use_ipv6 = False
    return _use_ipv6

def localhost_family_and_addr():
    """Returns the tuple (family, address) to use for the localhost.
    We only try to use ipv4 here - this is only used by Miro internally
    for the eventloop and prevents problems on hosts with (possibly)
    misconfigured ipv6 setup.
    """
    return (socket.AF_INET, '127.0.0.1')

def make_dummy_socket_pair():
    """Create a pair of sockets connected to each other on the local
    interface.  Used to implement SocketHandler.wakeup().

    On Unixish systems, port 0 will pick the next available port.
    But that appears to have problems on Windows possibly with
    firewall software.  So if we hit a socketerror with port 0, we
    try ports between 50000 and 65500.
    """
    attempts = 0
    port = 0
    family, addr = localhost_family_and_addr()
    while 1:
        attempts += 1
        try:
            dummy_server = socket.socket(family, socket.SOCK_STREAM)
            dummy_server.bind((addr, port))
            dummy_server.listen(1)
            server_address = dummy_server.getsockname()
            first = socket.socket(dummy_server.family, socket.SOCK_STREAM)
            first.connect(server_address)
            second, address = dummy_server.accept()
            dummy_server.close()
            return first, second
        except socket.error:
            # if we hit this, then it's hopeless--give up
            if port > 65500:
                sys.stderr.write(
                    ("Tried %s bind attempts and failed on "
                     "addr %s port %d\n") % (
                        attempts, addr, port))
                raise
            # bump us into ephemeral ports if we need to try a bunch
            if port == 0:
                port = 50000
            else:
                port += 10


def get_torrent_info_hash(path):
    """get_torrent_info_hash(path)

    NOTE: Important.  These OS functions can throw IOError or OSError.  Make
    sure you catch these in the caller.
    """
    if os.path.getsize(path) > MAX_TORRENT_SIZE:
        # file is too large, bailout.  (see #12301)
        raise ValueError("%s is not a valid torrent" % path)

    f = open(path, 'rb')
    try:
        import libtorrent
        data = f.read(MAX_TORRENT_SIZE)
        if not data or data[0] != 'd':
            # File doesn't start with 'd', bailout  (see #12301)
            raise ValueError("%s is not a valid torrent" % path)
        metainfo = libtorrent.bdecode(data)
        try:
            infohash = metainfo['info']
        except StandardError:
            raise ValueError("%s is not a valid torrent" % path)
        infohash = sha(libtorrent.bencode(infohash)).digest()
        return infohash
    finally:
        f.close()

def get_name_from_torrent_metadata(metadata):
    """Get the name of a torrent

    metadata must be the contents of a torrent file.

    :returns: torrent name unicode string
    :raises ValueError: metadata was not formatted properly
    """
    import libtorrent
    metadata_dict = libtorrent.bdecode(metadata)
    if metadata_dict is None:
        raise ValueError("metadata is not bencoded")
    try:
        return metadata_dict['info']['name'].decode('utf-8')
    except KeyError, e:
        raise ValueError("key missing when reading metadata: %s (%s)", e,
                         metadata_dict)
    except UnicodeError:
        raise ValueError("torrent name is not valid utf-8")

def gather_media_files(path):
    """Gather media files on the disk in a directory tree.
    This is used by the first time startup dialog.

    path -- absolute file path to search
    """
    from miro import prefs
    from miro import app
    from miro.plat.utils import dirfilt

    parsed = 0
    found = []
    short_app_name = app.config.get(prefs.SHORT_APP_NAME)
    for root, dirs, files in os.walk(path):
        for f in files:
            parsed = parsed + 1
            if (filetypes.is_video_filename(f) or
                filetypes.is_audio_filename(f)):
                found.append(os.path.join(root, f))

        if short_app_name in dirs:
            dirs.remove(short_app_name)

        # Filter out naughty directories on a platform-specific basis
        # that we never want to be parsing.  This is mainly useful on 
        # Mac OS X where we do not want to descend into file packages.  A bit
        # of a wart, long term solution is to write our own os.walk() shim 
        # that is platform aware cleanly but right now it's not worth the 
        # effort.
        dirfilt(root, dirs)

        if parsed > 1000:
            adjusted_parsed = int(parsed / 100.0) * 100
        elif parsed > 100:
            adjusted_parsed = int(parsed / 10.0) * 10
        else:
            adjusted_parsed = parsed

        yield adjusted_parsed, found

def gather_subtitle_files(movie_path):
    """Given an absolute path for a video file, this returns a list of
    filenames of sidecar subtitle file that are in the same directory
    or in a subtitles directory that are associated with the video
    file.

    >>> gather_subtitles_file('/tmp/foo.ogv')
    []
    >>> gather_subtitle_files('/tmp/bar.ogv')
    ['/tmp/bar.en.srt', '/tmp/bar.fr.srt']
    >>> gather_subtitle_files('/tmp/baz.ogv')
    ['/tmp/subtitles/baz.en.sub', '/tmp/subtitles/baz.fr.sub']
    """
    check_f(movie_path)
    subtitle_files = []
    if movie_path is None:
        return subtitle_files
    dirname, movie_file = os.path.split(movie_path)
    basename, ext = os.path.splitext(movie_file)

    # check for files in the current directory
    if os.path.exists(dirname):
        possible = [os.path.join(dirname, mem)
                    for mem in os.listdir(dirname)
                    if mem.startswith(basename)
                    and filetypes.is_subtitle_filename(mem)]
        if len(possible) > 0:
            subtitle_files.extend(possible)

    # check for files in the subtitles/ directory
    subdir = os.path.join(dirname, "subtitles")
    if os.path.exists(subdir):
        possible = [os.path.join(subdir, mem)
                    for mem in os.listdir(subdir)
                    if mem.startswith(basename)
                    and filetypes.is_subtitle_filename(mem)]
        if len(possible) > 0:
            subtitle_files.extend(possible)

    subtitle_files.sort()
    return subtitle_files

def copy_subtitle_file(sub_path, video_path):
    """Copies the subtitle file located at sub_path alongside the
    video file located at video_path.  It also changes the name
    so that the subtitle file follows the rules of sidecar files.

    Returns the path the subtitle file was copied to.
    """
    from miro import iso639
    
    sub_basename = os.path.basename(sub_path)
    match = re.match("(.*)(\....?)(\..*)", sub_basename)
    if match is not None:
        sub_basename_root = match.group(1)
        sub_language = match.group(2)
        sub_ext = match.group(3)
        if iso639.find(sub_language[1:]) is not None:
            sub_ext = sub_language + sub_ext
        else:
            sub_basename_root = sub_basename_root + sub_language
    else:
        sub_basename_root, sub_ext = os.path.splitext(sub_basename)

    video_basename = os.path.basename(video_path)
    video_basename_root, video_ext = os.path.splitext(video_basename)
    if sub_basename_root != video_basename_root:
        sub_basename = video_basename_root + sub_ext
    dest_path = os.path.join(os.path.dirname(video_path), sub_basename)
    if sub_path != dest_path:
        try:
            if os.path.exists(dest_path):
                os.remove(dest_path)
            shutil.copyfile(sub_path, dest_path)
        except EnvironmentError:
            logging.exception('unable to remove existing subtitle file '
                              'or copy subtitle file')
            dest_path = ''
    return dest_path

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
    """Clamps text to a maximum length and ...

    :param text: the string to clamp
    :param max_length: the maximum length for the text--minimum is 4.

    :returns: clamped text
    """
    if max_length < 4:
        max_length = 3
    if len(text) > max_length:
        return text[:max_length-3] + '...'
    else:
        return text

def db_mem_usage_test():
    from miro import models
    from miro.database import DDBObject
    last_usage = get_mem_usage()
    logging.debug("baseline memory usage: %s", last_usage)
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
        logging.debug("memory usage for %s: %s (%d bytes per object)",
                ddb_object_class.__name__, class_usage,
                class_usage * 1024 / count)
        last_usage = current_usage
    logging.debug("total memory usage: %s", last_usage)
    logging.debug("feed count: %s", models.Feed.make_view().count())
    logging.debug("item count: %s", models.Item.make_view().count())

def get_mem_usage():
    return int(call_command('ps', '-o', 'rss', 'hp', str(os.getpid())))

def setup_logging():
    """Adds TIMING and JSALERT logging levels.
    """
    logging.addLevelName(15, "STACK TRACE")
    def stacktrace(msg, *args, **kwargs):
        msg = "%s\n" + msg
        stack = "".join(traceback.format_stack())
        args = (stack,) + args
        logging.log( 15, msg, *args, **kwargs)
    logging.stacktrace = stacktrace

    logging.addLevelName(25, "TIMING")
    logging.timing = lambda msg, *args, **kargs: logging.log(25, msg,
                                                             *args, **kargs)
    logging.addLevelName(26, "JSALERT")
    logging.jsalert = lambda msg, *args, **kargs: logging.log(26, msg,
                                                              *args, **kargs)

    logging.addLevelName(21, "DBLOG")
    logging.dblog = lambda msg, *args, **kargs: logging.log(21, msg,
                                                            *args, **kargs)

class MiroUnicodeError(StandardError):
    """Returned when input to a template function isn't unicode
    """
    pass

def check_u(text):
    """Raises an exception if input isn't unicode
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
    check_func.__name__ = func.__name__
    check_func.__doc__ = func.__doc__
    return check_func

def check_b(text):
    """Raise an exception if input isn't a binary string
    """
    if text is not None and not isinstance(text, str):
        raise MiroUnicodeError(
            u"text \"%s\" is not a binary string (%r)" % (text, text))

def returns_binary(func):
    """Decorator that raises an exception if the function doesn't
    return unicode
    """
    def check_func(*args, **kwargs):
        result = func(*args, **kwargs)
        if result is not None:
            check_b(result)
        return result
    return check_func

def check_f(text):
    """Raises exception if input isn't a filename type
    """
    from miro.plat.utils import PlatformFilenameType
    if text is not None and not isinstance(text, PlatformFilenameType):
        raise MiroUnicodeError, (u"text %r is not a valid filename type" %
                                 text)

def returns_file(func):
    """Decorator that raises an exception if the function doesn't
    return a filename, file object
    """
    def check_func(*args, **kwargs):
        result = func(*args, **kwargs)
        try:
            filename, fileobj = result
            if result is not None and type(fileobj) != file:
                raise ValueError('returns_file: not a valid file object')
            check_f(filename)
        except ValueError:
            raise ValueError('returns_file: not a name, fileobj tuple')
        return result
    return check_func

def returns_filename(func):
    """Decorator that raises an exception if the function doesn't
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

def stringify(stringobj, handleerror="xmlcharrefreplace"):
    """Takes a possibly unicode string and converts it to a string
    string.  This is required for some logging especially where the
    things being logged are filenames which can be Unicode in the
    Windows platform.

    You can pass in a handleerror argument which defaults to
    ``'xmlcharrefreplace'``.  This will increase the string size as it
    converts unicode characters that don't have ascii equivalents into
    escape sequences.  If you don't want to increase the string
    length, use ``'replace'`` which will use ? for unicode characters
    that don't have ascii equivalents.

    .. note::

       This is not the inverse of unicodify!
    """
    if isinstance(stringobj, unicode):
        return stringobj.encode("ascii", handleerror)
    if isinstance(stringobj, str):
        # make sure bytestrings are ASCII
         return stringobj.decode('ascii', 'replace').encode('ascii',
                                                            'replace')
    else:
        # convert objects to strings, then ensure they are ASCII
        return stringify(str(stringobj))

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

def call_command(*args, **kwargs):
    """Call an external command.  If the command doesn't exit with
    status 0, or if it outputs to stderr, an exception will be raised.
    Returns stdout.

    :param ignore_stderr: boolean.  defaults to False.  If True and
        the command returns stderr, it's ignored rather than raising
        an exception.
    :param return_everything: boolean.  defaults to False.  If True,
        then this returns (retcode, stdout, stderr).  This implies
        ignore_stderr is True, so you don't need to explicitly state
        that, too.
    :param env: dict.  Environment to pass to subprocess.Popen
    """
    ignore_stderr = kwargs.pop('ignore_stderr', False)
    return_everything = kwargs.pop('return_everything', False)
    env = kwargs.pop('env', None)

    if kwargs:
        raise TypeError('extra keyword arguments: %s' % kwargs)

    pipe = Popen(args, stdout=subprocess.PIPE,
                 stdin=subprocess.PIPE, stderr=subprocess.PIPE,
                 env=env)
    stdout, stderr = pipe.communicate()
    if return_everything:
        return (pipe.returncode, stdout, stderr)
    elif pipe.returncode != 0:
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
    Find the first *best* video enclosure in a feedparser entry.

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
    if result is None and encoding is not None and not encoding == '':
        # If we knew the encoding of the s, try that.
        try:
            decoded = s.decode(encoding, 'replace')
        except (UnicodeDecodeError, LookupError):
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

        # if it's just white space, we skip all the work.
        if s.isspace():
            return (u"", [])

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
        try:
            if ref.startswith('x'):
                charnum = int(ref[1:], 16)
            else:
                charnum = int(ref)
        except ValueError:
            logging.warn("Error parsing charref: %s", ref, exc_info=True)
        else:
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
    >>> m[3, 4] = 'foo'
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

MAGNET_MATCH_RE = re.compile(r"^magnet:")

def is_magnet_uri(uri):
    """ Returns true if this is a magnet link
        which can be handled by Miro.
    """
    return bool(MAGNET_MATCH_RE.match(uri) and info_hash_from_magnet(uri))

MAGNET_INFO_HASH_MATCH = re.compile(r'(?<=btih:)[a-zA-Z0-9]+')

def info_hash_from_magnet(uri):
    """ Returns the magnet URIs bittorrent info hash if it has one.
    """
    m = MAGNET_INFO_HASH_MATCH.search(uri)
    if m:
        return m.group(0)
    else:
       return None

def title_from_magnet(uri):
    """Get the title from a magnet URI, or None if there is not one
    """
    try:
        query = uri[uri.find('?')+1:]
        query_parsed = cgi.parse_qs(query)
        if 'dn' in query_parsed:
            return query_parsed['dn'][0]
        else:
            return None
    except StandardError:
        logging.warn("Error parsing title from magnet URI", exc_info=True)

def _strip_accents(text):
    nfkd_form = unicodedata.normalize('NFKD', unicode(text))
    return u"".join([c for c in nfkd_form if not unicodedata.combining(c)])

NUM_RE = re.compile('([0-9]+\.?[0-9]*)')

def _trynum(text):
    try:
        return float(text)
    except ValueError:
        return _strip_accents(text)

def name_sort_key(text):
    """This is a sort key for names.  This handles sorting several
    situations:

    * names with accented characters.
    * names with numbers in them.  ex. episode 1
    * names with a leading "the" or "a"

    Use it like this:

    >>> listofnames.sort(key=lambda x: name_sort_key(x.name))
    """
    if text is None:
        # put blank entries on the bottom (#17357)
        return "ZZZZZZZZZZZZZ"
    text = text.lower()
    if text.startswith("a "):
        text = text[2:] + ', a'
    elif text.startswith("the "):
        text = text[4:] + ', the'
    return tuple(_trynum(c) for c in NUM_RE.split(text))

LOWER_TRANSLATE = string.maketrans(string.ascii_uppercase,
                                   string.ascii_lowercase)

def ascii_lower(s):
    """Converts a string to lower case, using a simple translations of
    ASCII characters.

    This method is not locale-dependant, which is useful in some
    cases.  Normally s.lower() should be used though.

    Note: This is not for ui stuff--this is for Python code-fu.
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

def mtime_invalidator(path):
    """
    Returns a function which returns True if the mtime of path is greater than
    it was when this function was initially called.  Useful as an invalidator
    for Cache.
    """
    path = os.path.abspath(path)
    try:
        mtime = os.stat(path).st_mtime
    except EnvironmentError:
        # if the file doesn't exist or has a problem when we start, the cache
        # will always be invalid
        return lambda x: True

    def invalidator(key):
        try:
            return os.stat(path).st_mtime > mtime
        except EnvironmentError:
            # if the file disappears, the cache is also invalid
            return True

    return invalidator

class Cache(object):
    def __init__(self, size):
        self.size = size
        self.dict = {}
        self.counter = itertools.count()
        self.access_times = {}
        self.invalidators = {}

    def get(self, key, invalidator=None):
        if key in self.dict:
            existing_invalidator = self.invalidators[key]
            if (existing_invalidator is None or
                not existing_invalidator(key)):
                self.access_times[key] = self.counter.next()
                return self.dict[key]

        value = self.create_new_value(key, invalidator=invalidator)
        self.set(key, value, invalidator=invalidator)
        return value

    def set(self, key, value, invalidator=None):
        if len(self.dict) == self.size:
            self.shrink_size()
        self.access_times[key] = self.counter.next()
        self.dict[key] = value
        self.invalidators[key] = invalidator

    def remove(self, key):
        if key in self.dict:
            del self.dict[key]
            del self.access_times[key]
        if key in self.invalidators:
            del self.invalidators[key]

    def keys(self):
        return self.dict.iterkeys()

    def shrink_size(self):
        # shrink by LRU
        to_sort = self.access_times.items()
        to_sort.sort(key=lambda m: m[1])
        new_dict = {}
        new_access_times = {}
        new_invalidators = {}
        latest_times = to_sort[len(self.dict) // 2:]
        for (key, time) in latest_times:
            new_dict[key] = self.dict[key]
            new_invalidators[key] = self.invalidators[key]
            new_access_times[key] = time
        self.dict = new_dict
        self.access_times = new_access_times

    def create_new_value(self, val, invalidator=None):
        raise NotImplementedError()

def all_subclasses(cls):
    """Find all subclasses of a given new-style class.

    This method also returns sub-subclasses, etc.
    """
    for subclass in cls.__subclasses__():
        yield subclass
        for sub_subclass in all_subclasses(subclass):
            yield sub_subclass

def import_module(module_name):
    """Import a module and return it.

    This function works like __import__, except it returns the last module
    named, rather than the first.  If you import 'foo.bar', __import__ will
    return foo, but import_module will return bar.
    """
    mod = __import__(module_name)
    parts = module_name.split('.')
    for part in parts[1:]:
        mod = getattr(mod, part)
    return mod

def make_file_url(path):
    """Get a file:// URL for a file path."""
    if isinstance(path, unicode):
        path = path.encode('utf-8')
    path_part = urllib.pathname2url(os.path.abspath(path))
    # On windows pathname2url adds a leading "///" to absolute paths.  This is
    # pretty weird and annoying, but easy to fix
    path_part = re.sub(r'^/+', '', path_part)
    # Always return str.  Pathname2url() returns a str and from that point
    # there are no unicode to infect us for a unicode type upgrade.
    return 'file:///' + path_part

def split_values_for_sqlite(value_list):
    """Split a list of values into chunks that SQL can handle.

    The cursor.execute() method can only handle 999 values at once, this
    method splits long lists into chunks where each chunk has is safe to feed
    to sqlite.
    """
    CHUNK_SIZE = 990 # use 990 just to be on the safe side.
    for start in xrange(0, len(value_list), CHUNK_SIZE):
        yield value_list[start:start+CHUNK_SIZE]


class SupportDirBackup(object):
    """Backup the support directory to send in a crash report."""
    def __init__(self, support_dir, skip_dirs, max_size):
        logging.info("Attempting to back up support directory: %r",
                     support_dir)
        backupfile_start = os.path.join(tempfile.gettempdir(),
                                        'miro-support-backup.zip')
        self.backupfile, fp = next_free_filename(backupfile_start)
        archive = zipfile.ZipFile(fp, "w")
        self.skip_dirs = [os.path.normpath(d) for d in skip_dirs]

        total_size = 0
        for root, directories, files in os.walk(support_dir):
            self.filter_directories(root, directories)
            relativeroot = os.path.relpath(root, support_dir)
            for fn in files:
                if self.should_skip_file(root, fn):
                    continue
                path = os.path.join(root, fn)
                if relativeroot != '.':
                    relpath = os.path.join(relativeroot, fn)
                else:
                    relpath = fn
                relpath = self.ensure_ascii_filename(relpath)
                archive.write(path, relpath)
                total_size += archive.getinfo(relpath).compress_size
                if total_size >= max_size:
                    break
            if total_size >= max_size:
                logging.warn("Support directory backup too big.  "
                             "Quitting after %s bytes", total_size)
                break
        archive.close()
        logging.info("Support directory backed up to %s (%d bytes)",
                     self.backupfile, os.path.getsize(self.backupfile))

    def filter_directories(self, root, directories):
        """Remove directories from the list that os.walk() passes us."""
        filtered = [d for d in directories
                    if not self.should_skip_directory(os.path.join(root, d))]
        # os.walk() wants us to change directories in-place
        directories[:] = filtered

    def should_skip_directory(self, directory):
        for skip_dir in self.skip_dirs:
            if directory.startswith(skip_dir):
                return True
        return False

    def should_skip_file(self, directory, filename):
        if os.path.islink(os.path.join(directory, filename)):
            return True
        if filename == 'httpauth':
            # don't send http passwords over the internet
            return True
        if filename == 'preferences.bin':
            # On windows, don't send the config file.  Other
            # platforms don't handle config the same way, so we
            # don't need to worry about them
            return True
        return False

    def ensure_ascii_filename(self, relpath):
        """Ensure that a path we are about to archive is ASCII."""

        # NOTE: zipfiles in general, and especially the python zipfile module
        # don't seem to support them well.  The only filenames we should be
        # sending are ASCII anyways, so let's just use a hack here to force
        # things.  See the "zipfile and unicode filenames" thread here:
        # http://mail.python.org/pipermail/python-dev/2007-June/thread.html
        if isinstance(relpath, unicode):
            return relpath.encode('ascii', 'ignore')
        else:
            return relpath.decode('ascii', 'ignore').encode('ascii', 'ignore')

    def fileobj(self):
        """Get a file object for the archive file."""
        return open(self.backupfile, "rb")

def next_free_filename_candidates(path):
    """Generates candidate names for next_free_filename."""

    # try unmodified path first
    yield path
    # add stuff to the filename to try to make it unique

    dirname, filename = os.path.split(path)
    if not filename:
        raise ValueError("%s is a directory name" % path)
    basename, ext = os.path.splitext(filename)
    count = 1
    while True:
        filename = "%s.%s%s" % (basename, count, ext)
        yield os.path.join(dirname, filename)
        count += 1
        if count > 1000:
            raise ValueError("Can't find available filename for %s" % path)

@returns_file
def next_free_filename(name):
    """Finds a filename that's unused and similar the the file we want
    to download and returns an open file handle to it.
    """ 
    check_f(name)
    mask = os.O_CREAT | os.O_EXCL | os.O_RDWR
    # On Windows we need to pass in O_BINARY, fdopen() even with 'b' 
    # specified is not sufficient.
    if sys.platform == 'win32':
        mask |= os.O_BINARY

    candidates = next_free_filename_candidates(name)
    while True:
        # Try with the name supplied.
        newname = candidates.next()
        try:
            fd = os.open(newname, mask)
            fp = os.fdopen(fd, 'wb')
            return newname, fp
        except OSError:
            continue
    return (newname, fp)

def next_free_directory_candidates(name):
    """Generates candidate names for next_free_directory."""
    yield name
    count = 1
    while True:
        yield "%s.%s" % (name, count)
        count += 1
        if count > 1000:
            raise ValueError("Can't find available directory for %s" % name)

@returns_filename
def next_free_directory(name):
    """Finds a unused directory name using name as a base.

    This method doesn't create the directory, it just finds an an-used one.
    """
    candidates = next_free_directory_candidates(name)
    while True:
        candidate = candidates.next()
        if not os.path.exists(candidate):
            return candidate

@contextlib.contextmanager
def alarm(timeout, set_signal=True):
    def alarm_handler(signum, frame):
        raise IOError('timeout after %i seconds' % timeout)
    if set_signal:
        set_signal = hasattr(signal, 'SIGALRM')
    if set_signal:
        signal.signal(signal.SIGALRM, alarm_handler)
        signal.alarm(timeout)
    yield set_signal
    if set_signal:
        signal.alarm(0)

def supports_alarm():
    return hasattr(signal, 'SIGALRM')

def namedtuple(class_name, fields, docstring=None):
    """Version of collections.namedtuple that adds docstring support."""
    # make the base class using the standard namedtuple
    nt = collections.namedtuple(class_name + "Tuple", fields)
    # make a subclass that adds the docstring and doesn't add a per-instance
    # dict.
    dct = { '__slots__': () }
    if docstring:
        dct['__doc__'] = docstring
    return type(class_name, (nt,), dct)
