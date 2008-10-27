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

import re
from miro import httpclient
import urlparse
import cgi
from xml.dom import minidom
from urllib import unquote_plus
from miro.util import checkU, returnsUnicode
import logging

# =============================================================================

def tryScrapingURL(url, callback):
    checkU(url)
    scrape =_getScrapeFunctionFor(url)
    if scrape is not None:
        scrape(url,lambda x, y=u"video/x-flv":_actualURLCallback(url,callback,x,y))
    else:
        callback(url)
    
# =============================================================================

# The callback is wrapped in this for flv videos
def _actualURLCallback(url, callback, newURL, contentType):
    if newURL:
        checkU(newURL)
    callback(newURL, contentType=contentType)

def _getScrapeFunctionFor(url):
    checkU(url)
    for scrapeInfo in scraperInfoMap:
        if re.compile(scrapeInfo['pattern']).match(url) is not None:
            return scrapeInfo['func']
    return None

def _scrapeYouTubeURL(url, callback):
    checkU(url)
    httpclient.grabHeaders(url, lambda x:_youTubeCallback(x,callback), lambda x:_youTubeErrback(x,callback))

def _youTubeCallback(info, callback):
    redirected_url = info["redirected-url"]
    try:
        components = urlparse.urlsplit(redirected_url)
        params = cgi.parse_qs(components[3])
        videoID = params['video_id'][0]
        url = u"http://www.youtube.com/get_video_info?video_id=%s&el=embedded&ps=default&eurl=" % videoID
        httpclient.grabURL(url, lambda x: _youTubeCallbackStep2(x, videoID, callback),
                           lambda x: _youTubeErrback(x, callback))
    except:
        logging.exception("youTubeCallback: unable to scrape YouTube Video URL")
        callback(None)

def _youTubeCallbackStep2(info, videoID, callback):
    try:
        body = info['body']
        params = cgi.parse_qs(body)
        token = params['token'][0]

        url = u"http://www.youtube.com/get_video?video_id=%s&t=%s&eurl=&el=embedded&ps=default" % (videoID, token)
        callback(url)
    except:
        logging.exception("youTubeCallbackStep2: unable to scrape YouTube Video URL")
        callback(None)

def _youTubeErrback(err, callback):
    print "DTV: WARNING, network error scraping You Tube Video URL"
    callback(None)

def _scrapeGoogleVideoURL(url, callback):
    try:
        components = urlparse.urlsplit(url)
        params = cgi.parse_qs(components[3])
        docId = params['docId'][0]
        url = u"http://video.google.com/videofile/%s.flv?docid=%s&itag=5" % (docId, docId)
        callback(url)
    except:
        print "DTV: WARNING, unable to scrape Google Video URL: %s" % url
        callback(None)

def _scrapeLuLuVideoURL(url, callback):
    try:
        components = urlparse.urlsplit(url)
        params = cgi.parse_qs(components[3])
        url = unquote_plus(params['file'][0]).decode('ascii','replace')
        callback(url)
    except:
        print "DTV: WARNING, unable to scrape LuLu.tv Video URL: %s" % url
        callback(None)

def _scrapeVMixVideoURL(url, callback):
    try:
        components = urlparse.urlsplit(url)
        params = cgi.parse_qs(components[3])
        t = params['type'][0]
        ID = params['id'][0]
        l = params['l'][0]
        url = u"http://sdstage01.vmix.com/videos.php?type=%s&id=%s&l=%s" % (t,ID,l)
        httpclient.grabURL(url, lambda x:_scrapeVMixCallback(x,callback),
                           lambda x:_scrapeVMixErrback(x,callback))

    except:
        print "DTV: WARNING, unable to scrape VMix Video URL: %s" % url
        callback(None)

def _scrapeVMixCallback(info, callback):
    try:
        doc = minidom.parseString(info['body'])
        url = doc.getElementsByTagName('file').item(0).firstChild.data.decode('ascii','replace')
        callback(url)
    except:
        print "DTV: WARNING, unsable to scrape XML for VMix Video URL %s" % info['redirected-url']
        callback(None)

def _scrapeVMixErrback(err, callback):
    print "DTV: WARNING, network error scraping VMix Video URL"
    callback(None)

def _scrapeDailyMotionVideoURL(url, callback):
    httpclient.grabHeaders(url, lambda x:_scrapeDailyMotionCallback(x,callback),
                           lambda x:_scrapeDailyMotionErrback(x,callback))

