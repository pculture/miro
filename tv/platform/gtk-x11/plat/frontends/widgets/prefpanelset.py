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

"""This module holds functions that extend the panels in the preferences
panel with platform-specific options.

See portable/frontends/widgets/prefpanel.py for more information.
"""

from miro.gtcache import gettext as _
from miro.plat.frontends.widgets import widgetset
from miro.frontends.widgets import widgetutil
from miro.frontends.widgets.prefpanel import attach_radio, attach_combo, note_label, build_hbox

from miro.plat import options 

from miro import config

def _playback_panel():
    extras = []

    lab = widgetset.Label(_("Renderer options:"))
    lab.set_bold(True)
    extras.append(widgetutil.align_left(lab))

    note = note_label(_("You must restart Miro for renderer changes to take effect."))
    extras.append(note)


    lab = widgetset.Label(_("Use this renderer to play videos:"))
    rbg = widgetset.RadioButtonGroup()
    gstreamer_radio = widgetset.RadioButton("gstreamer", rbg)
    xine_radio = widgetset.RadioButton("xine", rbg)
    attach_radio([(gstreamer_radio, "gstreamer"), (xine_radio, "xine")],
                 options.USE_RENDERER)

    extras.append(build_hbox(lab, gstreamer_radio, xine_radio))

    xine_vbox = widgetset.VBox()
    audio_lab = widgetset.Label(_("Use this for video when playing audio:"))
    audio_options = ["none", "goom", "oscope"]
    audio_combo = widgetset.OptionMenu(audio_options)
    attach_combo(audio_combo, options.XINE_VIZ, audio_options)
    xine_vbox.pack_start(build_hbox(audio_lab, audio_combo))        

    extras.append(xine_vbox)

    def handle_clicked(widget):
        if widget is gstreamer_radio:
            xine_vbox.disable_widget()
        elif widget is xine_radio:
            xine_vbox.enable_widget()

    gstreamer_radio.connect('clicked', handle_clicked)
    xine_radio.connect('clicked', handle_clicked)

    if config.get(options.USE_RENDERER) == "gstreamer":
        handle_clicked(gstreamer_radio)
    else:
        handle_clicked(xine_radio)

    h = widgetset.HBox()
    h.pack_start(lab, padding=5)
    h.pack_start(gstreamer_radio, padding=5)
    h.pack_start(xine_radio, padding=5)

    extras.append(h)

    return extras

def get_platform_specific(panel_name):
    if panel_name == "playback":
        return _playback_panel()
