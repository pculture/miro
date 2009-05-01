# Miro - an RSS based video player application
# Copyright (C) 2007-2009 Participatory Culture Foundation
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
import os
from miro.eventloop import asUrgent
from miro.database import DDBObject
from miro import opml
from miro.plat import resources
from miro import guide
from miro import feed
from miro import folder
from miro import playlist
from miro import signals

class ThemeHistory(DDBObject):
    def setup_new(self):
        self.lastTheme = None
        self.pastThemes = []
        self.theme = config.get(prefs.THEME_NAME)
        if self.theme is not None:
            self.theme = unicode(self.theme)
        # if we don't have a theme, self.theme will be None
        self.pastThemes.append(self.theme)
        self.on_first_run()

    # We used to do this on restore, but we need to make sure that the
    # whole database is loaded because we're checking to see if objects
    # are present.  So, we call it when we access the object in app.py
    def check_new_theme(self):
        self.theme = config.get(prefs.THEME_NAME)
        if self.theme is not None:
            self.theme = unicode(self.theme)
        if self.theme not in self.pastThemes:
            self.pastThemes.append(self.theme)
            self.on_first_run()
            self.signal_change()
        if self.lastTheme != self.theme:
            self.lastTheme = self.theme
            self.on_theme_change()

    @asUrgent
    def on_theme_change(self):
        if self.theme is None: # vanilla Miro
            guideURL = config.get(prefs.CHANNEL_GUIDE_URL)
            if guide.get_guide_by_url(guideURL) is None:
                # This happens when the DB is initialized with a theme that
                # doesn't have it's own set of default channels; None is
                # artificially added to the pastThemes lists to prevent the
                # default channels from being added again.  However, it means
                # that we need to add the Miro Guide to the DB ourselves.
                logging.warn('Installing default guide after switch to vanilla Miro')
                guide.ChannelGuide(guideURL,
                                   unicode(config.get(
                            prefs.CHANNEL_GUIDE_ALLOWED_URLS)).split())
        self.signal_change()

    def on_first_run(self):
        logging.info("Spawning Miro Guide...")
        guideURL = unicode(config.get(prefs.CHANNEL_GUIDE_URL))
        if guide.get_guide_by_url(guideURL) is None:
            guide.ChannelGuide(guideURL,
            unicode(config.get(prefs.CHANNEL_GUIDE_ALLOWED_URLS)).split())

        if self.theme is not None: # we have a theme
            new_guides = unicode(config.get(prefs.ADDITIONAL_CHANNEL_GUIDES)).split()
            for temp_guide in new_guides:
                if guide.get_guide_by_url(temp_guide) is None:
                    guide.ChannelGuide(temp_guide)
            if ((config.get(prefs.DEFAULT_CHANNELS_FILE) is not None) and
                    (config.get(prefs.THEME_NAME) is not None)):
                importer = opml.Importer()
                filepath = resources.theme_path(config.get(prefs.THEME_NAME), 
                    config.get(prefs.DEFAULT_CHANNELS_FILE))
                if os.path.exists(filepath):
                    importer.import_subscriptions(filepath,
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
                # if guide.get_guide_by_url(prefs.CHANNEL_GUIDE_URL.default) is None:
                #     guide.ChannelGuide(prefs.CHANNEL_GUIDE_URL.default)
                self.pastThemes.append(None)
                self._install_default_feeds()
        else: # no theme
            self._install_default_feeds()
        signals.system.theme_first_run(self.theme)

    @asUrgent
    def _install_default_feeds(self):
        logging.info("Adding default feeds")

        defaultFeedURLs = []

        defaultFeedURLs.extend([
            (u'http://feeds.miroguide.com/miroguide/new', False),
            (u'http://feeds.miroguide.com/miroguide/featured', False),
            (u'http://feeds.feedburner.com/earth-touch_podcast_720p', False),
            (u'http://www.linktv.org/rss/hq/globalpulse.xml', False),

        ])

        for default in defaultFeedURLs:
            # folder
            if isinstance(default, tuple) and isinstance(default[1], list):
                defaultFolder = default
                c_folder = folder.ChannelFolder(defaultFolder[0])
                for url, autodownload in defaultFolder[1]:
                    d_feed = feed.Feed(url, initiallyAutoDownloadable=autodownload)
                    d_feed.set_folder(c_folder)

            # feed
            else:
                d_feed = feed.Feed(default[0], initiallyAutoDownloadable=default[1])

        # create example playlist
        playlist.SavedPlaylist(_(u"Example Playlist"))

        # create default site
        cg = guide.ChannelGuide(u"http://beta.legaltorrents.com/")
        cg.set_title(u"LegalTorrents")
