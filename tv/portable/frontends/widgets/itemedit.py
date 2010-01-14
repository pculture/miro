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

"""miro.frontends.widgets.itemedit -- dialog for editing and
metainformation about an item.
"""

from miro.gtcache import gettext as _
from miro.plat.frontends.widgets import widgetset
from miro.frontends.widgets.dialogs import MainDialog
from miro.frontends.widgets import dialogwidgets
from miro.dialogs import BUTTON_CANCEL, BUTTON_APPLY

import logging

def build_text_entry(key, label, value):
    """Takes a key, label, and value and generates a label, text entry
    and a handler.

    :param key: used as the key in the response dict
    :param label: the label the user sees
    :param value: the current value of this thing

    :returns: label widget, section widget, handler function
    """
    lab = widgetset.Label(label)
    entry = widgetset.TextEntry()
    entry.set_text(value)

    def handler(response_dict):
        if entry.get_text() != value:
            response_dict[key] = entry.get_text()

    return lab, entry, handler

def build_radio(key, label, value, options):
    """Takes a key, label, value and list of (option label, option value)
    pairs and generates a radio button group, label and handler.

    :param key: used as the key in the response dict
    :param label: the label the user sees
    :param value: the current value of this thing
    :param options: list of (label, value) tuples one for each radio
                    button

    :returns: label widget, section widget, handler function
    """
    hbox = widgetset.HBox()

    lab = widgetset.Label(label)
    rbg = widgetset.RadioButtonGroup()
    option_buttons = []
    for option, option_value in options:
        butt = widgetset.RadioButton(option, rbg)
        option_buttons.append((butt, option_value))
        hbox.pack_start(butt)
        if option_value == value:
            butt.set_selected()

    def handler(response_dict):
        selected = rbg.get_selected()
        for rb, rbv in option_buttons:
            if rb == selected:
                if rbv != value:
                    response_dict[key] = rbv
                break

    return lab, hbox, handler

def _run_dialog(iteminfo):
    """Creates and launches the item edit dialog.  This
    dialog waits for the user to press "Apply" or "Cancel".

    Returns a dict of new name -> value.
    """
    window = MainDialog(_('Edit Item'),
                        _('Edit the metadata of this item.'))
    try:
        try:
            window.add_button(BUTTON_APPLY.text)
            window.add_button(BUTTON_CANCEL.text)

            sections = []

            sections.append(build_text_entry(
                "name", _("Item title:"), iteminfo.name))
            sections.append(build_radio(
                "file_type",
                _("Media type:"),
                iteminfo.file_type,
                [(_("video"), u"video"),
                 (_("audio"), u"audio"),
                 (_("other"), u"other")]))

            grid = dialogwidgets.ControlGrid()
            
            for lab, sec, handler in sections:
                grid.pack(lab, grid.ALIGN_LEFT)
                grid.pack(sec)
                grid.end_line(spacing=5)

            window.set_extra_widget(grid.make_table())

            response = window.run()

            response_dict = {}
            if response == 0:
                for lab, sec, handler in sections:
                    handler(response_dict)
            logging.info("response dict: %r", response_dict)
            return response_dict

        except StandardError:
            logging.exception("itemedit threw exception.")
    finally:
        window.destroy()
        
def run_dialog(iteminfo):
    """Creates and launches the "edit item" dialog.
    
    Returns a response dict of name -> value pairs that need to
    be updated.
    """
    response_dict = _run_dialog(iteminfo)

    return response_dict
