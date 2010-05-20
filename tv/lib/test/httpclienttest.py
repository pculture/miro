import rfc822
import tempfile
import os
import pycurl
import urllib
from cStringIO import StringIO

from miro import eventloop
from miro import httpclient
from miro.plat import resources
from miro.test.framework import EventLoopTest

TEST_PATH = 'test.txt'
TEST_BODY = 'Miro HTTP Test\n'

class HTTPClientTestBase(EventLoopTest):
    def setUp(self):
        EventLoopTest.setUp(self)
        self.start_http_server()
        self.grab_url_info = self.grab_url_error = None
        self.expecting_errback = False
        self.event_loop_timeout = 0.5

    def grab_url_callback(self, info):
        self.grab_url_info = info
        self.stopEventLoop(abnormal=False)

    def grab_url_errback(self, error):
        self.grab_url_error = error
        self.stopEventLoop(abnormal=False)

    def runEventLoop(self, timeout):
        EventLoopTest.runEventLoop(self, timeout=timeout)
        if self.grab_url_error is not None and not self.expecting_errback:
            raise AssertionError("grab_url error: %s" % self.grab_url_error)

    def grab_url(self, url, *args, **kwargs):
        self.grab_url_error = self.grab_url_info = None
        self.client = httpclient.grab_url(url, self.grab_url_callback,
                self.grab_url_errback, *args, **kwargs)
        self.runEventLoop(timeout=self.event_loop_timeout)

    def grab_headers(self, url, *args, **kwargs):
        self.grab_url_error = self.grab_url_info = None
        self.client = httpclient.grab_headers(url, self.grab_url_callback,
                self.grab_url_errback, *args, **kwargs)
        self.runEventLoop(timeout=self.event_loop_timeout)

    def check_errback_called(self):
        self.assertNotEquals(self.grab_url_error, None)
        self.assertEquals(self.grab_url_info, None)

