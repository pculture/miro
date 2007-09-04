# Miro - an RSS based video player application
# Copyright (C) 2005-2007 Participatory Culture Foundation
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

import sys
import frontend
import time
import resources
import config
import prefs
import os
import searchengines
import views
from platformutils import _getLocale as getLocale

from frontend_implementation import HTMLDisplay
import migrateappname

###############################################################################
#### Application object                                                    ####
###############################################################################
class Application:

    def __init__(self):
        print "Application init"

    def Run(self):
        HTMLDisplay.initTempDir()

        lang = getLocale()
        if lang:
            if not os.path.exists(resources.path(r"..\chrome\locale\%s" % (lang,))):
                lang = "en-US"
        else:
            lang = "en-US"

        from xpcom import components
        ps_cls = components.classes["@mozilla.org/preferences-service;1"]
        ps = ps_cls.getService(components.interfaces.nsIPrefService)
        branch = ps.getBranch("general.useragent.")
        branch.setCharPref("locale", lang)

        import psyco
        #psyco.log('\\dtv.psyco')
        psyco.profile(.03)

        # Start the core.
        if frontend.startup.search:
            self.onStartup(frontend.startup.search.getFiles())
        else:
            self.onStartup()
        frontend.jsBridge.positionVolumeSlider(config.get(prefs.VOLUME_LEVEL))

    def onStartup(self):
        # For overriding
        pass

    def finishStartupSequence(self):
        from xpcom import components
        pybridge = components.classes["@participatoryculture.org/dtv/pybridge;1"].getService(components.interfaces.pcfIDTVPyBridge)
        self.initializeSearchEngines()
        migrateappname.migrateVideos('Democracy', 'Miro')
        pybridge.updateTrayMenus()

    def initializeSearchEngines(self):
        names = []
        titles = []
        for engine in views.searchEngines:
            names.append(engine.name)
            titles.append(engine.title)
        frontend.jsBridge.setSearchEngineInfo(names, titles)
        frontend.jsBridge.setSearchEngine(searchengines.getLastEngine())

    def onShutdown(self):
        # For overriding
        pass

    # This is called on OS X when we are handling a click on an RSS feed
    # button for Safari. NEEDS: add code here to register as a RSS feed
    # reader on Windows too. Just call this function when we're launched
    # to handle a click on a feed.
    def addAndSelectFeed(self, url):
        # For overriding
        pass

    def onUnwatchedItemsCountChange(self, obj, id):
        from xpcom import components
        pybridge = components.classes["@participatoryculture.org/dtv/pybridge;1"].getService(components.interfaces.pcfIDTVPyBridge)
        pybridge.updateTrayMenus()

    def onDownloadingItemsCountChange(self, obj, id):
        from xpcom import components
        pybridge = components.classes["@participatoryculture.org/dtv/pybridge;1"].getService(components.interfaces.pcfIDTVPyBridge)
        pybridge.updateTrayMenus()

###############################################################################
###############################################################################
