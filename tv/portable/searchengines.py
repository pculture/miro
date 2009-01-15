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

from miro.util import checkU, returnsUnicode
from miro.xhtmltools import urlencode
from xml.dom.minidom import parse
from miro.plat import resources
import os
from miro import config
from miro import prefs
import logging
from miro.gtcache import gettext as _

class SearchEngineInfo:
    def __init__(self, name, title, url, sort_order=0, filename=None):
        checkU(name)
        checkU(title)
        checkU(url)
        self.name = name
        self.title = title
        self.url = url
        self.sort_order = sort_order
        self.filename = filename # used for changing icon location on themed
                                 # searches

    def get_request_url(self, query, filterAdultContents, limit):
        requestURL = self.url.replace(u"%s", urlencode(query))
        requestURL = requestURL.replace(u"%a", unicode(int(not filterAdultContents)))
        requestURL = requestURL.replace(u"%l", unicode(int(limit)))
        return requestURL

    def __repr__(self):
        return "<SearchEngineInfo %s %s>" % (self.name, self.title)

_engines = []

def delete_engines():
    global _engines
    _engines = []

def search_for_search_engines(dir_):
    engines = {}
    try:
        for f in os.listdir(dir_):
            if f.endswith(".xml"):
                engines[os.path.normcase(f)] = os.path.normcase(os.path.join(dir_, f))
    except OSError:
        pass
    return engines

def warn(filename, message):
    logging.warn("Error parsing searchengine: %s: %s", filename, message)

def load_search_engine(filename):
    try:
        dom = parse(filename)
        id_ = displayname = url = sort = None
        root = dom.documentElement
        for child in root.childNodes:
            if child.nodeType == child.ELEMENT_NODE:
                tag = child.tagName
                text = child.childNodes[0].data
                if tag == "id":
                    if id_ != None:
                        warn(filename, "Duplicated id tag")
                        return
                    id_ = text
                elif tag == "displayname":
                    if displayname != None:
                        warn(filename, "Duplicated displayname tag")
                        return
                    displayname = text
                elif tag == "url":
                    if url != None:
                        warn(filename, "Duplicated url tag")
                        return
                    url = text
                elif tag == "sort":
                    if sort != None:
                        warn(filename, "Duplicated sort tag")
                        return
                    sort = float(text)
                else:
                    warn(filename, "Unrecognized tag %s" % tag)
                    return
        dom.unlink()
        if id_ == None:
            warn(filename, "Missing id tag")
            return
        if displayname == None:
            warn(filename, "Missing displayname tag")
            return
        if url == None:
            warn(filename, "Missing url tag")
            return
        if sort == None:
            sort = 0

        _engines.append(SearchEngineInfo(id_, displayname, url,
                                         sort_order=sort,
                                         filename=filename))

    except (SystemExit, KeyboardInterrupt):
        raise
    except:
        warn(filename, "Exception parsing file")

def create_engines():
    global _engines
    delete_engines()
    engines = search_for_search_engines(resources.path("searchengines"))
    engines_dir = os.path.join(config.get(prefs.SUPPORT_DIRECTORY), "searchengines")
    engines.update(search_for_search_engines(engines_dir))
    if config.get(prefs.THEME_NAME):
        theme_engines_dir = resources.theme_path(config.get(prefs.THEME_NAME),
                                                 'searchengines')
        engines.update(search_for_search_engines(theme_engines_dir))
    for fn in engines.itervalues():
        load_search_engine(fn)

    _engines.append(SearchEngineInfo(u"all", _("Search All"), u"", -1))
    _engines.sort(lambda a, b: cmp((a.sort_order, a.name, a.title), 
                                   (b.sort_order, b.name, b.title)))

    # SEARCH_ORDERING is a comma-separated list of search engine names to
    # include.  An * as the last engine includes the rest of the engines.
    if config.get(prefs.SEARCH_ORDERING):
        search_names = config.get(prefs.SEARCH_ORDERING).split(',')
        new_engines = []
        if '*' in search_names and '*' in search_names[:-1]:
            raise RuntimeError('wildcard search ordering must be at the end')
        for name in search_names:
            if name != '*':
                engine = get_engine_for_name(name)
                if not engine:
                    warn(__file__, 'Invalid search name: %r' % name)
                else:
                    new_engines.append(engine)
                    _engines.remove(engine)
            else:
                new_engines.extend(_engines)
        _engines = new_engines

@returnsUnicode
def get_request_url(engine_name, query, filter_adult_contents=True, limit=50):
    if query == "LET'S TEST DTV'S CRASH REPORTER TODAY":
        # FIXME - should change this to a real exception rather than a NameError
        someVariable = intentionallyUndefinedVariableToTestCrashReporter
        return u""

    if query == "LET'S DEBUG DTV: DUMP DATABASE":
        from miro import database
        database.defaultDatabase.liveStorage.dumpDatabase(database.defaultDatabase)
        return u""

    if engine_name == u'all':
        all_urls = [urlencode(engine.get_request_url(query, filter_adult_contents, limit)) 
                    for engine in _engines if engine.name != u'all']
        return "dtv:multi:" + ','.join(all_urls) + "," + query

    for engine in _engines:
        if engine.name == engine_name:
            return engine.get_request_url(query, filter_adult_contents, limit)
    return u""

def get_search_engines():
    return list(_engines)

def get_engine_for_name(name):
    for mem in get_search_engines():
        if mem.name == name:
            return mem
    return None

def get_last_engine():
    """Checks the preferences and returns the SearchEngine object of that
    name or None.
    """
    e = config.get(prefs.LAST_SEARCH_ENGINE)
    engine = get_engine_for_name(e)
    if engine:
        return engine
    return get_search_engines()[0]

def set_last_engine(engine):
    """Takes a SearchEngine and persists it to preferences."""
    if not isinstance(engine, basestring):
        engine = engine.name
    engine = str(engine)
    config.set(prefs.LAST_SEARCH_ENGINE, engine)
