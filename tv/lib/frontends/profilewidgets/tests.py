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

"""miro.frontends.profilewidgets -- Tests to profile
"""

import cProfile
import os
import datetime
import itertools
import pstats
import random
import tempfile

from miro import app
from miro import messages
from miro import util
from miro.plat.frontends.widgets import threads
from miro.plat.frontends.widgets import widgetset
from miro.frontends.widgets import dialogs
from miro.frontends.widgets import itemlistwidgets
from miro.frontends.widgets import itemlist

def startup():
    threads.call_on_ui_thread(_startup)

def _startup():
    profiled_code = pick_test()
    if profiled_code is None:
        app.widgetapp.quit_ui()
        return
    profiled_code.startup()

def pick_test():
    choices = [
        ProfileItemView,
        ProfileListItemView,
        ProfileItemViewAdd,
        ProfileItemViewRemove,
        ProfileItemViewResort,
    ]
    labels = [c.friendly_name() for c in choices]
    index = dialogs.ask_for_choice('Pick Test',
            'Choose which test you want to run', labels)
    if index is None:
        return None
    return choices[index]()

class ProfiledCode(object):
    stats_cutoff = 0.4

    def startup(self):
        window = widgetset.MainWindow('Miro Profiler', widgetset.Rect(100,
            100, 700, 500))
        self.vbox = widgetset.VBox()
        button = widgetset.Button("Start Test")
        button.connect('clicked', self.start_button_clicked)
        self.vbox.pack_end(button)
        window.set_content_widget(self.vbox)
        window.show()
        self.set_up()

    def start_button_clicked(self, button):
        path = tempfile.mktemp()
        cProfile.runctx('self.profiled_code()', globals(), locals(), path)
        self.tear_down()
        stats = pstats.Stats(path)
        stats = stats.strip_dirs().sort_stats('cumulative')
        stats.print_stats(self.stats_cutoff)
        os.unlink(path)
        app.widgetapp.quit_ui()

    def set_up(self):
        pass

    def tear_down(self):
        pass

    def profiled_code(self):
        pass

    @classmethod
    def friendly_name(self):
        raise NotImplementedError()

