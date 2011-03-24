# -*- coding: utf-8 -*-
# Miro - an RSS based video player application
# Copyright (C) 2007, 2008, 2009, 2010, 2011
# Participatory Culture Foundation
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

"""``miro.theme`` -- Holds the ThemeHistory object.
"""

import urllib

from miro.gtcache import gettext as _
import logging
from miro import app
from miro import prefs
import os
from miro.eventloop import as_urgent
from miro.database import DDBObject, ObjectNotFoundError
from miro import opml
from miro.plat import resources
from miro import guide
from miro import feed
from miro import folder
from miro import playlist
from miro import signals

class ThemeHistory(DDBObject):
    """DDBObject that keeps track of the themes used in regards
    to setting up new themes and changing themes.
    """
    def setup_new(self):
        self.lastTheme = None
        self.pastThemes = []
        self.theme = app.config.get(prefs.THEME_NAME)
        if self.theme is not None:
            self.theme = unicode(self.theme)
        # if we don't have a theme, self.theme will be None
        self.pastThemes.append(self.theme)
        self.on_first_run()

    # We used to do this on restore, but we need to make sure that the
    # whole database is loaded because we're checking to see if objects
    # are present.  So, we call it when we access the object in app.py
    def check_new_theme(self):
        self.theme = app.config.get(prefs.THEME_NAME)
        if self.theme is not None:
            self.theme = unicode(self.theme)
        if self.theme not in self.pastThemes:
            self.pastThemes.append(self.theme)
            self.on_first_run()
            self.signal_change()
        if self.lastTheme != self.theme:
            self.lastTheme = self.theme
            self.on_theme_change()

    @as_urgent
    def on_theme_change(self):
        if self.theme is None: # vanilla Miro
            guide_url = app.config.get(prefs.CHANNEL_GUIDE_URL)
            if guide.get_guide_by_url(guide_url) is None:
                # This happens when the DB is initialized with a theme that
                # doesn't have it's own set of default channels; None is
                # artificially added to the pastThemes lists to prevent the
                # default channels from being added again.  However, it means
                # that we need to add the Miro Guide to the DB ourselves.
                logging.warn('Installing default guide after switch to vanilla Miro')
                guide.ChannelGuide(guide_url,
                                   unicode(app.config.get(
                            prefs.CHANNEL_GUIDE_ALLOWED_URLS)).split())
        self.signal_change()

    def on_first_run(self):
        logging.info("Spawning Miro Guide...")
        guide_url = unicode(app.config.get(prefs.CHANNEL_GUIDE_URL))
        if guide.get_guide_by_url(guide_url) is None:
            allowed_urls = app.config.get(prefs.CHANNEL_GUIDE_ALLOWED_URLS)
            guide.ChannelGuide(guide_url, unicode(allowed_urls).split())

        if self.theme is not None:
            # we have a theme
            new_guides = unicode(app.config.get(prefs.ADDITIONAL_CHANNEL_GUIDES)).split()
            for temp_guide in new_guides:
                if guide.get_guide_by_url(temp_guide) is None:
                    guide.ChannelGuide(temp_guide)
            if (((app.config.get(prefs.DEFAULT_CHANNELS_FILE) is not None)
                 and (app.config.get(prefs.THEME_NAME) is not None))):
                importer = opml.Importer()
                filepath = resources.theme_path(app.config.get(prefs.THEME_NAME), 
                    app.config.get(prefs.DEFAULT_CHANNELS_FILE))
                if os.path.exists(filepath):
                    importer.import_subscriptions(filepath,
                                                  show_summary=False)
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
        else:
            # no theme
            self._install_default_feeds()
        signals.system.theme_first_run(self.theme)

    def _add_default(self, default):
        # folder
        if isinstance(default, tuple) and isinstance(default[1], list):
            defaultFolder = default
            try:
                c_folder = folder.ChannelFolder.get_by_title(defaultFolder[0])
            except ObjectNotFoundError:
                c_folder = folder.ChannelFolder(defaultFolder[0])
                c_folder.signal_change()
            for url, autodownload in defaultFolder[1]:
                logging.info("adding feed %s" % (url,))
                d_feed = feed.lookup_feed(default[0])
                if d_feed is None:
                    d_feed = feed.Feed(url, initiallyAutoDownloadable=autodownload)
                    d_feed.set_folder(c_folder)
                    d_feed.signal_change()
        # feed
        else:
            d_feed = feed.lookup_feed(default[0])
            if d_feed is None:
                logging.info("adding feed %s" % (default,))
                d_feed = feed.Feed(default[0], initiallyAutoDownloadable=default[1])
                d_feed.signal_change()

    @as_urgent
    def _install_default_feeds(self):
        logging.info("Adding default feeds")
        default_feeds = [
            (u'http://vodo.net/feeds/promoted', False),
            (u'http://feeds.feedburner.com/earth-touch_podcast_720p', False),
            (u'http://www.linktv.org/rss/hq/globalpulse.xml', False),
            (u'http://feeds.thisamericanlife.org/talpodcast', False)
            ]

        for default in default_feeds:
            self._add_default(default)

        # create example playlist
        default_playlists = [
            u"Example Playlist"
            ]
        for default in default_playlists:
            try:
                playlist.SavedPlaylist.get_by_title(default)
            except ObjectNotFoundError:
                playlist.SavedPlaylist(_("Example Playlist"))

        default_guides = [
            (u"http://www.clearbits.net/", u"ClearBits", False),
            (u"http://www.youtorrent.com/", u"YouTorrent", False),
            (u"https://www.miroguide.com/audio/", u"Miro Audio Guide", False),
            (u'http://www.amazon.com/b?_encoding=UTF8&site-redirect=&'
             'node=163856011&tag=pcultureorg-20&linkCode=ur2&camp=1789&'
             'creative=9325', u"Amazon MP3 Store", True)
            ]

        if app.debugmode:
            default_guides.append(
                (u"http://bugzilla.pculture.org/enter_bug.cgi?product=Miro",
                 u"Report a Miro Bug", False))
            default_guides.append(
                (u"http://develop.participatoryculture.org/index.php/Miro-Current-Release-Testing",
                 u"Miro Testing", False))

        for default in default_guides:
            try:
                cg = guide.ChannelGuide.get_by_url(default[0])
            except ObjectNotFoundError:
                cg = guide.ChannelGuide(default[0])
                cg.store = default[2] # before title because title saves the
                                      # object
                cg.set_title(default[1])

        base_url = u"http://www.amazon.com/gp/redirect.html?ie=UTF8&location=%s&tag=pcultureorg-20&linkCode=ur2&camp=1789&creative=9325"
        other_stores = (
            ('http://www.amazon.fr/T%C3%A9l%C3%A9charger-Musique-mp3/b/ref=sa_menu_mp31?ie=UTF8&node=77196031', u'Amazon Téléchargements MP3 (FR)'),
            ('http://www.amazon.de/MP3-Musik-Downloads/b/ref=sa_menu_mp31?ie=UTF8&node=77195031', u'Amazon MP3-Downloads (DE/AT/CH)'),
            ('http://www.amazon.co.jp/MP3-%E3%83%80%E3%82%A6%E3%83%B3%E3%83%AD%E3%83%BC%E3%83%89-%E9%9F%B3%E6%A5%BD%E9%85%8D%E4%BF%A1-DRM%E3%83%95%E3%83%AA%E3%83%BC/b/ref=sa_menu_dmusic1?ie=UTF8&node=2128134051', u'Amazon MP3ダウンロード (JP)'),
            ('http://www.amazon.co.uk/MP3-Music-Download/b/ref=sa_menu_dm1?ie=UTF8&node=77197031', u'Amazon MP3 Downloads (UK)'))

        for url, name in other_stores:
            store_url = base_url % urllib.quote(url, safe='')
            try:
                cg = guide.ChannelGuide.get_by_url(store_url)
            except ObjectNotFoundError:
                cg = guide.ChannelGuide(store_url)
                cg.store = cg.STORE_INVISIBLE
                cg.set_title(name)
