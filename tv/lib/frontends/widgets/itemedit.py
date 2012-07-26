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

import logging
import os

from miro import displaytext
from miro.gtcache import gettext as _
from miro.gtcache import ngettext
from miro.plat import resources
from miro.plat.frontends.widgets import widgetset
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
        if default:
            self._dialog.set_path(default)
        self._make_dialog()

    def _make_dialog(self):
        """Create and return a dialog object."""
        return self._dialog_class(self._title)

    def show_dialog(self, *_args):
        """Usually should be connected to some kind of button's click event.
        Accepts and discards an arbitrary number of arguments, so that it can be
        connected to any signal.
        """
        self._dialog.run()
        self._value = self._dialog.get_path()
        self._dialog.destroy()
        self.on_dialog_close(self._value)
        # prepare for the chooser to be opened again:
        self._dialog = self._make_dialog()

    def get_value(self):
        """Returns the value set by the dialog, or None if the dialog was
        canceled.
        """
        return self._value

    def on_dialog_close(self, _value):
        """Override to react to newly-set values."""
        pass

class Field(object):
    """A metadata property.

    :param field: the attribute of each item tied to this field
    :param items: the set of items potentially being edited
    :param label: text to display to the left of the field
    :param readonly: Field cannot be edited
    :param multiple: keyword for common value function
    """
    HAS_MIXED_STATE=False
    def __init__(self, field, items, label, readonly=False, multiple=None):
        self.mixed_values = False
        if multiple is None:
            self.common_value = self._find_common_value(field, iter(items))
        elif multiple == 'sum':
            self.common_value = sum(getattr(item, field) for item in items)
        self.field = field
        self.label = widgetset.Label(label)
        self.label_width = 50
        self.extra = []
        self.inside = False
        self.right = False
        self.widget = NotImplemented
        self.read_only = readonly
        if not readonly and len(items) > 1 and not self.HAS_MIXED_STATE:
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

    # TODO: calculate per-column label widths automatically
    def set_label_width(self, width):
        self.label_width = width

    def get_box(self, partial=False):
        """Return the displayable widget for this field.
        
        :param partial: set if this is not the last field in its row
        """
        box = widgetset.HBox()
        if self.inside:
            # not aligned with anything, close to its widget, on the right
            left, right = 4, 5
        elif self.right:
            # if it's in the right column, it's right-aligned
            pad = self.label_width - self.label.get_width()
            pad = max(pad, 0)
            left, right = pad, 15
        else:
            # ordinary left-aligned left column field
            pad = self.label_width - self.label.get_width()
            pad = max(pad, 0)
            left, right = 25, pad
        label_alignment = widgetutil.align_top(self.label,
                          right_pad=right, left_pad=left, top_pad=5)
        box.pack_start(label_alignment)
        packables = [self.widget]
        packables.extend(self.extra)
        for packable in packables[:-1]:
            box.pack_start(packable, expand=True)
        if partial:
            parts_right_pad = 4
        else:
            parts_right_pad = 20
        if self.checkbox:
            right_pad = 12
        else:
            right_pad = parts_right_pad
        last = widgetutil.pad(packables[-1], right=right_pad)
        box.pack_start(last, expand=True)
        if self.checkbox:
            right = parts_right_pad
            checkbox_alignment = widgetutil.align_top(self.checkbox,
                                 top_pad=2, right_pad=right)
            box.pack_end(checkbox_alignment)
        return box

    @classmethod
    def _value_filter(cls, value, _item):
        """Function to be applied to all items' original values before looking
        for a common value. Noop for most fields.
        """
        return value

    def _find_common_value(self, field, items):
        """Return the value of field that all items have in common, or None."""
        values = (self._value_filter(getattr(item, field), item) for item in items)
        common = values.next()
        if all(value == common for value in values):
            return common
        else:
            self.mixed_values = True
            return None

    def get_results(self):
        """Return a map of {field: new_value} for any changes."""
        if self.read_only or (self.checkbox and not self.checkbox.get_checked()):
            # field is read only, or field has a checkbox because selection is
            # multiple and checkbox is unchecked
            return {}
        new_value = self.get_value()
        if not self.mixed_values and new_value == self.common_value:
            # nothing has been changed
            return {}
        else:
            # this field has is enabled and has been changed
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
    def __init__(self, field, items, label, formatter, multiple=None):
        Field.__init__(self, field, items, label,
                       readonly=True, multiple=multiple)
        value = self.common_value
        if self.mixed_values:
            value = _("(mixed)")
        else:
            value = formatter(value)
        label = widgetset.Label(value)
        self.widget = widgetutil.pad(label, top=6)

