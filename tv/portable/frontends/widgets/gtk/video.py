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

"""video.py -- Video code. """

import time

import gobject
import gtk
import logging

from miro import app
from miro.gtcache import gettext as _
from miro import util
from miro import messages
from miro import displaytext
from miro.plat import screensaver
from miro.frontends.widgets.gtk.widgetset import Widget, VBox, Label, HBox, Alignment, Background
from miro.frontends.widgets.gtk.persistentwindow import PersistentWindow

BLACK = (0.0, 0.0, 0.0)
WHITE = (1.0, 1.0, 1.0)

class ClickableLabel(Widget):
    """This is like a label and reimplements many of the Label things, but
    it's an EventBox with a Label child widget.
    """
    def __init__(self, text, size=0.77, color=WHITE):
        Widget.__init__(self)
        self.set_widget(gtk.EventBox())

        self.label = Label(text)

        self._widget.add(self.label._widget)
        self.label._widget.show()
        self._widget.set_above_child(False)
        self._widget.set_visible_window(False)

        self.set_size(size)
        self.set_color(color)

        self.wrapped_widget_connect('button-release-event', self.on_click)
        self.wrapped_widget_connect('enter-notify-event', self.on_enter_notify)
        self.wrapped_widget_connect('leave-notify-event', self.on_leave_notify)
        self.create_signal('clicked')

    def on_click(self, widget, event):
        self.emit('clicked')
        return True

    def on_enter_notify(self, widget, event):
        self._widget.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.HAND1))

    def on_leave_notify(self, widget, event):
        if self._widget.window:
            self._widget.window.set_cursor(None)

    def set_size(self, size):
        self.label.set_size(size)

    def set_color(self, color):
        self.label.set_color(color)

    def set_text(self, text):
        self.label.set_text(text)

    def hide(self):
        self.label._widget.hide()

    def show(self):
        self.label._widget.show()

class NullRenderer(object):
    def can_play_file(self, path, yes_callback, no_callback):
        no_callback()

    def reset(self):
        pass

def make_hidden_cursor():
    pixmap = gtk.gdk.Pixmap(None, 1, 1, 1)
    color = gtk.gdk.Color()
    return gtk.gdk.Cursor(pixmap, pixmap, color, color, 0, 0)

def _align_left(widget, top_pad=0, bottom_pad=0, left_pad=0, right_pad=0):
    """Align left."""
    alignment = Alignment(0, 0, 0, 1)
    alignment.set_padding(top_pad, bottom_pad, left_pad, right_pad)
    alignment.add(widget)
    return alignment

def _align_right(widget, top_pad=0, bottom_pad=0, left_pad=0, right_pad=0):
    """Align right."""
    alignment = Alignment(1, 0, 0, 1)
    alignment.set_padding(top_pad, bottom_pad, left_pad, right_pad)
    alignment.add(widget)
    return alignment


# Couple of utility functions to grab GTK widgets out of the widget tree for
# fullscreen code
def _videobox_widget():
    return app.widgetapp.window.videobox._widget

def _window():
    return app.widgetapp.window._window

def can_play_file(path, yes_callback, no_callback):
    if app.renderer is not None:
        app.renderer.can_play_file(path, yes_callback, no_callback)
        return
    logging.warn("can_play_file: app.renderer is None")
    no_callback()

class VideoWidget(Widget):
    def __init__(self, renderer):
        Widget.__init__(self)
        self.set_widget(PersistentWindow())
        self._widget.set_double_buffered(False)
        self._widget.add_events(gtk.gdk.POINTER_MOTION_MASK)
        self._widget.add_events(gtk.gdk.BUTTON_PRESS_MASK)
        renderer.set_widget(self._widget)

