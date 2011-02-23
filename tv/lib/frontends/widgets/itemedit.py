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

"""miro.frontends.widgets.itemedit -- dialog for editing item metadata.
"""

#import textwrap
import logging
import os

from miro import displaytext
from miro.gtcache import gettext as _
from miro.gtcache import ngettext
from miro.plat import resources
from miro.plat.frontends.widgets import widgetset
from miro.frontends.widgets.dialogs import MainDialog
#from miro.frontends.widgets import dialogwidgets
from miro.frontends.widgets import widgetconst
from miro.frontends.widgets import widgetutil
from miro.dialogs import BUTTON_CANCEL, BUTTON_OK

class DialogOwnerMixin(object):
    """Shared methods for fields whose values are determined by a file/directory
    chooser dialog.

    :param dialog: the class of dialog to be created
    :param title: title of the dialog
    :param default: (optional) the value if nothing is changed; the dialog will
                    start out at the path given.
    """
    def __init__(self, dialog, title, default=None):
        self._title = title
        self._dialog_class = dialog
        self._dialog = self._make_dialog()
        self._value = default
        if default is not None:
            self._dialog.set_path(default)
        self._make_dialog()

    def _make_dialog(self):
        return self._dialog_class(self._title)

    def show_dialog(self, *unused):
        """Usually should be connected to some kind of button's click event.
        Accepts and discards an arbitrary number of arguments, so that it can be
        connected to any signal.
        """
        self._dialog.run()
        self._value = self._dialog.get_path()
        self._dialog.destroy()
        # prepare for the chooser to be opened again:
        self._dialog = self._make_dialog()

    def get_value(self):
        return self._value

class Field(object):
    """A metadata property.

    :param field: the attribute of each item tied to this field
    :param items: the set of items potentially being edited
    :param label: text to display to the left of the field
    """
    EXPAND = False
    def __init__(self, field, items, label, readonly=False):
        self.common_value = None
        self.mixed_values = False
        self._find_common_value(field, iter(items))
        self.field = field
        self.label = widgetset.Label(label)
        self.extra = []
        self.inside = False
        self.right = False
        self.widget = NotImplemented
        if not readonly and len(items) > 1:
            self.checkbox = widgetset.Checkbox()
            if not self.mixed_values:
                self.checkbox.set_checked(True)
        else:
            self.checkbox = None

    def set_inside(self, inside=True):
        """Set whether field is not the leftmost column in its row (affects
        label alignment)
        """
        self.inside = inside

    def set_right(self, right=True):
        """Set whether field is in the right column of the dialog (affects label
        alignment)
        """
        self.right = right

    def get_box(self):
        """Return the displayable widget for this field."""
        box = widgetset.HBox()
        label_width = 50
        if self.inside:
            # not aligned with anything, close to its widget, on the right
            left, right = 4, 5
        elif self.right:
            # if it's in the right column, it's right-aligned
            pad = label_width - self.label.get_width()
            left, right = pad, 15
        else:
            # ordinary left-aligned left column field
            pad = label_width - self.label.get_width()
            left, right = 25, pad
        label_alignment = widgetutil.align_top(self.label,
                          right_pad=right, left_pad=left, top_pad=5)
        box.pack_start(label_alignment)
        if self.EXPAND:
            _width, height = self.widget.get_size_request()
            self.widget.set_size_request(250, height)
            box.pack_start(self.widget)
        else:
            widget_alignment = widgetutil.align_left(self.widget)
            box.pack_start(widget_alignment)
        for control in self.extra:
            box.pack_start(control)
        if self.checkbox is not None:
            right = self.right and 20 or 0
            checkbox_alignment = widgetutil.align_top(self.checkbox,
                                 left_pad=12, top_pad=2, right_pad=20)
            box.pack_end(checkbox_alignment)
        return box

    def _value_filter(self, value, item):
        """Function to be applied to all items' original values before looking
        for a common value. Noop for most fields.
        """
        return value

    def _find_common_value(self, field, items):
        """Return the value of field that all items have in common, or None."""
        values = (self._value_filter(getattr(item, field), item) for item in items)
        common = values.next()
        if all(value == common for value in values):
            self.common_value = common
        else:
            self.mixed_values = True

    def get_results(self):
        """Return a map of {field: new_value} for any changes."""
        if self.checkbox is not None and not self.checkbox.get_checked():
            # change is not enabled
            logging.debug("%s: checkbox not set", self.field)
            return {}
        new_value = self.get_value()
        if not self.mixed_values and new_value == self.common_value:
            # nothing has been changed
            logging.debug("%s: new == common", self.field)
            return {}
        else:
            # this field has is enabled and has been changed
            logging.debug("%s: new value = %s; old = %s", self.field,
                    repr(new_value), repr(self.common_value))
            return {self.field: new_value}

    def get_value(self):
        """Return the current value of the field, whether it has been changed or
        not. This method does not need to worry about whether the reason it is
        blank is that the inputs were mixed; if the field is blank, return
        blank.
        """
        raise NotImplementedError()