class HTTPClientTest(HTTPClientTestBase):
    def test_simple_get(self):
        self.grab_url(self.httpserver.build_url('test.txt'))
        self.assertEquals(self.grab_url_info['body'], TEST_BODY)

    def test_file_get(self):
        path = resources.path("testdata/httpserver/test.txt")
        self.grab_url("file://" + path)
        self.assertEquals(self.grab_url_info['body'], TEST_BODY)

    def test_simple_get_url_with_spaces(self):
        self.grab_url(self.httpserver.build_url('test%20with%20spaces.txt'))
        self.assertEquals(self.grab_url_info['body'], TEST_BODY)
        # Having spaces in the URL is not legal, but could happen in the wild.
        # We should work around buggy feeds.
        self.grab_url(self.httpserver.build_url('test with spaces.txt'))
        self.assertEquals(self.grab_url_info['body'], TEST_BODY)

    def test_unicode_url(self):
        self.grab_url(unicode(self.httpserver.build_url('test.txt')))
        self.assertEquals(self.grab_url_info['body'], TEST_BODY)

    def check_header(self, key, value):
        self.assertEqual(self.last_http_info('headers')[key], value)

    def check_header_not_present(self, key):
        self.assert_(key not in self.last_http_info('headers'))

    def test_etag(self):
        self.grab_url(self.httpserver.build_url('test.txt'))
        self.check_header_not_present('etag')
        self.grab_url(self.httpserver.build_url('test.txt'), etag='abcdef')
        self.check_header('etag', 'abcdef')

    def test_modified(self):
        m_str = 'Wed, 24 Mar 2010 01:31:03 GMT'
        self.grab_url(self.httpserver.build_url('test.txt'))
        self.check_header_not_present('if-modified-since')
        self.grab_url(self.httpserver.build_url('test.txt'), modified=m_str)
        self.check_header('if-modified-since', m_str)

    def test_unicode_values(self):
        self.grab_url(self.httpserver.build_url('test.txt'),
            modified= u'Wed, 24 Mar 2010 01:31:03 GMT',
            etag=u'abcdef')

    def test_post_vars(self):
        self.grab_url(self.httpserver.build_url('test.txt'), post_vars={'abc': '123', 'foo': 'bar'})
        self.assertEqual(self.last_http_info('method'), 'POST')
        post_data = self.last_http_info('post_data')
        self.assertSameSet(post_data.keys(), ['abc', 'foo'])
        self.assertEquals(post_data.getvalue('abc'), '123')
        self.assertEquals(post_data.getvalue('foo'), 'bar')

    def test_post_files(self):
        f1 = {'filename': 'testing.txt',
                    'mimetype': 'text/plain',
                    'handle': StringIO('contents#1'),
        }
        f2 = {'filename': 'index.html',
                    'mimetype': 'text/html',
                    'handle': StringIO('404 not found'),
        }
        self.grab_url(self.httpserver.build_url('test.txt'), post_vars={'abc': '123'},
                post_files={'file1': f1, 'file2': f2})

    def test_head(self):
        url = self.httpserver.build_url('test.txt')
        self.grab_url(url)
        get_info = self.grab_url_info

        self.grab_headers(url)
        head_info = self.grab_url_info

        self.assertEquals(head_info['body'], '')

        self.assertSameSet(get_info.keys(), head_info.keys())
        for k in head_info:
            if k != 'body':
                if get_info[k] != head_info[k]:
                    raise AssertionError("values differ for key %s: %r, %r"
                            % (k, get_info[k], head_info[k]))

    def test_head_get_fallback(self):
        self.httpserver.disable_head_requests()
        self.test_head()

    def test_info(self):
        self.httpserver.add_header('x-foo', 'bar')
        self.grab_url(self.httpserver.build_url('test.txt'))
        self.assertEquals(self.grab_url_info['x-foo'], 'bar')
        path = resources.path("testdata/httpserver/test.txt")
        self.assertEquals(self.grab_url_info['content-length'],
                len(open(path).read()))

    def test_info_header_callback(self):
        self.httpserver.add_header('x-foo', 'bar')

        def on_headers(headers):
            self.header_callback_info = headers.copy()
        self.grab_url(self.httpserver.build_url('test.txt'), header_callback=on_headers)
        self.assertEquals(self.header_callback_info['x-foo'], 'bar')
        path = resources.path("testdata/httpserver/test.txt")
        self.assertEquals(self.header_callback_info['content-length'],
                len(open(path).read()))
        self.assert_('body' not in self.header_callback_info)

    def check_redirects(self, original, updated, redirected):
        info = self.grab_url_info
        self.assertEquals(info['original-url'],
                self.httpserver.build_url(original))
        self.assertEquals(info['updated-url'],
                self.httpserver.build_url(updated))
        self.assertEquals(info['redirected-url'],
                self.httpserver.build_url(redirected))

    def test_redirect(self):
        self.grab_url(self.httpserver.build_url('temp-redirect'))
        self.check_redirects('temp-redirect', 'temp-redirect', 'test.txt')
        self.grab_url(self.httpserver.build_url('perm-redirect'))
        self.check_redirects('perm-redirect', 'test.txt', 'test.txt')
        self.grab_url(self.httpserver.build_url('temp-then-perm-redirect'))
        self.check_redirects('temp-then-perm-redirect',
                'temp-then-perm-redirect', 'test.txt')
        # try the same thing with HEAD requests
        self.grab_headers(self.httpserver.build_url('temp-redirect'))
        self.check_redirects('temp-redirect', 'temp-redirect', 'test.txt')
        self.grab_headers(self.httpserver.build_url('perm-redirect'))
        self.check_redirects('perm-redirect', 'test.txt', 'test.txt')
        self.grab_headers(self.httpserver.build_url('temp-then-perm-redirect'))
        self.check_redirects('temp-then-perm-redirect',
                'temp-then-perm-redirect', 'test.txt')

    def test_redirect_headers(self):
        # check that we get the headers from the redirected URL, not the
        # original one
        def header_callback(headers):
            self.headers = headers
        self.grab_url(self.httpserver.build_url('temp-redirect'),
                header_callback=header_callback)
        self.assertEquals(self.headers['content-length'], len(TEST_BODY))

    def test_circular_redirect_headers(self):
        def header_callback(headers):
            self.headers = headers
        self.expecting_errback = True
        self.grab_url(self.httpserver.build_url('circular-redirect'),
                header_callback=header_callback)
        self.assert_(isinstance(self.grab_url_error,
            httpclient.TooManyRedirects))
        self.assert_(not hasattr(self, 'headers'))

    def test_filename(self):
        self.grab_url(self.httpserver.build_url("test.txt"))
        self.assertEqual(self.grab_url_info['filename'], 'test.txt')
        # redirects should use the last filename
        self.grab_headers(self.httpserver.build_url('temp-redirect'))
        self.assertEqual(self.grab_url_info['filename'], 'test.txt')
        # content-disposition overrides the default
        self.httpserver.add_header('Content-disposition',
                'filename="myfile.txt"; size=45')
        self.grab_url(self.httpserver.build_url("test.txt"))
        self.assertEqual(self.grab_url_info['filename'], 'myfile.txt')

    def test_charset(self):
        self.grab_url(self.httpserver.build_url("test.txt"))
        self.assertEquals(self.grab_url_info['charset'], 'iso-8859-1')

        self.httpserver.add_header("Content-Type", "text/html; charset=UTF-8")
        self.grab_url(self.httpserver.build_url("test.txt"))
        self.assertEquals(self.grab_url_info['charset'], 'UTF-8')

    def test_upload_progress(self):
        # upload a 100k file
        data = '0' * (1000 * 1024)
        f1 = {'filename': 'testing.txt',
                    'mimetype': 'text/plain',
                    'handle': StringIO(data),
        }
        self.event_loop_timeout = 5
        TIMEOUT = 0.001
        progress_stats = []

        self.last_uploaded = None
        self.last_total = None
        self.saw_total = False
        def check_upload_progress():
            progress = self.client.get_stats()
            if progress.upload_total == -1:
                # client didn't know the total upload at this point.
                self.assertEquals(progress.uploaded, -1)
                eventloop.add_timeout(TIMEOUT, check_upload_progress,
                        'upload progress timeout')
                return
            self.saw_total = True

            if self.last_uploaded is not None:
                # the currently upload size should only increase
                self.assert_(progress.uploaded >= self.last_uploaded)
            self.last_uploaded = progress.uploaded

            if self.last_total is not None:
                # the total upload size shouldn't change
                self.assertEquals(progress.upload_total, self.last_total)
            self.last_total = progress.upload_total

            eventloop.add_timeout(TIMEOUT, check_upload_progress,
                    'upload progress timeout')

        eventloop.add_timeout(TIMEOUT, check_upload_progress,
                'upload progress timeout')
        self.grab_url(self.httpserver.build_url('test.txt'),
                post_files={'file1': f1})

        # make sure at least one of our sending_progress() calls worked
        self.assert_(self.saw_total)
        # there probably could be more tests but I'm not sure how to implement
        # them.

    def test_content_checker(self):
        def check_content(data):
            return True
        self.grab_url(self.httpserver.build_url('test.txt'),
                content_check_callback=check_content)
        self.assertEquals(self.grab_url_error, None)
        self.assertEquals(self.grab_url_info['body'], TEST_BODY)

    def test_content_checker_cancel(self):
        self.httpserver.pause_after(5)
        self.check_content_data = None
        def check_content(data):
            self.check_content_data = data
            if len(data) == 5:
                # wait a bit to see if any more data comes through, which it
                # shouldn't
                eventloop.add_timeout(0.2, self.stopEventLoop, 'stop download',
                        args=(False,))
                return False
            return True
        self.grab_url(self.httpserver.build_url('test.txt'),
                content_check_callback=check_content)
        self.assertEquals(self.grab_url_info, None)
        self.assertEquals(self.grab_url_error, None)
        self.assertEquals(self.check_content_data, 'Miro ')

    def test_content_checker_exception(self):
        self.httpserver.pause_after(5)
        self.check_content_data = None
        self.error_signal_okay = True
        def check_content(data):
            self.check_content_data = data
            if len(data) == 5:
                # wait a bit to see if any more data comes through, which it
                # shouldn't
                eventloop.add_timeout(0.2, self.stopEventLoop, 'stop download',
                        args=(False,))
                1/0
            return True
        self.grab_url(self.httpserver.build_url('test.txt'),
                content_check_callback=check_content)
        self.assertEquals(self.grab_url_info, None)
        self.assertEquals(self.grab_url_error, None)
        self.assertEquals(self.check_content_data, 'Miro ')
        self.assert_(self.saw_error)

    def test_write_file(self):
        filename = tempfile.mktemp('.txt')
        self.grab_url(self.httpserver.build_url('test.txt'),
                write_file=filename)
        self.assert_('body' not in self.grab_url_info)
        self.assertEquals(open(filename).read(), TEST_BODY)

    def _write_partial_file(self, filename):
        # Write the start of test.txt to a file to test HTTP resume capability
        fp = open(filename, 'w')
        fp.write("Miro ")
        fp.close()

    def test_write_file_resume(self):
        filename = tempfile.mktemp('.txt')
        self._write_partial_file(filename)
        self.grab_url(self.httpserver.build_url('test.txt'),
                write_file=filename, resume=True)
        self.assertEquals(open(filename).read(), TEST_BODY)
        self.check_header('Range', 'bytes=5-')

    def test_write_file_no_resume(self):
        filename = tempfile.mktemp('.txt')
        self._write_partial_file(filename)
        self.grab_url(self.httpserver.build_url('test.txt'),
                write_file=filename, resume=False)
        self.assertEquals(open(filename).read(), TEST_BODY)
        self.check_header_not_present('Range')

    def test_write_file_failed_resume(self):
        self.httpserver.disable_resume()
        self.expecting_errback = True
        filename = tempfile.mktemp('.txt')
        self._write_partial_file(filename)
        self.grab_url(self.httpserver.build_url('test.txt'),
                write_file=filename, resume=True)
        self.assert_(isinstance(self.grab_url_error, httpclient.ResumeFailed))

    def test_resume_sizes(self):
        filename = tempfile.mktemp('.txt')
        self._write_partial_file(filename)
        def on_headers(headers):
            self.headers = headers
        self.grab_url(self.httpserver.build_url('test.txt'),
                write_file=filename, resume=True, header_callback=on_headers)
        path = resources.path("testdata/httpserver/test.txt")
        file_size = len(open(path).read())
        initial_size = len("Miro ")
        download_size = file_size - initial_size
        self.assertEquals(self.headers['total-size'], file_size)
        self.assertEquals(self.headers['content-length'], file_size -
                initial_size)
        self.assertEquals(self.client.get_stats().downloaded, download_size)
        self.assertEquals(self.client.get_stats().initial_size, initial_size)

    def test_resume_no_file(self):
        filename = tempfile.mktemp('.txt')
        self.grab_url(self.httpserver.build_url('test.txt'),
                write_file=filename, resume=True)
        self.assertEquals(open(filename).read(), TEST_BODY)
 
    def test_cancel(self):
        filename = tempfile.mktemp('.txt')
        self.httpserver.pause_after(5)
        def cancel_after_5_bytes():
            if self.client.get_stats().downloaded == 5:
                self.client.cancel()
                self.stopEventLoop(False)
            else:
                eventloop.add_timeout(0.1, cancel_after_5_bytes, 'cancel')
        eventloop.add_timeout(0.1, cancel_after_5_bytes, 'cancel')
        self.expecting_errback = True
        self.grab_url(self.httpserver.build_url('test.txt'),
                write_file=filename)
        # Neither the callback, nor the errback should be called
        self.assertEquals(self.grab_url_info, None)
        self.assertEquals(self.grab_url_error, None)
        # We shouldn't delete the file
        self.assert_(os.path.exists(filename))

    def test_remove_file(self):
        filename = tempfile.mktemp('.txt')
        self.httpserver.pause_after(5)
        def cancel_after_5_bytes():
            if self.client.get_stats().downloaded == 5:
                self.client.cancel(remove_file=True)
                self.stopEventLoop(False)
            else:
                eventloop.add_timeout(0.1, cancel_after_5_bytes, 'cancel')
        eventloop.add_timeout(0.1, cancel_after_5_bytes, 'cancel')
        self.expecting_errback = True
        self.grab_url(self.httpserver.build_url('test.txt'),
                write_file=filename)
        self.assertEquals(self.grab_url_info, None)
        self.assertEquals(self.grab_url_error, None)
        self.wait_for_libcurl_manager()
        self.assert_(not os.path.exists(filename))

