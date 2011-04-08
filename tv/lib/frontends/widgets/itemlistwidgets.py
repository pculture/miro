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

"""itemlistwidgets.py -- Widgets to display lists of items

itemlist, itemlistcontroller and itemlistwidgets work together using
the MVC pattern.  itemlist handles the Model, itemlistwidgets handles
the View and itemlistcontroller handles the Controller.

The classes inside this module are meant to be as dumb as possible.
They should only worry themselves about how things are displayed.  The
only thing they do in response to user input or other signals is to
forward those signals on.  It's the job of ItemListController
subclasses to handle the logic involved.
"""

import logging
import math

from miro import app
from miro import prefs
from miro import displaytext
from miro import util
from miro import eventloop
from miro.gtcache import gettext as _
from miro.gtcache import declarify
from miro.frontends.widgets import imagepool
from miro.frontends.widgets import style
from miro.frontends.widgets import widgetconst
from miro.frontends.widgets import widgetutil
from miro.frontends.widgets import segmented
from miro.frontends.widgets import separator
from miro.frontends.widgets.widgetstatestore import WidgetStateStore
from miro.plat import resources
from miro.plat.frontends.widgets import widgetset
from miro.plat.frontends.widgets import use_upside_down_sort
from miro.plat.utils import get_available_bytes_for_movies

class Toolbar(widgetset.Background):
    def draw(self, context, layout):
        context.move_to(0, 0.5)
        context.rel_line_to(context.width, 0)
        context.set_color((224.0 / 255, 224.0 / 255, 224.0 / 255))
        context.stroke()
        gradient = widgetset.Gradient(0, 1, 0, context.height)
        gradient.set_start_color((212.0 / 255, 212.0 / 255, 212.0 / 255))
        gradient.set_end_color((168.0 / 255, 168.0 / 255, 168.0 / 255))
        context.rectangle(0, 1, context.width, context.height)
        context.gradient_fill(gradient)

class Titlebar(Toolbar):
    def __init__(self):
        Toolbar.__init__(self)
        self.set_size_request(-1, 55)

class TogglerButton(widgetset.CustomButton):
    LEFT = 0
    RIGHT = 1
    def __init__(self, image_name, pos):
        widgetset.CustomButton.__init__(self)
        self.set_can_focus(False)
        self.state = 'normal'
        self._enabled = False
        self._pos = pos
        self.surface = imagepool.get_surface(
            resources.path('images/%s.png' % image_name))
        self.active_surface = imagepool.get_surface(
            resources.path('images/%s_active.png' % image_name))

    def do_size_request(self):
        return (max(self.surface.width, self.active_surface.width),
                max(self.surface.height, self.active_surface.height))

    def size_request(self, layout):
        return self.do_size_request()

    def set_pressed(self, pressed):
        self._enabled = pressed
        self.queue_redraw()

    def draw(self, context, layout):
        if self._enabled:
            surface = self.active_surface
        else:
            surface = self.surface
        # XXX Working on the basis of LEFT/RIGHT only does not allow toggles
        # with multiple states.
        w = int(surface.width)
        h = int(surface.height)
        y = 0
        if self._pos == TogglerButton.RIGHT:
            x = 0
        else:
            x = int(self.do_size_request()[0] - surface.width)
        surface.draw(context, x, y, w, h)

class ViewToggler(widgetset.HBox):
    def __init__(self):
        widgetset.HBox.__init__(self)
        self.create_signal('normal-view-clicked')
        self.create_signal('list-view-clicked')
        self.selected_view = WidgetStateStore.get_standard_view_type()
        self.togglers = dict()
        standard_view = WidgetStateStore.get_standard_view_type()
        list_view = WidgetStateStore.get_list_view_type()

        self.toggler_events = dict()

        self.toggler_events[standard_view] = 'normal-view-clicked'
        self.toggler_events[list_view] = 'list-view-clicked'

        self.togglers[standard_view] = TogglerButton('standard-view',
                                                     TogglerButton.LEFT)
        self.togglers[list_view]= TogglerButton('list-view',
                                                 TogglerButton.RIGHT)

        for t in self.togglers.values():
            t.connect('clicked', self.on_clicked)

        self.togglers[self.selected_view].set_pressed(True)
        self.pack_start(self.togglers[standard_view])
        self.pack_start(self.togglers[list_view])

    def size_request(self, layout):
        w = sum([widget.size_request()[0] for widget in self.togglers.values()])
        return w, 50 # want to make the titlebar higher

    def switch_to_view(self, view):
        if view is not self.selected_view:
            self.selected_view = view
            for key in self.togglers:
                enabled = key == self.selected_view
                self.togglers[key].set_pressed(enabled)

    def on_clicked(self, button):
        for key in self.togglers:
            if self.togglers[key] is button:
                self.emit(self.toggler_events[key])
                self.switch_to_view(key)
                break

class FilterButton(widgetset.CustomButton):

    SURFACE = widgetutil.ThreeImageSurface('filter')
    TEXT_SIZE = widgetutil.font_scale_from_osx_points(10)
    ON_COLOR = (1, 1, 1)
    OFF_COLOR = (0.247, 0.247, 0.247)

    def __init__(self, text, enabled=False):
        self.text = text
        self.enabled = enabled
        widgetset.CustomButton.__init__(self)
        self.set_can_focus(False)
        self.connect('clicked', self._on_clicked)

    def _textbox(self, layout):
        layout.set_font(self.TEXT_SIZE)
        return layout.textbox(self.text)

    def size_request(self, layout):
        width, height = [int(v) for v in self._textbox(layout).get_size()]
        return width + 20, max(self.SURFACE.height, height)

    def draw(self, context, layout):
        surface_y = (context.height - self.SURFACE.height) / 2
        if self.enabled:
            self.SURFACE.draw(context, 0, surface_y, context.width)
            layout.set_text_color(self.ON_COLOR)
        else:
            layout.set_text_color(self.OFF_COLOR)
        textbox = self._textbox(layout)
        text_width, text_height = textbox.get_size()
        text_x = (context.width - text_width) / 2
        text_y = (context.height - text_height) / 2 - 1
        textbox.draw(context, text_x, text_y, context.width, context.height)

    def set_enabled(self, enabled):
        if enabled != self.enabled:
            self.enabled = enabled
            self.queue_redraw()

    def _on_clicked(self, button):
        self.set_enabled(not self.enabled)

class BoxedIconDrawer(widgetset.DrawingArea):
    """Draws the icon for an item list."""
    def __init__(self, image):
        widgetset.DrawingArea.__init__(self)
        self.icon = widgetset.ImageSurface(image)

    def size_request(self, layout):
        return (41, 41)

    def draw(self, context, layout):
        widgetutil.draw_rounded_icon(context, self.icon, 0, 0, 41, 41,
                                     inset=1)
        context.set_line_width(1)
        # Draw the black inner border
        context.set_color((0, 0, 0), 0.16)
        widgetutil.round_rect(context, 1.5, 1.5, 38, 38, 3)
        context.stroke()
        # Draw the white outer border
        context.set_color((1, 1, 1), 0.76)
        widgetutil.round_rect(context, 0.5, 0.5, 40, 40, 3)
        context.stroke()

class ResumePlaybackButton(widgetset.CustomButton):
    FONT_SIZE = 0.8
    TEXT_PADDING_LEFT = 5
    TEXT_PADDING_RIGHT = 5
    MIN_TITLE_CHARS = 5

    def __init__(self):
        widgetset.CustomButton.__init__(self)
        self.set_can_focus(False)
        button_images = ('resume-playback-button.png',
                'titlebar-middle.png', 'titlebar-right.png')
        button_images_pressed = ('resume-playback-button-pressed.png',
                'titlebar-middle_active.png', 'titlebar-right_active.png')
        self.button_surfaces = [
                imagepool.get_surface(resources.path('images/%s' % i))
                for i in button_images
        ]
        self.button_surfaces_pressed = [
                imagepool.get_surface(resources.path('images/%s' % i))
                for i in button_images_pressed
        ]
        self.button_height = self.button_surfaces[0].height
        self.title_middle = imagepool.get_surface(resources.path(
            'images/resume-playback-title-middle.png'))
        self.title_right = imagepool.get_surface(resources.path(
            'images/resume-playback-title-right.png'))
        self.title = self.resume_time = None
        self.min_usable_width = 0

    def update(self, title, resume_time):
        self.title = title
        self.resume_time = resume_time
        self.queue_redraw()

    def _make_text(self, title, resume_time):
        if resume_time > 0:
            resume_text = displaytext.short_time_string(resume_time)
            return _("%(item)s at %(resumetime)s",
                    {"item": title, "resumetime": resume_text})
        else:
            return _("%(item)s", {"item": title})

    def make_button(self, layout_manager, pressed):
        layout_manager.set_font(self.FONT_SIZE)
        textbox = layout_manager.textbox(_("Resume"))
        if pressed:
            left, middle, right = self.button_surfaces_pressed
        else:
            left, middle, right = self.button_surfaces
        return widgetutil.ThreeImageTextSurface(textbox, left, middle, right)

    def non_text_width(self, button):
        return (button.width + self.TEXT_PADDING_LEFT +
                self.TEXT_PADDING_RIGHT)

    def size_request(self, layout_manager):
        # we want the button to dissapear when we get smaller than our min
        # size.  To do that, we calculate our min size, store it, but then
        # just return a 0 width
        layout_manager.set_font(self.FONT_SIZE)
        # request enough space to show at least a little text
        text = self._make_text("A" * self.MIN_TITLE_CHARS, 123)
        text_size = layout_manager.textbox(text).get_size()
        button = self.make_button(layout_manager, False)
        self.min_usable_width = text_size[0] + self.non_text_width(button)
        return (0, self.button_height)

    def do_size_allocated(self, width, height):
        self.set_disabled(width < self.min_usable_width)

    def draw(self, context, layout_manager):
        if self.get_disabled():
            return
        if self.title is None:
            return
        # make button on the left
        pressed = (self.state == 'pressed')
        left_button = self.make_button(layout_manager, pressed)
        non_text_width = self.non_text_width(left_button)
        # make textbox
        textbox = self.make_textbox(layout_manager, context.width -
            non_text_width)
        # size and layout things
        text_width, text_height = textbox.get_size()
        total_width = text_width + non_text_width
        text_y = (left_button.height - text_height) // 2
        text_x = left_button.width + self.TEXT_PADDING_LEFT
        # draw the title background, position it just under the right cap of
        # the left button so that the lines appear solid
        title_background_x = left_button.width - left_button.right.width
        title_middle_width = (total_width - title_background_x -
                self.title_right.width)
        self.title_middle.draw(context, title_background_x, 0,
                title_middle_width, self.title_middle.height)
        self.title_right.draw(context, total_width-self.title_right.width,
                0, self.title_right.width, self.title_right.height)
        # draw the button
        left_button.draw(context, 0, 0, left_button.width, left_button.height)
        # draw text
        textbox.draw(context, text_x, text_y, text_width, text_height)

    def make_textbox(self, layout_manager, max_width):
        layout_manager.set_font(self.FONT_SIZE)
        textbox = layout_manager.textbox(self._make_text(self.title,
            self.resume_time))
        if textbox.get_size()[0] <= max_width:
            return textbox
        # our title is to big to fit.  shrink it until it's small enough
        for cut_off_count in xrange(4, len(self.title)):
            title = self.title[:-cut_off_count] + '...'
            textbox = layout_manager.textbox(self._make_text(title,
                self.resume_time))
            if textbox.get_size()[0] <= max_width:
                return textbox
        # we can't fit the textbox in the space we have
        return None

