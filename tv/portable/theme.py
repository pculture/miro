# Miro - an RSS based video player application
# Copyright (C) 2007 Participatory Culture Foundation
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

import config
import prefs
import app
import views
import os
from eventloop import asUrgent
from database import DDBObject
import opml
import iconcache

class ThemeHistory(DDBObject):
    def __init__(self):
        DDBObject.__init__(self)
        self.lastTheme = None
        self.pastThemes = []
        self.theme = unicode(config.get(prefs.THEME_NAME))
        if self.theme is not None:
            self.pastThemes.append(self.theme)
            self.onFirstRun()

    def onRestore(self):
        self.theme = unicode(config.get(prefs.THEME_NAME))
        if not (self.theme is None or self.theme in self.pastThemes):
            self.pastThemes.append(self.theme)
            self.onFirstRun()
        if self.lastTheme != self.theme:
            self.onThemeChange()
            self.lastTheme = self.theme

    @asUrgent
    def onThemeChange(self):
        if len(views.default_guide) > 0:
            views.default_guide[0].title = None
            views.default_guide[0].favicon = None
            views.default_guide[0].updated_url = None
            views.default_guide[0].iconCache.remove()
            views.default_guide[0].iconCache= iconcache.IconCache (views.default_guide[0], is_vital = True)
            views.default_guide[0].signalChange()
        self.signalChange()
        

    # This should be run once for each theme
    @asUrgent
    def onFirstRun(self):
        # Clear out the channel guide icon
        if config.get(prefs.MAXIMIZE_ON_FIRST_RUN).lower() not in ['false','no','0']:
            app.delegate.maximizeWindow()
        # FIXME -- this needs to be here and in app.py. We should
        #          unify the code --NN
        if ((config.get(prefs.DEFAULT_CHANNELS_FILE) is not None) and
            (config.get(prefs.THEME_NAME) is not None) and 
            (config.get(prefs.THEME_DIRECTORY) is not None)):
            importer = opml.Importer()
            filepath = os.path.join(
                config.get(prefs.THEME_DIRECTORY),
                config.get(prefs.THEME_NAME),
                config.get(prefs.DEFAULT_CHANNELS_FILE))
            importer.importSubscriptionsFrom(filepath,
                                             showSummary = False)
