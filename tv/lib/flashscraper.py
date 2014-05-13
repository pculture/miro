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

"""``miro.flashscraper`` -- functions for converting a web-page url
to a media url.
"""

import logging
import re
from miro import httpclient
import urlparse
import cgi
from xml.dom import minidom
from urllib import unquote_plus, urlencode
from miro.util import check_u

try:
    import simplejson as json
except ImportError:
    import json

def is_maybe_flashscrapable(url):
    """Returns whether or not the given url is possibly handled by one
    of the flash url converters we have.

    Example:

    >>> is_maybe_flashscrapable(u"http://www.youtube.com/watch?v=qRuNxHqwazs")
    True
    """
    return _get_scrape_function_for(url) is not None

def try_scraping_url(url, callback):
    check_u(url)
    scrape = _get_scrape_function_for(url)

    if scrape is not None:
        scrape(url,
               lambda newurl, content_type=u"video/x-flv", title=None: _actual_url_callback(url, callback, newurl, content_type, title))
    else:
        callback(url)

# =============================================================================

# The callback is wrapped in this for flv videos
def _actual_url_callback(url, callback, new_url, content_type, title):
    if new_url:
        check_u(new_url)
    callback(new_url, content_type=content_type, title=title)

def _get_scrape_function_for(url):
    check_u(url)
    for scrape_info in SCRAPER_INFO_MAP:
        if scrape_info['pattern'].match(url) is not None:
            return scrape_info['func']
    return None

def _scrape_youtube_url(url, callback):
    check_u(url)

    components = urlparse.urlsplit(url)
    params = cgi.parse_qs(components[3])

    video_id = None
    if components[2] == u'/watch' and 'v' in params:
        try:
            video_id = params['v'][0]
        except IndexError:
            pass
    elif components[2].startswith('/v/'):
        m = re.compile(r'/v/([\w-]+)').match(components[2])
        if m is not None:
            video_id = m.group(1)

    if video_id is None:
        logging.warning('_scrape_youtube_url: unable to scrape YouTube Video URL')
        callback(None)
        return

    try:
        url = u"http://www.youtube.com/get_video_info?video_id=%s&el=embedded&ps=default&eurl=" % video_id
        httpclient.grab_url(
            url,
            lambda x: _youtube_callback_step2(x, video_id, callback),
            lambda x: _youtube_errback(x, callback))

    except StandardError:
        logging.exception("youtube_callback: unable to scrape YouTube Video URL")
        callback(None)

def _youtube_callback_step2(info, video_id, callback):
    try:
        body = info['body']
        params = cgi.parse_qs(body)
        if params.get("status", [""])[0] == "fail":
            logging.warning("youtube download failed because: %s",
                            params.get("reason", ["unknown"])[0])
            callback(None)
            return

        # fmt_url_map is a comma separated list of pipe separated
        # pairs of fmt, url
        # build the format codes.
        fmt_list = [x.split('/')[0] for x in params['fmt_list'][0].split(',')]
        # build the list of available urls.
        stream_map = params["url_encoded_fmt_stream_map"][0].split(",")
        fmt_url_map = dict()
        # strip url= from url=xxxxxx, strip trailer.  Strip duplicate params.
        for fmt, stream_map_data in zip(fmt_list, stream_map):
            stream_map = cgi.parse_qs(stream_map_data)
            fmt_url_map[fmt] = stream_map['url'][0]

        title = params.get("title", ["No title"])[0]
        try:
            title = title.decode("utf-8")
        except UnicodeDecodeError:
            title = title.decode("ascii", "ignore")

        logging.debug("fmt_url_map keys: %s", fmt_url_map.keys())

        # http://en.wikipedia.org/wiki/YouTube#Quality_and_codecs
        for fmt, content_type in [("22", u"video/mp4"),
                                  ("18", u"video/mp4"),
                                  ("5", u"video/x-flv")]:
            if fmt in fmt_url_map:
                new_url = fmt_url_map[fmt]
                logging.debug("youtube download: trying %s %s", fmt, new_url)

                callback(
                    unicode(new_url), content_type=content_type,
                    title=title)
                return

        _youtube_errback(info, callback)

    except StandardError:
        logging.exception("youtube_callback_step2: unable to scrape YouTube URL")
        callback(None)

def _youtube_errback(err, callback):
    logging.warning("youtube_errback: network error scraping YouTube url %s", err)
    callback(None)

def _scrape_google_video_url(url, callback):
    try:
        components = urlparse.urlsplit(url)
        params = cgi.parse_qs(components[3])
        doc_id = params['docId'][0]
        url = (u"http://video.google.com/videofile/%s.flv?docid=%s&itag=5" %
               (doc_id, doc_id))
        callback(url)
    except StandardError:
        logging.warning("unable to scrape Google Video URL: %s", url)
        callback(None)