class ItemListTitlebar(Titlebar):
    """Titlebar for feeds, playlists and static tabs that display
    items.

    :signal list-view-clicked: (widget) User requested to switch to
        list view
    :signal normal-view-clicked: (widget) User requested to switch to
        normal view
    :signal search-changed: (self, search_text) -- The value in the
        search box changed and the items listed should be filtered
    """
    def __init__(self):
        Titlebar.__init__(self)
        self.create_signal('resume-playing')
        hbox = widgetset.HBox()
        self.add(hbox)
        # Pack stuff to the right
        start = self._build_titlebar_start()
        if start:
            hbox.pack_start(start)
        self.filter_box = widgetset.HBox(spacing=10)
        hbox.pack_start(widgetutil.align_middle(self.filter_box, left_pad=10))
        extra = self._build_titlebar_extra()
        if extra:
            if isinstance(extra, list):
                [hbox.pack_end(w) for w in extra[::-1]]
            else:
                hbox.pack_end(extra)
        toggle = self._build_view_toggle()
        if toggle:
            hbox.pack_end(widgetutil.align_middle(toggle))
        self.resume_button = ResumePlaybackButton()
        self.resume_button.connect('clicked', self._on_resume_button_clicked)
        self.resume_button_holder = widgetutil.HideableWidget(
                widgetutil.pad(self.resume_button, left=10))
        hbox.pack_end(widgetutil.align_middle(self.resume_button_holder),
                expand=True)

        self.filters = {}

    def update_resume_button(self, text, resume_time):
        """Update the resume button text.

        If text is None, we will hide the resume button.  Otherwise we
        will show the button and have it display text.
        """
        if text is None:
            self.resume_button_holder.hide()
        else:
            self.resume_button.update(text, resume_time)
            self.resume_button_holder.show()

    def _build_titlebar_start(self):
        """Builds the widgets to place at the start of the titlebar.
        """
        return None

    def _build_titlebar_extra(self):
        """Builds the widget(s) to place to the right of the title.

        By default we add a search box, but subclasses can override
        this.
        """
        self.create_signal('search-changed')
        self.searchbox = widgetset.SearchTextEntry()
        self.searchbox.connect('activate', self._on_search_activate)
        self.searchbox.connect('changed', self._on_search_changed)
        return widgetutil.align_middle(self.searchbox, right_pad=14,
                                       left_pad=15)

    def _build_view_toggle(self):
        self.create_signal('list-view-clicked')
        self.create_signal('normal-view-clicked')
        self.view_toggler = ViewToggler()
        self.view_toggler.connect('list-view-clicked', self._on_list_clicked)
        self.view_toggler.connect('normal-view-clicked',
                                  self._on_normal_clicked)
        return self.view_toggler

    def _on_resume_button_clicked(self, button):
        self.emit('resume-playing')

    def _on_search_activate(self, searchbox):
        # User hit enter in the searchbox, focus the item list.
        app.item_list_controller_manager.focus_view()

    def _on_search_changed(self, searchbox):
        self.emit('search-changed', searchbox.get_text())

    def _on_normal_clicked(self, button):
        self.emit('normal-view-clicked')

    def _on_list_clicked(self, button):
        self.emit('list-view-clicked')

    def switch_to_view(self, view):
        self.view_toggler.switch_to_view(view)

    def set_title(self, title):
        self.title_drawer = title
        self.title_drawer.queue_redraw()

    def set_search_text(self, text):
        self.searchbox.set_text(text)

    def start_editing_search(self, text):
        self.searchbox.start_editing(text)

    def toggle_filter(self, filter_):
        # implemented by subclasses
        pass

    def add_filter(self, name, signal_name, signal_param, label):
        if not self.filters:
            enabled = True
        else:
            enabled = False
        self.create_signal(signal_name)
        def callback(button):
            self.emit(signal_name, signal_param)
        button = FilterButton(label, enabled=enabled)
        button.connect('clicked', callback)
        self.filter_box.pack_start(button)
        self.filters[name] = button
        return button

class FolderContentsTitlebar(ItemListTitlebar):
    def _build_titlebar_start(self):
        self.create_signal('podcast-clicked')
        self.podcast_button = widgetutil.TitlebarButton(_('Back to podcast'))
        self.podcast_button.connect('clicked', self._on_podcast_clicked)
        return widgetutil.align_middle(self.podcast_button, left_pad=20)

    def _on_podcast_clicked(self, button):
        self.emit('podcast-clicked', button)

class ConvertingTitlebar(ItemListTitlebar):
    """
    Titlebar for conversion display.

    :signal stop-all: (self) The stop all button was clicked.
    :signal reveal: (self) The reveal button was clicked.
    :signal clear-finished: (self) The clear finished button was clicked.
    """
    def _build_titlebar_start(self):
        self.create_signal('stop-all')
        self.create_signal('reveal')
        self.create_signal('clear-finished')

        stop_all_button = widgetutil.TitlebarButton(_('Stop All Conversions'))
        stop_all_button.disable()
        stop_all_button.connect('clicked', self._on_stop_all_clicked)
        self.stop_all_button = stop_all_button

        reveal_button = widgetutil.TitlebarButton(_('Show Conversion Folder'))
        reveal_button.connect('clicked', self._on_reveal_clicked)
        self.reveal_button = reveal_button

        clear_finished_button = widgetutil.TitlebarButton(
                _('Clear Finished Conversions'))
        clear_finished_button.connect('clicked',
                self._on_clear_finished_clicked)
        self.clear_finished_button = clear_finished_button

        h = widgetset.HBox(spacing=20)
        h.pack_start(widgetutil.align_middle(stop_all_button, left_pad=25))
        h.pack_start(widgetutil.align_middle(reveal_button))
        h.pack_start(widgetutil.align_middle(clear_finished_button))

        return h

    # Don't build anything special.
    def _build_titlebar_extra(self):
        return None

    # Cannot toggle view for converting controller.
    def _build_view_toggle(self):
        return None

    def _on_stop_all_clicked(self, button):
        self.emit('stop-all')

    def _on_reveal_clicked(self, button):
        self.emit('reveal')

    def _on_clear_finished_clicked(self, button):
        self.emit('clear-finished')

    def enable_stop_all(self, enable):
        if enable:
            self.stop_all_button.enable()
        else:
            self.stop_all_button.disable()

    def enable_clear_finished(self, enable):
        if enable:
            self.clear_finished_button.enable()
        else:
            self.clear_finished_button.disable()

    
class SearchTitlebar(ItemListTitlebar):
    """
    Titlebar for views which can save their view as a podcast.

    :signal save-search: (self, search_text) The current search
        should be saved as a search channel.
    """
    def _build_titlebar_start(self):
        self.create_signal('save-search')
        button = widgetutil.TitlebarButton(self.save_search_title())
        button.connect('clicked', self._on_save_search)
        self.save_button = widgetutil.HideableWidget(
                widgetutil.pad(button, right=20))
        return widgetutil.align_middle(self.save_button, left_pad=20)

    def save_search_title(self):
        return _('Save as Podcast')

    def get_search_text(self):
        return self.searchbox.get_text()

    def _on_save_search(self, button):
        self.emit('save-search', self.get_search_text())

    def _on_search_changed(self, searchbox):
        if searchbox.get_text() == '':
            self.save_button.hide()
        else:
            self.save_button.show()
        self.emit('search-changed', searchbox.get_text())

class VideoAudioFilterMixin(object):
    def __init__(self):
        view_video = WidgetStateStore.get_view_video_filter()
        view_audio = WidgetStateStore.get_view_audio_filter()
        self.add_filter('view-video', 'toggle-filter', view_video,
                        _('Video'))
        self.add_filter('view-audio', 'toggle-filter', view_audio,
                        _('Audio'))

    def toggle_filter(self):
        view_video = WidgetStateStore.is_view_video_filter(self.filter)
        view_audio = WidgetStateStore.is_view_audio_filter(self.filter)
        self.filters['view-video'].set_enabled(view_video)
        self.filters['view-audio'].set_enabled(view_audio)

class UnplayedFilterMixin(object):
    def __init__(self):
        unwatched = WidgetStateStore.get_unwatched_filter()
        self.add_filter('only-unplayed', 'toggle-filter', unwatched,
                        _('Unplayed'))

    def toggle_filter(self):
        unwatched = WidgetStateStore.has_unwatched_filter(self.filter)
        self.filters['only-unplayed'].set_enabled(unwatched)

