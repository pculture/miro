# Miro - an RSS based video player application
# Copyright (C) 2007-2008 Participatory Culture Foundation
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

from miro.gtcache import gettext as _
import logging
from miro import config
from miro import prefs
from miro import app
from miro import views
from miro import indexes
import os
from miro.eventloop import asUrgent
from miro.database import DDBObject
from miro import opml
from miro import iconcache
from miro.plat import resources
from miro import plat
from miro import guide
from miro import feed
from miro import folder
from miro import playlist
from miro import signals

class ThemeHistory(DDBObject):
    def __init__(self):
        DDBObject.__init__(self)
        self.lastTheme = None
        self.pastThemes = []
        self.theme = config.get(prefs.THEME_NAME)
        if self.theme is not None:
            self.theme = unicode(self.theme)
        # if we don't have a theme, self.theme will be None
        self.pastThemes.append(self.theme)
        self.onFirstRun()

    # We used to do this on restore, but we need to make sure that the
    # whole database is loaded because we're checking to see if objects
    # are present.  So, we call it when we access the object in app.py
    def checkNewTheme(self):
        self.theme = config.get(prefs.THEME_NAME)
        if self.theme is not None:
            self.theme = unicode(self.theme)
        if self.theme not in self.pastThemes:
            self.pastThemes.append(self.theme)
            self.onFirstRun()
            self.signalChange()
        if self.lastTheme != self.theme:
            self.lastTheme = self.theme
            self.onThemeChange()

    @asUrgent
    def onThemeChange(self):
        self.signalChange()

    def onFirstRun(self):
        logging.info("Spawning Miro Guide...")
        guideURL = unicode(config.get(prefs.CHANNEL_GUIDE_URL))
        if guide.getGuideByURL(guideURL) is None:
            guide.ChannelGuide(guideURL,
            unicode(config.get(prefs.CHANNEL_GUIDE_ALLOWED_URLS)).split())

        if self.theme is not None: # we have a theme
            new_guides = unicode(config.get(prefs.ADDITIONAL_CHANNEL_GUIDES)).split()
            for temp_guide in new_guides:
                if guide.getGuideByURL(temp_guide) is None:
                    guide.ChannelGuide(temp_guide)
            if ((config.get(prefs.DEFAULT_CHANNELS_FILE) is not None) and
                    (config.get(prefs.THEME_NAME) is not None)):
                importer = opml.Importer()
                filepath = resources.theme_path(config.get(prefs.THEME_NAME), 
                    config.get(prefs.DEFAULT_CHANNELS_FILE))
                if os.path.exists(filepath):
                    importer.importSubscriptionsFrom(filepath,
                            showSummary = False)
                else:
                    logging.warn("Theme subscription file doesn't exist: %s",
                            filepath)
            elif None not in self.pastThemes:
                # We pretend to have run the default theme, and then
                # install the default channels.  XXX: If Miro Guide isn't
                # installed by the theme and it doesn't provide a default
                # set of channels, we'll never install the Miro Guide.

                # This code would install the Miro Guide if it isn't
                # already installed
                # if guide.getGuideByURL(prefs.CHANNEL_GUIDE_URL.default) is None:
                #     guide.ChannelGuide(prefs.CHANNEL_GUIDE_URL.default)
                self.pastThemes.append(None)
                self._installDefaultFeeds()
        else: # no theme
            self._installDefaultFeeds()
        signals.system.themeFirstRun(self.theme)

    @asUrgent
    def _installDefaultFeeds(self):
        initialFeeds = resources.path("initial-feeds.democracy")
        if os.path.exists(initialFeeds):
            urls = subscription.parseFile(initialFeeds)
            if urls is not None:
                for url in urls:
                    feed.Feed(url, initiallyAutoDownloadable=False)
            dialog = dialogs.MessageBoxDialog(_("Custom Channels"), Template(_("You are running a version of $longAppName with a custom set of channels.")).substitute(longAppName=config.get(prefs.LONG_APP_NAME)))
            dialog.run()
            app.controller.initial_feeds = True
        else:
            logging.info("Adding default feeds")
            if plat.system() == 'Darwin':
                defaultFeedURLs = [u'http://www.getmiro.com/screencasts/mac/mac.feed.rss']
            elif plat.system() == 'Windows':
                defaultFeedURLs = [u'http://www.getmiro.com/screencasts/windows/win.feed.rss']
            else:
                defaultFeedURLs = [u'http://www.getmiro.com/screencasts/windows/win.feed.rss']
            defaultFeedURLs.extend([ (_('Starter Channels'),
                                      [u'http://richie-b.blip.tv/posts/?skin=rss',
                                       u'http://feeds.pbs.org/pbs/kcet/wiredscience-video',
                                       u'http://www.jpl.nasa.gov/multimedia/rss/podfeed-hd.xml',
                                       u'http://www.linktv.org/rss/hq/mosaic.xml']),
                                   ])

            for default in defaultFeedURLs:
                if isinstance(default, tuple): # folder
                    defaultFolder = default
                    c_folder = folder.ChannelFolder(defaultFolder[0])
                    for url in defaultFolder[1]:
                        d_feed = feed.Feed(url, initiallyAutoDownloadable=False)
                        d_feed.setFolder(c_folder)
                else: # feed
                    d_feed = feed.Feed(default, initiallyAutoDownloadable=False)
            playlist.SavedPlaylist(_(u"Example Playlist"))
