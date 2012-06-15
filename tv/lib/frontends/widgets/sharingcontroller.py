# Miro - an RSS based video player application
# Copyright (C) 2010 Participatory Culture Foundation
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

"""playlist.py -- Handle displaying a playlist."""

from miro.frontends.widgets import itemlistcontroller
from miro.frontends.widgets import itemlistwidgets
from miro.frontends.widgets import itemrenderer
from miro.frontends.widgets import itemtrack
from miro.gtcache import gettext as _

# The spinning progress bar while a user connects is done by the backend
# with messages sent to the frontend, the idea is the backend should know
# when it is a connect or not so let it handle that case.
class SharingView(itemlistcontroller.SimpleItemListController):
    def __init__(self, share):
        self.type = u'sharing'
        self.share = share
        self.id = share.id
        itemlistcontroller.SimpleItemListController.__init__(self)

    def make_drag_handler(self):
        return None

    def make_titlebar(self):
        titlebar = itemlistwidgets.SharingTitlebar()
        titlebar.connect('search-changed', self._on_search_changed)
        titlebar.connect('filter-clicked', self.on_filter_clicked)
        titlebar.hide_album_view_button()
        return titlebar

    def build_renderer(self):
        return itemrenderer.SharingItemRenderer(display_channel=False)

    def handle_delete(self):
        pass

    def build_item_list(self):
        # FIXME: Make this work again
        raise NotImplementedError()

    def build_widget(self):
        itemlistcontroller.SimpleItemListController.build_widget(self)

        # this only gets shown when the user is searching for things
        # in the feed and there are no results.
        text = _('No Results')
        self.widget.list_empty_mode_vbox.pack_start(
                itemlistwidgets.EmptyListHeader(text))

    def _on_search_changed(self, widget, search_text):
        self.set_search(search_text)
