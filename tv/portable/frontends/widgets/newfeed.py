# Miro - an RSS based video player application
# Copyright (C) 2005-2009 Participatory Culture Foundation
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

"""miro.frontends.widgets.newfeed -- Holds dialog and processing
code for adding a new feed.
"""

from miro.gtcache import gettext as _
from miro import searchengines

from miro.plat.frontends.widgets import widgetset
from miro.frontends.widgets import widgetutil
from miro.frontends.widgets.dialogs import MainDialog
from miro.dialogs import BUTTON_CANCEL, BUTTON_CREATE_FEED

from miro import app
from miro import feed

import logging

def _run_dialog(title, description, initial_text):
    """Creates and launches the New Feed dialog.  This dialog waits for
    the user to press "Create Feed" or "Cancel".

    Returns a tuple of the (url, section).
    """
    window = MainDialog(title, description)
    try:
        try:
            window.add_button(BUTTON_CREATE_FEED.text)
            window.add_button(BUTTON_CANCEL.text)

            extra = widgetset.VBox()

            lab = widgetset.Label(_('URL:'))
            url_entry = widgetset.TextEntry()
            url_entry.set_text(initial_text)
            url_entry.set_activates_default(True)

            h = widgetset.HBox()
            h.pack_start(lab, padding=5)
            h.pack_start(url_entry, expand=True)
            extra.pack_start(h, padding=5)

            lab = widgetset.Label(_('Feed should go in this section:'))
            rbg = widgetset.RadioButtonGroup()
            video_rb = widgetset.RadioButton(_("video"), rbg)
            audio_rb = widgetset.RadioButton(_("audio"), rbg)

            extra.pack_start(widgetutil.build_hbox((lab, video_rb, audio_rb)))

            window.set_extra_widget(extra)

            response = window.run()

            if response == 0:
                if rbg.get_selected() == video_rb:
                    section = u"video"
                else:
                    section = u"audio"

                text = url_entry.get_text()
                return (text, section)
            
            return (None, None)

        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            logging.exception("newfeed threw exception.")
    finally:
        window.destroy()
        
def run_dialog():
    """Creates and launches the New Feed dialog.  This dialog waits for
    the user to press "Create Feed" or "Cancel".

    Returns a tuple of the (url, section).
    """
    text = app.widgetapp.get_clipboard_text()
    if text and feed.validate_feed_url(text):
        text = feed.normalize_feed_url(text)
    else:
        text = ""

    title = _('Add Feed')
    description = _('Enter the URL of the feed to add')

    while 1:
        text, section = _run_dialog(title, description, initial_text=text)
        if text == None:
            return (None, None)

        normalized_url = feed.normalize_feed_url(text)
        if feed.validate_feed_url(normalized_url):
            return (normalized_url, section)

        title = _('Add Feed - Invalid URL')
        description = _('The address you entered is not a valid url.\nPlease check the URL and try again.\n\nEnter the URL of the feed to add')