class DisplayField(Field):
    """A field that displays a value that is never editable, e.g. Size."""
    def __init__(self, field, items, label, formatter):
        Field.__init__(self, field, items, label, readonly=True)
        value = self.common_value
        if value is None and len(items) > 1:
            value = _("(mixed)")
        else:
            value = formatter(value)
        self.widget = widgetset.Label(value)
    
    def get_results(self):
        """Readonly field; explicitly returns no changes."""
        return {}

class TextField(Field):
    """A single-line field for editing a text property."""
    EXPAND = True
    def __init__(self, field, items, label):
        Field.__init__(self, field, items, label)
        self.widget = widgetset.TextEntry()
        self.widget.set_text(self.common_value or "")

    def get_value(self):
        value = self.widget.get_text()
        return value

class LongTextField(Field):
    """A multi-line field for editing a text property."""
    def __init__(self, field, items, label):
        Field.__init__(self, field, items, label)
        self.textbox = widgetset.MultilineTextEntry()
        self.textbox.set_text(self.common_value or "")
        self.widget = widgetset.Scroller(False, True)
        self.widget.set_has_borders(True)
        self.widget.set_size_request(250, 130)
        self.widget.add(self.textbox)

    def get_value(self):
        value = self.textbox.get_text()
        return value

class NumberField(Field):
    """A single-line text field accepting arbitrary integer values."""
    def __init__(self, field, items, label, width):
        Field.__init__(self, field, items, label)
        self.widget = widgetset.NumberEntry()
        self.widget.set_width(width)
        self.widget.set_max_length(width)
        value = self.common_value or ""
        self.widget.set_text(str(value))

    def get_value(self):
        value = self.widget.get_text()
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            logging.error("non-digit in numeric field: %s", repr(value))
            raise

class OptionsField(Field):
    """A drop-down field with text options."""
    def __init__(self, field, items, label, option_map):
        Field.__init__(self, field, items, label)
        labels = dict(option_map)
        labels['_mixed'] = _("(mixed)")
        self.options = [option[0] for option in option_map]
        if self.mixed_values:
            self.options.insert(0, '_mixed')
        option_labels = (labels[option] for option in self.options)
        self.widget = widgetset.OptionMenu(option_labels)
        self.widget.set_width(134)
        if self.common_value is not None:
            self.widget.set_selected(self.options.index(self.common_value))

    def get_value(self):
        return self.options[self.widget.get_selected()]

class RatingField(OptionsField):
    """A field for setting or unsetting ratings."""
    def __init__(self, items):
        options = [(rating, unicode(rating)) for rating in xrange(1, 6)]
        options.insert(0, (None, _("None")))
        OptionsField.__init__(self, 'rating', items, _("Rating"), options)

