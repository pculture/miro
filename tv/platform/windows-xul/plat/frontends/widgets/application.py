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

import logging
import os
import sys
import traceback
import webbrowser
from urlparse import urlparse

import gtk

from miro import app
from miro import config
from miro import eventloop
from miro import prefs
from miro.frontends.widgets import dialogs
from miro.frontends.widgets.application import Application
from miro.plat import migrateappname
from miro.plat import clipboard
from miro.plat.renderers.vlc import VLCRenderer
from miro.plat.frontends.widgets import xulrunnerbrowser

class WindowsApplication(Application):
    def run(self):
        app.renderer = VLCRenderer()
        self.initXULRunner()
        gtk.gdk.threads_init()
        self.startup()
        gtk.gdk.threads_enter()
        try:
            gtk.main()
        finally:
            gtk.gdk.threads_leave()
        xulrunnerbrowser.shutdown()
        app.controller.onShutdown()

    def quit_ui(self):
        gtk.main_quit()

    def get_clipboard_text(self):
        return clipboard.get_text()

    def copy_text_to_clipboard(self, text):
        clipboard.set_text(text)

    def initXULRunner(self):
        app_dir = os.path.dirname(sys.executable)
        xul_dir = os.path.join(app_dir, 'xulrunner')
        xulrunnerbrowser.initialize(xul_dir, app_dir)

    def handleStartupSuccess(self, obj):
        migrateappname.migrateVideos('Democracy', 'Miro')
        Application.handleStartupSuccess(self, obj)

    def open_url(self, url):
        # It looks like the maximum URL length is about 2k. I can't
        # seem to find the exact value
        if len(url) > 2047:
            url = url[:2047]
        try:
            webbrowser.get("windows-default").open_new(url)
        except:
            logging.warn("Error opening URL: %r\n%s", url,
                    traceback.format_ext())
            recommendURL = config.get(prefs.RECOMMEND_URL)

            if url.startswith(config.get(prefs.VIDEOBOMB_URL)):
                title = _('Error Bombing Item')
            elif url.startswith(recommendURL):
                title = _('Error Recommending Item')
            else:
                title = _("Error Opening Website")

            scheme, host, path, params, query, fragment = urlparse(url)
            shortURL = '%s:%s%s' % (scheme, host, path)
            msg = _("There was an error opening %s.  Please try again in "
                    "a few seconds") % shortURL
            dialogs.show_message(title, msg)

    def open_file(self, fn):
        if not os.path.isdir(fn):
            fn = os.path.dirname(fn)
        os.startfile(fn)
