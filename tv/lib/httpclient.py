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

"""httpclient.py.

Implements a HTTP client using pylibcurl.

The main ways this module used is grab_url() and grab_headers().  grab_url
fetches a HTTP or HTTPS url, while grab_headers only fetches the headers.
"""

import logging
import os
import stat
import threading
import urllib
import Queue
from cStringIO import StringIO

import pycurl

from miro import app
from miro import download_utils
from miro import eventloop
from miro import fileutil
from miro import httpauth
from miro import net
from miro import prefs
from miro import signals
from miro import util
from miro.gtcache import gettext as _
from miro.xhtmltools import url_encode_dict, multipart_encode
from miro.plat import utils
from miro.plat.resources import get_osname
from miro.net import NetworkError, ConnectionError, ConnectionTimeout

try:
    import gzip
except:
    gzip = None

REDIRECTION_LIMIT = 10
MAX_AUTH_ATTEMPTS = 5

_logged_noproxy_error = False

def user_agent():
    return "%s/%s (%s; %s)" % (app.config.get(prefs.SHORT_APP_NAME),
            app.config.get(prefs.APP_VERSION),
            app.config.get(prefs.PROJECT_URL),
            get_osname())

def _proxy_auth_url():
    """Create a URL to use to store proxy auth data."""

    # we hack things by using a "proxy" scheme.  This keeps it separate from
    # regular HTTP passwords
    return 'proxy://%s:%s/' % (app.config.get(prefs.HTTP_PROXY_HOST),
            app.config.get(prefs.HTTP_PROXY_PORT))

def trap_call(when, function, *args, **kwargs):
    """Version of trap_call for the libcurl thread.

    :retval the return value of the function, or the exception raised.
    """
    try:
        return function(*args, **kwargs)
    except (SystemExit, KeyboardInterrupt), e:
        # If we just re-raise these, then we will just crash the libcurl
        # thread.  Instead, we want to shutdown the eventloop.
        logging.warn("saw %s in libcurl thread, quitting")
        app.controller.shutdown()
    except Exception, e:
        logging.stacktrace("libcurl thread exception while %s" % when)
        eventloop.add_idle("sending exception", signals.system.failed,
                args=(when,))
        return e

class HTTPError(NetworkError):
    def __init__(self, longDescription):
        NetworkError.__init__(self, _("HTTP error"), longDescription)

class ServerClosedConnection(HTTPError):
    def __init__(self, host):
        HTTPError.__init__(self, _('%(host)s closed connection',
                                   {"host": host}))

class EmptyResponse(HTTPError):
    def __init__(self, host):
        HTTPError.__init__(self, _('%(host)s gave us an empty response',
                                   {"host": host}))

class PossiblyTemporaryError(HTTPError):
    def __init__(self, status):
        self.friendlyDescription = _("Host returned %(status)s",
                                     {"status": status})
        self.longDescription = _("Please retry later")

class ResumeFailed(HTTPError):
    def __init__(self, host):
        HTTPError.__init__(self, _('%(host)s doesn\'t support HTTP resume',
                                   {"host": host}))

class TooManyRedirects(HTTPError):
    def __init__(self, url):
        HTTPError.__init__(self, _('HTTP Redirection limit hit for %(url)s',
                                   {"url": url}))

class ProxyAuthorizationFailed(HTTPError):
    def __init__(self):
        HTTPError.__init__(self,
                _('Authorization failed for proxy: %(host)s:%(port)s',
                               {"host": app.config.get(prefs.HTTP_PROXY_HOST),
                               "port": app.config.get(prefs.HTTP_PROXY_PORT)}))

class UnexpectedStatusCode(HTTPError):
    def __init__(self, code):
        if code == 404:
            self.friendlyDescription = _("File not found")
            self.longDescription = _("Got 404 status code")
        else:
            HTTPError.__init__(self, _("Host returned bad status code: %(code)s",
                                       {"code": util.unicodify(code)}))
        self.code = code

class AuthorizationFailed(HTTPError):
    def __init__(self):
        HTTPError.__init__(self, _("Authorization failed"))
        self.friendlyDescription = _("Authorization failed")

class AuthorizationCanceled(HTTPError):
    def __init__(self):
        HTTPError.__init__(self, _("Authorization canceled"))
        self.friendlyDescription = _("Authorization canceled by user")

class MalformedURL(NetworkError):
    def __init__(self, url):
        NetworkError.__init__(self, _('Invalid URL'),
                _('"%(url)s" is not a valid URL', {"url": url}))

class InvalidRedirect(NetworkError):
    def __init__(self, url):
        NetworkError.__init__(self, _('Invalid Redirect'),
                _('"%(url)s" is not a valid redirect URL', {"url": url}))

