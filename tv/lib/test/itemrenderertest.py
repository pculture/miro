# Miro - an RSS based video player application
# Copyright (C) 2012
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

"""itemrenderertest.py -- Test rendering items."""

from miro import app
from miro import downloader
from miro import models
from miro.data import itemtrack
from miro.data import item
from miro.frontends.widgets import itemrenderer
from miro.test import mock
from miro.test.framework import MiroTestCase

class ItemRendererTest(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.renderer = itemrenderer.ItemRenderer()
        self.feed = models.Feed(u'http://example.com/feed.rss')
        self.item = self.make_item(self.feed, u'item')
        self.manual_feed = models.Feed(u'dtv:manualFeed',
                                       initiallyAutoDownloadable=False)
        self.file_item = models.FileItem(self.make_temp_path(),
                                         self.manual_feed.id)
        self.item_fetcher = item.ItemFetcher()
        app.saved_items = set()
        app.playback_manager = mock.Mock()
        app.playback_manager.item_resume_policy.return_value = False

    def _get_item(self, item_id):
        return self.item_fetcher.fetch(app.db.connection, item_id)

    def check_render(self, item):
        """Check that ItemRenderer can sucessfully render a row.

        NOTE: we don't actually check the correctness of the render, just that
        it doesn't crash.
        """
        self.renderer.attrs = {}
        self.renderer.info = self._get_item(item.id)
        context = mock.Mock()
        layout_manager = mock.Mock()
        hotspot = hover = None
        context.width = self.renderer.MIN_WIDTH
        context.height = self.renderer.HEIGHT
        mock_textbox = layout_manager.textbox.return_value
        mock_textbox.font.line_height.return_value = 16
        mock_textbox.get_size.return_value = (100, 16)
        layout_manager.current_font.line_height.return_value = 16
        layout_manager.current_font.ascent.return_value = 12
        for selected in (False, True):
            self.renderer.render(context, layout_manager, selected, hotspot,
                                 hover)

    def test_undownloaded(self):
        self.check_render(self.item)

    def test_downloading(self):
        self.item.download()
        fake_status = {
            'current_size': 100,
            'total_size': None,
            'state': u'downloading',
            'rate': 100,
            'eta': None,
            'type': 'HTTP',
            'dlid': self.item.downloader.dlid,
        }
        downloader.RemoteDownloader.update_status(fake_status)
        self.check_render(self.item)

    def test_downloaded(self):
        self.item.download()
        fake_status = {
            'current_size': 100,
            'total_size': 100,
            'state': u'finished',
            'rate': 0,
            'eta': 0,
            'type': 'HTTP',
            'dlid': self.item.downloader.dlid,
            'filename': self.make_temp_path()
        }
        downloader.RemoteDownloader.update_status(fake_status)
        self.check_render(self.item)

    def test_file_item(self):
        self.check_render(self.file_item)