class DownloadedUnplayedFilterMixin(UnplayedFilterMixin):
    def __init__(self):
        downloaded = WidgetStateStore.get_downloaded_filter()
        self.add_filter('only-downloaded', 'toggle-filter', downloaded,
                        _('Downloaded'))
        UnplayedFilterMixin.__init__(self)

    def toggle_filter(self):
        downloaded = WidgetStateStore.has_downloaded_filter(self.filter)
        self.filters['only-downloaded'].set_enabled(downloaded)
        UnplayedFilterMixin.toggle_filter(self)

class FilteredTitlebar(ItemListTitlebar):
    def __init__(self):
        ItemListTitlebar.__init__(self)
        # this "All" is different than other "All"s in the codebase, so it
        # needs to be clarified
        view_all = WidgetStateStore.get_view_all_filter()
        self.add_filter('view-all', 'toggle-filter', view_all,
                         declarify(_('View|All')))
        self.filter = view_all

    def toggle_filter(self, filter_):
        self.filter = WidgetStateStore.toggle_filter(self.filter, filter_)
        view_all = WidgetStateStore.is_view_all_filter(self.filter)
        self.filters['view-all'].set_enabled(view_all)

class MediaTitlebar(SearchTitlebar, FilteredTitlebar):
    def save_search_title(self):
        return _('Save as playlist')

# Note that this is not related to VideoAudioFilterMixin.
# VideoAudioFilterMixin adds video and audio filtering, 
# while VideosTitlebar is the static video tab.
class VideosTitlebar(MediaTitlebar):
    def __init__(self):
        FilteredTitlebar.__init__(self)
        view_all = WidgetStateStore.get_view_all_filter()
        view_movies = WidgetStateStore.get_view_movies_filter()
        view_shows = WidgetStateStore.get_view_shows_filter()
        view_clips = WidgetStateStore.get_view_clips_filter()
        view_podcasts = WidgetStateStore.get_view_podcasts_filter()

        self.add_filter('view-movies', 'toggle-filter', view_movies,
                            _('Movies'))
        self.add_filter('view-shows', 'toggle-filter', view_shows,
                            _('Shows'))
        self.add_filter('view-clips', 'toggle-filter', view_clips,
                            _('Clips'))
        self.add_filter('view-podcasts', 'toggle-filter', view_podcasts,
                            _('Podcasts'))

    def toggle_filter(self, filter_):
        FilteredTitlebar.toggle_filter(self, filter_)
        view_movies = WidgetStateStore.is_view_movies_filter(self.filter)
        view_shows = WidgetStateStore.is_view_shows_filter(self.filter)
        view_clips = WidgetStateStore.is_view_clips_filter(self.filter)
        view_podcasts = WidgetStateStore.is_view_podcasts_filter(self.filter)
        self.filters['view-movies'].set_enabled(view_movies)
        self.filters['view-shows'].set_enabled(view_shows)
        self.filters['view-clips'].set_enabled(view_clips)
        self.filters['view-podcasts'].set_enabled(view_podcasts)

class MusicTitlebar(MediaTitlebar, UnplayedFilterMixin):
   def __init__(self):
        FilteredTitlebar.__init__(self)
        UnplayedFilterMixin.__init__(self)

   def toggle_filter(self, filter_):
       FilteredTitlebar.toggle_filter(self, filter_)
       UnplayedFilterMixin.toggle_filter(self)


class AllFeedsTitlebar(FilteredTitlebar, DownloadedUnplayedFilterMixin,
                       VideoAudioFilterMixin):
    def __init__(self):
        FilteredTitlebar.__init__(self)
        DownloadedUnplayedFilterMixin.__init__(self)
        VideoAudioFilterMixin.__init__(self)

    def toggle_filter(self, filter_):
        FilteredTitlebar.toggle_filter(self, filter_)
        DownloadedUnplayedFilterMixin.toggle_filter(self)
        VideoAudioFilterMixin.toggle_filter(self)

class ChannelTitlebar(SearchTitlebar, FilteredTitlebar,
                      DownloadedUnplayedFilterMixin):
    """Titlebar for a channel
    """
    def __init__(self):
        FilteredTitlebar.__init__(self)
        DownloadedUnplayedFilterMixin.__init__(self)

    def toggle_filter(self, filter_):
        FilteredTitlebar.toggle_filter(self, filter_)
        DownloadedUnplayedFilterMixin.toggle_filter(self)

class WatchedFolderTitlebar(FilteredTitlebar, VideoAudioFilterMixin):
    def __init__(self):
        FilteredTitlebar.__init__(self)
        unwatched = WidgetStateStore.get_unwatched_filter()
        self.add_filter('only-unplayed', 'toggle-filter', unwatched,
                        _('Unplayed'))
        VideoAudioFilterMixin.__init__(self)

    def toggle_filter(self, filter_):
        FilteredTitlebar.toggle_filter(self, filter_)
        downloaded = WidgetStateStore.has_downloaded_filter(self.filter)
        unwatched = WidgetStateStore.has_unwatched_filter(self.filter)
        if downloaded:
            # make sure 'All' is on
            self.filters['view-all'].set_enabled(downloaded)
        self.filters['only-unplayed'].set_enabled(unwatched)
        VideoAudioFilterMixin.toggle_filter(self)

class SearchListTitlebar(SearchTitlebar):
    """Titlebar for the search page.
    """
    def _on_search_activate(self, obj):
        app.search_manager.set_search_info(
            obj.selected_engine(), obj.get_text())
        app.search_manager.perform_search()

    def get_engine(self):
        return self.searchbox.selected_engine()

    def get_text(self):
        return self.searchbox.get_text()

    def set_search_engine(self, engine):
        self.searchbox.select_engine(engine)

    def _build_titlebar_extra(self):
        hbox = widgetset.HBox()
        self.create_signal('search-changed')
        self.searchbox = widgetset.VideoSearchTextEntry()
        w, h = self.searchbox.get_size_request()
        self.searchbox.set_size_request(200, h)
        self.searchbox.connect('validate', self._on_search_activate)
        self.searchbox.connect('changed', self._on_search_changed)
        hbox.pack_start(widgetutil.align_middle(self.searchbox, 0, 0, 15))

        return [widgetutil.align_middle(hbox, right_pad=14)]

class ItemView(widgetset.TableView):
    """TableView that displays a list of items."""
    def __init__(self, item_list, scroll_pos, selection):
        widgetset.TableView.__init__(self, item_list.model)

        self.item_list = item_list
        self.set_fixed_height(True)
        self.allow_multiple_select = True

        self.create_signal('scroll-position-changed')
        self.scroll_pos = scroll_pos
        self.set_scroll_position(scroll_pos)

        if selection is not None:
            self.set_selection_as_strings(selection)

    def on_undisplay(self):
        self.scroll_pos = self.get_scroll_position()
        if self.scroll_pos is not None:
            self.emit('scroll-position-changed', self.scroll_pos)

class SorterWidgetOwner(object):
    """Mixin for objects that need to handle a set of
    ascending/descending sort indicators.
    """
    def __init__(self):
        self.create_signal('sort-changed')

    def on_sorter_clicked(self, widget, sort_key):
        ascending = not (widget.get_sort_indicator_visible() and
                widget.get_sort_order_ascending())
        self.emit('sort-changed', sort_key, ascending)

    def change_sort_indicator(self, sort_key, ascending):
        for widget_sort_key, widget in self.sorter_widget_map.iteritems():
            if widget_sort_key == sort_key:
                widget.set_sort_order(ascending)
                widget.set_sort_indicator_visible(True)
            else:
                widget.set_sort_indicator_visible(False)

class ColumnRendererSet(object):
    """A set of potential columns for an ItemView"""
    def __init__(self):
        self._column_map = {}

    def add_renderer(self, name, renderer):
        self._column_map[name] = renderer

    def get(self, name):
        return self._column_map[name]

class ListViewColumnRendererSet(ColumnRendererSet):
    # FIXME: a unittest should verify that these exist for every possible field
    COLUMN_RENDERERS = {
        'state': style.StateCircleRenderer,
        'name': style.NameRenderer,
        'artist': style.ArtistRenderer,
        'album': style.AlbumRenderer,
        'track': style.TrackRenderer,
        'year': style.YearRenderer,
        'genre': style.GenreRenderer,
        'rating': style.RatingRenderer,
        'date': style.DateRenderer,
        'length': style.LengthRenderer,
        'status': style.StatusRenderer,
        'size': style.SizeRenderer,
        'feed-name': style.FeedNameRenderer,
        'eta': style.ETARenderer,
        'torrent-details': style.TorrentDetailsRenderer,
        'rate': style.DownloadRateRenderer,
        'date-added': style.DateAddedRenderer,
        'last-played': style.LastPlayedRenderer,
        'description': style.DescriptionRenderer,
        'drm': style.DRMRenderer,
        'file-type': style.FileTypeRenderer,
        'show': style.ShowRenderer,
        'kind': style.KindRenderer,
    }

    def __init__(self):
        ColumnRendererSet.__init__(self)
        for name, klass in self.COLUMN_RENDERERS.items():
            self.add_renderer(name, klass())

class StandardView(ItemView):
    """TableView that displays a list of items using the standard
    view.
    """
    BACKGROUND_COLOR = (0.05, 0.10, 0.15)

    draws_selection = False

    def __init__(self, item_list, scroll_pos, selection, item_renderer):
        ItemView.__init__(self, item_list, scroll_pos, selection)
        self.renderer = item_renderer
        self.column = widgetset.TableColumn('item', self.renderer)
        self.set_column_spacing(0)
        self.column.set_min_width(self.renderer.MIN_WIDTH)
        self.add_column(self.column)
        self.set_show_headers(False)
        self.set_auto_resizes(True)
        self.set_background_color(self.BACKGROUND_COLOR)