class UnknownHostError(NetworkError):
    """A file: URL doesn't exist"""
    def __init__(self, host):
        NetworkError.__init__(self, _('Unknown Host'),
            _('The domainname "%(host)s" couldn\'t be found', {"host": host}))

class FileURLNotFoundError(NetworkError):
    """A file: URL doesn't exist"""
    def __init__(self, path):
        NetworkError.__init__(self, _('File not found'),
            _('The file "%(path)s" doesn\'t exist', {"path": path}))

class FileURLReadError(NetworkError):
    def __init__(self, path):
        NetworkError.__init__(self, _('Read error'),
            _('Error while reading from "%(path)s"', {"path": path}))

class WriteError(NetworkError):
    """Error while writing a file with grab_url().  This is not strictly a
    "network" error, but it works to have it in the exception hierarchy here.
    """

    def __init__(self, path):
        msg = _("Could not write to %(filename)s",
            {"filename": util.stringify(path)})
        NetworkError.__init__(self, _('Write error'), msg)

class TransferOptions(object):
    """Holds data about an upcoming transfer.

    This class stores transfer data like the URL, etag/modified, post data,
    etc.  It's very similar to a libcurl handle, but built to work with Miro's
    thread system.  I'm (BDK) pretty sure we could just build a libcurl
    handle in any thread, but having this class means that we don't have to
    worry about any potential threading issues with building a handle in one
    thread, then using it in another.
    """

    def __init__(self, url, etag=None, modified=None, resume=False,
            post_vars=None, post_files=None, write_file=None,
                 extra_headers=None):
        self.url = url
        self.etag = etag
        self.modified = modified
        self.extra_headers = extra_headers
        self.resume = resume
        self.post_vars = post_vars
        self.post_files = post_files
        self.write_file = write_file
        self.requires_cookies = False
        self.head_request = False
        self.invalid_url = False
        # _cancel_on_body_data is an internal attribute used for grab_headers.
        self._cancel_on_body_data = False
        self.parse_url()
        self.post_length = 0

    def parse_url(self):
        self.scheme = self.host = _('Unknown')
        if self.url is None:
            self.invalid_url = True
            return 
        try:
            self.url = self.url.encode("ascii")
        except UnicodeError:
            self.invalid_url = True
            return
        scheme, host, port, path = download_utils.parse_url(self.url)
        self.scheme = scheme
        self.host = host
        self.path = path
        if scheme not in ['http', 'https'] or host == '' or path == '':
            self.invalid_url = True
            return

    def build_handle(self, out_headers):
        """Build a libCURL handle.  This should only be called inside the
        LibCURLManager thread.
        """
        if self.etag is not None:
            out_headers['etag'] = self.etag
        if self.modified is not None:
            out_headers['If-Modified-Since'] = self.modified
        if self.extra_headers is not None:
            out_headers.update(self.extra_headers)

        handle = self._init_handle()
        self._setup_post(handle, out_headers)
        self._setup_headers(handle, out_headers)
        return handle

    def _init_handle(self):
        handle = pycurl.Curl()
        handle.setopt(pycurl.USERAGENT, user_agent())
        handle.setopt(pycurl.FOLLOWLOCATION, 1)
        handle.setopt(pycurl.MAXREDIRS, REDIRECTION_LIMIT)
        handle.setopt(pycurl.NOPROGRESS, 1)
        handle.setopt(pycurl.NOSIGNAL, 1)
        handle.setopt(pycurl.CONNECTTIMEOUT, net.SOCKET_CONNECT_TIMEOUT)
        if self.requires_cookies:
            # we don't do this for every request, since on OS X this generates
            # a new cookies.txt file
            handle.setopt(pycurl.COOKIEFILE, utils.get_cookie_path())

        # The following 2 settings makes it so that if we don't receive any
        # data after SOCKET_READ_TIMEOUT, the transfer ends in an error
        handle.setopt(pycurl.LOW_SPEED_LIMIT, 1)
        handle.setopt(pycurl.LOW_SPEED_TIME, net.SOCKET_READ_TIMEOUT)
        handle.setopt(pycurl.URL, self.url)
        if self.head_request:
            handle.setopt(pycurl.NOBODY, 1)
        self._setup_proxy(handle)
        return handle

    def _setup_proxy(self, handle):
        if not app.config.get(prefs.HTTP_PROXY_ACTIVE):
            return

        # FIXME honor prefs.HTTP_PROXY_SCHEME
        handle.setopt(pycurl.PROXY, str(app.config.get(prefs.HTTP_PROXY_HOST)))
        handle.setopt(pycurl.PROXYPORT,
                int(app.config.get(prefs.HTTP_PROXY_PORT)))

        ignore_hosts = app.config.get(prefs.HTTP_PROXY_IGNORE_HOSTS)
        if ignore_hosts:
            try:
                handle.setopt(pycurl.NOPROXY, ','.join(
                    str(h) for h in ignore_hosts))
            except AttributeError:
                global _logged_noproxy_error
                if not _logged_noproxy_error:
                    logging.warn("pycurl.NOPROXY doesn't exist")
                    _logged_noproxy_error = True

    def _setup_headers(self, handle, out_headers):
        headers = ['%s: %s' % (str(k), str(out_headers[k]))
                   for k in out_headers]
        handle.setopt(pycurl.HTTPHEADER, headers)

    def _setup_post(self, handle, out_headers):
        data = None
        if self.post_files is not None:
            (data, boundary) = multipart_encode(self.post_vars,
                    self.post_files)
            content_type = 'multipart/form-data; boundary=%s' % boundary
            out_headers['content-type'] = content_type
            out_headers['content-length'] = len(data)
            out_headers['expect'] = ''
        elif self.post_vars is not None:
            data = url_encode_dict(self.post_vars)

        if data is not None:
            handle.setopt(pycurl.POSTFIELDS, data)
            # Bind the post data to a instance varible so that it doesn't get
            # garbage collected while libcurl is reading it (#14631)
            self.post_data = data
            self.post_length = len(data)

