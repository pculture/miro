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

"""``miro.flashscraper`` -- functions for converting a web-page url
to a media url.
"""

import logging
import re
from miro import httpclient
import urlparse
import cgi
from xml.dom import minidom
from urllib import unquote_plus
from miro.util import check_u

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
    callback(new_url, contentType=content_type, title=title)

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

    if components[2] == u'/watch' and 'v' in params:
        video_id = params['v'][0]
    elif components[2].startswith('/v/'):
        video_id = re.compile(r'/v/([\w-]+)').match(components[2]).group(1)
    else:
        logging.warning('_scrape_youtube_url: unable to scrape YouTube Video URL')
        callback(None)
        return

    try:
        url = u"http://www.youtube.com/get_video_info?video_id=%s&el=embedded&ps=default&eurl=" % video_id
        httpclient.grab_url(
            url,
            lambda x: _youtube_callback_step2(x, video_id, callback),
            lambda x: _youtube_errback(x, callback))

    except (SystemExit, KeyboardInterrupt):
        raise
    except:
        logging.exception("youtube_callback: unable to scrape YouTube Video URL")
        callback(None)

def _youtube_callback_step2(info, video_id, callback):
    try:
        body = info['body']
        params = cgi.parse_qs(body)
        if params.get("status", [""])[0] == "fail":
            logging.info("youtube download failed because: %s",
                         params.get("reason", ["unknown"])[0])
            callback(None)
            return

        # fmt_url_map is a comma separated list of pipe separated
        # pairs of fmt, url
        fmt_url_map = params["fmt_url_map"][0].split(",")
        fmt_url_map = dict([mem.split("|") for mem in fmt_url_map])

        title = params.get("title", ["No title"])[0]
        try:
            title = title.decode("utf-8")
        except UnicodeDecodeError:
            title = title.decode("ascii", "ignore")

        # http://en.wikipedia.org/wiki/YouTube#Quality_and_codecs
        for fmt, content_type in [("22", u"video/mp4"),
                                  ("18", u"video/mp4"),
                                  ("5", u"video/x-flv")]:
            if fmt in fmt_url_map:
                new_url = fmt_url_map[fmt]
                logging.debug("youtube download: trying %s", new_url)

                callback(
                    unicode(new_url), content_type=content_type,
                    title=title)
                return

        _youtube_errback(info, callback)

    except (SystemExit, KeyboardInterrupt):
        raise
    except:
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
    except (SystemExit, KeyboardInterrupt):
        raise
    except:
        logging.warning("unable to scrape Google Video URL: %s", url)
        callback(None)

def _scrape_lulu_video_url(url, callback):
    try:
        components = urlparse.urlsplit(url)
        params = cgi.parse_qs(components[3])
        url = unquote_plus(params['file'][0]).decode('ascii', 'replace')
        callback(url)
    except (SystemExit, KeyboardInterrupt):
        raise
    except:
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

    except (SystemExit, KeyboardInterrupt):
        raise
    except:
        logging.warning("unable to scrape VMix Video URL: %s", url)
        callback(None)

def _scrape_vmix_callback(info, callback):
    try:
        doc = minidom.parseString(info['body'])
        url = doc.getElementsByTagName('file').item(0).firstChild.data.decode('ascii', 'replace')
        callback(url)
    except (SystemExit, KeyboardInterrupt):
        raise
    except:
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
    except (SystemExit, KeyboardInterrupt):
        raise
    except:
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
    except (SystemExit, KeyboardInterrupt):
        raise
    except:
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
    except (SystemExit, KeyboardInterrupt):
        raise
    except:
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
    except (SystemExit, KeyboardInterrupt):
        raise
    except:
        logging.warning("unable to scrape Break URL: %s", url)
        callback(None)

def _scrape_break_errback(info, callback):
    logging.warning("network error scraping Break Video URL")
    callback(None)

def _scrape_green_peace_video_url(url, callback):
    logging.warning("unable to scrape Green peace Video URL %s", url)
    callback(None)