class ListView(ItemView, SorterWidgetOwner):
    """TableView that displays a list of items using the list view."""
    COLUMN_PADDING = 12
    def __init__(self, item_list, renderer_set,
            columns_enabled, column_widths, scroll_pos, selection):
        ItemView.__init__(self, item_list, scroll_pos, selection)
        SorterWidgetOwner.__init__(self)
        self.column_widths = {}
        self.create_signal('columns-enabled-changed')
        self.create_signal('column-widths-changed')
        self._column_name_to_column = {}
        self.sorter_widget_map = self._column_name_to_column
        self._column_by_label = {}
        self.columns_enabled = []
        self.set_show_headers(True)
        self.set_columns_draggable(True)
        self.set_column_spacing(self.COLUMN_PADDING)
        self.set_row_spacing(5)
        self.set_grid_lines(False, False)
        self.set_alternate_row_backgrounds(True)
        self.html_stripper = util.HTMLStripper()
        self.renderer_set = renderer_set
        self.update_columns(columns_enabled, column_widths)

    def _get_ui_state(self):
        if not self._set_initial_widths:
            return # don't save if view isn't set up
        order = []
        # FIXME: though identifying columns by their labels should always work,
        # it's really gross
        for name in (self._column_by_label[l] for l in self.get_columns()):
            order.append(name)
            self.column_widths[name] = int(
                self._column_name_to_column[name].get_width())
        assert set(self.columns_enabled) == set(order)
        self.columns_enabled = order

    def on_undisplay(self):
        self._get_ui_state()
        ItemView.on_undisplay(self)
        self.emit('column-widths-changed', self.column_widths)
        self.emit('columns-enabled-changed', self.columns_enabled)

    def get_tooltip(self, iter_, column):
        if ('name' in self._column_name_to_column and
                self._column_name_to_column['name'] == column):
            info = self.item_list.model[iter_][0]
            text, links = self.html_stripper.strip(info.description)
            if text:
                if len(text) > 1000:
                    text = text[:994] + ' [...]'
                return text

        elif ('state' in self._column_name_to_column and
                self._column_name_to_column['state'] is column):
            info = self.item_list.model[iter_][0]
            # this logic is replicated in style.StateCircleRenderer
            # with text from style.StatusRenderer
            if info.state == 'downloading':
                return _("Downloading")
            elif (info.downloaded and info.is_playable
                  and not info.video_watched):
                return _("Unplayed")
            elif (not info.item_viewed and not info.expiration_date
                  and not info.is_external):
                return _("Newly Available")
        return None

    def update_columns(self, new_columns, new_widths):
        assert set(new_columns).issubset(new_widths)
        old_columns = set(self.columns_enabled)
        self.columns_enabled = new_columns
        self.column_widths = new_widths
        for name in sorted(set(new_columns) - old_columns,
                key=new_columns.index):
            resizable = not name in widgetconst.NO_RESIZE_COLUMNS
            pad = not name in widgetconst.NO_PAD_COLUMNS
            if name == 'state':
                header = u''
            else:
                header = widgetconst.COLUMN_LABELS[name]
            renderer = self.renderer_set.get(name)
            self._make_column(header, renderer, name, resizable, pad)
            self._column_by_label[header] = name
        for name in old_columns - set(new_columns):
            column = self._column_name_to_column[name]
            index = self.columns.index(column)
            self.remove_column(index)
            del self._column_name_to_column[name]
        self._set_initial_widths = False

    def _make_column(self, header, renderer, column_name, resizable=True,
            pad=True):
        column = widgetset.TableColumn(header, renderer,
            SortBarButton(header, column=True))
        column.set_min_width(renderer.min_width)
        if resizable:
            column.set_resizable(True)
        if not pad:
            column.set_do_horizontal_padding(pad)
        if hasattr(renderer, 'right_aligned') and renderer.right_aligned:
            column.set_right_aligned(True)
        if column_name in widgetconst.NO_RESIZE_COLUMNS:
            self.column_widths[column_name] = renderer.min_width
            if pad:
                self.column_widths[column_name] += self.COLUMN_PADDING
            column.set_width(renderer.min_width)
        column.connect_weak('clicked', self.on_sorter_clicked, column_name)
        self._column_name_to_column[column_name] = column
        self.add_column(column)

    def get_renderer(self, column_name):
        return self._column_name_to_column[column_name].renderer

    def do_size_allocated(self, total_width, height):
        if self._set_initial_widths:
            return
        self._set_initial_widths = True

        available_width = self.width_for_columns(total_width)
        extra_width = available_width 

        total_weight = 0
        for name in self.columns_enabled:
            total_weight += widgetconst.COLUMN_WIDTH_WEIGHTS.get(name, 0)
            extra_width -= self.column_widths[name]

        rounded_off = 0 # carry forward rounded-off part of each value
        for name in self.columns_enabled:
            if total_weight:
                weight = (1.0 * widgetconst.COLUMN_WIDTH_WEIGHTS.get(name, 0) /
                    total_weight)
            else: # if no columns are weighted, all are weighted equally
                weight = 1.0 / len(self.columns_enabled)
            extra, rounded_off = divmod(extra_width * weight + rounded_off, 1)
            self.column_widths[name] += int(extra)
            self._column_name_to_column[name].set_width(self.column_widths[name])

class HideableSection(widgetutil.HideableWidget):
    """Widget that contains an ItemView, along with an expander to
    show/hide it.

    The label for a HideableSection expander is made up of 2 parts.
    The header is displayed first using a bold text, then the info is
    displayed using normal font.
    """

    def __init__(self, header_text, item_view):
        self.expander = widgetset.Expander(item_view)
        self.expander.set_expanded(False)
        widget = widgetutil.pad(self.expander, top=3, bottom=3, left=5)
        self._make_label(header_text)
        widgetutil.HideableWidget.__init__(self, widget)

    def set_info(self, text):
        self.info_label.set_text(text)

    def set_header(self, text):
        self.header_label.set_text(text)

    def expand(self):
        self.expander.set_expanded(True)

    def _make_label(self, header_text):
        hbox = widgetset.HBox()
        self.header_label = widgetset.Label(header_text)
        self.header_label.set_size(0.85)
        self.header_label.set_bold(True)
        self.header_label.set_color((0.27, 0.27, 0.27))
        hbox.pack_start(self.header_label)
        self.info_label = widgetset.Label("")
        self.info_label.set_size(0.85)
        self.info_label.set_color((0.72, 0.72, 0.72))
        hbox.pack_start(widgetutil.pad(self.info_label, left=7))
        self.expander.set_label(hbox)

class DownloadStatusToolbar(Toolbar):
    """Widget that shows free space and download and upload speed
    status.
    """

    def __init__(self):
        Toolbar.__init__(self)

        v = widgetset.VBox()

        sep = separator.HSeparator((0.85, 0.85, 0.85), (0.95, 0.95, 0.95))
        v.pack_start(sep)

        h = widgetset.HBox(spacing=5)

        self._free_disk_icon = widgetset.ImageDisplay(
            imagepool.get(resources.path('images/hard-drive.png')))

        h.pack_start(widgetutil.align_left(self._free_disk_icon,
                     top_pad=10, bottom_pad=10, left_pad=12))

        self._free_disk_label = widgetset.Label("")
        self._free_disk_label.set_size(widgetconst.SIZE_SMALL)

        h.pack_start(widgetutil.align_left(self._free_disk_label,
                     top_pad=10, bottom_pad=10, left_pad=3), expand=True)


        # Sigh.  We want to fix these sizes so they don't jump about
        # so reserve the maximum size for these things.  The upload
        # and download are both the same so we only need to
        # auto-detect for one.
        placeholder_bps = 1000 * 1024    # 1000 kb/s - not rounded 1 MB/s yet
        text_up = _("%(rate)s",
                    {"rate": displaytext.download_rate(placeholder_bps)})

        first_label = widgetset.Label("")
        first_label.set_size(widgetconst.SIZE_SMALL)

        # Now, auto-detect the size required.
        first_label.set_text(text_up)
        width, height = first_label.get_size_request()

        first_image = widgetutil.HideableWidget(widgetset.ImageDisplay(
                          widgetset.Image(resources.path('images/up.png'))))
        self._first_image = first_image
        h.pack_start(widgetutil.align_middle(widgetutil.align_right(
                     self._first_image)))

        # Don't forget to reset the label to blank after we are done
        # fiddling with it.
        first_label.set_text("")
        first_label.set_size_request(width, -1)
        self._first_label = first_label

        h.pack_start(widgetutil.align_middle(widgetutil.align_right(
                     self._first_label, right_pad=20)))

        second_image = widgetutil.HideableWidget(widgetset.ImageDisplay(
                           widgetset.Image(resources.path('images/down.png'))))
        self._second_image = second_image
        # NB: pad the top by 1px - Morgan reckons it looks better when
        # the icon is moved down by 1px.
        h.pack_start(widgetutil.align_middle(widgetutil.align_right(
                     self._second_image), top_pad=1))

        second_label = widgetset.Label("")
        second_label.set_size(widgetconst.SIZE_SMALL)
        second_label.set_size_request(width, -1)
        self._second_label = second_label

        h.pack_start(widgetutil.align_middle(widgetutil.align_right(
                     self._second_label, right_pad=20)))

        v.pack_start(h)
        self.add(v)

        app.frontend_config_watcher.connect('changed', self.on_config_change)

    def on_config_change(self, obj, key, value):
        if ((key == prefs.PRESERVE_X_GB_FREE.key
             or key == prefs.PRESERVE_DISK_SPACE.key)):
            self.update_free_space()

    def update_free_space(self):
        """Updates the free space text on the downloads tab.

        amount -- the total number of bytes free.
        """
        amount = get_available_bytes_for_movies()
        if app.config.get(prefs.PRESERVE_DISK_SPACE):
            available = (app.config.get(prefs.PRESERVE_X_GB_FREE) *
                         1024 * 1024 * 1024)
            available = amount - available

            if available < 0:
                available = available * -1.0
                text = _(
                    "%(available)s below downloads space limit (%(amount)s "
                    "free on disk)",
                    {"amount": displaytext.size_string(amount),
                     "available": displaytext.size_string(available)}
                )
            else:
                text = _(
                    "%(available)s free for downloads (%(amount)s free "
                    "on disk)",
                    {"amount": displaytext.size_string(amount),
                     "available": displaytext.size_string(available)}
                )
        else:
            text = _("%(amount)s free on disk",
                     {"amount": displaytext.size_string(amount)})
        self._free_disk_label.set_text(text)

    def update_rates(self, down_bps, up_bps):
        text_up = text_down = ''
        if up_bps >= 10:
            text_up = _("%(rate)s",
                        {"rate": displaytext.download_rate(up_bps)})
        if down_bps >= 10:
            text_down = _("%(rate)s",
                          {"rate": displaytext.download_rate(down_bps)})

        # first label is always used for upload, while second label is
        # always used for download.  This prevents the text jumping
        # around.
        self._first_label.set_text(text_up)
        self._second_label.set_text(text_down)
        if text_up:
            self._first_image.show()
        else:
            self._first_image.hide()
        if text_down:
            self._second_image.show()
        else:
            self._second_image.hide()

