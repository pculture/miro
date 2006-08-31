import re
import httplib
import urlparse
import cgi
from urllib import unquote_plus

# =============================================================================

def tryScrapingURL(url):
    scrape = _getScrapeFunctionFor(url)
    if scrape is not None:
        return scrape(url)
    else:
        return url
    
# =============================================================================

def _getScrapeFunctionFor(url):
    for scrapeInfo in scraperInfoMap:
        if re.compile(scrapeInfo['pattern']).match(url) is not None:
            return scrapeInfo['func']
    return None

def _scrapeYouTubeURL(url):
    videoIDPattern = re.compile('\?video_id=([^&]+)')
    paramPattern = re.compile('&t=([^&?]+)')
    scrapedURL = None
    try:
        status = 0
        while status != 200:
            components = list(urlparse.urlsplit(url))
            http = httplib.HTTPConnection(components[1])
            http.request('HEAD', "%s?%s" % (components[2], components[3]))
            response = http.getresponse()
            status = response.status
            if status in (301, 302, 303, 307):
                location = response.getheader('location')
                if location.startswith('http://'):
                    url = location
                else:
                    components[2] = location
                    url = urlparse.urlunsplit(components)
            elif status == 200:
                videoID = videoIDPattern.search(url).group(1)
                tParam = paramPattern.search(url).group(1)
                scrapedURL = "http://youtube.com/get_video.php?video_id=%s&t=%s" % (videoID, tParam)
            else:
                print "DTV: WARNING, unsupported HTTP status code %d" % status
                raise
    except:
        print "DTV: WARNING, unable to scrape YouTube URL: %s" % url
    return scrapedURL

def _scrapeGoogleVideoURL(url):
    try:
        components = urlparse.urlsplit(url)
        params = cgi.parse_qs(components[3])
        url = unquote_plus(params['videoUrl'][0])
    except:
        print "DTV: WARNING, unable to scrape Google Video URL: %s" % url
    return url

# =============================================================================

scraperInfoMap = [
    {'pattern': 'http://youtube.com',         'func': _scrapeYouTubeURL},
    {'pattern': 'http://video.google.com/googleplayer.swf', 'func': _scrapeGoogleVideoURL}
]