class TextField(Field):
    """A single-line field for editing a text property."""
    def __init__(self, field, items, label):
        Field.__init__(self, field, items, label)
        self.widget = widgetset.TextEntry()
        self.widget.set_text(self.common_value or "")

    def get_value(self):
        return self.widget.get_text()

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
    def __init__(self, field, items, label, width=None):
        Field.__init__(self, field, items, label)
        self.widget = widgetset.NumberEntry()
        if width:
            self.widget.set_width(width)
            self.widget.set_max_length(width)
        value = self.common_value or ""
        # Ugh!  Convert to utf-8 or else decode may not work!
        if isinstance(value, unicode):
            value = value.encode('utf-8')
        try:
            value = str(value)
        except TypeError, ValueError:
            value = ''
        self.widget.set_text(value)

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
    HAS_MIXED_STATE=True
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

    def get_results(self):
        index = self.widget.get_selected()
        if index == 0 and self.mixed_values:
            #17450: never saved 'mixed' state
            return {}
        new_value = self.options[index]
        if not self.mixed_values and new_value == self.common_value:
            # nothing has been changed
            return {}
        else:
            # this field has is enabled and has been changed
            return {self.field: new_value}

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
    HAS_MIXED_STATE=True
    TITLE = _("Choose a thumbnail file")
    DIALOG = widgetset.FileOpenDialog
    def __init__(self, items, label):
        Field.__init__(self, 'cover_art', items, label)
        DialogOwnerMixin.__init__(self, self.DIALOG, self.TITLE)
        path = self.common_value

        vbox = widgetset.VBox(spacing=5)
        label = widgetset.Label()
        label.set_text(_('Click to choose image.'))
        label.set_color(widgetutil.css_to_color('#a9a9a9'))
        try:
            widget = widgetset.ClickableImageButton(path, 134, 134)
        except ValueError:
            # ValueError can happen if the image isn't valid and can't
            # be loaded
            path = resources.path('images/broken-image.gif')
            widget = widgetset.ClickableImageButton(path, 134, 134)

        widget.connect('clicked', self.show_dialog)

        vbox.pack_start(widget)
        vbox.pack_start(label)

        self.thumb_widget = widget
        self.widget = vbox

    @classmethod
    def _value_filter(cls, value, item):
        if value is not None:
            return value
        elif item.thumbnail is not None:
            base = os.path.basename(item.thumbnail)
            if not base.startswith('thumb-default-'):
                return item.thumbnail
        return None

    def on_dialog_close(self, new_path):
        """When the user closes the dialog, if a new path has been selected
        update the thumbnail.
        """
        # FIXME: there's no way to "unset" the thumbnail; it seems an
        # overreaction to Canceling the file chooser. Probably should have a "No
        # image" button in the dialog?
        if new_path:
            try:
                self.thumb_widget.set_path(new_path)
            except ValueError:
                pass

    def get_results(self):
        new_value = self.get_value()
        if new_value is None: # dialog not run, or canceled
            return {}
        else:
            return {self.field: new_value}

class PathField(DialogOwnerMixin, Field):
    """A field for choosing the location for a file. Becomes a
    SingleFilePathField or MultipleFilePathField, as appropriate.
    """
    DIALOG = NotImplemented
    TITLE = NotImplemented

    def __new__(cls, field, items, label, readonly=False):
        if len(items) > 1:
            return object.__new__(MultipleFilePathField, field, items, label, readonly)
        else:
            return object.__new__(SingleFilePathField, field, items, label, readonly)

    def __init__(self, field, items, label, readonly):
        Field.__init__(self, field, items, label, readonly=readonly)
        DialogOwnerMixin.__init__(self, self.DIALOG, self.TITLE,
                                  default=self.common_value)
        label = widgetset.Label(self.common_value or '')
        label.set_selectable(True)
        self.widget = widgetset.Scroller(True, False)
        self.widget.set_has_borders(False)
        self.widget.add(label)
        if label.get_width() > 440:
            height = 50
        else:
            height = 25
        # have to set height and width or gtk will make it very small
        self.widget.set_size_request(440, height)
        if not readonly:
            button = widgetset.Button(_("Move"))
            button.connect('clicked', self.show_dialog)
            self.extra.append(button)

