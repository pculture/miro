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
    def can_play_file(self, path):
        return False

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

def can_play_file(path):
    if app.renderer is not None:
        return app.renderer.can_play_file(path)
    logging.warn("can_play_file: app.renderer is None")
    return False

class VideoWidget(Widget):
    def __init__(self):
        Widget.__init__(self)
        self.set_widget(gtk.DrawingArea())
        self._widget.set_double_buffered(False)
        self._widget.add_events(gtk.gdk.POINTER_MOTION_MASK)

class VideoDetailsWidget(Background):
    def __init__(self):
        Background.__init__(self)
        self.add(self.build_video_details())

    def build_video_details(self):
        h = HBox()

        # left side
        v = VBox()
        self.__item_name = Label("")
        self.__item_name.set_bold(True)
        self.__item_name.set_size(1.0)
        self.__item_name.set_color(WHITE)
        v.pack_start(_align_left(self.__item_name, left_pad=5))

        self.__channel_name = Label("")
        self.__channel_name.set_color(WHITE)
        v.pack_start(_align_left(self.__channel_name, left_pad=5))
        h.pack_start(v)

        # right side
        v = VBox()
        self.__email_link = ClickableLabel(_("Email a friend"))
        v.pack_start(_align_right(self.__email_link, right_pad=5))

        h2 = HBox()
        self.__comments_link = ClickableLabel(_("Comments"))
        h2.pack_start(_align_right(self.__comments_link, right_pad=10), expand=True)
        self.__permalink_link = ClickableLabel(_("Permalink"))
        h2.pack_start(_align_right(self.__permalink_link, right_pad=5))
        v.pack_start(h2)

        h2 = HBox()
        self.__expiration_label = Label("")
        self.__expiration_label.set_size(0.77)
        self.__expiration_label.set_color(WHITE)
        h2.pack_start(_align_right(self.__expiration_label, right_pad=15), expand=True)
        self.__keep_link = ClickableLabel(_("Keep"))
        h2.pack_start(_align_right(self.__keep_link, right_pad=5))
        self.__dash = Label("-")
        self.__dash.set_size(0.77)
        self.__dash.set_color(WHITE)
        h2.pack_start(_align_right(self.__dash, right_pad=5))
        self.__delete_link = ClickableLabel(_("Delete"))
        h2.pack_start(_align_right(self.__delete_link, right_pad=5))
        v.pack_start(h2)

        h.pack_start(_align_right(v), expand=True)
        return h

    def set_expiration_bits(self, item_info):
        self.__keep_link.disconnect_all()

        def handle_keep(widget):
            messages.KeepVideo(item_info.id).send_to_backend()
            self.__expiration_label.hide()
            self.__keep_link.hide()
            self.__dash.hide()

        if not item_info.is_external:
            if item_info.video_watched:
                if item_info.expiration_date is not None:
                    text = displaytext.expiration_date(item_info.expiration_date)
                    self.__expiration_label.set_text(text)
                    self.__keep_link.connect('clicked', handle_keep)
                    self.__keep_link.show()
                    self.__dash.show()
                else:
                    self.__expiration_label.hide()
                    self.__keep_link.hide()
                    self.__dash.hide()
            else:
                self.__expiration_label.hide()
                self.__keep_link.connect('clicked', handle_keep)
                self.__keep_link.show()
                self.__dash.show()

    def set_video_details(self, item_info):
        """This gets called when the item is set to play.  It should make
        no assumptions about the state of the video details prior to being
        called.
        """
        self.__item_name.set_text(util.clampText(item_info.name, 100))

        channels = app.tab_list_manager.feed_list.get_feeds()
        channels = [ci for ci in channels if ci.id == item_info.feed_id]
        if len(channels) == 0:
            logging.warn("item with a feed id that doesn't have a corresponding channel?")
            self.__channel_name.set_text("")
        else:
            self.__channel_name.set_text(util.clampText(channels[0].name, 100))

        for mem in [self.__email_link, self.__comments_link, self.__permalink_link,
                self.__delete_link]:
            mem.disconnect_all()

        def handle_email(widget):
            link = item_info.commentslink or item_info.permalink or item_info.file_url
            app.widgetapp.mail_to_friend(link, item_info.name)
        self.__email_link.connect('clicked', handle_email)

        if item_info.commentslink:
            def handle_commentslink(widget):
                app.widgetapp.open_url(item_info.commentslink)
            self.__comments_link.set_text(_("Comments"))
            self.__comments_link.connect('clicked', handle_commentslink)
        else:
            self.__comments_link.set_text("")

        if item_info.permalink:
            def handle_permalink(widget):
                app.widgetapp.open_url(item_info.permalink)
            self.__permalink_link.set_text(_("Permalink"))
            self.__permalink_link.connect('clicked', handle_permalink)
        else:
            self.__permalink_link.set_text("")

        def handle_delete(widget):
            self.__delete_link.on_leave_notify(None, None)
            app.widgetapp.on_stop_clicked(None)
            messages.DeleteVideo(item_info.id).send_to_backend()
        self.__delete_link.connect('clicked', handle_delete)

        self.set_expiration_bits(item_info)

    def draw(self, context, layout):
        context.set_color(BLACK)
        context.rectangle(0, 0, context.width, context.height)
        context.fill()

    def is_opaque(self):
        return True

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

        self.__video_widget = VideoWidget()
        self.pack_start(self.__video_widget, expand=True)

        self.__video_details = VideoDetailsWidget()
        self.pack_start(self.__video_details)

        self.renderer.set_widget(self.__video_widget._widget)
        self.hide_controls_timeout = None
        self.motion_handler = None
        self.videobox_motion_handler = None
        self.hidden_cursor = make_hidden_cursor()

    def teardown(self):
        self.renderer.reset()

    def set_movie_item(self, item_info):
        self.__video_details.set_video_details(item_info)
        self.renderer.select_file(item_info.video_path)

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
        self.renderer.stop()

    def set_playback_rate(self, rate):
        print "set_playback_rate: implement me!"

    def seek_to(self, position):
        time = self.get_total_playback_time() * position
        self.seek_to_time(time)

    def seek_to_time(self, time_pos):
        self.renderer.set_current_time(time_pos)

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

    def on_mouse_motion(self, widget, event):
        if not _videobox_widget().props.visible:
            self.show_controls()
            self.schedule_hide_controls(self.HIDE_CONTROLS_TIMEOUT)
        else:
            self.last_motion_time = time.time()

    def show_controls(self):
        _videobox_widget().show()
        _window().window.set_cursor(None)

    def on_hide_controls_timeout(self):
        # Check if the mouse moved before the timeout
        time_since_motion = int((time.time() - self.last_motion_time) * 1000)
        timeout_left = self.HIDE_CONTROLS_TIMEOUT - time_since_motion
        if timeout_left <= 0:
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
        _videobox_widget().show()
        _window().unfullscreen()
        self._widget.disconnect(self.motion_handler)
        _videobox_widget().disconnect(self.videobox_motion_handler)
        self.cancel_hide_controls()
        _window().window.set_cursor(None)
