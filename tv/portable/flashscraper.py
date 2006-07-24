import re
import httplib
import urlparse
import xml.sax.saxutils

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
    print "DTV: Scraping YouTube URL: %s" % url
    scrapedURL = None
    try:
        components = urlparse.urlparse(url)
        http = httplib.HTTPConnection(components[1])
        http.request('GET', components[2])
        response = http.getresponse()
        if response.status == 303:
            location = response.getheader('location')
            videoID = re.compile('\?video_id=([^&]+)').search(location).group(1)
            tParam = re.compile('&t=([^&]+)').search(location).group(1)
            scrapedURL = "http://youtube.com/get_video.php?video_id=%s&t=%s" % (videoID, tParam)
    except:
        print "DTV: WARNING, unable to scrape YouTube URL: %s" % url
    return scrapedURL

def _scrapeGoogleVideoURL(url):
    return xml.sax.saxutils.unescape(url)

# =============================================================================

scraperInfoMap = [
    {'pattern': 'http://youtube.com',         'func': _scrapeYouTubeURL},
    {'pattern': 'http://vp.video.google.com', 'func': _scrapeGoogleVideoURL}
]