class ThumbnailField(DialogOwnerMixin, Field):
    """Displays any available cover art or thumbnail. Allows selection of a new
    cover art file.
    """
    TITLE = _("Choose a thumbnail file")
    DIALOG = widgetset.FileOpenDialog
    def __init__(self, items, label):
        Field.__init__(self, 'cover_art', items, label)
        DialogOwnerMixin.__init__(self, self.DIALOG, self.TITLE)
        path = self.common_value
        if path is None:
            if self.mixed_values:
                path = resources.path('images/thumb-mixed.png')
            else:
                path = resources.path('images/thumb-none.png')
        self.widget = widgetset.ClickableImageButton(path, 134, 134)
        self.widget.connect('clicked', self.show_dialog)

    def _value_filter(self, value, item):
        if value is not None:
            return value
        elif item.thumbnail is not None:
            base = os.path.basename(item.thumbnail)
            if not base.startswith('thumb-default-'):
                return item.thumbnail
        return None

class PathField(DialogOwnerMixin, Field):
    """A field for choosing the location for a file. Becomes a
    SingleFilePathField or MultipleFilePathField, as appropriate.
    """
    DIALOG = NotImplemented
    TITLE = NotImplemented

    def __new__(cls, field, items, label):
        if cls != PathField:
            return Field.__new__(cls, field, items, label)
        if len(items) > 1:
            return MultipleFilePathField(field, items, label)
        else:
            return SingleFilePathField(field, items, label)

    def __init__(self, field, items, label):
        Field.__init__(self, field, items, label)
        DialogOwnerMixin.__init__(self, self.DIALOG, self.TITLE,
                                  default=self.common_value)
        label = widgetset.Label(self.common_value)
        self.widget = widgetset.Scroller(True, False)
        self.widget.set_has_borders(False)
        self.widget.add(label)
        if label.get_width() > 440:
            height = 50
        else:
            height = 25
        # have to set height and width or gtk will make it very small
        self.widget.set_size_request(440, height)
        self.extra.append(self._make_button())

    def _make_button(self):
        button = widgetset.Button(_("Move"))
        button.connect('clicked', self.show_dialog)
        return button

class SingleFilePathField(PathField):
    """A field for choosing a file."""
    TITLE = _("Choose location for file")
    DIALOG = widgetset.FileSaveDialog

class MultipleFilePathField(PathField):
    """A field for choosing a directory."""
    TITLE = "Choose destination directory"
    DIALOG = widgetset.DirectorySelectDialog

    def _value_filter(self, value, item):
        """For a MultipleFile dialog, the original value is the path directly
        containing all of the items, if any.
        """
        return os.path.dirname(value) + os.path.sep

class MultifieldRow(object):
    """A composite field."""
    def __init__(self, *fields):
        self.box = widgetset.HBox()
        self.fields = list(fields)
        for field in self.fields[1:]:
            field.set_inside()
        for field in self.fields[:-1]:
            self.box.pack_start(field.get_box())
        self.box.pack_end(self.fields[-1].get_box())

    def get_box(self):
        """Return a widget containing all child widgets."""
        return self.box 
    
    def get_results(self):
        """Returns a changes map containing all child fields' changes."""
        results = {}
        for field in self.fields:
            results.update(field.get_results())
        return results