class SingleFilePathField(PathField):
    """A field for choosing a file."""
    TITLE = _("Choose location for file")
    DIALOG = widgetset.FileSaveDialog

class MultipleFilePathField(PathField):
    """A field for choosing a directory."""
    TITLE = "Choose destination directory"
    DIALOG = widgetset.DirectorySelectDialog

    @classmethod
    def _value_filter(cls, value, _item):
        """For a MultipleFile dialog, the original value is the path directly
        containing all of the items, if any.
        """
        return os.path.dirname(value) + os.path.sep

class MultifieldRow(object):
    """A composite field."""
    def __init__(self, *fields):
        self.fields = list(fields)

    def get_box(self):
        """Return a widget containing all child widgets."""
        box = widgetset.HBox()
        for field in self.fields[1:]:
            field.set_inside()
        for field in self.fields[:-1]:
            box.pack_start(field.get_box(partial=True))
        box.pack_end(self.fields[-1].get_box())
        return box

    # XXX: MultifieldRows in the right column not currently supported
    # (dialog does not use them). As is, label would be aligned wrong.
    # Solution would probably be to implement set_right that enables
    # self.fields[0].set_right() in get_box

    def get_results(self):
        """Returns a changes map containing all child fields' changes."""
        results = {}
        for field in self.fields:
            results.update(field.get_results())
        return results

    def set_label_width(self, width):
        """Sets the label width of the leftmost child; this is the child with a
        label that has other labels to align with.
        """
        self.fields[0].set_label_width(width)

class DialogPanel(object):
    """A panel that is shown when it is the selected tab."""
    def __init__(self, items):
        self.items = items
        self.vbox = widgetset.VBox()
        self.fields = []

    def get_results(self):
        """Return the aggregated results of all this Panel's fields."""
        results = {}
        for field in self.fields:
            results.update(field.get_results())
        return results

class GeneralPanel(DialogPanel):
    """The (default) 'General' tab."""
    def __init__(self, items):
        DialogPanel.__init__(self, items)
        self._pack_middle()
        self._pack_bottom()

    # FIXME: resizing the dialog causes the padding between the two columns to
    # take up the slack.
    def _pack_middle(self):
        """Pack the columnated portion of the panel."""
        middle = widgetset.HBox()
        self._pack_left(middle)
        self._pack_right(middle)
        self.vbox.pack_start(middle)

    def _pack_left(self, vbox):
        """Pack the left column into the middle HBox of the main VBox."""
        widget = widgetset.VBox()
        left = []
        left.append(TextField('title', self.items, _("Name")))
        left.append(TextField('artist', self.items, _("Artist")))
        left.append(TextField('album', self.items, _("Album")))
        left.append(TextField('genre', self.items, _("Genre")))
        left.append(MultifieldRow(
            NumberField('track', self.items, _("Track"), width=2),
            NumberField('album_tracks', self.items, _("/"), width=2),
            NumberField('year', self.items, _("Year"), width=4),
        ))
        left.append(LongTextField('description', self.items, _("About")))
        for field in left:
            widget.pack_start(field.get_box(), padding=5)
        vbox.pack_start(widget)
        self.fields.extend(left)

    def _pack_right(self, vbox):
        """Pack the right column into the middle HBox of the main VBox."""
        widget = widgetset.VBox()
        right = []
        right.append(RatingField(self.items))
        right.append(OptionsField('file_type', self.items, _("Type"), [
            (u'audio', _("Music")),
            (u'video', _("Video")),
            (u'other', _("Misc"))
        ]))
        right.append(DisplayField('size', self.items, _("Size"),
            displaytext.size_string, multiple='sum'))
        right.append(ThumbnailField(self.items, _("Art")))
        for field in right:
            field.set_right()
        for field in right[:-1]:
            widget.pack_start(field.get_box(), padding=5)
        widget.pack_end(right[-1].get_box())
        vbox.pack_end(widget)
        self.fields.extend(right)

    def _pack_bottom(self):
        """Pack the bottom row into the VBox."""
        bottom = [PathField('filename', self.items, _("Path"), readonly=True)]
        self.vbox.pack_start(widgetutil.pad(widgetset.HLine(), top=25, bottom=10,
            left=15, right=15))
        for field in bottom:
            self.vbox.pack_start(field.get_box())
        self.vbox.pack_start(widgetutil.pad(widgetset.HLine(), top=10,
            left=15, right=15))
        self.fields.extend(bottom)

