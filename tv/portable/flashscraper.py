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

import logging
import re
from miro import httpclient
import urlparse
import cgi
from xml.dom import minidom
from urllib import unquote_plus
from miro.util import checkU

def is_maybe_flashscrapable(url):
    return _get_scrape_function_for(url) is not None

def try_scraping_url(url, callback):
    checkU(url)
    scrape = _get_scrape_function_for(url)
    if scrape is not None:
        scrape(url, lambda x, y=u"video/x-flv": _actual_url_callback(url, callback, x, y))
    else:
        callback(url)

# =============================================================================

# The callback is wrapped in this for flv videos
def _actual_url_callback(url, callback, newURL, contentType):
    if newURL:
        checkU(newURL)
    callback(newURL, contentType=contentType)

def _get_scrape_function_for(url):
    checkU(url)
    for scrapeInfo in scraperInfoMap:
        if scrapeInfo['pattern'].match(url) is not None:
            return scrapeInfo['func']
    return None

def _scrape_youtube_url(url, callback):
    checkU(url)

    components = urlparse.urlsplit(url)
    params = cgi.parse_qs(components[3])

    # if it's a watch url, we convert it to a form we already handle
    if components[2] == u'/watch' and 'v' in params:
        url = 'http://www.youtube.com/v/%s&f=gdata_videos' % params["v"][0]

    httpclient.grabHeaders(url, lambda x: _youtube_callback(x, callback),
                           lambda x:_youtube_errback(x, callback))

def _youtube_callback(info, callback):
    redirected_url = info['redirected-url']
    try:
        components = urlparse.urlsplit(redirected_url)
        params = cgi.parse_qs(components[3])
        videoID = params['video_id'][0]
        url = u"http://www.youtube.com/get_video_info?video_id=%s&el=embedded&ps=default&eurl=" % videoID
        httpclient.grabURL(url, lambda x: _youtube_callback_step2(x, videoID, callback),
                           lambda x: _youtube_errback(x, callback))

    except (SystemExit, KeyboardInterrupt):
        raise
    except:
        logging.exception("youtube_callback: unable to scrape YouTube Video URL")
        callback(None)

def _youtube_get_first_successful(info, current_url, urls, callback):
    status = info["status"]

    if not (status == 0 or status / 100 == 4):
        callback(current_url)
        return

    if len(urls) == 0:
        callback(None)
        return

    current_url, urls = urls[0], urls[1:]

    logging.debug("youtube download: trying %s", current_url)
    httpclient.grabHeaders(current_url, lambda x: _youtube_get_first_successful(x, current_url, urls, callback),
            lambda x: _youtube_errback(x, callback))

def _youtube_callback_step2(info, videoID, callback):
    try:
        body = info['body']
        params = cgi.parse_qs(body)
        token = params['token'][0]

        lodef_url = u"http://www.youtube.com/get_video?video_id=%s&t=%s&eurl=&el=embedded&ps=default" % (videoID, token)
        hidef_url = lodef_url + u"&fmt=18"
        hihidef_url = lodef_url + u"&fmt=22"
        logging.debug("youtube download: trying %s", hihidef_url)
        # go through the urls we have until we find one that's successful or
        # 404 on all of them.
        httpclient.grabHeaders(hihidef_url,
                lambda x: _youtube_get_first_successful(x, hihidef_url, [hidef_url, lodef_url], callback),
                lambda x: _youtube_errback(x, callback))

    except:
        logging.exception("youtube_callback_step2: unable to scrape YouTube Video URL")
        callback(None)

def _youtube_errback(err, callback):
    logging.warning("youtube_errback: network error scraping YouTube video url %s", err)
    callback(None)

def _scrape_google_video_url(url, callback):
    try:
        components = urlparse.urlsplit(url)
        params = cgi.parse_qs(components[3])
        docId = params['docId'][0]
        url = u"http://video.google.com/videofile/%s.flv?docid=%s&itag=5" % (docId, docId)
        callback(url)
    except (SystemExit, KeyboardInterrupt):
        raise
    except:
        print "DTV: WARNING, unable to scrape Google Video URL: %s" % url
        callback(None)

def _scrape_lulu_video_url(url, callback):
    try:
        components = urlparse.urlsplit(url)
        params = cgi.parse_qs(components[3])
        url = unquote_plus(params['file'][0]).decode('ascii','replace')
        callback(url)
    except (SystemExit, KeyboardInterrupt):
        raise
    except:
        print "DTV: WARNING, unable to scrape LuLu.tv Video URL: %s" % url
        callback(None)

def _scrape_vmix_video_url(url, callback):
    try:
        components = urlparse.urlsplit(url)
        params = cgi.parse_qs(components[3])
        t = params['type'][0]
        ID = params['id'][0]
        l = params['l'][0]
        url = u"http://sdstage01.vmix.com/videos.php?type=%s&id=%s&l=%s" % (t, ID, l)
        httpclient.grabURL(url, lambda x: _scrape_vmix_callback(x, callback),
                           lambda x: _scrape_vmix_errback(x, callback))

    except (SystemExit, KeyboardInterrupt):
        raise
    except:
        print "DTV: WARNING, unable to scrape VMix Video URL: %s" % url
        callback(None)