class CurlTransfer(object):
    """A in-progress CURL download.

    CurlTransfer objects are created in grab_url, then passed to the
    LibCURLManager thread.  After that they shouldn't be accessed outside of
    that thread, except with the get_info() method.
    """

    def __init__(self, options, callback, errback, header_callback=None,
            content_check_callback=None):
        """Create a CurlTransfer object.

        :param options: TransferOptions object.  The object shouldn't be
            modified after passing it in.
        :param callback: function to call when the transfer succeeds
        :param errback: function to call when the transfer fails
        """
        self.options = options
        self._reset_transfer_data()
        self.callback = callback
        self.header_callback = header_callback
        self.content_check_callback = content_check_callback
        self.errback = errback
        self.auth_attempts = {'http': 0, 'proxy': 0}
        self.canceled = False
        self.last_url = None

        self.stats = TransferStats()
        self._lookup_auth()
        self.lock = threading.Lock()

    def _reset_transfer_data(self):
        self.headers = {}
        self.handle = None
        self.current_auth_type = None
        self.buffer = StringIO()
        self.saw_temporary_redirect = False
        self.headers_finished = False
        self._filehandle = None
        self.resume_from = 0
        self.out_headers = {}
        self.status_code = None
        self.trying_head_request = False
        self.saw_head_success = False

    def _send_new_request(self):
        self._reset_transfer_data()
        curl_manager.add_transfer(self)

    def start(self):
        if self.options.invalid_url:
            self.call_errback(MalformedURL(self.options.url))
            return
        try:
            curl_manager.add_transfer(self)
        except AttributeError:
            if hasattr(app, 'in_unit_tests'):
                # this is okay for unittests that create feeds, but don't
                # expect to download their contents
                return
            raise

    def cancel(self, remove_file):
        curl_manager.remove_transfer(self, remove_file)
        self.canceled = True

    def handle_http_auth(self):
        url = self.options.url
        location = (_("Website"), url)
        self._handle_auth('http', 'www-authenticate', url, location)

    def handle_proxy_auth(self):
        url = _proxy_auth_url()
        location = (_("Proxy"), url)
        self._handle_auth('proxy', 'proxy-authenticate', url, location)

    def handle_auth_failure(self):
        if self.current_auth_type == 'http':
            self.call_errback(AuthorizationFailed())
        elif self.current_auth_type == 'proxy':
            self.call_errback(ProxyAuthorizationFailed())
        else:
            logging.warn("Unknown current_auth_type: %s",
                    self.current_auth_type)
            self.call_errback(AuthorizationFailed())

    @eventloop.as_idle
    def _handle_auth(self, auth_type, header_key, url, location):
        # this method needs to run in the eventloop because it uses the
        # httpauth module.  At this point the transfer is removed from
        # curl_manager's, so we don't have to worry about accessing our
        # attributes.
        self.current_auth_type = auth_type
        self.auth_attempts[auth_type] += 1
        if auth_type == 'http' and self.http_auth is not None:
            httpauth.remove(self.http_auth)
        elif auth_type == 'proxy' and self.proxy_auth is not None:
            httpauth.remove(self.proxy_auth)
        if self.auth_attempts[auth_type] > MAX_AUTH_ATTEMPTS:
            self.handle_auth_failure()
            return
        try:
            auth_header = self.headers[header_key]
        except KeyError:
            self.handle_auth_failure()
            return
        if auth_type == 'http':
            # now that we have the www-authenticate header, try again to find
            # an existing password
            existing_auth = httpauth.find_http_auth(url, auth_header)
            if existing_auth is not None:
                self.http_auth = existing_auth
                self._send_new_request()
                return
        try:
            httpauth.ask_for_http_auth(self._ask_for_http_auth_callback,
                    url, auth_header, location)
        except (AssertionError, ValueError), e:
            logging.warn("Error when parsing auth header: %s", e)
            self.handle_auth_failure()

    def _ask_for_http_auth_callback(self, auth):
        if self.canceled:
            return
        if auth is None:
            self.call_errback(AuthorizationCanceled())
        else:
            if self.current_auth_type == 'http':
                self.http_auth = auth
            else:
                self.proxy_auth = auth
            self._send_new_request()

    def build_handle(self):
        """Build a libCURL handle.  This should only be called inside the
        LibCURLManager thread.
        """
        self.handle = self.options.build_handle(self.out_headers)
        # don't authenticate SSL certificates see #15180
        self.handle.setopt(pycurl.SSL_VERIFYPEER, 0)

        self._setup_http_auth()
        self._setup_proxy_auth()
        if self.options._cancel_on_body_data:
            self.handle.setopt(pycurl.WRITEFUNCTION, self._write_func_abort)
        elif self.options.write_file is not None:
            if not self.saw_head_success:
                # try a HEAD request first to see if the request will work.
                # It avoids the issue of RESUME_FROM being applied to the 
                # error response.
                self.handle.setopt(pycurl.NOBODY, 1)
                self.trying_head_request = True
            else:
                self.handle.setopt(pycurl.URL, self.last_url)
                self._open_file()
                self.handle.setopt(pycurl.WRITEFUNCTION, self._write_file)
        elif self.content_check_callback is not None:
            self.handle.setopt(pycurl.WRITEFUNCTION, self._call_content_check)
        else:
            self.handle.setopt(pycurl.WRITEFUNCTION, self.buffer.write)
        self.handle.setopt(pycurl.HEADERFUNCTION, self.header_func)
        if self.should_debug_request():
            logging.warn("debugging request: %s", self.options.url)
            self.handle.setopt(pycurl.VERBOSE, 1)
            self.handle.setopt(pycurl.DEBUGFUNCTION, self.debug_func)

    def _write_file(self, buf):
        if self.check_response_code(self.status_code):
            self._filehandle.write(buf)

    def _lookup_auth(self):
        """Lookup existing HTTP passwords to use.

        We need to do this before we are running in the libcurl thread because
        we access the httpauth module.
        """
        self.http_auth = httpauth.find_http_auth(self.options.url)
        self.proxy_auth = httpauth.find_http_auth(_proxy_auth_url())

    def _setup_http_auth(self):
        if self.http_auth is not None:
            if self.http_auth.scheme == 'basic':
                self.handle.setopt(pycurl.HTTPAUTH, pycurl.HTTPAUTH_BASIC)
            elif self.http_auth.scheme == 'digest':
                self.handle.setopt(pycurl.HTTPAUTH, pycurl.HTTPAUTH_DIGEST)
            else:
                logging.warn("Unknown HTTP Auth scheme: %s",
                        self.http_auth.scheme)
                return
            self.handle.setopt(pycurl.USERPWD,
                    str("%s:%s" % (self.http_auth.username,
                        self.http_auth.password)))

    def _setup_proxy_auth(self):
        # first try passwords stored by miro.  proxy_auth was setup in
        # _lookup_auth()
        if self.proxy_auth is not None:
            user_pwd = str('%s:%s' % (self.proxy_auth.username,
                    self.proxy_auth.password))
            self.handle.setopt(pycurl.PROXYUSERPWD, user_pwd)
        else:
            # fallback on system auth info
            if app.config.get(prefs.HTTP_PROXY_AUTHORIZATION_ACTIVE):
                self.handle.setopt(pycurl.PROXYUSERPWD, '%s:%s' % (
                    str(app.config.get(prefs.HTTP_PROXY_AUTHORIZATION_USERNAME)),
                    str(app.config.get(prefs.HTTP_PROXY_AUTHORIZATION_PASSWORD))))

    def _call_content_check(self, data):
        self.buffer.write(data)
        rv = trap_call('content check callback', self.content_check_callback,
                self.buffer.getvalue())
        if rv == False or isinstance(rv, Exception):
            curl_manager.remove_transfer(self)

    def _open_file(self):
        if self.options.resume:
            mode = 'ab'
            try:
                path = self.options.write_file
                self.resume_from = int(os.stat(path)[stat.ST_SIZE])
            except OSError:
                # file doesn't exist, just skip resuming
                pass
            else:
                self.handle.setopt(pycurl.RESUME_FROM, self.resume_from)
        else:
            mode = 'wb'
        try:
            self._filehandle = fileutil.open_file(self.options.write_file, mode)
        except IOError:
            raise WriteError(self.options.write_file)

    def should_debug_request(self):
        # return True here to debug HTTP requests in the log file
        return False


    def debug_func(self, typ, msg):
        type_map = {
                pycurl.INFOTYPE_HEADER_IN: 'header-in',
                pycurl.INFOTYPE_HEADER_OUT: 'header-out',
                pycurl.INFOTYPE_DATA_IN: 'data-in',
                pycurl.INFOTYPE_DATA_OUT: 'data-out',
                pycurl.INFOTYPE_TEXT: 'text',
        }
        type_str = type_map.get(typ, typ)
        logging.warn("libcurl debug (%s) %r", type_str, msg)


    def header_func(self, line):
        line = line.strip()
        if line.startswith("HTTP"):
            # we can't use self.header.getinfo() because we're inside the
            # perform call.  However, we also can't use call_after_perform()
            # because that call might happen after a redirect, which might
            # make us miss the temporary redirect.  So parse the status
            # ourselves.
            try:
                code = self.status_code = int(line.split()[1])
            except Exception, e:
                logging.warn("Error parsing status line (%r): %s", line, e)
                self.status_code = 200
            else:
                if 300 <= code <= 399 and code != 301:
                    self.saw_temporary_redirect = True
            return
        if line == '':
            if self.status_code == 100:
                # server sent a HTTP 100 continue.  we ditch the data
                # we got so far and ignore this "empty header" because
                # it's not the response we're looking for.
                self.status_code = None
            elif 'location' in self.headers:
                # doing a redirect, clear out the headers
                redirect_url = self.headers['location']
                scheme, _, _, _ = download_utils.parse_url(redirect_url)
                if not scheme:
                    logging.warn("%s: Non-absolute redirect URL: %s",
                                 self.options.url, redirect_url)
                elif scheme not in ('http', 'https'):
                    self.cancel(remove_file=True)
                    self.call_errback(InvalidRedirect(redirect_url))
                    return
                self.headers = {}
            elif not self.headers_finished:
                curl_manager.call_after_perform(self.on_headers_finished)
                self.headers_finished = True
            else:
                msg = "httpclient: saw multiple empty header lines (%s)"
                logging.warning(msg, self.options.url)
            return
        elif self.headers_finished:
            msg = "httpclient: saw content after empty header (%s)"
            logging.warning(msg, self.options.url)
            return
        try:
            header, value = line.split(":", 1)
        except ValueError:
            logging.debug("Bad header from %s: no :", self.options.url, line)
            return
        value = value.strip()
        header = header.lstrip().lower()
        if value == '':
            logging.debug("Bad header from %s: empty value", self.options.url)

        if header not in self.headers:
            self.headers[header] = value
        else:
            self.headers[header] += (',%s' % value)

    def on_headers_finished(self):
        if self.header_callback:
            eventloop.add_idle(self.header_callback,
                    'httpclient header callback',
                    args=(self._make_callback_info(),))

    def check_response_code(self, code):
        expected_codes = set([200])
        if self.options.resume:
            expected_codes.add(206)
        if self.options.etag or self.options.modified:
            expected_codes.add(304)
        return code in expected_codes

    def _make_callback_info(self):
        info = self.headers.copy()
        info['status'] = self.handle.getinfo(pycurl.RESPONSE_CODE)
        if 'content-length' in info:
            # Use libcurl's content length rather than the raw header string
            info['content-length'] = self.stats.download_total
            info['total-size'] = self.stats.download_total + self.resume_from
        info['original-url'] = self.options.url
        info['redirected-url'] = self.handle.getinfo(pycurl.EFFECTIVE_URL)
        info['filename'] = self.calc_filename(info['redirected-url'])
        info['charset'] = self.calc_charset()
        if self.saw_temporary_redirect:
            info['updated-url'] = info['original-url']
        else:
            info['updated-url'] = info['redirected-url']
        return info

    def _write_func_abort(self, bytes_):
        curl_manager.remove_transfer(self)
        curl_manager.call_after_perform(self.on_finished)

    def on_finished(self):
        info = self._make_callback_info()
        self.last_url = self.handle.getinfo(pycurl.EFFECTIVE_URL)
        if self.options.write_file is None:
            if gzip and info.get('content-encoding', '') == 'gzip':
                try:
                    self.buffer.seek(0)
                    info['body'] = gzip.GzipFile(
                                       fileobj=self.buffer).read()
                except IOError, e:
                    info['body'] = self.buffer.getvalue()
                    logging.warning("Received header with content-encoding "
                                    "gzip, but content is not gzip encoded")
            else:
                info['body'] = self.buffer.getvalue()

        if self.check_response_code(info['status']):
            if not self.trying_head_request:
                self.call_callback(info)
            else:
                # we tried a HEAD request and it worked, now we can do the
                # transfer for real
                self._send_new_request()
                self.saw_head_success = True
        elif info['status'] == 401:
            self.handle_http_auth()
        elif info['status'] == 407:
            self.handle_proxy_auth()
        elif self.trying_head_request:
            # The response code wasn't what we expected, but we are doing
            # a HEAD request.
            #
            # Servers have "inventive" strategies for dealing with HEAD
            # requests.  I don't really feel like handling them one by
            # one since you never know what comes through, so just assume
            # things are okay and let the actual download handler deal with
            # failure.
            #
            # We handle this before all of the error handling to make sure
            # we have a chance to catch this.
            self._send_new_request()
            self.saw_head_success = True
        elif ((info['status'] >= 500 and info['status'] < 600) or
              (info['status'] == 404 and
               self.last_url.startswith(('http://vimeo.com',
                                         'http://www.vimeo.com')))):
            # 500 errors are hopefully temporary, as are 404s from Vimeo
            # (#19066)
            logging.info("httpclient: possibly temporary http error: HTTP %s",
                         info['status'])
            self.call_errback(PossiblyTemporaryError(info['status']))
        else:
            self.call_errback(UnexpectedStatusCode(info['status']))

    def on_cancel(self, remove_file):
        self._cleanup_filehandle()
        if remove_file and self.options.write_file:
            try:
                fileutil.remove(self.options.write_file)
            except OSError:
                pass

    def find_value_from_header(self, header, target):
        """Finds a value from a response header that uses key=value pairs with
        the ';' char as a separator.  This is how content-disposition and
        content-type work.
        """
        for part in header.split(';'):
            try:
                name, value = part.split("=", 1)
            except ValueError:
                pass
            else:
                if name.strip().lower() == target.lower():
                    return value.strip().strip('"')
        return None

    def calc_charset(self):
        try:
            content_type = self.headers['content-type']
        except KeyError:
            pass
        else:
            charset = self.find_value_from_header(content_type, 'charset')
            if charset is not None:
                return charset
        return 'iso-8859-1'

    def calc_filename(self, redirected_url):
        try:
            disposition = self.headers['content-disposition']
        except KeyError:
            pass
        else:
            filename = self.find_value_from_header(disposition, 'filename')
            if filename is not None:
                return download_utils.clean_filename(filename)
        return download_utils.filename_from_url(util.unicodify(redirected_url), 
                clean=True)

    def on_error(self, code, handle):
        if code in (pycurl.E_URL_MALFORMAT, pycurl.E_UNSUPPORTED_PROTOCOL):
            error = MalformedURL(self.options.url)
        elif code == pycurl.E_COULDNT_CONNECT:
            error = ConnectionError(self.options.host)
        elif code == pycurl.E_PARTIAL_FILE:
            error = ServerClosedConnection(self.options.host)
        elif code == pycurl.E_GOT_NOTHING:
            error = EmptyResponse(self.options.host)
        elif code == pycurl.E_HTTP_RANGE_ERROR:
            error = ResumeFailed(self.options.host)
        elif code == pycurl.E_TOO_MANY_REDIRECTS:
            error = TooManyRedirects(self.options.url)
        elif code == pycurl.E_COULDNT_RESOLVE_HOST:
            error = UnknownHostError(self.options.host)
        elif code == pycurl.E_OPERATION_TIMEOUTED:
            error = ConnectionTimeout(self.options.host)
        elif (code == pycurl.E_RECV_ERROR and
                self.handle.getinfo(pycurl.HTTP_CONNECTCODE) == 407):
            # Hack for proxy authentication errors with HTTPS
            self.handle_proxy_auth()
            return
        else:
            logging.warn("Unknown network error.  Code: %s", code)
            errstr = handle.errstr()
            try:
                description = errstr.decode('utf-8')
            except UnicodeError, e:
                logging.warn("error converting errstr: %s (%r)", e, errstr)
                description = u'Unknown'
            error = NetworkError(_("Unknown"), description)
        self.call_errback(error)

    def call_callback(self, info):
        self._cleanup_filehandle()
        msg = 'curl transfer callback: %s' % (self.callback,)
        eventloop.add_idle(self.callback, msg, args=(info,))

    def call_errback(self, error):
        self._cleanup_filehandle()
        msg = 'curl transfer errback: %s' % (self.errback,)
        eventloop.add_idle(self.errback, msg, args=(error,))

    def _cleanup_filehandle(self):
        if self._filehandle is not None:
            self._filehandle.close()
            self._filehandle = None

    def build_stats(self):
        stats = TransferStats()
        getinfo = self.handle.getinfo # for easy typing

        if 'content-length' in self.headers:
            stats.download_total = int(getinfo(pycurl.CONTENT_LENGTH_DOWNLOAD))
        stats.upload_total = self.options.post_length

        stats.downloaded = int(getinfo(pycurl.SIZE_DOWNLOAD))
        stats.uploaded = int(getinfo(pycurl.SIZE_UPLOAD))
        stats.download_rate = int(getinfo(pycurl.SPEED_DOWNLOAD))
        stats.upload_rate = int(getinfo(pycurl.SPEED_UPLOAD))
        stats.status_code = self.status_code
        stats.initial_size = self.resume_from

        return stats

    def update_stats(self):
        new_stats = self.build_stats()
        self.lock.acquire()
        try:
            self.stats = new_stats
        finally:
            self.lock.release()

    def get_stats(self):
        self.lock.acquire()
        try:
            return self.stats
        finally:
            self.lock.release()