class VideoPanel(DialogPanel):
    """The 'Video' tab."""
    def __init__(self, items):
        DialogPanel.__init__(self, items)
        self.fields = [
            TextField('show', self.items, _("Show")),
            TextField('episode_id', self.items, _("Episode ID")),
            MultifieldRow(
                NumberField('season_number', self.items, _("Season Number"),
                    width=15),
                NumberField('episode_number', self.items, _("Episode Number"),
                    width=15),
            ),
            OptionsField('kind', self.items, _("Video Kind"), [
                # FIXME: changes here need also be applied in messages
                (None, u""),
                (u'movie', _("Movie")),
                (u'show', _("Show")),
                (u'clip', _("Clip")),
                (u'podcast', _("Podcast")),
            ]),
        ]
        self.vbox = widgetset.VBox()
        for field in self.fields:
            field.set_label_width(120)
            self.vbox.pack_start(field.get_box(), padding=5)

class ToggleButtonBackground(widgetset.Background):
    """Gradiated background for an individual ToggleButton."""
    def __init__(self, left_edge, right_edge):
        widgetset.Background.__init__(self)
        self.active = False
        self.left_edge = left_edge
        self.right_edge = right_edge
        self.surface = widgetutil.ThreeImageSurface()

    def draw(self, context, _layout):
        active = self.active and 'active' or 'inactive'
        left, center, right = 'left', 'center', 'right'
        # visually correct images for more than 2 options not implemented
        if not self.right_edge:
            right = center
        if not self.left_edge:
            left = center
        images = (
            widgetutil.make_surface('toggle-button-{active}_{part}'.format(
                active=active,
                part=part,
            )) for part in (left, center, right))
        self.surface.set_images(*images)
        self.surface.draw(context, 0, 0, context.width)

class ToggleButton(widgetset.CustomButton):
    """Button to switch between tabs."""
    COLORS = {
        True: widgetutil.WHITE,
        False: widgetutil.BLACK,
    }
    def __init__(self, text, left_edge):
        widgetset.CustomButton.__init__(self)
        self.text = text
        self.background = ToggleButtonBackground(left_edge, True)
        self._width = None
        self._height = 24
        self.selected = False
        self.set_can_focus(False)

    def set_selected(self, selected):
        """Set whether this button is the selected button."""
        self.background.active = selected
        changed = self.selected != selected
        if changed:
            self.selected = selected
            self.queue_redraw()

    def set_right_edge(self, right_edge):
        """Set whether this button is the rightmost in the row."""
        self.background.right_edge = right_edge

    def set_left_edge(self, left_edge):
        """Set whether this button is the leftmost in the row."""
        self.background.left_edge = left_edge

    def draw(self, context, layout):
        self.background.draw(context, layout)
        layout.set_font(0.75)
        layout.set_text_color(ToggleButton.COLORS[self.selected])
        textbox = layout.textbox(self.text)
        size = textbox.get_size()
        x = (context.width - size[0]) // 2
        y = (context.height - size[1]) // 2
        textbox.draw(context, x, y, size[0], size[1])

    def size_request(self, layout):
        if not self._width:
            layout.set_font(0.75)
            textbox = layout.textbox(self.text)
            self._width = textbox.get_size()[0] + 50
        return self._width, self._height

class Toggler(widgetset.HBox):
    """Horizontal row of custom pick-one buttons."""
    def __init__(self):
        widgetset.HBox.__init__(self)
        self.create_signal('choose')
        self.selected = None
        self.last = None
        self.buttons = {}

    def add_option(self, option, text):
        """Add a new option button."""
        if self.last:
            self.buttons[self.last].set_right_edge(False)
        left_edge = not self.last
        button = ToggleButton(text, left_edge)
        self.buttons[option] = button
        self.pack_start(button)
        self.last = option
        button.connect('clicked', self.on_choose, option)

    def on_choose(self, _widget, option):
        """Signal from widget; update widget and send up."""
        self.choose(option)
        self.emit('choose', option)

    def choose(self, option):
        """Visually select the specified option."""
        if self.selected:
            self.buttons[self.selected].set_selected(False)
        self.selected = option
        self.buttons[self.selected].set_selected(True)

