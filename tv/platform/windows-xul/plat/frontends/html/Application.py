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

import sys
import time
import os
import logging

from miro import app
from miro import config
from miro import prefs
from miro import eventloop
from miro.plat import resources
from miro.plat import flash
from miro import searchengines
from miro import views
from miro import u3info
from miro.plat.utils import _getLocale as getLocale
from miro.frontends.html.main import HTMLApplication
from miro.plat.frontends.html import HTMLDisplay
from miro.plat.frontends.html import startup
from miro.plat import migrateappname
from miro.plat.xulhelper import makeService, pcfIDTVPyBridge

###############################################################################
#### Application object                                                    ####
###############################################################################
class Application(HTMLApplication):
    def run(self):
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
        ps = makeService("@mozilla.org/preferences-service;1",components.interfaces.nsIPrefService,False)
        branch = ps.getBranch("general.useragent.")
        branch.setCharPref("locale", lang)

        import psyco
        #psyco.log('\\dtv.psyco')
        psyco.profile(.03)

        app.jsBridge.positionVolumeSlider(config.get(prefs.VOLUME_LEVEL))

        self.startup()

    def quitUI(self):
        app.jsBridge.closeWindow()

    def handleStartupSuccess(self, obj):
        """
        Override in order to send the files to self.finishStartup().
        """
        if self.AUTOUPDATE_SUPPORTED and not u3info.u3_active and \
                not config.get(prefs.STARTUP_TASKS_DONE):
            config.set(prefs.STARTUP_TASKS_DONE, True)
            if startup.search is not None: # user searched for files
                foundFiles = startup.search.getFiles()
            else:
                foundFiles = None
            self.finishStartup(foundFiles)
        else:
            HTMLApplication.handleStartupSuccess(self, obj)
        
    def finishStartupSequence(self):
        eventloop.addIdle(flash.checkFlashInstall, 'Install Flash')            
        pybridge = makeService("@participatoryculture.org/dtv/pybridge;1",pcfIDTVPyBridge,True, False)
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
        HTMLApplication.onUnwatchedItemsCountChange(self, obj, id)
        pybridge = makeService("@participatoryculture.org/dtv/pybridge;1",pcfIDTVPyBridge, True, False)
        pybridge.updateTrayMenus()

    def onDownloadingItemsCountChange(self, obj, id):
        HTMLApplication.onDownloadingItemsCountChange(self, obj, id)
        pybridge = makeService("@participatoryculture.org/dtv/pybridge;1",pcfIDTVPyBridge, True, False)
        pybridge.updateTrayMenus()

###############################################################################
###############################################################################
