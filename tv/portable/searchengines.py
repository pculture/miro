
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
    SearchEngine ("youtube", u"YouTube",
                  "http://www.youtube.com/rss/tag/"
                  "%s.rss",
                  0)
    SearchEngine ("yahoo",  u"Yahoo! Video",
                  "http://api.search.yahoo.com/VideoSearchService/rss/videoSearch.xml"
                  "?appid=dtv_search"
                  "&adult_ok=%a"
                  "&results=%l"
                  "&format=any"
                  "&query=%s",
                  1)
    SearchEngine ("google",  u"Google Video",
                  "http://video.google.com/videofeed?type=search"
                  "&q=%s"
                  "+is:free"
                  "&num=%l"
                  "&format=any"
                  "&output=rss",
                  2)
    SearchEngine ("blogdigger", u"Blogdigger",
                  "http://blogdigger.com/media/rss.jsp"
                  "?q=%s"
                  "&media=video"
                  "&media=torrent"
                  "&sortby=date",
                  3)
    SearchEngine ("revver", u"Revver",
                  "http://api.revver.com/rss/0.1/search/%s",
                  4)
    SearchEngine ("dailymotion", u"DailyMotion",
                  "http://www.dailymotion.com/rss/search/%s",
                  5)
    SearchEngine ("bliptv", u"blip.tv",
                  "http://blip.tv/?1=1&search=%s;s=posts&skin=rss",
                  6)

def getRequestURL(engineName, query, filterAdultContents=True, limit=50):
    if query == "LET'S TEST DTV'S CRASH REPORTER TODAY":
        someVariable = intentionallyUndefinedVariableToTestCrashReporter
    if query == "LET'S DEBUG DTV: DUMP DATABASE":
        import database
        database.defaultDatabase.liveStorage.dumpDatabase (database.defaultDatabase)
        return ""
    if type(query) == unicode:
        query = query.encode('utf-8')

    for engine in views.searchEngines:
        if engine.name == engineName:
            return engine.getRequestURL(query, filterAdultContents, limit)
    return ""


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

def getLastEngine():
    return _getSearchFeed().lastEngine

def getLastQuery():
    return _getSearchFeed().lastQuery

def _getSearchFeed():
    return util.getSingletonDDBObject (views.feeds.filterWithIndex(indexes.feedsByURL, 'dtv:search'))