class DownloadTitlebar(ItemListTitlebar):
    """Titlebar with pause/resume/... buttons for downloads, and other
    data.

    :signal pause-all: All downloads should be paused
    :signal resume-all: All downloads should be resumed
    :signal cancel-all: All downloads should be canceled
    :signal settings: The preferences panel downloads tab should be
        opened
    """

    def __init__(self):
        ItemListTitlebar.__init__(self)

        self.create_signal('pause-all')
        self.create_signal('resume-all')
        self.create_signal('cancel-all')
        self.create_signal('settings')

    def _build_titlebar_start(self):
        h = widgetset.HBox(spacing=5)

        pause_button = widgetutil.TitlebarButton(_('Pause All'),
                                                 'download-pause')
        pause_button.connect('clicked', self._on_pause_button_clicked)
        h.pack_start(widgetutil.align_middle(pause_button, top_pad=5,
            bottom_pad=5, left_pad=16))

        resume_button = widgetutil.TitlebarButton(_('Resume All'),
                                                  'download-resume')
        resume_button.connect('clicked', self._on_resume_button_clicked)
        h.pack_start(widgetutil.align_middle(resume_button, top_pad=5,
            bottom_pad=5))

        cancel_button = widgetutil.TitlebarButton(_('Cancel All'),
                                                  'download-cancel')
        cancel_button.connect('clicked', self._on_cancel_button_clicked)
        h.pack_start(widgetutil.align_middle(cancel_button, top_pad=5,
            bottom_pad=5))

        settings_button = widgetutil.TitlebarButton(_('Download Settings'),
                                                    'download-settings')
        settings_button.connect('clicked', self._on_settings_button_clicked)
        h.pack_start(widgetutil.align_middle(settings_button, top_pad=5,
            bottom_pad=5, right_pad=16))
        return h

    def _on_pause_button_clicked(self, widget):
        self.emit('pause-all')

    def _on_resume_button_clicked(self, widget):
        self.emit('resume-all')

    def _on_cancel_button_clicked(self, widget):
        self.emit('cancel-all')

    def _on_settings_button_clicked(self, widget):
        self.emit('settings')

class FeedToolbar(widgetset.Background):
    """Toolbar that appears below the title in a feed.

    :signal remove-feed: (widget) The 'remove feed' button was pressed
    :signal show-settings: (widget) The show settings button was pressed
    :signal auto-download-changed: (widget, value) The auto-download
        setting was changed by the user
    """

    def __init__(self):
        widgetset.Background.__init__(self)
        self.create_signal('remove-feed')
        self.create_signal('show-settings')
        self.create_signal('auto-download-changed')
        hbox = widgetset.HBox(spacing=5)

        settings_button = widgetutil.TitlebarButton(
            _("Settings"), 'feed-settings')
        settings_button.connect('clicked', self._on_settings_clicked)
        self.settings_button = widgetutil.HideableWidget(settings_button)

        autodownload_button = widgetutil.MultiStateTitlebarButton(
            [('autodownload-all', _("Auto-Download All"), "all"),
             ('autodownload-new', _("Auto-Download New"), "new"),
             ('autodownload-off', _("Auto-Download Off"), "off")])
        autodownload_button.connect('clicked', self._on_autodownload_changed)

        self.autodownload_button_actual = autodownload_button
        self.autodownload_button = widgetutil.HideableWidget(
            self.autodownload_button_actual)

        remove_button = widgetutil.TitlebarButton(
            _("Remove podcast"), 'feed-remove-podcast')
        remove_button.connect('clicked', self._on_remove_clicked)
        self.remove_button = remove_button

        hbox.pack_start(widgetutil.align_middle(self.settings_button))
        hbox.pack_start(widgetutil.align_middle(self.autodownload_button))
        hbox.pack_end(widgetutil.align_middle(self.remove_button))
        self.add(widgetutil.pad(hbox, top=4, bottom=4, left=4, right=4))

        self.autodownload_dc = None

    def set_autodownload_mode(self, autodownload_mode):
        if autodownload_mode == 'all':
            self.autodownload_button_actual.set_toggle_state(0)
        elif autodownload_mode == 'new':
            self.autodownload_button_actual.set_toggle_state(1)
        elif autodownload_mode == 'off':
            self.autodownload_button_actual.set_toggle_state(2)

    def draw(self, context, layout):
        key = 74.0 / 255
        top = 223.0 / 255
        bottom = 199.0 / 255

        gradient = widgetset.Gradient(0, 0, 0, context.height)
        gradient.set_start_color((top, top, top))
        gradient.set_end_color((bottom, bottom, bottom))
        context.rectangle(0, 0, context.width, context.height)
        context.gradient_fill(gradient)
        context.set_color((key, key, key))
        context.move_to(0, 0.5)
        context.rel_line_to(context.width, 0)
        context.stroke()

    def _on_settings_clicked(self, button):
        self.emit('show-settings')

    def _on_remove_clicked(self, button):
        self.emit('remove-feed')

    def _on_autodownload_changed(self, widget):
        if self.autodownload_dc is not None:
            self.autodownload_dc.cancel()
            self.autodownload_dc = None

        toggle_state = self.autodownload_button_actual.get_toggle_state()
        toggle_state = (toggle_state + 1) % 3
        self.autodownload_button_actual.set_toggle_state(toggle_state)
        value = self.autodownload_button_actual.get_toggle_state_information()
        value = value[0]
        self.autodownload_dc = eventloop.add_timeout(
            3, self._on_autodownload_changed_timeout, "autodownload change",
            args=(value,))

    def _on_autodownload_changed_timeout(self, value):
        self.emit('auto-download-changed', value)

class HeaderToolbar(Toolbar, SorterWidgetOwner):
    """Toolbar used to sort items and switch views.

    Signals:

    :signal sort-changed: (widget, sort_key, ascending) User changed
        the sort.  sort_key will be one of 'name', 'date', 'size' or
        'length'
    :signal view-all-clicked: User requested to view all items
    :signal toggle-unwatched-clicked: User toggled the
        unwatched/unplayed items only view
    :signal toggle-non-feed-clicked: User toggled the non feed items
        only view
    """
    def __init__(self):
        Toolbar.__init__(self)
        SorterWidgetOwner.__init__(self)

        self.background_image = imagepool.get_surface(
            resources.path('images/headertoolbar.png'))

        self._button_hbox = widgetset.HBox()
        self._button_hbox_container = widgetutil.WidgetHolder()
        self._button_hbox_container.set(self._button_hbox)

        self._hbox = widgetset.HBox()

        self._hbox.pack_end(widgetutil.align_middle(
            self._button_hbox_container))
        self.pack_hbox_extra()

        self.add(self._hbox)

        self._button_map = {}
        self.sorter_widget_map = self._button_map
        self._make_buttons()
        self._button_map['date'].set_sort_order(ascending=False)

        self.filter = WidgetStateStore.get_view_all_filter()

    def switch_to_view(self, view):
        standard_view = WidgetStateStore.get_standard_view_type()
        # NB: SAFE - even if no child widget stored.
        self._button_hbox_container.unset()
        if view == standard_view:
            self._button_hbox_container.set(self._button_hbox)

    def _make_buttons(self):
        self._make_button(_('Name'), 'name')
        self._make_button(_('Date'), 'date')
        self._make_button(_('Size'), 'size')
        self._make_button(_('Time'), 'length')
        self._make_button(_('Watched'), 'status')

    def pack_hbox_extra(self):
        pass

    def draw(self, context, layout):
        self.background_image.draw(context, 0, 0, context.width, context.height)

    def _make_button(self, text, sort_key):
        button = SortBarButton(text)
        button.connect('clicked', self.on_sorter_clicked, sort_key)
        self._button_map[sort_key] = button
        self._button_hbox.pack_start(button)

    def make_filter_switch(self, *args, **kwargs):
        """Helper method to make a SegmentedButtonsRow that switches
        between filters.
        """
        self.filter_switch = segmented.SegmentedButtonsRow(*args, **kwargs)

    def add_filter(self, button_name, signal_name, signal_param, label):
        """Helper method to add a button to the SegmentedButtonsRow
        made in make_filter_switch()

        :param button_name: name of the button
        :param signal_name: signal to emit
        :param label: human readable label for the button
        """

        self.create_signal(signal_name)
        def callback(button):
            self.emit(signal_name, signal_param)
        self.filter_switch.add_text_button(button_name, label, callback)

    def add_filter_switch(self):
        self._hbox.pack_start(widgetutil.align_middle(
            self.filter_switch.make_widget(), left_pad=12))

    def size_request(self, layout):
        width = self._hbox.get_size_request()[0]
        height = self._button_hbox.get_size_request()[1]
        return width, height

    def toggle_filter(self, filter_):
        # implemented by subclasses
        pass