class TransferStats(object):
    """Holds data about a lib curl transfer.

    Attributes:
        status_code -- HTTP status code (or None if we haven't seen one yet)
        downloaded -- current bytes downloaded
        uploaded -- current bytes uploaded
        download_total -- total bytes to download (or -1 if we don't know)
        upload_total -- total bytes to upload (or -1 if we don't know)
        download_rate -- download rate in bytes/second
        upload_rate -- upload rate in bytes/second
        initial_size -- bytes that we starting downloading from
    """
    def __init__(self):
        self.downloaded = self.download_total = 0
        self.uploaded = self.upload_total = -1
        self.download_rate = self.upload_rate = 0
        self.initial_size = 0
        self.status_code = None

class LibCURLManager(eventloop.SimpleEventLoop):
    """Manage a set of CurlTransfers.

    This class does a few things:

      - Runs a thread for pycurl to use
      - Manages the libcurl multi object
      - Handles adding/removing CurlTransfers objects
    """

    def __init__(self):
        eventloop.SimpleEventLoop.__init__(self)
        self.multi = pycurl.CurlMulti()
        self.transfer_map = {}
        self.transfers_to_add = Queue.Queue()
        self.transfers_to_remove = Queue.Queue()
        self.after_perform_callbacks = []

    def start(self):
        self.thread = threading.Thread(target=utils.thread_body,
                                       args=[self.loop],
                                       name="LibCURL Event Loop")
        self.thread.start()

    def stop(self):
        self.quit_flag = True
        self.wakeup()
        self.thread.join()

    def loop(self):
        eventloop.SimpleEventLoop.loop(self)
        for transfer in self.transfer_map.values():
            self.multi.remove_handle(transfer.handle)
            transfer.handle.close()
        self.multi.close()

    def add_transfer(self, transfer):
        self.transfers_to_add.put(transfer)
        self.wakeup()

    def remove_transfer(self, transfer, remove_file=False):
        self.transfers_to_remove.put((transfer, remove_file))
        self.wakeup()

    def call_after_perform(self, callback):
        self.after_perform_callbacks.append(callback)

    def calc_fds(self):
        return self.multi.fdset()

    def calc_timeout(self):
        timeout = self.multi.timeout()
        if timeout < 0:
            # libcurl documentation says this means to wait "not too long"
            # Let's try 2 seconds
            return 2.0
        else:
            return timeout / 1000.0

    def process_events(self, readfds, writefds, excfds):
        self.process_queues()
        while True:
            rv, num_handles = self.multi.perform()
            self.update_stats()
            for callback in self.after_perform_callbacks:
                trap_call('after perform callback', callback)
            self.after_perform_callbacks = []
            if rv != pycurl.E_CALL_MULTI_PERFORM:
                break
        self.process_queues()
        self.check_finished()

    def update_stats(self):
        for transfer in self.transfer_map.values():
            transfer.update_stats()

    def process_queues(self):
        while True:
            try:
                transfer = self.transfers_to_add.get_nowait()
            except Queue.Empty:
                break
            try:
                transfer.build_handle()
            except NetworkError, e:
                transfer.call_errback(e)
                continue
            self.transfer_map[transfer.handle] = transfer
            self.multi.add_handle(transfer.handle)

        while True:
            try:
                transfer, remove_file = self.transfers_to_remove.get_nowait()
            except Queue.Empty:
                break
            transfer.on_cancel(remove_file)
            try:
                del self.transfer_map[transfer.handle]
            except KeyError:
                continue
            self.multi.remove_handle(transfer.handle)

    def check_finished(self):
        queued, finished, errors = self.multi.info_read()
        for handle in finished:
            try:
                self.pop_transfer(handle).on_finished()
            except StandardError:
                logging.warning("Error calling on_finished()", exc_info=True)
        for handle, code, message in errors:
            try:
                self.pop_transfer(handle).on_error(code, handle)
            except StandardError:
                logging.warning("Error calling on_error()", exc_info=True)

    def pop_transfer(self, handle):
        transfer = self.transfer_map.pop(handle)
        self.multi.remove_handle(handle)
        return transfer

