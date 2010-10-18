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

"""``miro.searchengines`` -- This module holds
:class:`SearchEngineInfo` and related helper functions.
"""

from miro.util import check_u, returns_unicode
from miro.xhtmltools import urlencode
from xml.dom.minidom import parse
from miro.plat import resources
from miro.plat.utils import unicode_to_filename
import os
from miro import app
from miro import prefs
import logging
from miro.gtcache import gettext as _

class IntentionalCrash(Exception):
    pass

class SearchEngineInfo:
    """Defines a search engine in Miro.

    .. note::

       Don't instantiate this yourself---search engines are defined by
       ``.xml`` files in the ``resources/searchengines/`` directory.
    """
    def __init__(self, name, title, url, sort_order=0, filename=None):
        check_u(name)
        check_u(title)
        check_u(url)
        self.name = name
        self.title = title
        self.url = url
        self.sort_order = sort_order
        if filename is not None:
            self.filename = os.path.normcase(filename)
            # used for changing icon location on themed searches
        else:
            self.filename = None

    def get_request_url(self, query, filterAdultContents, limit):
        """Returns the request url expanding the query, filter adult content,
        and results limit place holders.
        """
        request_url = self.url.replace(u"%s", urlencode(query))
        request_url = request_url.replace(u"%a", 
                                          unicode(int(not filterAdultContents)))
        request_url = request_url.replace(u"%l", unicode(int(limit)))

        return request_url

    def __repr__(self):
        return "<SearchEngineInfo %s %s>" % (self.name, self.title)

_engines = []

def _delete_engines():
    global _engines
    _engines = []

def _search_for_search_engines(dir_):
    """Returns a dict of search engine -> search engine xml file for
    all search engines in the specified directory ``dir_``.
    """
    engines = {}
    try:
        for f in os.listdir(dir_):
            if f.endswith(".xml"):
                engines[os.path.normcase(f)] = os.path.normcase(
                    os.path.join(dir_, f))
    except OSError:
        pass
    return engines

def warn(filename, message):
    logging.warn("Error parsing searchengine: %s: %s", filename, message)

def _load_search_engine(filename):
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
    """Creates all the search engines specified in the
    ``resources/searchengines/`` directory and the theme searchengines
    directory.  After doing that, it adds an additional "Search All"
    engine.
    """
    global _engines
    _delete_engines()
    engines = _search_for_search_engines(resources.path("searchengines"))
    engines_dir = os.path.join(
        app.config.get(prefs.SUPPORT_DIRECTORY), "searchengines")
    engines.update(_search_for_search_engines(engines_dir))
    if app.config.get(prefs.THEME_NAME):
        theme_engines_dir = resources.theme_path(app.config.get(prefs.THEME_NAME),
                                                 'searchengines')
        engines.update(_search_for_search_engines(theme_engines_dir))
    for fn in engines.itervalues():
        _load_search_engine(fn)

    _engines.append(SearchEngineInfo(u"all", _("Search All"), u"", -1))
    _engines.sort(lambda a, b: cmp((a.sort_order, a.name, a.title), 
                                   (b.sort_order, b.name, b.title)))

    # SEARCH_ORDERING is a comma-separated list of search engine names to
    # include.  An * as the last engine includes the rest of the engines.
    if app.config.get(prefs.SEARCH_ORDERING):
        search_names = app.config.get(prefs.SEARCH_ORDERING).split(',')
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

def get_request_urls(engine_name, query, filter_adult_contents=True, limit=50):
    """Get a list of RSS feed URLs for a search.

    Usually this will return a single URL, but in the case of the "all" engine
    it will return multiple URLs.

    :param engine_name: which engine to use, or "all" for all engines
    :param query: search query
    :param filter_adult_contents: Should we include "adult" results
    :param limit: Limit the results to this number (per engine returned)

    There are two "magic" queries:

    * ``LET'S TEST DTV'S CRASH REPORTER TODAY`` which rases a
      NameError thus allowing us to test the crash reporter

    * ``LET'S DEBUT DTV: DUMP DATABASE`` which causes Miro to dump the
       database to xml and place it in the Miro configuration
       directory
    """
    if query == "LET'S TEST DTV'S CRASH REPORTER TODAY":
        raise IntentionalCrash("intentional error here")

    if query == "LET'S DEBUG DTV: DUMP DATABASE":
        app.db.dumpDatabase()
        return u""

    if engine_name == u'all':
        return [engine.get_request_url(query, filter_adult_contents, limit) \
                for engine in _engines if engine.name != u'all']

    for engine in _engines:
        if engine.name == engine_name:
            url = engine.get_request_url(query, filter_adult_contents, limit)
            return [url]
    return []

def get_search_engines():
    """Returns the list of :class:`SearchEngineInfo` instances.
    """
    return list(_engines)

def get_engine_for_name(name):
    """Returns the :class:`SearchEngineInfo` instance for the given
    id.  If no such search engine exists, returns ``None``.
    """
    for mem in get_search_engines():
        if mem.name == name:
            return mem
    return None

def get_last_engine():
    """Checks the preferences and returns the SearchEngine object of
    that name or ``None``.
    """
    e = app.config.get(prefs.LAST_SEARCH_ENGINE)
    engine = get_engine_for_name(e)
    if engine:
        return engine
    return get_search_engines()[0]

def set_last_engine(engine):
    """Takes a :class:`SearchEngineInfo` or search engine id and
    persists it to preferences.
    """
    if not isinstance(engine, basestring):
        engine = engine.name
    engine = str(engine)
    if not get_engine_for_name(engine):
        engine = str(get_search_engines()[0].name)
    app.config.set(prefs.LAST_SEARCH_ENGINE, engine)

def icon_path_for_engine(engine):
    engine_name = unicode_to_filename(engine.name)
    icon_path = resources.path('images/search_icon_%s.png' % engine_name)
    if app.config.get(prefs.THEME_NAME):
        logging.debug('engine %s filename: %s' % (engine.name, engine.filename))
        test_icon_path = resources.theme_path(app.config.get(prefs.THEME_NAME),
                                              'images/search_icon_%s.png' %
                                              engine_name)
        if os.path.exists(test_icon_path):
            # this search engine came from a theme; look up the icon in the
            # theme directory instead
            icon_path = test_icon_path
    return icon_path
