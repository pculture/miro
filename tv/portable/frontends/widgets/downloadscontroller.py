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

"""Controller for Downloads tab."""

from miro.gtcache import gettext as _

from miro.frontends.widgets.itemlistcontroller import SimpleItemListController
from miro.frontends.widgets import itemlistwidgets

from miro import messages
from miro import downloader

from miro.plat.utils import get_available_bytes_for_movies

class DownloadsController(SimpleItemListController):
    type = 'downloads'
    id = None
    image_filename = 'icon-downloading_large.png'
    title = _("Downloads")

    def __init__(self):
        SimpleItemListController.__init__(self)
        self.button_toolbar = itemlistwidgets.DownloadButtonToolbar()
        self.button_toolbar.connect("pause-all", self._on_pause_all)
        self.button_toolbar.connect("resume-all", self._on_resume_all)
        self.button_toolbar.connect("cancel-all", self._on_cancel_all)
        self.label_toolbar = itemlistwidgets.DownloadLabelToolbar()
        self._update_free_space()
        self.widget.titlebar_vbox.pack_start(self.label_toolbar)
        self.widget.titlebar_vbox.pack_start(self.button_toolbar)

    def _update_free_space(self):
        self.label_toolbar.update_free_space(get_available_bytes_for_movies())

    def _on_pause_all(self, widget):
        messages.PauseAllDownloads().send_to_backend()

    def _on_resume_all(self, widget):
        messages.ResumeAllDownloads().send_to_backend()

    def _on_cancel_all(self, widget):
        messages.CancelAllDownloads().send_to_backend()

    def on_items_changed(self):
        self.label_toolbar.update_downloading_rate(downloader.totalDownRate)
        self.label_toolbar.update_uploading_rate(downloader.totalUpRate)