class ProfileItemView(ProfiledCode):
    descriptions_to_generate = 100
    initial_items = 30

    @classmethod
    def friendly_name(cls):
        return "Profile rendering items"

    def set_up(self):
        self.html_stripper = util.HTMLStripper()
        self.id_counter = itertools.count()
        self.setup_text()
        self.item_list = itemlist.ItemList()
        self.item_list.set_sort(itemlist.DateSort(True))
        self.item_list.add_items(self.generate_items(self.initial_items))
        self.make_item_view()
        scroller = widgetset.Scroller(False, True)
        scroller.add(self.item_view)
        self.vbox.pack_start(scroller, expand=True)

    def setup_text(self):
        # 200 words of lorem ipsum
        lorem = ("Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
                "Vivamus enim tortor, volutpat at blandit nec, posuere "
                "id dui.  Sed pharetra porta nibh sed blandit. Praesent "
                "vitae enim ac elit condimentum bibendum eu eu tellus. "
                "Maecenas diam neque, rhoncus sit amet eleifend et, "
                "ornare sed sem.  Vestibulum sollicitudin pretium "
                "hendrerit. Nam venenatis, ligula nec laoreet euismod, "
                "ligula augue tempor mauris, nec semper leo massa et "
                "velit. Cras viverra ultricies est ac egestas. Nulla "
                "pulvinar elit nec orci ultrices in aliquet risus "
                "tempor. Fusce vitae lorem sapien, in lacinia tortor. "
                "Cum sociis natoque penatibus et magnis dis parturient "
                "montes, nascetur ridiculus mus. Maecenas nec justo "
                "velit.  Quisque tempus laoreet risus.  Aenean urna "
                "arcu, consectetur at accumsan sit amet, tempor rutrum "
                "tortor. Ut bibendum libero id nulla vehicula vel "
                "viverra magna dignissim. Aliquam malesuada metus "
                "ultricies nunc feugiat viverra. Curabitur vel leo "
                "sapien. Cum sociis natoque penatibus et magnis dis "
                "parturient montes, nascetur ridiculus mus. Vestibulum "
                "fermentum massa et augue adipiscing et imperdiet lorem "
                "aliquet. Pellentesque posuere vestibulum tortor, eu "
                "facilisis nibh venenatis eu.  Fusce eleifend, felis "
                "varius commodo fringilla, dui nisl porttitor lacus, et "
                "gravida est ipsum a arcu. Fusce vitae mi ut diam "
                "blandit ornare. Sed viverra metus at massa viverra.  ")
        lorem = lorem.split()
        self.names = itertools.cycle(' '.join(random.sample(lorem, 5))
                for x in xrange(self.descriptions_to_generate))
        descriptions = []
        for x in xrange(self.descriptions_to_generate):
            random.shuffle(lorem)
            p1 = ' '.join(lorem)
            random.shuffle(lorem)
            p2 = ' '.join(lorem)
            random.shuffle(lorem)
            p3 = ' '.join(lorem)
            descriptions.append("\n".join((p1, p2, p3)))
        self.descriptions = itertools.cycle(descriptions)

    def make_item_view(self):
        self.item_view = itemlistwidgets.StandardView(self.item_list)

    def profiled_code(self):
        for x in xrange(30):
            self.item_view.redraw_now()
            for item in self.item_list:
                self.mutate_item(item)
            self.item_list.update_items(self.item_list)
            self.item_view.model_changed()

    def mutate_item(self, item):
        # make sure an items text is unique so the text layout isn't cached
        item.name = self.names.next()
        item.description = self.descriptions.next()
        item.description_stripped = self.html_stripper.strip(item.description)
        item.release_date += datetime.timedelta(days=1)
        item.duration += 1
        item.size += 1

    def generate_items(self, count):
        item_info_template = {
         'down_rate': None,
         'rating': None,
         'commentslink': u'',
         'file_type': None,
         'pending_manual_dl': False,
         'download_info': None,
         'device': None,
         'feed_id': 31,
         'year': -1,
         'duration': 0,
         'size': 328195214,
         'album': u'',
         'can_be_saved': False,
         'file_format': u'.mov',
         'video_path': None,
         'feed_name': u'Wildlife Highlights, HD, short version',
         'payment_link': u'',
         'state': u'new',
         'is_container_item': None,
         'down_total': None,
         'seeding_status': None,
         'thumbnail':
         '/home/ben/miro-dev-home/.miro/icon-cache/ET_HD-dopvhost=podcast.earth-touch.com_doppl=e53b4d7fa9c4ec65a994ec65ec8454a5_dopsig=6778f4808f4.51041537.jpg',
         'mime_type': u'video/quicktime',
         'up_total': None,
         'children': [],
         'track': -1,
         'resume_time': 0,
         'pending_auto_dl': False,
         'is_playable': False,
         'is_playing': False,
         'subtitle_encoding': None,
         'downloaded': False,
         'item_viewed': False,
         'genre': u'',
         'has_shareable_url': True,
         'is_external': False,
         'permalink':
         u'http://www.earth-touch.com/?hguid=825ae0b0-4b9c-11df-a87c-00304858a4c8',
         'feed_url': u'http://feeds.feedburner.com/earth-touch_podcast_720p',
         'license': u'',
         'leechers': None,
         'expiration_date': None,
         'release_date': datetime.datetime(2010, 4, 21, 12, 37, 22, 2),
         'artist': u'',
         'file_url':
         u'http://feedproxy.google.com/~r/earth-touch_podcast_720p/~5/ivaGTHV-Idw/PC1510_QT720_voice.mov',
         'video_watched': False,
         'thumbnail_url': None,
         'seeders': None,
         'up_rate': None,
         'up_down_ratio': 0.0
         }
        retval = []
        for x in xrange(count):
            item_info = messages.ItemInfo.__new__(messages.ItemInfo)
            item_info.__dict__ = item_info_template.copy()
            self.mutate_item(item_info)
            item_info.id = self.id_counter.next()
            retval.append(item_info)
        return retval

class ProfileListItemView(ProfileItemView):
    @classmethod
    def friendly_name(cls):
        return "Profile rendering items in list view"

    def make_item_view(self):
        enabled_columns = [u'state', u'name', u'feed-name', u'eta', u'rate',
                u'artist', u'album', u'track', u'year', u'genre']
        column_widths = {}
        for name in enabled_columns:
            if name != 'name':
                column_widths[name] = 40
            else:
                column_widths[name] = 150
        self.item_view = itemlistwidgets.ListItemView(self.item_list,
                enabled_columns, column_widths)

class ProfileItemViewAdd(ProfileItemView):
    initial_items = 0

    @classmethod
    def friendly_name(cls):
        return "Profile adding lots of items"

    def set_up(self):
        ProfileItemView.set_up(self)
        # add some more items
        self.items_to_add = self.generate_items(10000)

    def profiled_code(self):
        self.item_view.start_bulk_change()
        self.item_list.add_items(self.items_to_add)
        self.item_view.model_changed()

class ProfileItemViewRemove(ProfileItemView):
    initial_items = 10000

    @classmethod
    def friendly_name(cls):
        return "Profile removing lots of items"

    def profiled_code(self):
        self.item_view.start_bulk_change()
        self.item_list.remove_items(range(10000))
        self.item_view.model_changed()

class ProfileItemViewResort(ProfileItemView):
    initial_items = 10000

    @classmethod
    def friendly_name(cls):
        return "Profile resorting lots of items"

    def profiled_code(self):
        self.item_list.set_sort(itemlist.NameSort(False))
        self.item_view.model_changed()
