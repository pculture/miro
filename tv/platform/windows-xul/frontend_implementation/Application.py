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
import app
import time
import resources
import config
import prefs
import os
import searchengines
import views
from platformutils import _getLocale as getLocale
from frontends.html.main import HTMLApplication
from miroplatform.frontends.html import HTMLDisplay
from xulhelper import makeService, pcfIDTVPyBridge
import migrateappname
import logging

###############################################################################
#### Application object                                                    ####
###############################################################################
class Application(HTMLApplication):
    def Run(self):
        HTMLDisplay.initTempDir()

        lang = getLocale()
        if lang:
            if not os.path.exists(resources.path(r"..\chrome\locale\%s" % (lang,))):
                lang = "en-US"
        else:
            lang = "en-US"

        # FIXME: This should run in the Mozilla thread --NN
        logging.warn("Application.Run() is creating XPCOM objects in the wrong thread!")
        from xpcom import components
        ps = makeService("@mozilla.org/preferences-service;1",components.interfaces.nsIPrefService)
        branch = ps.getBranch("general.useragent.")
        branch.setCharPref("locale", lang)

        import psyco
        #psyco.log('\\dtv.psyco')
        psyco.profile(.03)

        app.jsBridge.positionVolumeSlider(config.get(prefs.VOLUME_LEVEL))

        self.startup()

    def quitUI(self):
        app.jsBridge.closeWindow()

    def finishStartupSequence(self):
        pybridge = makeService("@participatoryculture.org/dtv/pybridge;1",pcfIDTVPyBridge)
        self.initializeSearchEngines()
        migrateappname.migrateVideos('Democracy', 'Miro')
        pybridge.updateTrayMenus()

    def initializeSearchEngines(self):
        names = []
        titles = []
        for engine in views.searchEngines:
            names.append(engine.name)
            titles.append(engine.title)
        app.jsBridge.setSearchEngineInfo(names, titles)
        app.jsBridge.setSearchEngine(searchengines.getLastEngine())

    def onShutdown(self):
        # For overriding
        pass

    def onUnwatchedItemsCountChange(self, obj, id):
        HTMLApplication.onDownloadingItemsCountChange(self, obj, id)
        pybridge = makeService("@participatoryculture.org/dtv/pybridge;1",pcfIDTVPyBridge)
        pybridge.updateTrayMenus()

    def onDownloadingItemsCountChange(self, obj, id):
        HTMLApplication.onDownloadingItemsCountChange(self, obj, id)
        pybridge = makeService("@participatoryculture.org/dtv/pybridge;1",pcfIDTVPyBridge)
        pybridge.updateTrayMenus()

###############################################################################
###############################################################################
