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

from miro import views
from miro import indexes
import re
from miro.util import getSingletonDDBObject, checkU, returnsUnicode, quoteattr, escape
from miro.database import DDBObject
from miro.xhtmltools import urlencode
from xml.dom.minidom import parse
from miro.plat import resources
import os
from miro import config
from miro import prefs
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

def createEngines():
    deleteEngines()
    searchEngines = searchForSearchEngines(resources.path("searchengines"))
    searchEngines.update (searchForSearchEngines(os.path.join (config.get(prefs.SUPPORT_DIRECTORY), "searchengines")))
    for file in searchEngines.itervalues():
        loadSearchEngine (file)
    SearchEngine(u"all", u"Search All", u"", -1)

@returnsUnicode
def getRequestURL(engineName, query, filterAdultContents=True, limit=50):
    if query == "LET'S TEST DTV'S CRASH REPORTER TODAY":
        someVariable = intentionallyUndefinedVariableToTestCrashReporter
    if query == "LET'S DEBUG DTV: DUMP DATABASE":
        from miro import database
        database.defaultDatabase.liveStorage.dumpDatabase (database.defaultDatabase)
        return u""
    if engineName == u'all':
        all_urls = [urlencode(engine.getRequestURL(query, filterAdultContents, limit)) for engine in views.searchEngines if engine.name != u'all']
        return "dtv:multi:" + ','.join(all_urls)
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

def getLastEngineTitle():
    return getEngineTitle(getLastEngine())

def getEngineTitle(which):
    for engine in views.searchEngines:
        if engine.name == which:
            return engine.title
    return u''

def getLastEngine():
    searchFeed = _getSearchFeed()
    if not hasattr(searchFeed, 'lastEngine'):
        return u'youtube'
    return searchFeed.lastEngine

def getLastQuery():
    searchFeed = _getSearchFeed()
    if not hasattr(searchFeed, 'lastQuery'):
        return ''
    return searchFeed.lastQuery

def _getSearchFeed():
    return getSingletonDDBObject (views.feeds.filterWithIndex(indexes.feedsByURL, 'dtv:search'))