def _scrape_vmix_callback(info, callback):
    try:
        doc = minidom.parseString(info['body'])
        url = doc.getElementsByTagName('file').item(0).firstChild.data.decode('ascii', 'replace')
        callback(url)
    except (SystemExit, KeyboardInterrupt):
        raise
    except:
        print "DTV: WARNING, unsable to scrape XML for VMix Video URL %s" % info['redirected-url']
        callback(None)

def _scrape_vmix_errback(err, callback):
    print "DTV: WARNING, network error scraping VMix Video URL"
    callback(None)

def _scrape_dailymotion_video_url(url, callback):
    httpclient.grabHeaders(url, lambda x: _scrape_dailymotion_callback(x, callback),
                           lambda x: _scrape_dailymotion_errback(x, callback))

def _scrape_dailymotion_callback(info, callback):
    url = info['redirected-url']
    try:
        components = urlparse.urlsplit(url)
        params = cgi.parse_qs(components[3])
        url = unquote_plus(params['video'][0]).decode('ascii', 'replace')
        url = url.split("||")[0]
        url = url.split("@@")[0]
        url = u"http://www.dailymotion.com%s" % url
        callback(url)
    except (SystemExit, KeyboardInterrupt):
        raise
    except:
        print "DTV: WARNING, unable to scrape Daily Motion URL: %s" % url
        callback(None)

def _scrape_dailymotion_errback(info, callback):
    print "DTV: WARNING, network error scraping Daily Motion Video URL"
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
        print "DTV: WARNING, unable to scrape VSocial URL: %s" % url
        callback(None)

def _scrape_veohtv_video_url(url, callback):
    try:
        components = urlparse.urlsplit(url)
        params = cgi.parse_qs(components[3])
        t = params['type'][0]
        permalinkId = params['permalinkId'][0]
        url = u'http://www.veoh.com/movieList.html?type=%s&permalinkId=%s&numResults=45' % (t, permalinkId)
        httpclient.grabURL(url, lambda x: _scrape_veohtv_callback(x, callback),
                           lambda x: _scrape_veohtv_errback(x, callback))
    except (SystemExit, KeyboardInterrupt):
        raise
    except:
        print "DTV: WARNING, unable to scrape Veoh URL: %s" % url
        callback(None)

def _scrape_veohtv_callback(info, callback):
    url = info['redirected-url']
    try:
        params = cgi.parse_qs(info['body'])
        fileHash = params['previewHashLow'][0]
        if fileHash.endswith(","):
            fileHash = fileHash[:-1]
        url = u'http://ll-previews.veoh.com/previews/get.jsp?fileHash=%s' % fileHash
        callback(url)
    except (SystemExit, KeyboardInterrupt):
        raise
    except:
        print "DTV: WARNING, unable to scrape Veoh URL data: %s" % url
        callback(None)

def _scrape_veohtv_errback(err, callback):
    print "DTV: WARNING, network error scraping Veoh TV Video URL"
    callback(None)

def _scrape_break_video_url(url, callback):
    httpclient.grabHeaders(url, lambda x: _scrape_break_callback(x, callback),
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
        print "DTV: WARNING, unable to scrape Break URL: %s" % url
        callback(None)

def _scrape_break_errback(info, callback):
    print "DTV: WARNING, network error scraping Break Video URL"
    callback(None)

def _scrape_green_peace_video_url(url, callback):
    print "DTV: Warning, unable to scrape Green peace Video URL %s" % url
    print callback(None)

# =============================================================================

scraperInfoMap = [
    {'pattern': re.compile(r'http://([^/]+\.)?youtube.com/(?!get_video(\.php)?)'), 'func': _scrape_youtube_url},
    {'pattern': re.compile(r'http://video.google.com/googleplayer.swf'), 'func': _scrape_google_video_url},
    {'pattern': re.compile(r'http://([^/]+\.)?lulu.tv/wp-content/flash_play/flvplayer'), 'func': _scrape_lulu_video_url},
    {'pattern': re.compile(r'http://([^/]+\.)?vmix.com/flash/super_player.swf'), 'func': _scrape_vmix_video_url},
    {'pattern': re.compile(r'http://([^/]+\.)?dailymotion.com/swf'), 'func': _scrape_dailymotion_video_url},
    {'pattern': re.compile(r'http://([^/]+\.)?vsocial.com/flash/vp.swf'), 'func': _scrape_vsocial_video_url},
    {'pattern': re.compile(r'http://([^/]+\.)?veoh.com/multiplayer.swf'), 'func': _scrape_veohtv_video_url},
    {'pattern': re.compile(r'http://([^/]+\.)?greenpeaceweb.org/GreenpeaceTV1Col.swf'), 'func': _scrape_green_peace_video_url},
    {'pattern': re.compile(r'http://([^/]+\.)?break.com/'), 'func': _scrape_break_video_url},
]