class HTTPClient(object):
    """HTTP client for a grab_url call.

    Most of the work for grab_url() happens in the lib curl thread.  This
    class provides an interface for code in the eventloop (and other threads)
    to use.
    """
    def __init__(self, transfer):
        self.transfer = transfer

    def cancel(self, remove_file=False):
        self.transfer.cancel(remove_file)

    def get_stats(self):
        """Get the current download/upload stats

        :returns: a TransferStats object
        """

        return self.transfer.get_stats()


def sanitize_url(url):
    """Fix poorly constructed URLs.

    The main use case for this is to replace " " characters with "%20"
    """
    return urllib.quote(url, safe="-_.!~*'();/?:@&=+$,%#")

def grab_url(url, callback, errback, header_callback=None,
        content_check_callback=None, write_file=None, etag=None, modified=None,
        default_mime_type=None, resume=False, post_vars=None,
        post_files=None, extra_headers=None):
    """Quick way to download a network resource

    grab_url is a simple interface to the HTTPClient class.

    :param url: URL to download
    :param callback: function to call on success
    :param errback: function to call on error
    :param header_callback: function to call after we recieve the headers
    :param content_check_callback: function to call as we recieve content data
        return False to cancel the transfer.  Note: this function runs in the
        libcurl thread.  Be mindful of threading issues when accessing data
    :param write_file: File path to write to
    :param etag: etag header to send
    :param modified: last-modified header to send
    :param default_mime_type: mime type for file:// URLs
    :param resume: if True and write_file is set, resume an interrupted HTTP
         transfer
    :param post_vars: dictionary of variables to send as POST data
    :param post_files: files to send as POST data (see
        xhtmltools.multipart_encode for the format)
    :param extra_headers: an option dictionary of extra headers to send

    The callback will be passed a dictionary that contains all the HTTP
    headers, as well as the following keys:
        'status': HTTP response code
        'body': The request body (if write_file is not given)
        'content-length': Length of the downloads as an int
        'total-size': Total size of the download (this is different from
            content-length because it includes the data we are resuming from)
        'original-url': the URL passed to grab_url()
        'redirected_url': the last URL we were redirected to
        'updated': the URL that we should save in the database, this will be
            either original-url or redirected-url depending on if we received
            a permanent redirect or a temporary one.
        'filename': Name of the file that we should use to save the data
        'charset': Charset encoding of the data

    :returns HTTPClient object
    """
    url = sanitize_url(url)
    if url.startswith("file://"):
        return _grab_file_url(url, callback, errback, default_mime_type)
    else:
        options = TransferOptions(url, etag, modified, resume, post_vars,
                post_files, write_file, extra_headers)
        transfer = CurlTransfer(options, callback, errback, header_callback,
                content_check_callback)
        transfer.start()
        return HTTPClient(transfer)