class ItemEditDialog(MainDialog):
    """Dialog to edit the metadata of one or more items."""
    def __init__(self):
        MainDialog.__init__(self, _('Edit Item'))
        self.items = set()
        self.results = {}
        self.fields = []

    def add_item(self, iteminfo):
        """Add an item to the set of items to be edited with this dialog."""
        self.items.add(iteminfo)

    def _pack_top(self, widget):
        """Pack the top row into the VBox."""
        items = len(self.items)
        if items > 1:
            # text1 is included because ngettext requires text1 to have all the
            # same placeholders as text2; it won't be used
            text = ngettext("%(items)d", "%(items)d items selected to edit",
                   items, {'items':items})
            label = widgetset.Label(text)
            label.set_bold(True)
            widget.pack_start(widgetutil.pad(label, top=20, bottom=3))

            text = _("To change a field for all the selected items, check the "
                     "checkbox next to the field you'd like to change.")
            label = widgetset.Label(text)
            label.set_size(widgetconst.SIZE_SMALL)
            widget.pack_start(widgetutil.pad(label, bottom=20, left=20, right=20))

    def _pack_left(self, vbox):
        """Pack the left column into the middle HBox of the main VBox."""
        widget = widgetset.VBox()
        fields = []
        fields.append(TextField('name', self.items, _("Name")))
        fields.append(TextField('artist', self.items, _("Artist")))
        fields.append(TextField('album', self.items, _("Album")))
        fields.append(TextField('genre', self.items, _("Genre")))
        fields.append(MultifieldRow(
            NumberField('track', self.items, _("Track"), width=2),
            NumberField('album_tracks', self.items, _("of"), width=2),
            NumberField('year', self.items, _("Year"), width=4),
        ))
        fields.append(LongTextField('description', self.items, _("About")))
        for field in fields:
            self.fields.append(field)
            widget.pack_start(field.get_box(), padding=5)
        vbox.pack_start(widget)

    def _pack_right(self, vbox):
        """Pack the right column into the middle HBox of the main VBox."""
        widget = widgetset.VBox()
        fields = []
        fields.append(RatingField(self.items))
        fields.append(OptionsField('file_type', self.items, _("Type"), [
            (u'audio', _("Audio")),
            (u'video', _("Video")),
            (u'other', _("Other"))
        ]))
        fields.append(DisplayField('size', self.items, _("Size"),
            displaytext.size_string))
        fields.append(ThumbnailField(self.items, _("Art")))
        for field in fields:
            field.set_right()
            self.fields.append(field)
        for field in fields[:-1]:
            widget.pack_start(field.get_box(), padding=5)
        widget.pack_end(fields[-1].get_box())
        vbox.pack_end(widget)

    def _pack_bottom(self, widget):
        """Pack the bottom row into the VBox."""
        fields = []
        fields.append(PathField('video_path', self.items, _("Path")))
        widget.pack_start(widgetutil.pad(widgetset.HLine(), top=25, bottom=10,
            left=15, right=15))
        for field in fields:
            widget.pack_start(field.get_box())
        widget.pack_start(widgetutil.pad(widgetset.HLine(), top=10, bottom=25,
            left=15, right=15))
        buttons = widgetset.HBox()
        cancel = widgetset.Button(BUTTON_CANCEL.text, width=75)
        ok = widgetset.Button(BUTTON_OK.text, width=75)
        buttons.pack_start(widgetutil.pad(cancel, left=15))
        buttons.pack_end(widgetutil.pad(ok, right=15))
        cancel.connect('clicked', self._on_button, BUTTON_CANCEL)
        ok.connect('clicked', self._on_button, BUTTON_OK)
        widget.pack_end(buttons)

    def _pack_middle(self, widget):
        middle = widgetset.HBox()
        self._pack_left(middle)
        self._pack_right(middle)
        widget.pack_start(middle)

    def _on_button(self, widget, button):
        """OK or Cancel has been pressed. Save changes, if OK; then close."""
        if button == BUTTON_OK:
            for field in self.fields:
                self.results.update(field.get_results())
        self.destroy()

    def run(self):
        """Displays the item edit dialog until the user presses OK or Cancel.

        Returns a dict of new name -> value, including only changed values.
        """
        super(ItemEditDialog, self).run()
        logging.debug(self.results)
        return self.results

    def build_content(self):
        vbox = widgetset.VBox()
        self._pack_top(vbox)
        self._pack_middle(vbox)
        self._pack_bottom(vbox)
        return vbox