def _scrape_lulu_video_url(url, callback):
    try:
        components = urlparse.urlsplit(url)
        params = cgi.parse_qs(components[3])
        url = unquote_plus(params['file'][0]).decode('ascii', 'replace')
        callback(url)
    except StandardError:
        logging.warning("unable to scrape LuLu.tv Video URL: %s", url)
        callback(None)

def _scrape_vmix_video_url(url, callback):
    try:
        components = urlparse.urlsplit(url)
        params = cgi.parse_qs(components[3])
        type_ = params['type'][0]
        id_ = params['id'][0]
        l = params['l'][0]
        url = (u"http://sdstage01.vmix.com/videos.php?type=%s&id=%s&l=%s" %
               (type_, id_, l))
        httpclient.grab_url(url, lambda x: _scrape_vmix_callback(x, callback),
                           lambda x: _scrape_vmix_errback(x, callback))

    except StandardError:
        logging.warning("unable to scrape VMix Video URL: %s", url)
        callback(None)

def _scrape_vmix_callback(info, callback):
    try:
        doc = minidom.parseString(info['body'])
        url = doc.getElementsByTagName('file').item(0).firstChild.data.decode('ascii', 'replace')
        callback(url)
    except StandardError:
        logging.warning("unsable to scrape XML for VMix Video URL %s",
                        info['redirected-url'])
        callback(None)

def _scrape_vmix_errback(err, callback):
    logging.warning("network error scraping VMix Video URL")
    callback(None)

def _scrape_vsocial_video_url(url, callback):
    try:
        components = urlparse.urlsplit(url)
        params = cgi.parse_qs(components[3])
        v = params['v'][0]
        url = u'http://static.vsocial.com/varmedia/vsocial/flv/%s_out.flv' % v
        callback(url)
    except StandardError:
        logging.warning("unable to scrape VSocial URL: %s", url)
        callback(None)

def _scrape_veohtv_video_url(url, callback):
    try:
        components = urlparse.urlsplit(url)
        params = cgi.parse_qs(components[3])
        t = params['type'][0]
        permalink_id = params['permalinkId'][0]
        url = u'http://www.veoh.com/movieList.html?type=%s&permalinkId=%s&numResults=45' % (t, permalink_id)
        httpclient.grab_url(url, lambda x: _scrape_veohtv_callback(x, callback),
                           lambda x: _scrape_veohtv_errback(x, callback))
    except StandardError:
        logging.warning("unable to scrape Veoh URL: %s", url)
        callback(None)

def _scrape_veohtv_callback(info, callback):
    url = info['redirected-url']
    try:
        params = cgi.parse_qs(info['body'])
        file_hash = params['previewHashLow'][0]
        if file_hash.endswith(","):
            file_hash = file_hash[:-1]
        url = (u'http://ll-previews.veoh.com/previews/get.jsp?fileHash=%s' %
               file_hash)
        callback(url)
    except StandardError:
        logging.warning("unable to scrape Veoh URL data: %s", url)
        callback(None)

def _scrape_veohtv_errback(err, callback):
    logging.warning("network error scraping Veoh TV Video URL")
    callback(None)

def _scrape_break_video_url(url, callback):
    httpclient.grab_headers(url, lambda x: _scrape_break_callback(x, callback),
                           lambda x: _scrape_break_errback(x, callback))

def _scrape_break_callback(info, callback):
    url = info['redirected-url']
    try:
        components = urlparse.urlsplit(url)
        params = cgi.parse_qs(components[3])
        url = unquote_plus(params['sVidLoc'][0]).decode('ascii', 'replace')
        callback(url)
    except StandardError:
        logging.warning("unable to scrape Break URL: %s", url)
        callback(None)

def _scrape_break_errback(info, callback):
    logging.warning("network error scraping Break Video URL")
    callback(None)

def _scrape_green_peace_video_url(url, callback):
    logging.warning("unable to scrape Green peace Video URL %s", url)
    callback(None)

VIMEO_RE = re.compile(r'http://([^/]+\.)?vimeo.com/[^\d]*(\d+)')

def _scrape_vimeo_video_url(url, callback, countdown=10):
    try:
        id_ = VIMEO_RE.match(url).group(2)
        download_url = 'http://vimeo.com/%s?action=download' % id_
        httpclient.grab_url(
            download_url,
            lambda x: _scrape_vimeo_download_callback(x, callback),
            lambda x: _scrape_vimeo_video_url_try_2(url, callback, id_),
            extra_headers={
                'Referer': 'http://vimeo.com/%s' % id_,
                'X-Requested-With': 'XMLHttpRequest',
                'User-Agent': ('Mozilla/5.0 (X11; Linux x86_64) '
                               'AppleWebKit/536.11 (KHTML, like Gecko) '
                               'Chrome/20.0.1132.8 Safari/536.11')
                })
    except StandardError:
        logging.exception("Unable to scrape vimeo.com video URL: %s", url)
        callback(None)

