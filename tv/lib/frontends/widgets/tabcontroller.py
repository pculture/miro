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
import math

from miro import app
from miro import prefs

from miro.gtcache import gettext as _

from miro.frontends.widgets import imagepool
from miro.frontends.widgets import style
from miro.frontends.widgets import widgetconst
from miro.frontends.widgets import widgetutil

from miro.plat import resources
from miro.plat.frontends.widgets import widgetset

class RoundedSolidBackground(widgetset.Background):
    SIZE = 10

    def __init__(self, color):
        self.color = color
        widgetset.Background.__init__(self)

    def draw(self, context, layout):
        widgetutil.round_rect(context, 0, 0, context.width, context.height,
                              self.SIZE)
        context.set_color(self.color)
        context.fill()

class PrettyToggleButton(widgetset.CustomButton):
    def __init__(self):
        widgetset.CustomButton.__init__(self)
        self.value = False
        self.background = imagepool.get_surface(
            resources.path('images/connect-toggle-bg.png'))
        self.on = imagepool.get_surface(
            resources.path('images/connect-toggle-on.png'))
        self.off = imagepool.get_surface(
            resources.path('images/connect-toggle-off.png'))

        self.connect('clicked', self.on_clicked)

    def set_value(self, value):
        if value == self.value:
            return # don't bother changing
        self.value = value
        self.queue_redraw()

    def get_value(self):
        return self.value

    def size_request(self, layout):
        return self.background.width, self.background.height

    def draw(self, context, layout):
        self.background.draw(context, 0, 0, self.background.width,
                             self.background.height)
        if self.value: # on
            text = _("On")
            left = self.background.width - self.on.width
            right = self.background.width
            self.on.draw(context, self.background.width - self.on.width, 0,
                         self.on.width, self.on.height)
        else:
            text = _("Off")
            left = 0
            right = self.off.width
            self.off.draw(context, 0, 0, self.off.width, self.off.height)

        textbox = layout.textbox(text.upper())
        layout.set_font(1)
        x = int(((right - left) - textbox.get_size()[0]) / 2) + left
        y = int((self.background.height - textbox.get_size()[1]) / 2)
        textbox.draw(context, x, y, *textbox.get_size())

    def on_clicked(self, button):
        self.set_value(not self.value)

class HelpButton(widgetset.CustomButton):
    def __init__(self):
        widgetset.CustomButton.__init__(self)

        self.image = imagepool.get_surface(
            resources.path('images/connect-help.png'))
        self.text = _("Get Help")

    def _get_textbox(self, layout):
        layout.set_font(0.8)
        return layout.textbox(self.text)

    def size_request(self, layout):
        text_width, text_height = self._get_textbox(layout).get_size()
        return (self.image.width + 15 + math.ceil(text_width),
                max(text_height, self.image.height))

    def draw(self, context, layout):
        y = int((context.height - self.image.height) / 2.0)
        self.image.draw(context, 10, y, self.image.width, self.image.height)
        textbox = self._get_textbox(layout)
        y = int((context.height - textbox.get_size()[1]) / 2.0)
        textbox.draw(context, 15 + self.image.width, y, context.width,
                     context.height)

class AppStoreButton(widgetset.CustomButton):
    def __init__(self):
        widgetset.CustomButton.__init__(self)

        self.image = imagepool.get_surface(
            resources.path('images/connect-appstore.png'))

    def size_request(self, layout):
        return self.image.width, self.image.height

    def draw(self, context, layout):
        self.image.draw(context, 0, 0, self.image.width, self.image.height)

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
              "other %(shortappname)ss on your local network and to the "
              "Miro iPad app.  It's awesome!", trans_data))
        label.set_size(widgetconst.SIZE_SMALL)
        label.set_wrap(True)
        self.pack_start(widgetutil.align_left(label, left_pad=20,
                                              bottom_pad=5))
        vbox = widgetset.VBox()
        hbox = widgetset.HBox()
        hbox.pack_start(widgetset.Checkbox(_("Videos")))
        hbox.pack_start(widgetset.Checkbox(_("Music")))
        hbox.pack_start(widgetset.Checkbox(_("Podcasts")))
        hbox.pack_end(PrettyToggleButton())
        vbox.pack_start(hbox)

        hbox = widgetset.HBox()
        #_("Off")
        hbox.pack_start(widgetset.Label(
            _("My %(shortappname)s Share Name", trans_data)))
        hbox.pack_start(widgetutil.pad(widgetset.TextEntry(), left=5))
        vbox.pack_start(widgetutil.pad(hbox, top=10))

        bg = RoundedSolidBackground(style.css_to_color('#dddddd'))
        bg.set_size_request(550, -1)
        bg.add(widgetutil.pad(vbox, 10, 10, 10, 10))
        self.pack_start(widgetutil.align_left(bg, left_pad=20, bottom_pad=50))

        # syncing
        hbox = widgetset.HBox()
        vbox = widgetset.VBox()
        label_line = widgetset.HBox()
        label = widgetset.Label(_("Sync a Phone or Tablet"))
        label.set_size(1.5)
        label_line.pack_start(widgetutil.align_left(label, left_pad=20,
                                              bottom_pad=5))
        help_button = HelpButton()
        help_button.connect('clicked', self.help_button_clicked)
        label_line.pack_start(help_button)
        vbox.pack_start(label_line)

        label = widgetset.Label(
            _("Connect the USB cable to sync your Android device with "
              "%(shortappname)s.  Be sure to set your device to 'USB Mass "
              "Storage' mode in your device settings.", trans_data))
        label.set_size(widgetconst.SIZE_SMALL)
        label.set_wrap(True)
        vbox.pack_start(widgetutil.align_left(label, left_pad=20,
                                              bottom_pad=5))

        show_all_vbox = widgetset.VBox()
        cb = widgetset.Checkbox(_("Show all attached devices and drives"))
        cb.set_checked(app.config.get(prefs.SHOW_UNKNOWN_DEVICES))
        cb.connect('toggled', self.show_all_devices_toggled)
        show_all_vbox.pack_start(cb)
        label = widgetset.Label(
            _("Use this if your phone doesn't appear in %(shortappname)s when "
              "you connect it to the computer, or if you want to sync with an "
              "external drive.", trans_data))
        label.set_size(widgetconst.SIZE_SMALL)
        label.set_wrap(True)
        show_all_vbox.pack_start(label)
        bg = RoundedSolidBackground(style.css_to_color('#dddddd'))
        bg.set_size_request(400, -1)
        bg.add(widgetutil.pad(show_all_vbox, 10, 10, 10, 10))
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
        label.set_size(widgetconst.SIZE_SMALL)
        label.set_wrap(True)
        vbox.pack_start(widgetutil.align_left(label, left_pad=20,
                                              right_pad=10,
                                              bottom_pad=5))
        hbox.pack_start(vbox)
        app_store_button = AppStoreButton()
        app_store_button.connect('clicked', self.app_store_button_clicked)
        hbox.pack_start(app_store_button)
        self.pack_start(hbox)

    def help_button_clicked(self, button):
        print 'help clicked'

    def show_all_devices_toggled(self, cb):
        app.device_manager.set_show_unknown(cb.get_checked())

    def app_store_button_clicked(self, button):
        print 'app store clicked'