class LibraryHeaderToolbar(HeaderToolbar):
    def __init__(self, unwatched_label):
        self.unwatched_label = unwatched_label
        HeaderToolbar.__init__(self)

    def pack_hbox_extra(self):
        self.make_filter_switch(behavior='custom')
        # this "All" is different than other "All"s in the codebase, so it
        # needs to be clarified
        view_all = WidgetStateStore.get_view_all_filter()
        unwatched = WidgetStateStore.get_unwatched_filter()
        non_feed = WidgetStateStore.get_non_feed_filter()
        self.add_filter('view-all', 'toggle-filter', view_all,
                         declarify(_('View|All')))
        self.add_filter('view-unwatched', 'toggle-filter', unwatched,
                        self.unwatched_label)
        self.add_filter('view-non-feed', 'toggle-filter', non_feed,
                        _('Non Podcast'))
        self.add_filter_switch()

    def toggle_filter(self, filter_):
        self.filter = WidgetStateStore.toggle_filter(self.filter, filter_)
        view_all = WidgetStateStore.is_view_all_filter(self.filter)
        unwatched = WidgetStateStore.has_unwatched_filter(self.filter)
        non_feed = WidgetStateStore.has_non_feed_filter(self.filter)
        self.filter_switch.set_active('view-all', view_all)
        self.filter_switch.set_active('view-unwatched', unwatched)
        self.filter_switch.set_active('view-non-feed', non_feed)

class PlaylistHeaderToolbar(HeaderToolbar):
    def _make_buttons(self):
        self._make_button(_('Order'), 'playlist')
        self._make_button(_('Name'), 'name')
        self._make_button(_('Date'), 'date')
        self._make_button(_('Size'), 'size')
        self._make_button(_('Time'), 'length')

class SortBarButton(widgetset.CustomButton):
    def __init__(self, text, column=False):
        widgetset.CustomButton.__init__(self)
        self.set_can_focus(False)
        self._text = text
        self._column = column
        self._enabled = False
        self._ascending = False
        self.state = 'normal'
        self.set_squish_width(True)
        self.set_squish_height(True)
        self.surface = imagepool.get_surface(
            resources.path('images/headertoolbar.png'))
        self.active_surface = imagepool.get_surface(
            resources.path('images/headertoolbar_active.png'))

    def get_sort_indicator_visible(self):
        return self._enabled

    def get_sort_order_ascending(self):
        return self._ascending

    def set_sort_indicator_visible(self, visible):
        self._enabled = visible
        self.queue_redraw()

    def set_sort_order(self, ascending):
        self._ascending = ascending
        if self._enabled:
            self.queue_redraw()

    def size_request(self, layout):
        layout.set_font(0.8, bold=True)
        text_size = layout.textbox(self._text).get_size()
        # Minus 1 because custom widgets don't currently draw a separator
        # at bottom ..
        return int(text_size[0]) + 36, int(max(text_size[1],
                                      widgetset.CUSTOM_HEADER_HEIGHT - 1))

    def draw(self, context, layout):
        text = 1    # white text
        arrow = 1   # white arrow
        if self._enabled:
            edge = 92.0 / 255
            surface = self.active_surface
        else:
            surface = self.surface
            edge = 72.0 / 255

        # background
        surface.draw(context, 0, 0, context.width, context.height)
        # borders
        context.set_line_width(1)
        context.set_color((edge, edge, edge))
        context.move_to(0.5, 0)
        context.line_to(0.5, context.height)
        context.stroke()
        # text
        layout.set_font(0.8, bold=True)
        layout.set_text_color((text, text, text))
        textbox = layout.textbox(self._text)
        text_size = textbox.get_size()
        triangle_padding = 0
        if self._enabled:
            triangle_padding = 6 + 6
        if not self._column:
            x = (context.width - text_size[0] - triangle_padding) / 2
            left = text_size[0] + x + 6
            if x < 0:
                x = 12
                left = text_size[0] + 18
        else:
            x = 9
            left = text_size[0] + 15
        y = int((context.height - textbox.get_size()[1]) / 2) - 1.5
        textbox.draw(context, x, y, text_size[0], text_size[1])
        context.set_color((arrow, arrow, arrow))
        self._draw_triangle(context, left)

    def _draw_triangle(self, context, left):
        if self._enabled:
            top = int((context.height - 4) / 2)
            ascending = self._ascending
            if use_upside_down_sort:
                ascending = not ascending
            if ascending:
                context.move_to(left, top + 4)
                direction = -1
            else:
                context.move_to(left, top)
                direction = 1
            context.rel_line_to(6, 0)
            context.rel_line_to(-3, 4 * direction)
            context.rel_line_to(-3, -4 * direction)
            context.fill()

class ItemListBackground(widgetset.Background):
    """Plain white background behind the item lists.
    """

    def __init__(self):
        widgetset.Background.__init__(self)
        self.empty_mode = False

    def set_empty(self, empty):
        self.empty_mode = empty

    def draw(self, context, layout):
        if context.style.use_custom_style and self.empty_mode:
            context.set_color((1, 1, 1))
            context.rectangle(0, 0, context.width, context.height)
            context.fill()

class EmptyListHeader(widgetset.Alignment):
    """Header Label for empty item lists."""
    def __init__(self, text):
        widgetset.Alignment.__init__(self, xalign=0.5, xscale=0.0)
        self.set_padding(24, 0, 0, 0)
        self.label = widgetset.Label(text)
        self.label.set_bold(True)
        self.label.set_color((0.8, 0.8, 0.8))
        self.label.set_size(2)
        self.add(self.label)

class EmptyListDescription(widgetset.Alignment):
    """Label for descriptions of empty item lists."""
    def __init__(self, text):
        widgetset.Alignment.__init__(self, xalign=0.5, xscale=0.5)
        self.set_padding(18)
        self.label = widgetset.Label(text)
        self.label.set_color((0.8, 0.8, 0.8))
        self.label.set_wrap(True)
        self.label.set_size_request(550, -1)
        self.add(self.label)

class ProgressToolbar(Toolbar):
    """Toolbar displayed above ItemViews to show the progress of
    reading new metadata, communicating with a device, and similar
    time-consuming operations.

    Assumes current ETA is accurate; keeps track of its own elapsed
    time.  Displays progress as: elapsed / (elapsed + ETA)
    """
    def __init__(self):
        Toolbar.__init__(self)
        loading_icon = widgetset.AnimatedImageDisplay(
                       resources.path('images/load-indicator.gif'))
        self.hbox = widgetset.HBox()
        self.add(self.hbox)
        self.label = widgetset.Label()
        self.meter = widgetutil.HideableWidget(loading_icon)
        self.label_widget = widgetutil.HideableWidget(self.label)
        self.elapsed = None
        self.eta = None
        self.total = None
        self.remaining = None
        self.mediatype = 'other'
        self.displayed = False
        self.set_up = False

    def _display(self):
        if not self.set_up:
            padding = 380 - self.label.get_width()
            self.hbox.pack_start(
                widgetutil.align(
                    self.label_widget, 1, 0.5, 1, 0, 0, 0, padding, 10),
                expand=False)
            self.hbox.pack_start(widgetutil.align_left(
                            self.meter, 0, 0, 0, 200), expand=True)
            self.set_up = True
        if not self.displayed:
            self.label_widget.show()
            self.meter.show()
            self.displayed = True

    def _update_label(self):
        # TODO: display eta
        state = (self.total-self.remaining, self.total)
        if self.mediatype == 'audio':
            text = _("Importing audio details and artwork: "
                    "{0} of {1}").format(*state)
        elif self.mediatype == 'video':
            text = _("Importing video details and creating thumbnails: "
                    "{0} of {1}").format(*state)
        else:
            text = _("Importing file details: "
                    "{0} of {1}").format(*state)
        self.label.set_text(text)

    def update(self, mediatype, remaining, seconds, total):
        """Update progress."""
        self.mediatype = mediatype
        self.eta = seconds
        self.total = total
        self.remaining = remaining
        if total:
            self._update_label()
            self._display()
        else:
            self.label_widget.hide()
            self.meter.hide()
            self.displayed = False

class ItemDetailsBackground(widgetset.Background):
    """Nearly white background behind the item details widget
    """

    def draw(self, context, layout):
        if context.style.use_custom_style:
            context.set_color((0.9, 0.9, 0.9))
            context.rectangle(0, 0, context.width, context.height)
            context.fill()

class ItemDetailsImageBackground(widgetset.Background):
    def __init__(self):
        widgetset.Background.__init__(self)
        self.image = imagepool.get_surface(resources.path(
            'images/item-details-image-bg.png'))

    def draw(self, context, layout):
        self.image.draw(context, 0, 0, context.width, context.height)