VIMEO_LINK_RE = re.compile('<a href="/(.*?)" download=".*?_(\d+)x(\d+).mp4"')
def _scrape_vimeo_download_callback(info, callback):
    """
    Currently, Vimeo returns links like this:
    * Mobile HD
    * HD
    * SD
    * Original

    We grab them all, and callback the one with the largest width by height.
    """
    largest_url, size = None, 0
    try:
        for url, width, height in VIMEO_LINK_RE.findall(info['body']):
            trial_size = int(width) * int(height)
            if int(width) * int(height) > size:
                largest_url, size = url, trial_size
    except:
        logging.exception('during parse of Vimeo response for %r',
                          info['original-url'])
        callback(None)

    if largest_url is not None:
        callback(u'http://vimeo.com/%s' % largest_url,
                 content_type=u'video/mp4')
    else:
        _scrape_vimeo_download_errback("no largest url", callback,
                                       info['original-url'])

def _scrape_vimeo_video_url_try_2(url, callback, vimeo_id):
    """Try scraping vimeo URLs by scraping the javascript code.

    This method seems less reliable than the regular method, but it works for
    private videos.  See #19305
    """
    video_url = u'http://vimeo.com/%s' % vimeo_id

    httpclient.grab_url(
            video_url,
            lambda x: _scrape_vimeo_download_try_2_callback(x, callback,
                                                            vimeo_id),
            lambda x: _scrape_vimeo_download_errback(x, callback, url))

VIMEO_JS_DATA_SCRAPE_RE = re.compile(r'clip[0-9_]+\s*=\s*(.*}});')
VIMEO_SCRAPE_SIG_RE = re.compile(r'"signature":"([0-9a-fA-F]+)"')
VIMEO_SCRAPE_TIMESTAMP_RE = re.compile(r'"timestamp":([0-9]+)')
VIMEO_SCRAPE_FILES_RE = re.compile(r'"files":({[^}]+})')

def _scrape_vimeo_download_try_2_callback(info, callback, vimeo_id):
    # first step is to find the javascript code that we care about in the HTML
    # page
    m = VIMEO_JS_DATA_SCRAPE_RE.search(info['body'])
    if m is None:
        logging.warn("Unable to scrape %s for JSON", info['original-url'])
        callback(None)
        return
    json_data = m.group(1)
    try:
        signature = VIMEO_SCRAPE_SIG_RE.search(json_data).group(1)
        timestamp = VIMEO_SCRAPE_TIMESTAMP_RE.search(json_data).group(1)
        files_str = VIMEO_SCRAPE_FILES_RE.search(json_data).group(1)
    except AttributeError:
        # one of the RE's retured None
        logging.warn("Unable to scrape %s", info['original-url'])
        callback(None)
        return
    try:
        files_data = json.loads(files_str)
        codec = files_data.keys()[0]
        quality = files_data[codec][0]
    except StandardError:
        logging.warn("Unable to scrape vimeo files variable (%s)",
                     files_match.group(1))
        callback(None)
    url = ('http://player.vimeo.com/play_redirect?'
           'clip_id=%s&quality=%s&codecs=%s&time=%s'
           '&sig=%s&type=html5_desktop_local' %
           (vimeo_id, quality, codec, timestamp, signature))
    logging.debug("_scrape_vimeo_download_try_2_callback scraped URL: %s",
                  url)
    callback(url)

def _scrape_vimeo_download_errback(err, callback, url):
    logging.warning("Unable to scrape %r\nerror: %s", url, err)
    callback(None)

# =============================================================================

SCRAPER_INFO_MAP = [
    {'pattern': re.compile(r'https?://([^/]+\.)?youtube.com/(watch|v)'), 'func': _scrape_youtube_url},
    {'pattern': re.compile(r'http://video.google.com/googleplayer.swf'), 'func': _scrape_google_video_url},
    {'pattern': re.compile(r'http://([^/]+\.)?lulu.tv/wp-content/flash_play/flvplayer'), 'func': _scrape_lulu_video_url},
    {'pattern': re.compile(r'http://([^/]+\.)?vmix.com/flash/super_player.swf'), 'func': _scrape_vmix_video_url},
    {'pattern': re.compile(r'http://([^/]+\.)?vsocial.com/flash/vp.swf'), 'func': _scrape_vsocial_video_url},
    {'pattern': re.compile(r'http://([^/]+\.)?veoh.com/multiplayer.swf'), 'func': _scrape_veohtv_video_url},
    {'pattern': re.compile(r'http://([^/]+\.)?greenpeaceweb.org/GreenpeaceTV1Col.swf'), 'func': _scrape_green_peace_video_url},
    {'pattern': re.compile(r'http://([^/]+\.)?break.com/'), 'func': _scrape_break_video_url},
    {'pattern': re.compile(r'http://([^/]+\.)?vimeo.com/\d+'), 'func': _scrape_vimeo_video_url},
    {'pattern': re.compile(r'http://([^/]+\.)?vimeo.com/moogaloop.swf'), 'func': _scrape_vimeo_video_url},
]
