# Miro - an RSS based video player application
# Copyright (C) 2005-2010 Participatory Culture Foundation
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
import pstats
import tempfile

from miro import app
from miro import messages
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
    ]
    labels = [c.__name__ for c in choices]
    index = dialogs.ask_for_choice('Pick Test',
            'Choose which test you want to run', labels)
    if index is None:
        return None
    return choices[index]()

class ProfiledCode(object):
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
        stats.strip_dirs().sort_stats('cumulative').print_stats(0.2)
        os.unlink(path)
        app.widgetapp.quit_ui()

    def set_up(self):
        pass

    def tear_down(self):
        pass

    def profiled_code(self):
        pass

class ProfileItemView(ProfiledCode):
    def set_up(self):
        self.item_list = itemlist.ItemList()
        self.item_list.set_sort(itemlist.DateSort(True))
        self.item_list.add_items(self.generate_items())
        self.make_item_view()
        scroller = widgetset.Scroller(False, True)
        scroller.add(self.item_view)
        self.vbox.pack_start(scroller, expand=True)

    def make_item_view(self):
        self.item_view = itemlistwidgets.ItemView(self.item_list)

    def profiled_code(self):
        for x in xrange(10):
            self.item_view.redraw_now()

    def generate_items(self):
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
         'id': 170,
         'size': 328195214,
         'album': u'',
         'media_type_checked': False,
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
         'description': u'<p>This week\'s first clip takes us to Botswana\'s '
         'Okavango Delta, where Brad Bestelink films a pair of lions and a lo'
         'ne hippo bull.</p>\n<p>In the forests of Thailand\'s Kaeng Krachan '
         'National Park, cameraman Darryl Sweetland encounters a tortoise wit'
         'h an unusual adaptation.</p>\n<p>Next, a black-backed jackal remain'
         's alert as it feeds on the remains of a carcass in South Africa\'s '
         'Free State.</p>\n<p>Finally, cameraman Graeme Duane films the numer'
         'ous cichlid species that inhabit Lake Malawi.</p><br /><img src="ht'
         'tp://podcast.earth-touch.com/images/upload/stories/PC1510/storythum'
         'b.jpg" /><div class="feedflare">\n<a href="http://feeds.feedburner.'
         'com/~ff/earth-touch_podcast_720p?a=s9hm49puBzo:Ac3ddk2VfCI:yIl2AUo'
         'C8zA"><img src="http://feeds.feedburner.com/~ff/earth-touch_podcas'
         't_720p?d=yIl2AUoC8zA" border="0" /></a> <a href="http://feeds.feed'
         'burner.com/~ff/earth-touch_podcast_720p?a=s9hm49puBzo:Ac3ddk2VfCI:'
         'qj6IDK7rITs"><img src="http://feeds.feedburner.com/~ff/earth-touc'
         'h_podcast_720p?d=qj6IDK7rITs" border="0" /></a> <a href="http://f'
         'eeds.feedburner.com/~ff/earth-touch_podcast_720p?a=s9hm49puBzo:Ac'
         '3ddk2VfCI:V_sGLiPBpWU"><img src="http://feeds.feedburner.com/~ff/'
         'earth-touch_podcast_720p?i=s9hm49puBzo:Ac3ddk2VfCI:V_sGLiPBpWU" '
         'border="0" /></a>\n</div><img src="http://feeds.feedburner.com/~'
         'r/earth-touch_podcast_720p/~4/s9hm49puBzo" height="1" width="1" />',
         'name': u'Wildlife podcast, week 15 2010',
         'track': -1,
         'resume_time': 0,
         'pending_auto_dl': False,
         'is_playable': False,
         'subtitle_encoding': None,
         'downloaded': False,
         'item_viewed': False,
         'genre': u'',
         'has_sharable_url': True,
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
        for x in xrange(30):
            item_info = messages.ItemInfo.__new__(messages.ItemInfo)
            item_info.__dict__ = item_info_template.copy()
            retval.append(item_info)
        return retval

class ProfileListItemView(ProfileItemView):
    def make_item_view(self):
        enabled_columns = [u'state', u'name', u'feed-name', u'eta', u'rate',
                u'artist', u'album', u'track', u'year', u'genre']
        self.item_view = itemlistwidgets.ListItemView(self.item_list,
                enabled_columns)