VIMEO_RE = re.compile(r'http://([^/]+\.)?vimeo.com/(\d+)')

def _scrape_vimeo_video_url(url, callback):
    try:
        id_ = VIMEO_RE.match(url).group(2)
        url = u"http://www.vimeo.com/moogaloop/load/clip:%s" % id_
        httpclient.grab_url(
            url,
            lambda x: _scrape_vimeo_callback(x, callback),
            lambda x: _scrape_vimeo_errback(x, callback))
    except (SystemExit, KeyboardInterrupt):
        raise
    except:
        logging.warning("Unable to scrape vimeo.com video URL: %s", url)
        callback(None)

MEGALOOP_RE = re.compile(r'http://([^/]+\.)?vimeo.com/moogaloop.swf\?clip_id=(\d+)')

def _scrape_vimeo_moogaloop_url(url, callback):
    try:
        id_ = MEGALOOP_RE.match(url).group(2)
        url = u"http://www.vimeo.com/moogaloop/load/clip:%s" % id_
        httpclient.grab_url(
            url,
            lambda x: _scrape_vimeo_callback(x, callback),
            lambda x: _scrape_vimeo_errback(x, callback))
    except (SystemExit, KeyboardInterrupt):
        raise
    except:
        logging.warning("Unable to scrape vimeo.com moogaloop URL: %s", url)
        callback(None)

VIMEO_CLIP_RE = re.compile(r'http://www.vimeo.com/moogaloop/load/clip:(\d+)')

def _scrape_vimeo_callback(info, callback):
    url = info['redirected-url']
    try:
        doc = minidom.parseString(info['body'])
        id_ = VIMEO_CLIP_RE.match(url).group(1)
        req_sig = doc.getElementsByTagName('request_signature').item(0).firstChild.data.decode('ascii', 'replace')
        req_sig_expires = doc.getElementsByTagName('request_signature_expires').item(0).firstChild.data.decode('ascii', 'replace')
        url = (u"http://www.vimeo.com/moogaloop/play/clip:%s/%s/%s/?q=sd" %
               (id_, req_sig, req_sig_expires))
        # TODO: HD support
        callback(url)
    except (SystemExit, KeyboardInterrupt):
        raise
    except:
        logging.warning("Unable to scrape XML for vimeo.com video URL: %s", url)
        callback(None)

def _scrape_vimeo_errback(err, callback):
    logging.warning("Network error scraping vimeo.com video URL")
    callback(None)

# =============================================================================

SCRAPER_INFO_MAP = [
    {'pattern': re.compile(r'http://([^/]+\.)?youtube.com/(watch|v)'), 'func': _scrape_youtube_url},
    {'pattern': re.compile(r'http://video.google.com/googleplayer.swf'), 'func': _scrape_google_video_url},
    {'pattern': re.compile(r'http://([^/]+\.)?lulu.tv/wp-content/flash_play/flvplayer'), 'func': _scrape_lulu_video_url},
    {'pattern': re.compile(r'http://([^/]+\.)?vmix.com/flash/super_player.swf'), 'func': _scrape_vmix_video_url},
    {'pattern': re.compile(r'http://([^/]+\.)?vsocial.com/flash/vp.swf'), 'func': _scrape_vsocial_video_url},
    {'pattern': re.compile(r'http://([^/]+\.)?veoh.com/multiplayer.swf'), 'func': _scrape_veohtv_video_url},
    {'pattern': re.compile(r'http://([^/]+\.)?greenpeaceweb.org/GreenpeaceTV1Col.swf'), 'func': _scrape_green_peace_video_url},
    {'pattern': re.compile(r'http://([^/]+\.)?break.com/'), 'func': _scrape_break_video_url},
    {'pattern': re.compile(r'http://([^/]+\.)?vimeo.com/\d+'), 'func': _scrape_vimeo_video_url},
    {'pattern': re.compile(r'http://([^/]+\.)?vimeo.com/moogaloop.swf'), 'func': _scrape_vimeo_moogaloop_url},
]
