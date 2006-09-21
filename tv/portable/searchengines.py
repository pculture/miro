
import views
import indexes
import re
import template
import util
from database import DDBObject
from xhtmltools import urlencode
from templatehelper import quoteattr, escape

class SearchEngine(DDBObject):
    def __init__(self, name, title, url, sortOrder=0):
        self.name = name
        self.title = title
        self.url = url
        self.sortOrder = sortOrder
        DDBObject.__init__(self)

    def getRequestURL (self, query, filterAdultContents, limit):
        requestURL = self.url.replace("%s", urlencode(query))
        requestURL = requestURL.replace("%a", str(int(not filterAdultContents)))
        requestURL = requestURL.replace("%l", str(int(limit)))
        return requestURL

def deleteEngines():
    for engine in views.searchEngines:
        engine.remove()

def createEngines():
    deleteEngines()
    SearchEngine ("yahoo",  u"Yahoo! Video",
                  "http://api.search.yahoo.com/VideoSearchService/rss/videoSearch.xml"
                  "?appid=dtv_search"
                  "&adult_ok=%a"
                  "&results=%l"
                  "&format=any"
                  "&query=%s",
                  0)
    SearchEngine ("google",  u"Google Video",
                  "http://video.google.com/videofeed?type=search"
                  "&q=%s"
                  "+is:free"
                  "&num=%l"
                  "&format=any"
                  "&output=rss",
                  1)
    SearchEngine ("youtube", u"YouTube",
                  "http://www.youtube.com/rss/tag/"
                  "%s.rss",
                  2)
    SearchEngine ("blogdigger", u"Blogdigger",
                  "http://blogdigger.com/media/rss.jsp"
                  "&q=%s"
                  "&media=video"
                  "&media=torrent"
                  "&sortby=date",
                  3)


def getRequestURL(engineName, query, filterAdultContents=True, limit=50):
    if query == "LET'S TEST DTV'S CRASH REPORTER TODAY":
        someVariable = intentionallyUndefinedVariableToTestCrashReporter
    if type(query) == unicode:
        query = query.encode('utf-8')

    for engine in views.searchEngines:
        if engine.name == engineName:
            return engine.getRequestURL(query, filterAdultContents, limit)
    return None


def getSearchEnginesHTML ():
    searchFeed = util.getSingletonDDBObject (views.feeds.filterWithIndex(indexes.feedsByURL, 'dtv:search'))
    enginesHTML = u'<select name="engines" onChange="updateLastSearchEngine()">\n'
    for engine in views.searchEngines:
        enginesHTML += u'<option value="%s"' % (quoteattr(engine.name),)
        if engine.name == searchFeed.lastEngine:
            enginesHTML += u' selected="selected"'
        enginesHTML += u'>'
        enginesHTML += escape(engine.title)
        enginesHTML += u'</option>'
    enginesHTML += u'</select>'
    return enginesHTML.encode("utf8")
\