class VideoDetailsWidget(Background):
    def __init__(self):
        Background.__init__(self)
        self.add(self.build_video_details())

    def build_video_details(self):
        h = HBox()

        # left side
        v = VBox()
        self._item_name = Label("")
        self._item_name.set_bold(True)
        self._item_name.set_size(1.0)
        self._item_name.set_color(WHITE)
        v.pack_start(_align_left(self._item_name, left_pad=5))

        self._channel_name = Label("")
        self._channel_name.set_color(WHITE)
        v.pack_start(_align_left(self._channel_name, left_pad=5))
        h.pack_start(v)

        # right side
        v = VBox()
        self._email_link = ClickableLabel(_("EMAIL A FRIEND"))
        self._email_link.connect('clicked', self.handle_email)
        v.pack_start(_align_right(self._email_link, right_pad=5))

        h2 = HBox()
        self._comments_link = ClickableLabel(_("COMMENTS"))
        self._comments_link.connect('clicked', self.handle_commentslink)
        h2.pack_start(_align_right(self._comments_link, right_pad=10), expand=True)

        self._permalink_link = ClickableLabel(_("PERMALINK"))
        self._permalink_link.connect('clicked', self.handle_permalink)
        h2.pack_start(_align_right(self._permalink_link, right_pad=5))
        v.pack_start(h2)

        h2 = HBox()
        self._expiration_label = Label("")
        self._expiration_label.set_size(0.77)
        self._expiration_label.set_color(WHITE)
        h2.pack_start(_align_right(self._expiration_label, right_pad=15), expand=True)

        self._add_to_library_link = ClickableLabel(_("ADD TO LIBRARY"))
        self._add_to_library_link.connect('clicked', self.handle_add_to_library)
        h2.pack_start(_align_right(self._add_to_library_link, right_pad=5))
        v.pack_start(h2)

        self._keep_link = ClickableLabel(_("KEEP"))
        self._keep_link.connect('clicked', self.handle_keep)
        h2.pack_start(_align_right(self._keep_link, right_pad=5))

        self._dash = Label("-")
        self._dash.set_size(0.77)
        self._dash.set_color(WHITE)
        h2.pack_start(_align_right(self._dash, right_pad=5))

        self._delete_link = ClickableLabel(_("DELETE"))
        self._delete_link.connect('clicked', self.handle_delete)
        h2.pack_start(_align_right(self._delete_link, right_pad=5))

        h.pack_start(_align_right(v), expand=True)
        return h

    def hide(self):
        self._widget.hide()

    def show(self):
        self._widget.show()

    def handle_keep(self, widget):
        messages.KeepVideo(self.item_info.id).send_to_backend()

    def handle_add_to_library(self, widget):
        messages.AddItemToLibrary(self.item_info.id).send_to_backend()

    def handle_delete(self, widget):
        self.reset()
        app.playback_manager.on_movie_finished()
        app.widgetapp.remove_items([self.item_info])

    def handle_commentslink(self, widget):
        app.widgetapp.open_url(self.item_info.commentslink)

    def handle_email(self, widget):
        link = self.item_info.commentslink or self.item_info.permalink or self.item_info.file_url
        app.widgetapp.mail_to_friend(link, self.item_info.name)

    def handle_permalink(self, widget):
        app.widgetapp.open_url(self.item_info.permalink)

    def update_info(self, item_info):
        self.item_info = item_info

        if item_info.is_external:
            if item_info.is_single:
                self._add_to_library_link.show()
                self._delete_link.hide()

            else:
                self._add_to_library_link.hide()
                self._delete_link.show()

        else:
            if item_info.video_watched:
                if item_info.expiration_date is not None:
                    text = displaytext.expiration_date(item_info.expiration_date)
                    self._expiration_label.set_text(text)
                    self._expiration_label.show()
                    self._keep_link.show()
                    self._dash.show()
                else:
                    self._expiration_label.hide()
                    self._keep_link.hide()
                    self._dash.hide()
            else:
                self._expiration_label.hide()
                self._keep_link.show()
                self._dash.show()

    def set_video_details(self, item_info):
        """This gets called when the item is set to play.  It should make
        no assumptions about the state of the video details prior to being
        called.
        """
        self.item_info = item_info
        self._item_name.set_text(util.clampText(item_info.name, 100))

        if item_info.is_external:
            self._email_link.hide()
            self._comments_link.hide()
            self._permalink_link.hide()
            self._expiration_label.hide()
            self._keep_link.hide()
            self._dash.hide()

        else:
            channels = app.tab_list_manager.feed_list.get_feeds()
            channels = [ci for ci in channels if ci.id == item_info.feed_id]
            if len(channels) == 0:
                self._channel_name.set_text("")
            else:
                self._channel_name.set_text(util.clampText(channels[0].name, 100))

            self._add_to_library_link.hide()

            if item_info.commentslink:
                self._comments_link.show()
                self._comments_link.set_text(_("COMMENTS"))
            else:
                self._comments_link.hide()

            if item_info.permalink:
                self._permalink_link.show()
                self._permalink_link.set_text(_("PERMALINK"))
            else:
                self._permalink_link.hide()

        self.update_info(item_info)

    def draw(self, context, layout):
        context.set_color(BLACK)
        context.rectangle(0, 0, context.width, context.height)
        context.fill()

    def is_opaque(self):
        return True

    def reset(self):
        self._delete_link.on_leave_notify(None, None)