def _grab_file_url(url, callback, errback, default_mime_type):
    path = download_utils.get_file_url_path(url)
    try:
        f = file(path)
    except EnvironmentError:
        eventloop.add_idle(errback, 'grab file url errback',
                args=(FileURLNotFoundError(path),))
    else:
        try:
            data = f.read()
        except IOError:
            eventloop.add_idle(errback, 'grab file url errback',
                    args=(FileURLReadError(path),))
        else:
            info = {"body": data,
                          "updated-url":url,
                          "redirected-url":url,
                          "content-type": default_mime_type,
                          }
            eventloop.add_idle(callback, 'grab file url callback',
                    args=(info,))

def _grab_headers_using_get(url, callback, errback):
    options = TransferOptions(url)
    options._cancel_on_body_data = True
    transfer = CurlTransfer(options, callback, errback)
    transfer.start()
    return HTTPClient(transfer)

def grab_headers(url, callback, errback):
    """Quickly get the headers for a URL"""
    def errback_intercept(error):
        if isinstance(error, AuthorizationCanceled):
            # don't bother asking again
            return errback(error)
        _grab_headers_using_get(url, callback, errback)

    url = sanitize_url(url)
    options = TransferOptions(url)
    options.head_request = True
    transfer = CurlTransfer(options, callback, errback_intercept)
    transfer.start()
    return HTTPClient(transfer)

def init_libcurl():
    pycurl.global_init(pycurl.GLOBAL_ALL)

def cleanup_libcurl():
    pycurl.global_cleanup()

# ON_START_HOOKS and register_on_start allow front-ends to connect
# to signals on the CurlManager after it's been created.
ON_START_HOOKS = []

def register_on_start(fun):
    ON_START_HOOKS.append(fun)

# FIXME - this is a singleton global and the name should be all-caps
curl_manager = None

def start_thread():
    global curl_manager
    curl_manager = LibCURLManager()
    for mem in ON_START_HOOKS:
        mem(curl_manager)
    curl_manager.start()

def stop_thread():
    global curl_manager
    curl_manager.stop()
    curl_manager = None