class ItemEditDialog(widgetset.Dialog):
    """Dialog to edit the metadata of one or more items."""
    def __init__(self):
        widgetset.Dialog.__init__(self, _('Edit Item'))
        self.items = set()
        self.results = {}
        self.vbox = widgetset.VBox()
        self.panels = {}
        self.content_panel = widgetutil.WidgetHolder()
        self.toggler = Toggler()
        self.toggler.connect('choose', self.on_choose_panel)

    def add_item(self, iteminfo):
        """Add an item to the set of items to be edited with this dialog."""
        self.items.add(iteminfo)

    def _pack_top(self):
        """Pack the top row into the VBox; these components are visible in all
        panels.
        """
        self.vbox.pack_start(widgetutil.align_center(self.toggler, top_pad=10))
        items = len(self.items)
        if items > 1:
            # text1 is included because ngettext requires text1 to have all the
            # same placeholders as text2; it won't be used
            text = ngettext("%(items)d", "%(items)d items selected to edit",
                   items, {'items':items})
            label = widgetset.Label(text)
            label.set_bold(True)
            self.vbox.pack_start(widgetutil.align_center(label,
                top_pad=10, bottom_pad=3))

            text = _("To change a field for all the selected items, check the "
                     "checkbox next to the field you'd like to change.")
            label = widgetset.Label(text)
            label.set_size(widgetconst.SIZE_SMALL)
            self.vbox.pack_start(
                widgetutil.align_center(label, bottom_pad=20))

    def _pack_bottom(self):
        """Pack the bottom row into the VBox; these components are visible in
        all panels.
        """
        buttons = widgetset.HBox()
        cancel_button = widgetset.Button(BUTTON_CANCEL.text, width=75)
        ok_button = widgetset.Button(BUTTON_OK.text, width=75)
        buttons.pack_end(ok_button)
        buttons.pack_end(cancel_button)
        cancel_button.connect('clicked', self._on_button, BUTTON_CANCEL)
        ok_button.connect('clicked', self._on_button, BUTTON_OK)
        # FIXME: if we pack_end the buttons hbox, there are no buttons after
        # switching to the Video panel on OS X. This is a bug in something.
        self.vbox.pack_start(widgetutil.pad(buttons, top=15, bottom=15,
            left=15, right=15))

    def _on_button(self, _widget, button):
        """OK or Cancel has been pressed. Save changes, if OK; then close."""
        if button == BUTTON_OK:
            for panel in self.panels.itervalues():
                self.results.update(panel.get_results())
        self.destroy()

    def run(self):
        """Displays the item edit dialog until the user presses OK or Cancel.

        Returns a dict of new name -> value, including only changed values.
        """
        super(ItemEditDialog, self).run()
        logging.debug(self.results)
        # results will be set by on_button
        return self.results

    def _add_panel(self, label, name, content):
        """Add a potentially visible panel"""
        self.panels[name] = content
        self.toggler.add_option(name, label)

    def set_width_from_panels(self):
        """Set the min-width for our panels.

        We set the min-width to the width of the biggest panel, to avoid
        things moving too much when the user switches between them
        """
        max_width = -1
        for panel in self.panels.values():
            max_width = max(max_width, panel.vbox.get_size_request()[0])
        self.content_panel.set_size_request(max_width, -1)

    def on_choose_panel(self, _toggler, name):
        self.content_panel.set(self.panels[name].vbox)

    def build_content(self):
        """Called by parent in run(); returns a VBox"""
        self.items = frozenset(self.items)
        self._pack_top()
        self.vbox.pack_start(self.content_panel)
        self._add_panel(_("General"), 'general', GeneralPanel(self.items))
        self._add_panel(_("Video"), 'video', VideoPanel(self.items))
        self._pack_bottom()
        self.set_width_from_panels()
        self.toggler.choose('general')
        self.content_panel.set(self.panels['general'].vbox)
        return self.vbox
