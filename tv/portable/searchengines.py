import views
import indexes
import re
import template
from util import getSingletonDDBObject, checkU, returnsUnicode
from database import DDBObject
from xhtmltools import urlencode
from templatehelper import quoteattr, escape
from xml.dom.minidom import parse
import resources
import os
import config
import prefs
import logging

class SearchEngine(DDBObject):
    def __init__(self, name, title, url, sortOrder=0):
        checkU(name)
        checkU(title)
        checkU(url)
        self.name = name
        self.title = title
        self.url = url
        self.sortOrder = sortOrder
        DDBObject.__init__(self)

    def getRequestURL (self, query, filterAdultContents, limit):
        requestURL = self.url.replace(u"%s", urlencode(query))
        requestURL = requestURL.replace(u"%a", unicode(int(not filterAdultContents)))
        requestURL = requestURL.replace(u"%l", unicode(int(limit)))
        return requestURL

def deleteEngines():
    for engine in views.searchEngines:
        engine.remove()

def searchForSearchEngines (dir):
    engines = {}
    try:
        for f in os.listdir (dir):
            if f.endswith(".xml"):
                engines[os.path.normcase(f)] = os.path.normcase(os.path.join(dir, f))
    except OSError:
        pass
    return engines

def warn (file, message):
    logging.warn ("Error parsing searchengine: %s: %s", file, message)

def loadSearchEngine (file):
    try:
        dom = parse(file)
        id = displayname = url = sort = None
        root = dom.documentElement
        for child in root.childNodes:
            if child.nodeType == child.ELEMENT_NODE:
                tag = child.tagName
                text = child.childNodes[0].data
                if tag == "id":
                    if id != None:
                        warn(file, "Duplicated id tag")
                        return
                    id = text
                elif tag == "displayname":
                    if displayname != None:
                        warn(file, "Duplicated displayname tag")
                        return
                    displayname = text
                elif tag == "url":
                    if url != None:
                        warn(file, "Duplicated url tag")
                        return
                    url = text
                elif tag == "sort":
                    if sort != None:
                        warn(file, "Duplicated sort tag")
                        return
                    sort = float (text)
                else:
                    warn(file, "Unrecognized tag %s" % (tag,))
                    return
        dom.unlink()
        if id == None:
            warn(file, "Missing id tag")
            return
        if displayname == None:
            warn(file, "Missing displayname tag")
            return
        if url == None:
            warn(file, "Missing url tag")
            return
        if sort == None:
            sort = 0
        SearchEngine (id, displayname, url, sort)
    except:
        warn(file, "Exception parsing file")
        raise
        #return

def createEngines():
    deleteEngines()
    searchEngines = searchForSearchEngines(resources.path("searchengines"))
    searchEngines.update (searchForSearchEngines(os.path.join (config.get(prefs.SUPPORT_DIRECTORY), "searchengines")))
    for file in searchEngines.itervalues():
        loadSearchEngine (file)

@returnsUnicode
def getRequestURL(engineName, query, filterAdultContents=True, limit=50):
    if query == u"LET'S TEST DTV'S CRASH REPORTER TODAY":
        someVariable = intentionallyUndefinedVariableToTestCrashReporter
    if query == u"LET'S DEBUG DTV: DUMP DATABASE":
        import database
        database.defaultDatabase.liveStorage.dumpDatabase (database.defaultDatabase)
        return u""
    for engine in views.searchEngines:
        if engine.name == engineName:
            return engine.getRequestURL(query, filterAdultContents, limit)
    return u""

@returnsUnicode
def getSearchEnginesHTML ():
    searchFeed = getSingletonDDBObject (views.feeds.filterWithIndex(indexes.feedsByURL, 'dtv:search'))
    enginesHTML = u'<select name="engines" onChange="updateLastSearchEngine()">\n'
    for engine in views.searchEngines:
        enginesHTML += u'<option value="%s"' % (quoteattr(engine.name),)
        if engine.name == searchFeed.lastEngine:
            enginesHTML += u' selected="selected"'
        enginesHTML += u'>'
        enginesHTML += escape(engine.title)
        enginesHTML += u'</option>'
    enginesHTML += u'</select>'
    return enginesHTML

def getLastEngine():
    return _getSearchFeed().lastEngine

def getLastQuery():
    return _getSearchFeed().lastQuery

def _getSearchFeed():
    return getSingletonDDBObject (views.feeds.filterWithIndex(indexes.feedsByURL, 'dtv:search'))