class BadURLTest(HTTPClientTestBase):
    def setUp(self):
        HTTPClientTestBase.setUp(self)
        self.expecting_errback = True

    def test_scheme(self):
        self.grab_url('pculture.org/normalpage.txt')
        self.check_errback_called()
        self.assert_(isinstance(self.grab_url_error, httpclient.MalformedURL))

    def test_slashes(self):
        self.grab_url('http:jigsaw.w3.org/HTTP/')
        self.check_errback_called()
        self.assert_(isinstance(self.grab_url_error, httpclient.MalformedURL))

    def test_host(self):
        self.grab_url('http:///HTTP/')
        self.check_errback_called()
        self.assert_(isinstance(self.grab_url_error, httpclient.MalformedURL))

    def test_other_scheme(self):
        self.grab_url('rtsp://jigsaw.w3.org/')
        self.check_errback_called()
        self.assert_(isinstance(self.grab_url_error, httpclient.MalformedURL))

class NetworkErrorTest(HTTPClientTestBase):
    def setUp(self):
        HTTPClientTestBase.setUp(self)
        self.expecting_errback = True

    def test_connect_error(self):
        self.grab_url('http://255.255.255.255/')
        self.check_errback_called()
        self.assert_(isinstance(self.grab_url_error,
            httpclient.ConnectionError))

    def test_closed_connection_error(self):
        self.httpserver.add_header('content-length', 100000)
        self.httpserver.close_connection()
        self.grab_url(self.httpserver.build_url('test.txt'))
        self.check_errback_called()
        self.assert_(isinstance(self.grab_url_error,
            httpclient.ServerClosedConnection))

    def test_404_error(self):
        self.expecting_errback = True
        url = self.httpserver.build_url('badfile.txt')
        self.grab_url(url)
        self.assert_(isinstance(self.grab_url_error,
            httpclient.UnexpectedStatusCode))
        self.assertEquals(self.grab_url_error.friendlyDescription,
                "File not found")

    def test_bad_domain_name(self):
        self.grab_url('http://unknowndomainname/')
        self.check_errback_called()
        self.assert_(isinstance(self.grab_url_error,
            httpclient.UnknownHostError))

    def test_unknown_error(self):
        # This is a bit of a weird test.  We want to test the generic libcurl
        # error handle.  However, that code is only a fallback for libcurl
        # error codes that we don't know how to handle.  If we know a way to
        # produce that, then we should fix that code and add a handler for
        # that case.
        #
        # To test things, we manually call CurlTransfer.on_error(), which is
        # the method responsible for dealing with libcurl errors.
        class BogusLibcurlHandle:
            def errstr(self):
                return 'libcurl error'
        bogus_transfer = httpclient.CurlTransfer(None, self.grab_url_callback,
                self.grab_url_errback)
        bogus_transfer.on_error(123456, BogusLibcurlHandle())
        self.runPendingIdles()

        # Check that we saw a NetworkError and that the description strings
        # are unicode (#13359)
        self.check_errback_called()
        self.assert_(isinstance(self.grab_url_error,
            httpclient.NetworkError))
        self.assert_(isinstance(self.grab_url_error.longDescription, unicode))
        self.assert_(isinstance(self.grab_url_error.friendlyDescription,
            unicode))
