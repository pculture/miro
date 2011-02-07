# Miro - an RSS based video player application
# Copyright (C) 2005, 2006, 2007, 2008, 2009, 2010, 2011
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

"""Controllers for the root tabs (Connect, Sources, Stores, Podcasts, Playlists
"""
from miro import app
from miro import prefs

from miro.gtcache import gettext as _

from miro.frontends.widgets import imagepool
from miro.frontends.widgets import style
from miro.frontends.widgets import widgetutil

from miro.plat import resources
from miro.plat.frontends.widgets import widgetset

class ConnectTab(widgetset.VBox):
    def __init__(self):
        widgetset.VBox.__init__(self)
        self.set_size_request(600, -1)

        trans_data = {'shortappname': app.config.get(prefs.SHORT_APP_NAME)}

        title = widgetset.HBox()
        logo = widgetset.ImageDisplay(imagepool.get(
            resources.path('images/icon-connect_large.png')))
        title.pack_start(logo)
        label = widgetset.Label(_("Connect"))
        label.set_size(2)
        label.set_bold(True)
        title.pack_start(widgetutil.pad(label, left=5))
        self.pack_start(widgetutil.align_center(title, bottom_pad=20))

        # sharing
        label = widgetset.Label(_("%(shortappname)s Sharing", trans_data))
        label.set_size(1.5)
        self.pack_start(widgetutil.align_left(label, left_pad=20,
                                              bottom_pad=5))
        label = widgetset.Label(
            _("%(shortappname)s can stream and download files to and from "
              "other %(shortappname)s's on your local network and to the "
              "Miro iPad app.  It's awesome!", trans_data))
        label.set_wrap(True)
        self.pack_start(widgetutil.align_left(label, left_pad=20,
                                              bottom_pad=5))
        vbox = widgetset.VBox()
        hbox = widgetset.HBox()
        hbox.pack_start(widgetset.Checkbox(_("Videos")))
        hbox.pack_start(widgetset.Checkbox(_("Music")))
        hbox.pack_start(widgetset.Checkbox(_("Podcasts")))
        hbox.pack_end(widgetset.Checkbox(_("On")))
        vbox.pack_start(hbox)

        hbox = widgetset.HBox()
        #_("Off")
        hbox.pack_start(widgetset.Label(
            _("My %(shortappname)s Share Name", trans_data)))
        hbox.pack_start(widgetset.TextEntry())
        vbox.pack_start(widgetutil.pad(hbox, top=10))

        bg = widgetset.SolidBackground(style.css_to_color('#dddddd'))
        bg.set_size_request(400, 100)
        bg.add(vbox)
        self.pack_start(widgetutil.align_left(bg, left_pad=20, bottom_pad=50))

        # syncing
        hbox = widgetset.HBox()
        vbox = widgetset.VBox()
        label = widgetset.Label(_("Sync a Phone or Tablet"))
        _("Get Help")
        label.set_size(1.5)
        vbox.pack_start(widgetutil.align_left(label, left_pad=20,
                                              bottom_pad=5))
        label = widgetset.Label(
            _("Connect the USB cable to sync your Android device with "
              "%(shortappname)s.  Be sure to set your device to 'USB Mass "
              "Storage' mode in your device settings.", trans_data))
        label.set_wrap(True)
        vbox.pack_start(widgetutil.align_left(label, left_pad=20,
                                              bottom_pad=5))

        show_all_vbox = widgetset.VBox()
        show_all_vbox.pack_start(widgetset.Checkbox(
            _("Show all attached devices and drives")))
        label = widgetset.Label(
            _("Use this if your phone doesn't appear in %(shortappname)s when "
              "you connect it to the computer, or if you want to sync with an "
              "external drive.", trans_data))
        label.set_wrap(True)
        show_all_vbox.pack_start(label)
        bg = widgetset.SolidBackground(style.css_to_color('#dddddd'))
        bg.set_size_request(400, 100)
        bg.add(show_all_vbox)
        vbox.pack_start(widgetutil.pad(bg, left=20, right=10, bottom=50))
        hbox.pack_start(vbox)
        hbox.pack_start(widgetutil.align_right(widgetset.ImageDisplay(
            imagepool.get(resources.path('images/connect-android.png')))))
        self.pack_start(hbox)

        # iPad link
        hbox = widgetset.HBox()
        vbox = widgetset.VBox()
        label = widgetset.Label(_("Miro on your iPad"))
        label.set_size(1.5)
        vbox.pack_start(widgetutil.align_left(label, left_pad=20,
                                              bottom_pad=5))
        label = widgetset.Label(
            _("The gorgeous Miro iPad app lets you wirelessly stream music "
              "and videos from %(shortappname)s on your desktop to your iPad. "
              "You can also download songs and videos to your iPad and take "
              "them with you.", trans_data))
        label.set_wrap(True)
        vbox.pack_start(widgetutil.align_left(label, left_pad=20,
                                              right_pad=10,
                                              bottom_pad=5))
        hbox.pack_start(vbox)
        hbox.pack_start(widgetset.ImageDisplay(
            imagepool.get(resources.path('images/connect-appstore.png'))))
        self.pack_start(hbox)