class ItemDetailsExpanderButton(widgetset.CustomButton):
    """Button to expand/contract the item details view"""

    BACKGROUND_GRADIENT_TOP = (0.977,) * 3
    BACKGROUND_GRADIENT_BOTTOM = (0.836,) * 3
    LINE_TOP = widgetutil.css_to_color('#949494')
    LINE_BOTTOM = widgetutil.css_to_color('#161616')

    def __init__(self):
        widgetset.CustomButton.__init__(self)
        self.set_can_focus(False)
        self.expand_image = imagepool.get_surface(resources.path(
            'images/item-details-expander-arrow.png'))
        self.contract_image = imagepool.get_surface(resources.path(
            'images/item-details-expander-arrow-down.png'))
        self.mode = 'expand'

    def click_should_expand(self):
        return self.mode == 'expand'

    def set_mode(self, mode):
        """Change the mode for the widget.

        possible values "expand" or "contact"
        """
        if mode != 'expand' and mode != 'contract':
            raise ValueError("Unknown mode: %s", mode)
        self.mode = mode
        self.queue_redraw()

    def size_request(self, layout):
        return 30, 15

    def draw(self, context, layout):
        self.draw_gradient(context)
        self.draw_lines(context)
        self.draw_icon(context)

    def draw_gradient(self, context):
        # leave 1px on the top and bottom for the black links
        top = 1
        height = context.height - 1
        gradient = widgetset.Gradient(0, top, 0, top+height)
        gradient.set_start_color(self.BACKGROUND_GRADIENT_TOP)
        gradient.set_end_color(self.BACKGROUND_GRADIENT_BOTTOM)
        context.rectangle(0, 1, context.width, height)
        context.gradient_fill(gradient)

    def draw_lines(self, context):
        context.set_color(self.LINE_TOP)
        context.rectangle(0, 0, context.width, 1)
        context.fill()
        # NB: mode indicates alternate state, not our current state.
        if not self.mode == 'expand':
            context.set_color(self.LINE_BOTTOM)
            context.rectangle(0, context.height-1, context.width, 1)
            context.fill()

    def draw_icon(self, context):
        if self.mode == 'expand':
            icon = self.expand_image
        else:
            icon = self.contract_image
        x = int((context.width - icon.width) / 2)
        y = int((context.height - icon.height) / 2)
        icon.draw(context, x, y, icon.width, icon.height)

class TorrentInfoWidget(widgetset.Background):
    PADDING_TOP = 10
    PADDING_BOTTOM = 5
    LABEL_TEXT_COLOR = widgetutil.css_to_color('#686868')
    FONT_SIZE = widgetutil.font_scale_from_osx_points(11)
    FONT_SIZE_SMALL = widgetutil.font_scale_from_osx_points(9)
    VALUE_TEXT_COLOR = widgetutil.BLACK
    BACKGROUND_COLOR = widgetutil.css_to_color('#d5d5d5')
    BACKGROUND_LINE_COLOR = widgetutil.css_to_color('#b9b9b9')
    BACKGROUND_LINE_COLOR_BOTTOM = widgetutil.css_to_color('#f1f1f1')
    WIDTH = 370

    def __init__(self):
        widgetset.Background.__init__(self)
        self.eta_icon = imagepool.get_image_display(resources.path(
            'images/torrent-info-eta.png'))
        self.down_rate_icon = imagepool.get_image_display(resources.path(
            'images/torrent-info-down-rate.png'))
        self.up_rate_icon = imagepool.get_image_display(resources.path(
            'images/torrent-info-up-rate.png'))
        self.should_show = False
        self.layout_contents()

    def layout_contents(self):
        # make the left/right sections take up half the space minus 15px
        # pading for the sides
        section_width = (self.WIDTH / 2) - 15
        main_hbox = widgetset.HBox()
        left_side = self.build_left(section_width)
        right_side = self.build_right(section_width)
        main_hbox.pack_start(widgetutil.pad(left_side, left=10, right=5))
        main_hbox.pack_start(widgetutil.pad(right_side, left=5, right=10))
        self.add(widgetutil.pad(main_hbox, top=10, bottom=10))

    def _label(self, text=''):
        label = widgetset.Label(text)
        label.set_size(self.FONT_SIZE)
        if text:
            # inital text means this is a label, rather than a value
            label.set_color(self.LABEL_TEXT_COLOR)
        return label

    def _small_label(self, text=''):
        label = widgetset.Label(text)
        label.set_size(self.FONT_SIZE_SMALL)
        if text:
            label.set_color(self.LABEL_TEXT_COLOR)
        return label

    def build_left(self, width):
        remaining = self._label(_('Remaining'))
        download = self._label(_('Download'))
        upload = self._label(_('Upload'))
        total1 = self._small_label(_('Total'))
        total2 = self._small_label(_('Total'))
        self.eta = self._label()
        self.down_rate = self._label()
        self.up_rate= self._label()
        self.down_total = self._small_label()
        self.up_total = self._small_label()
        # pack each line.  Set expand=True for lines before spacing
        vbox = widgetset.VBox()
        vbox.set_size_request(width, -1)
        self.build_left_line(vbox, remaining, self.eta, width,
                self.eta_icon, True)
        self.build_left_line(vbox, download, self.down_rate, width,
                self.down_rate_icon, False)
        self.build_left_line(vbox, total1, self.down_total, width, None,
                True)
        self.build_left_line(vbox, upload, self.up_rate, width,
                self.up_rate_icon, False)
        self.build_left_line(vbox, total2, self.up_total, width, None,
                True)
        return vbox

    def build_left_line(self, vbox, label, value, width, icon, expand):
        ICON_AREA_WIDTH = 15

        line = widgetset.HBox()
        # pack label
        line.pack_start(label, expand=True)
        # pack icon, or pad empty space
        if icon:
            line.pack_start(widgetutil.align_bottom(icon,
                bottom_pad=label.baseline()), expand=False)
            left_pad = ICON_AREA_WIDTH - icon.image.width
        else:
            left_pad = ICON_AREA_WIDTH
        # pack value, set it's width so that it plus the icon takes up half
        # the line.
        value.set_size_request((width / 2) - ICON_AREA_WIDTH, -1)
        line.pack_start(widgetutil.pad(value, left=left_pad), expand=False)
        if expand:
            vbox.pack_start(widgetutil.align_top(line), expand=True)
        else:
            vbox.pack_start(line)

    def build_right(self, width):
        connected_peers = self._label(_('Connected Peers'))
        seeders = self._label(_('Seeders'))
        leechers = self._label(_('Leechers'))
        share_ratio = self._label(_('Share Ratio'))

        self.connections = self._label()
        self.seeders = self._label()
        self.leechers = self._label()
        self.ratio = self._label()
        # pack each line.  Set expand=True for all lines except the last to
        # ensure equal spacing
        vbox = widgetset.VBox()
        vbox.set_size_request(width, -1)
        self.build_right_line(vbox, connected_peers, self.connections, True)
        self.build_right_line(vbox, seeders, self.seeders, True)
        self.build_right_line(vbox, leechers, self.leechers, True)
        self.build_right_line(vbox, share_ratio, self.ratio, False)
        return vbox

    def build_right_line(self, vbox, label, value, expand):
        hbox = widgetset.HBox()
        hbox.pack_start(label)
        value.set_alignment(widgetconst.TEXT_JUSTIFY_RIGHT)
        hbox.pack_end(value)
        vbox.pack_start(widgetutil.align_top(hbox), expand=expand)

    def size_request(self, layout):
        if self.should_show:
            # hopefully this is big enough to fit all text
            return (self.WIDTH, 105)
        else:
            return (0, 0)

    def draw(self, context, layout_manager):
        # draw background for the torrent info section
        context.set_color(self.BACKGROUND_COLOR)
        widgetutil.round_rect(context, 0, 0, context.width, context.height, 5)
        context.fill()
        # prepare to draw lines.
        context.set_line_width(1)
        # offset coordinates by 0.5 so the stroke falls solidly on a pixel
        top = 0.5
        bottom = context.height-0.5
        left = 0.5
        right = context.width-0.5
        middle = round(context.width / 2.0) + 0.5
        radius = 5
        # draw top and middle lines with our dark line color
        context.set_color(self.BACKGROUND_LINE_COLOR)
        context.move_to(middle, 0)
        context.line_to(middle, context.height)
        context.stroke()
        context.move_to(left, top+radius)
        context.arc(left+radius, top+radius, radius, math.pi, math.pi * 3 / 2)
        context.line_to(right - radius, top)
        context.arc(right - radius, top + radius, radius, math.pi * 3 / 2,
                math.pi * 2)
        context.stroke()
        # draw bottom lines with our light line color
        context.set_color(self.BACKGROUND_LINE_COLOR_BOTTOM)
        context.arc(right-radius, bottom-radius, radius, 0, math.pi/2)
        context.line_to(left+radius, bottom)
        context.arc(left+radius, bottom-radius, radius, math.pi/2, math.pi)
        context.stroke()
        # draw side lines with a gradient from the left to the right colors
        # we use rectangles here to make gradients work, so we don't use the
        # top/bottom/left/right coordinates above.
        gradient = widgetset.Gradient(0, radius, 0, context.height-radius)
        gradient.set_start_color(self.BACKGROUND_LINE_COLOR)
        gradient.set_end_color(self.BACKGROUND_LINE_COLOR_BOTTOM)
        context.rectangle(0, radius, 1, context.height-radius*2)
        context.gradient_fill(gradient)
        context.rectangle(context.width-1, radius, 1,
                context.height-radius*2)
        context.gradient_fill(gradient)

    def set_info(self, info):
        self.should_show = (info.download_info and info.download_info.torrent
                and info.state in ('downloading', 'uploading'))
        if not self.should_show:
            return

        if info.seeders is None:
            # torrent still starting up
            for label in (self.connections, self.seeders, self.leechers,
                    self.down_rate, self.up_rate, self.ratio, self.eta):
                label.set_text("")
        else:
            self.connections.set_text(str(info.connections))
            self.seeders.set_text(str(info.seeders))
            self.leechers.set_text(str(info.leechers))
            self.down_rate.set_text(displaytext.download_rate(info.down_rate))
            self.up_rate.set_text(displaytext.download_rate(info.up_rate))
            self.ratio.set_text("%0.2f" % info.up_down_ratio)
            self.eta.set_text(displaytext.time_string_0_blank(
                info.download_info.eta))
        self.down_total.set_text(displaytext.size_string(info.down_total))
        self.up_total.set_text(displaytext.size_string(info.up_total))