class VideoRenderer(VBox):
    """Video renderer widget.

    Note: app.renderer must be initialized before instantiating this class.
    If no renderers can be found, set app.renderer to None.
    """

    HIDE_CONTROLS_TIMEOUT = 2000

    def __init__(self):
        VBox.__init__(self)
        if app.renderer is not None:
            self.renderer = app.renderer
        else:
            self.renderer = NullRenderer()

        self._video_widget = VideoWidget(self.renderer)
        self.pack_start(self._video_widget, expand=True)

        self._video_details = VideoDetailsWidget()
        self.pack_start(self._video_details)

        self.hide_controls_timeout = None
        self.motion_handler = None
        self.videobox_motion_handler = None
        self.hidden_cursor = make_hidden_cursor()
        self._items_changed_callback = app.info_updater.connect(
                'items-changed', self._on_items_changed)
        self._item_id = None

        self._video_widget.wrapped_widget_connect('button-press-event', self.on_button_press)

    def teardown(self):
        self.renderer.reset()
        app.info_updater.disconnect(self._items_changed_callback)
        self._items_changed_callback = None

    def _on_items_changed(self, controller, changed_items):
        for item_info in changed_items:
            if item_info.id == self._item_id:
                self._video_details.update_info(item_info)
                break

    def set_movie_item(self, item_info):
        self._video_details.set_video_details(item_info)
        self.renderer.select_file(item_info.video_path)
        self._item_id = item_info.id

    def get_elapsed_playback_time(self):
        return self.renderer.get_current_time()

    def get_total_playback_time(self):
        return self.renderer.get_duration()

    def set_volume(self, volume):
        self.renderer.set_volume(volume)

    def play(self):
        self.renderer.play()

    def play_from_time(self, resume_time=0):
        self.seek_to_time(resume_time)
        self.play()

    def pause(self):
        self.renderer.pause()

    def stop(self):
        self._video_details.reset()
        self.renderer.stop()

    def set_playback_rate(self, rate):
        self.renderer.set_rate(rate)

    def seek_to(self, position):
        time = self.get_total_playback_time() * position
        self.seek_to_time(time)

    def seek_to_time(self, time_pos):
        self.renderer.set_current_time(time_pos)

    def skip_forward(self):
        current = self.get_elapsed_playback_time()
        duration = self.get_total_playback_time()
        pos = min(duration, current + 30.0)
        self.seek_to_time(pos)

    def skip_backward(self):
        current = self.get_elapsed_playback_time()
        pos = max(0, current - 15.0)
        self.seek_to_time(pos)

    def enter_fullscreen(self):
        self.screensaver_manager = screensaver.create_manager()
        if self.screensaver_manager is not None:
            self.screensaver_manager.disable()
        self.motion_handler = self.wrapped_widget_connect(
                'motion-notify-event', self.on_mouse_motion)
        self.videobox_motion_handler = _videobox_widget().connect(
                'motion-notify-event', self.on_mouse_motion)
        app.widgetapp.window.menubar.hide()
        self.schedule_hide_controls(self.HIDE_CONTROLS_TIMEOUT)
        _window().fullscreen()

    def prepare_switch_to_attached_playback(self):
        self._widget.get_parent().remove(self._widget)

    def prepare_switch_to_detached_playback(self):
        pass

    def on_button_press(self, widget, event):
        if event.type == gtk.gdk._2BUTTON_PRESS:
            app.playback_manager.toggle_fullscreen()
            return True
        return False

    def on_mouse_motion(self, widget, event):
        if not _videobox_widget().props.visible:
            self.show_controls()
            self.schedule_hide_controls(self.HIDE_CONTROLS_TIMEOUT)
        else:
            self.last_motion_time = time.time()

    def show_controls(self):
        self._video_details.show()
        _videobox_widget().show()
        _window().window.set_cursor(None)

    def on_hide_controls_timeout(self):
        # Check if the mouse moved before the timeout
        time_since_motion = int((time.time() - self.last_motion_time) * 1000)
        timeout_left = self.HIDE_CONTROLS_TIMEOUT - time_since_motion
        if timeout_left <= 0:
            self._video_details.hide()
            _window().window.set_cursor(self.hidden_cursor)
            _videobox_widget().hide()
            self.hide_controls_timeout = None
        else:
            self.schedule_hide_controls(timeout_left)

    def cancel_hide_controls(self):
        if self.hide_controls_timeout is not None:
            gobject.source_remove(self.hide_controls_timeout)

    def schedule_hide_controls(self, time):
        self.hide_controls_timeout = gobject.timeout_add(time,
                self.on_hide_controls_timeout)
        self.last_motion_time = 0

    def exit_fullscreen(self):
        if self.screensaver_manager is not None:
            self.screensaver_manager.enable()
            self.screensaver_manager = None
        app.widgetapp.window.menubar.show()
        self._video_details.show()
        _videobox_widget().show()
        _window().unfullscreen()
        self._widget.disconnect(self.motion_handler)
        _videobox_widget().disconnect(self.videobox_motion_handler)
        self.cancel_hide_controls()
        _window().window.set_cursor(None)