def _scrapeDailyMotionCallback(info, callback):
    url = info['redirected-url']
    try:
        components = urlparse.urlsplit(url)
        params = cgi.parse_qs(components[3])
        url = unquote_plus(params['video'][0]).decode('ascii', 'replace')
        url = url.split("||")[0]
        url = url.split("@@")[0]
        url = u"http://www.dailymotion.com%s" % url
        callback(url)
    except:
        print "DTV: WARNING, unable to scrape Daily Motion URL: %s" % url
        callback(None)

def _scrapeDailyMotionErrback(info, callback):
    print "DTV: WARNING, network error scraping Daily Motion Video URL"
    callback(None)

def _scrapeVSocialVideoURL(url, callback):
    try:
        components = urlparse.urlsplit(url)
        params = cgi.parse_qs(components[3])
        v = params['v'][0]
        url = u'http://static.vsocial.com/varmedia/vsocial/flv/%s_out.flv' % v
        callback(url)
    except:
        print "DTV: WARNING, unable to scrape VSocial URL: %s" % url
        callback(None)

def _scrapeVeohTVVideoURL(url, callback):
    try:
        components = urlparse.urlsplit(url)
        params = cgi.parse_qs(components[3])
        t = params['type'][0]
        permalinkId= params['permalinkId'][0]
        url = u'http://www.veoh.com/movieList.html?type=%s&permalinkId=%s&numResults=45' % (t, permalinkId)
        httpclient.grabURL(url, lambda x: _scrapeVeohTVCallback(x, callback),
                           lambda x:_scrapeVeohTVErrback(x, callback))
    except:
        print "DTV: WARNING, unable to scrape Veoh URL: %s" % url
        callback(None)

def _scrapeVeohTVCallback(info, callback):
    url = info['redirected-url']
    try:
        params = cgi.parse_qs(info['body'])
        fileHash = params['previewHashLow'][0]
        if fileHash[-1] == ",":
            fileHash=fileHash[:-1]
        url = u'http://ll-previews.veoh.com/previews/get.jsp?fileHash=%s' % fileHash
        callback(url)
    except:
        print "DTV: WARNING, unable to scrape Veoh URL data: %s" % url
        callback(None)

def _scrapeVeohTVErrback(err, callback):
    print "DTV: WARNING, network error scraping Veoh TV Video URL"
    callback(None)

def _scrapeBreakVideoURL(url, callback):
    httpclient.grabHeaders(url, lambda x:_scrapeBreakCallback(x,callback),
                           lambda x:_scrapeBreakErrback(x,callback))

def _scrapeBreakCallback(info, callback):
    url = info['redirected-url']
    try:
        components = urlparse.urlsplit(url)
        params = cgi.parse_qs(components[3])
        url = unquote_plus(params['sVidLoc'][0]).decode('ascii','replace')
        callback(url)
    except:
        print "DTV: WARNING, unable to scrape Break URL: %s" % url
        callback(None)

def _scrapeBreakErrback(info, callback):
    print "DTV: WARNING, network error scraping Break Video URL"
    callback(None)

def _scrapeGreenPeaceVideoURL(url, callback):
    print "DTV: Warning, unable to scrape Green peace Video URL %s" % url
    print callback(None)

# =============================================================================

scraperInfoMap = [
    {'pattern': 'http://([^/]+\.)?youtube.com/(?!get_video\.php)', 'func': _scrapeYouTubeURL},
    {'pattern': 'http://video.google.com/googleplayer.swf', 'func': _scrapeGoogleVideoURL},
    {'pattern': 'http://([^/]+\.)?lulu.tv/wp-content/flash_play/flvplayer', 'func': _scrapeLuLuVideoURL},
    {'pattern': 'http://([^/]+\.)?vmix.com/flash/super_player.swf', 'func': _scrapeVMixVideoURL},
    {'pattern': 'http://([^/]+\.)?dailymotion.com/swf', 'func': _scrapeDailyMotionVideoURL},
    {'pattern': 'http://([^/]+\.)?vsocial.com/flash/vp.swf', 'func': _scrapeVSocialVideoURL},
    {'pattern': 'http://([^/]+\.)?veoh.com/multiplayer.swf', 'func': _scrapeVeohTVVideoURL},
    {'pattern': 'http://([^/]+\.)?greenpeaceweb.org/GreenpeaceTV1Col.swf', 'func': _scrapeGreenPeaceVideoURL},
    {'pattern': 'http://([^/]+\.)?break.com/', 'func': _scrapeBreakVideoURL},
]