class ItemDetailsWidget(widgetset.VBox):
    """Widget to display detailed information about an item.

    This usually shows the thumbnail, full description, etc. for the
    selected item.
    """
    PADDING_MIDDLE = 25
    PADDING_RIGHT = 30
    PADDING_ABOVE_TORRENT_INFO = 25
    PADDING_ABOVE_TITLE = 20
    PADDING_ABOVE_DESCRIPTION = 8
    PADDING_ABOVE_EXTRA_INFO = 25
    IMAGE_SIZE = (165, 165)
    TEXT_COLOR = (0.176, 0.176, 0.176)
    TITLE_SIZE = widgetutil.font_scale_from_osx_points(14)
    DESCRIPTION_SIZE = widgetutil.font_scale_from_osx_points(11)
    # give enough room to display the image, plus some more for the
    # scrollbars and the expander
    EXPANDED_HEIGHT = 190

    def __init__(self):
        widgetset.VBox.__init__(self)
        self.allocated_width = -1
        self.empty_thumbnail = imagepool.get(
                resources.path('images/item-details-empty-thumb.png'),
                self.IMAGE_SIZE)
        # content_hbox holds our contents
        self.content_hbox = widgetset.HBox(spacing=self.PADDING_MIDDLE)
        # pack left side
        self.image_widget = widgetset.ImageDisplay()
        image_background = ItemDetailsImageBackground()
        image_background.add(widgetutil.align(self.image_widget,
                xalign=0.5, yalign=0.5))
        image_background.set_size_request(*self.IMAGE_SIZE)
        self.content_hbox.pack_start(widgetutil.align_top(image_background))
        # pack right side
        self.right_side_normal = self.build_right()
        self.right_side_empty = self.build_right_empty()
        self.empty_mode = True
        self.content_hbox.pack_end(self.right_side_empty, expand=True)
        # expander_button is used to expand/collapse our content
        self.expander_button = ItemDetailsExpanderButton()
        self.pack_start(self.expander_button)
        # pack our content
        background = ItemDetailsBackground()
        background.add(widgetutil.align_top(self.content_hbox))
        self.scroller = widgetset.Scroller(False, True)
        self.scroller.add(background)
        self.scroller.set_size_request(-1, self.EXPANDED_HEIGHT)
        self._expanded = False
        self.license_url = None

    def _set_empty_mode(self, empty_mode):
        if empty_mode == self.empty_mode:
            return
        self.empty_mode = empty_mode
        if empty_mode:
            self.content_hbox.remove(self.right_side_normal)
            self.content_hbox.pack_end(self.right_side_empty, expand=True)
        else:
            self.content_hbox.remove(self.right_side_empty)
            self.content_hbox.pack_end(self.right_side_normal, expand=True)

    def on_license_clicked(self, button):
        if self.license_url:
            app.widgetapp.open_url(self.license_url)

    def build_right(self):
        vbox = widgetset.VBox(spacing=10)
        self.title_label = self.build_title()
        self.torrent_info = TorrentInfoWidget()
        self.description_label = self.build_description_label()
        self.extra_info_label = self.build_extra_info()
        self.torrent_info_holder = widgetutil.HideableWidget(
                widgetutil.align_left(self.torrent_info,
                    top_pad=self.PADDING_ABOVE_TORRENT_INFO))
        vbox.pack_start(self.torrent_info_holder)
        vbox.pack_start(widgetutil.align_left(self.title_label,
            top_pad=self.PADDING_ABOVE_TITLE))
        self.license_button = widgetset.Button(_('View License'))
        self.license_button.connect('clicked', self.on_license_clicked)
        self.license_holder = widgetutil.WidgetHolder()
        vbox.pack_start(widgetutil.align_left(self.license_holder))
        vbox.pack_start(widgetutil.align_left(self.description_label))
        vbox.pack_start(widgetutil.align_left(self.extra_info_label,
            top_pad=self.PADDING_ABOVE_EXTRA_INFO))
        return vbox

    def build_right_empty(self):
        hbox = widgetset.HBox(spacing=16)
        left_image = imagepool.get(resources.path('images/filigree-left.png'))
        right_image = imagepool.get(
                resources.path('images/filigree-right.png'))
        hbox.pack_start(widgetset.ImageDisplay(left_image))
        label = self.build_label()
        label.set_text(_("Select an item to view more of its details"))
        hbox.pack_start(label)
        hbox.pack_start(widgetset.ImageDisplay(right_image))
        # align things so that it's in the middle of the area available
        alignment = widgetset.Alignment(0.5, 0.5)
        alignment.add(hbox)
        alignment.set_size_request(-1, self.EXPANDED_HEIGHT)
        return alignment

    def build_label(self):
        label = widgetset.Label()
        label.set_selectable(True)
        label.set_alignment(widgetconst.TEXT_JUSTIFY_LEFT)
        label.set_wrap(True)
        label.set_color(self.TEXT_COLOR)
        return label

    def build_title(self):
        label = self.build_label()
        label.set_size(self.TITLE_SIZE)
        label.set_bold(True)
        return label

    def build_description_label(self):
        label = self.build_label()
        label.set_size(self.DESCRIPTION_SIZE)
        return label

    def build_extra_info(self):
        label = self.build_label()
        label.set_selectable(False)
        label.set_size(self.DESCRIPTION_SIZE)
        return label

    def set_expanded(self, expanded):
        if expanded == self._expanded:
            return
        if expanded:
            self.pack_end(self.scroller)
            self.expander_button.set_mode('contract')
        else:
            self.remove(self.scroller)
            self.expander_button.set_mode('expand')
        self._expanded = expanded

    def set_info(self, info):
        self.title_label.set_text(info.name)
        self.torrent_info.set_info(info)
        if self.torrent_info.should_show:
            self.torrent_info_holder.show()
        else:
            self.torrent_info_holder.hide()
        self.description_label.set_text(info.description_stripped[0])
        self.set_extra_info_text(info)
        self.setup_license_button(info)
        image = imagepool.get(info.thumbnail, self.IMAGE_SIZE)
        self.image_widget.set_image(image)
        self.set_label_widths()
        self._set_empty_mode(False)

    def set_extra_info_text(self, info):
        parts = []
        for attr in (info.display_date, info.display_duration,
                info.display_size, info.file_format):
            if attr:
                parts.append(attr)
        self.extra_info_label.set_text(' | '.join(parts))

    def setup_license_button(self, info):
        if info.license and info.license.startswith("http://"):
            # try license_info first
            self._set_license_url(info.license)
        elif info.permalink:
            # Fallback to the website
            self._set_license_url(info.permalink)
        else:
            # hide the button if nothing else works
            self._unset_license_url()

    def _set_license_url(self, url):
        self.license_holder.set(self.license_button)
        self.license_url = url

    def _unset_license_url(self):
        self.license_holder.unset()
        self.license_url = None

    def clear(self):
        self.title_label.set_text('')
        self.description_label.set_text('')
        self.extra_info_label.set_text('')
        self.image_widget.set_image(self.empty_thumbnail)
        self._set_empty_mode(True)

    def do_size_allocated(self, width, height):
        if width == self.allocated_width:
            return
        self.allocated_width = width
        self.set_label_widths()

    def set_label_widths(self):
        # resize our labels so that they take up exactly all of the width
        # Take into account that the image background will always be present
        # and be self.IMAGE_SIZE in size, regardless of whether we have a thumb
        # for it or not.
        image_width = self.IMAGE_SIZE[0]
        label_width = (self.allocated_width - image_width -
                self.PADDING_MIDDLE - self.PADDING_RIGHT)
        if label_width < 1:
            logging.warn("bad label width: %s", label_width)
            label_width = 0
        self.title_label.set_size_request(label_width, -1)
        self.description_label.set_size_request(label_width, -1)
        self.extra_info_label.set_size_request(label_width, -1)

class ItemContainerWidget(widgetset.VBox):
    """A Widget for displaying objects that contain items (feeds,
    playlists, folders, downloads tab, etc).

    :attribute titlebar_vbox: VBox for the title bar
    :attribute vbox: VBoxes for standard view and list view
    :attribute list_empty_mode_vbox: VBox for list empty mode
    :attribute toolbar: HeaderToolbar for the widget
    :attribute item_details: ItemDetailsWidget at the bottom of the widget
    """

    def __init__(self, toolbar, view):
        widgetset.VBox.__init__(self)
        self.vbox = {}
        standard_view = WidgetStateStore.get_standard_view_type()
        list_view = WidgetStateStore.get_list_view_type()
        self.vbox[standard_view] = widgetset.VBox()
        self.vbox[list_view] = widgetset.VBox()
        self.titlebar_vbox = widgetset.VBox()
        self.statusbar_vbox = widgetset.VBox()
        self.item_details = ItemDetailsWidget()
        self.list_empty_mode_vbox = widgetset.VBox()
        self.progress_toolbar = ProgressToolbar()
        self.toolbar = toolbar
        toolbar.switch_to_view(view)
        self.pack_start(self.titlebar_vbox)
        color1 = widgetutil.css_to_color('#303030')
        color2 = widgetutil.css_to_color('#020202')
        self.pack_start(separator.HThinSeparator(color1))
        self.pack_start(self.progress_toolbar)
        self.background = ItemListBackground()
        self.pack_start(self.background, expand=True)
        self.pack_start(self.item_details)
        self.pack_start(self.statusbar_vbox)
        self.selected_view = view
        self.list_empty_mode = False
        self.vbox[standard_view].pack_start(self.toolbar)
        self.vbox[standard_view].pack_start(separator.HThinSeparator(color2))
        self.background.add(self.vbox[view])

    def toggle_filter(self, filter_):
        self.toolbar.toggle_filter(filter_)

    def switch_to_view(self, view, toolbar=None):
        if self.selected_view != view:
            if not self.list_empty_mode:
                self.background.remove()
                self.background.add(self.vbox[view])
            self.selected_view = view
            self.toolbar.switch_to_view(view)

    def set_list_empty_mode(self, enabled):
        if enabled != self.list_empty_mode:
            self.background.remove()
            if enabled:
                self.background.set_empty(True)
                self.background.add(self.list_empty_mode_vbox)
            else:
                self.background.set_empty(False)
                self.background.add(self.vbox[self.selected_view])
            self.list_empty_mode = enabled

    def get_progress_meter(self):
        """Return a ProgressToolbar attached to the display."""
        return self.progress_toolbar
