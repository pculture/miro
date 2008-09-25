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

"""dialogwidgets.py -- Classes to help build dialog boxes.

Mostly these classes provide ways to lay out controls inside a dialog box in a
nice looking way.  ControlGrid provides a simple API for building up Table
widgets that are filled with controls.
"""

from miro.frontends.widgets import widgetconst
from miro.plat.frontends.widgets import widgetset

class ControlLine(object):
    """A Single row of controls for ControlGrid."""

    def __init__(self):
        self._packing = []

    def pack(self, widget, extra_space, pad_left, pad_right, span):
        if extra_space == ControlGrid.ALIGN_RIGHT:
            xalign= 1.0
            xscale = 0.0
        elif extra_space == ControlGrid.ALIGN_LEFT:
            xalign= 0.0
            xscale = 0.0
        elif extra_space == ControlGrid.FILL:
            xalign= 0.0
            xscale = 1.0
        self._packing.append((widget, span, xalign, xscale, 
            pad_left, pad_right))

    def add_to_table(self, table, row, pad_bottom=0):
        baselines = [widget.baseline() for widget, _, _, _, _, _ \
                in self._packing]
        max_baseline = max(baselines)
        column = 0
        for (widget, span, xalign, xscale, pad_left, pad_right), baseline in \
                zip(self._packing, baselines):
            bottom_pad = pad_bottom + max_baseline - baseline
            alignment = widgetset.Alignment(xalign, 1.0, xscale, 0.0)
            alignment.set_padding(0, bottom_pad, pad_left, pad_right)
            alignment.add(widget)
            table.pack(alignment, column, row, column_span=span)
            column += span

class ControlGrid(object):
    ALIGN_LEFT = 0
    ALIGN_RIGHT = 1
    FILL = 2

    def __init__(self):
        self._lines = []
        self._current_columns = 0
        self.columns = 0
        self._current_line = ControlLine()

    def pack_label(self, text, *args, **kwargs):
        if 'extra_space' not in kwargs and len(args) == 0:
            kwargs['extra_space'] = ControlGrid.ALIGN_LEFT
        self.pack(widgetset.Label(text), *args, **kwargs)

    def pack(self, widget, extra_space=FILL, pad_left=0,
            pad_right=6, span=1):
        self._current_line.pack(widget, extra_space, pad_left, pad_right, span)
        self._current_columns += span
        self.columns = max(self.columns, self._current_columns)

    def end_line(self, spacing=0):
        self._lines.append((self._current_line, spacing))
        self._current_line = ControlLine()
        self._current_columns = 0

    def make_table(self):
        lines = self._lines[:]
        if self._current_columns > 0:
            lines.append((self._current_line, 0))
        table = widgetset.Table(self.columns, len(lines))
        for i, (line, spacing) in enumerate(lines):
            line.add_to_table(table, i, spacing)
        return table

class ControlList(widgetset.VBox):
    """VBox containing controls.  The baseline for this widget is the baseline
    for the top control.
    """
    def __init__(self, top_control, spacing=0):
        widgetset.VBox.__init__(self, spacing)
        self.pack_start(top_control)
        self.top_control = top_control

    def baseline(self):
        bottom_extra = (self.get_size_request()[1] -
                self.top_control.get_size_request()[1])
        return self.top_control.baseline() + bottom_extra

def label_with_note(label_text, note_text):
    """Return a ControlList that displays a label with a note under it.  """
    label = widgetset.Label(label_text)
    note = widgetset.Label(note_text)
    note.set_size(widgetconst.SIZE_SMALL)
    list = ControlList(label)
    list.pack_start(note)
    return list

def radio_button_list(*radio_buttons):
    """List a radio buttons.  """
    list = ControlList(radio_buttons[0])
    for radio in radio_buttons[1:]:
        list.pack_start(radio)
    return list

def heading(text):
    label = widgetset.Label(text)
    label.set_bold(True)
    return label

def note(text):
    label = widgetset.Label(text)
    label.set_size(widgetconst.SIZE_SMALL)
    return label
