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

"""video.py -- Video code. """

import time

import gobject
import gtk

from miro import app
from miro.gtcache import gettext as _
from miro import messages
from miro.plat.frontends.widgets import hidemouse
from miro.plat import resources
from miro.plat import screensaver
from miro.frontends.widgets.gtk import player
from miro.frontends.widgets.gtk.window import Window, WrappedWindow
from miro.frontends.widgets.gtk.widgetset import (
    Widget, VBox, Label, HBox, Alignment, Background, DrawingArea,
    ClickableImageButton)
from miro.plat.frontends.widgets import videoembed

BLACK = (0.0, 0.0, 0.0)
WHITE = (1.0, 1.0, 1.0)
GREEN = (159.0 / 255.0, 202.0 / 255.0, 120.0 / 255.0)

class ClickableLabel(Widget):
    """This is like a label and reimplements many of the Label things,
    but it's an EventBox with a Label child widget.
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
        self.wrapped_widget_connect('unmap', self.on_unmap)
        self.create_signal('clicked')

    def on_click(self, widget, event):
        self.emit('clicked')
        return True

    def on_enter_notify(self, widget, event):
        self._widget.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.HAND1))

    def on_leave_notify(self, widget, event):
        if self._widget.window:
            self._widget.window.set_cursor(None)

    def on_unmap(self, widget):
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


class NullRenderer:
    def __init__(self):
        pass

    def reset(self):
        pass



def make_label(text, handler, visible=True):
    if visible:
        lab = ClickableLabel(text)
        lab.connect('clicked', handler)
        return lab

    # if the widget isn't visible, then we stick in an empty string--we just
    # need a placeholder so that things don't move around when the item state
    # changes.
    lab = Label("")
    lab.set_size(0.77)
    return lab


def make_image_button(image_path, handler):
    b = ClickableImageButton(resources.path(image_path))
    b.connect('clicked', handler)
    return b


def _align_left(widget, top_pad=0, bottom_pad=0, left_pad=0, right_pad=0):
    """Align left and pad."""
    alignment = Alignment(0, 0, 0, 1)
    alignment.set_padding(top_pad, bottom_pad, left_pad, right_pad)
    alignment.add(widget)
    return alignment


def _align_right(widget, top_pad=0, bottom_pad=0, left_pad=0, right_pad=0):
    """Align right and pad."""
    alignment = Alignment(1, 0, 0, 1)
    alignment.set_padding(top_pad, bottom_pad, left_pad, right_pad)
    alignment.add(widget)
    return alignment


def _align_center(widget, top_pad=0, bottom_pad=0, left_pad=0, right_pad=0):
    """Align center (horizontally) and pad."""
    alignment = Alignment(0.5, 0, 0, 1)
    alignment.set_padding(top_pad, bottom_pad, left_pad, right_pad)
    alignment.add(widget)
    return alignment


def _align_middle(widget, top_pad=0, bottom_pad=0, left_pad=0, right_pad=0):
    """Align center (vertically) and pad."""
    alignment = Alignment(0, 0.5, 0, 0)
    alignment.set_padding(top_pad, bottom_pad, left_pad, right_pad)
    alignment.add(widget)
    return alignment


# Couple of utility functions to grab GTK widgets out of the widget
# tree for fullscreen code
def _videobox_widget():
    return app.widgetapp.window.videobox._widget


def _window():
    """Returns the window used for playback.  This is either the main window
    or the detached window.
    """
    if app.playback_manager.detached_window:
        return app.playback_manager.detached_window._window
    return app.widgetapp.window._window


class VideoOverlay(Window):
    def __init__(self):
        Window.__init__(self, 'Miro Video Overlay')
        self._window.set_transient_for(_window())
        self.vbox = VBox()
        self.set_content_widget(self.vbox)

    def _make_gtk_window(self):
        return WrappedWindow(gtk.WINDOW_POPUP)

    def position_on_screen(self):
        window = self._window
        parent_window = window.get_transient_for()
        screen = parent_window.get_screen()
        monitor = screen.get_monitor_at_window(parent_window.window)
        screen_rect = screen.get_monitor_geometry(monitor)
        my_width, my_height = self.vbox.get_size_request()
        window.set_default_size(my_width, my_height)
        window.resize(screen_rect.width, my_height)
        window.move(screen_rect.x, screen_rect.y + screen_rect.height -
                my_height)

class Divider(DrawingArea):
    def size_request(self, layout):
        return (1, 25)

    def draw(self, context, layout):
        context.set_line_width(1)
        context.set_color((46.0 / 255.0, 46.0 / 255.0, 46.0 / 255.0))
        context.move_to(0, 0)
        context.rel_line_to(0, context.height)
        context.stroke()

class VideoDetailsWidget(Background):
    def __init__(self):
        Background.__init__(self)
        self.item_info = None
        self._menu = None
        self.rebuild_video_details()
        self._delete_link = self._delete_image = None
        self._keep_link = self._keep_image = None
        self._will_play_handle = app.playback_manager.connect(
            'will-play', self.on_will_play)
        self._info_changed_handle = app.playback_manager.connect(
            'playing-info-changed', self.on_info_changed)

    def on_will_play(self, widget, duration):
        # we need to update the video details now that the file is
        # open and we know more about subtitle track info.
        self.rebuild_video_details()

    def on_info_changed(self, widget, item_info):
        self.item_info = item_info
        self.rebuild_video_details()

    def rebuild_video_details(self):
        # this removes the child widget if there is one
        self.remove()

        if not self.item_info:
            self.add(HBox())
            return

        left_side_hbox = HBox(5)
        right_side_hbox = HBox(5)

        # fullscreen
        if app.playback_manager.is_fullscreen:
            fullscreen_image = make_image_button(
                'images/fullscreen_exit.png', self.handle_fullscreen)
        else:
            fullscreen_image = make_image_button(
                'images/fullscreen_enter.png', self.handle_fullscreen)

        fullscreen_link = make_label(_("Fullscreen"), self.handle_fullscreen)
        left_side_hbox.pack_start(_align_middle(fullscreen_image))
        left_side_hbox.pack_start(_align_middle(fullscreen_link))

        left_side_hbox.pack_start(_align_middle(
                Divider(), top_pad=3, bottom_pad=3, left_pad=5, right_pad=5))

        if app.playback_manager.detached_window is not None:
            pop_link = make_label(
                _("Pop-in"), self.handle_popin_popout)
            # FIXME - need popin image
            pop_image = make_image_button(
                'images/popin.png', self.handle_popin_popout)
        else:
            pop_link = make_label(
                _("Pop-out"), self.handle_popin_popout)
            pop_image = make_image_button(
                'images/popout.png', self.handle_popin_popout)

        left_side_hbox.pack_start(_align_middle(pop_image))
        left_side_hbox.pack_start(_align_middle(pop_link))

        left_side_hbox.pack_start(_align_middle(
                Divider(), top_pad=3, bottom_pad=3, left_pad=5, right_pad=5))


        right_side_hbox.pack_start(_align_middle(
                Divider(), top_pad=3, bottom_pad=3, left_pad=5, right_pad=5))

        right_side_hbox.pack_start(self.make_subtitles_button())

        right_side_hbox.pack_start(_align_middle(
                Divider(), top_pad=3, bottom_pad=3, left_pad=5, right_pad=5))

        self._delete_image = make_image_button(
            'images/delete.png', self.handle_delete)
        right_side_hbox.pack_start(_align_middle(self._delete_image))
        self._delete_link = make_label(_("Delete"), self.handle_delete)
        right_side_hbox.pack_start(_align_middle(self._delete_link))
        if self.item_info.can_be_saved: # keepable
            self._keep_image = make_image_button(
                'images/keep-button.png', self.handle_keep)
            right_side_hbox.pack_start(_align_middle(self._keep_image))
            self._keep_link = make_label(_("Keep"), self.handle_keep)
            right_side_hbox.pack_start(_align_middle(self._keep_link))

        outer_hbox = HBox()
        outer_hbox.pack_start(_align_left(left_side_hbox, left_pad=10),
                              expand=True)
        outer_hbox.pack_start(_align_right(right_side_hbox, right_pad=10))
        self.add(outer_hbox)

        # self.add(_align_right(outer_hbox, left_pad=15, right_pad=15))


    def make_subtitles_button(self):
        hbox = HBox(5)

        current_track = app.video_renderer.get_enabled_subtitle_track()

        # None, -1 and 0 all mean there is no current track.
        if current_track is not None and current_track > 0:
            ccimage = 'images/cc-on.png'
            cccolor = GREEN
            cctext = _("Subtitles On")

        else:
            tracks = app.video_renderer.get_subtitle_tracks()
            if tracks is not None and len(tracks) > 0:
                ccimage = 'images/cc-available.png'
                cctext = _("Subtitles Found")
                cccolor = WHITE
            else:
                ccimage = 'images/cc-available.png'
                cctext = _("Subtitles")
                cccolor = WHITE

        cc_image_button = make_image_button(ccimage, self.handle_subtitles)
        hbox.pack_start(_align_middle(cc_image_button))
        subtitles_link = make_label(cctext, self.handle_subtitles)
        subtitles_link.set_color(cccolor)
        hbox.pack_start(_align_middle(subtitles_link))

        subtitles_image = make_image_button(
            'images/subtitles_down.png', self.handle_subtitles)
        hbox.pack_start(_align_middle(subtitles_image))
        return hbox

    def hide(self):
        self._widget.hide()

    def show(self):
        self._widget.show()

    def handle_fullscreen(self, widget):
        app.playback_manager.toggle_fullscreen()

    def handle_popin_popout(self, widget):
        if app.playback_manager.is_fullscreen:
            app.playback_manager.exit_fullscreen()
        app.playback_manager.toggle_detached_mode()

    def handle_keep(self, widget):
        messages.KeepVideo(self.item_info.id).send_to_backend()
        self._widget.window.set_cursor(None)
        self.reset()
        self.rebuild_video_details()

    def handle_delete(self, widget):
        item_info = self.item_info
        app.widgetapp.remove_items([item_info])
        self.reset()

    def handle_subtitles(self, widget):
        tracks = []
        self._menu = gtk.Menu()

        tracks = app.video_renderer.get_subtitle_tracks()

        if len(tracks) == 0:
            child = gtk.MenuItem(_("None Available"))
            child.set_sensitive(False)
            child.show()
            self._menu.append(child)
        else:
            enabled_track = app.video_renderer.get_enabled_subtitle_track()

            first_child = None
            for i, lang in tracks:
                child = gtk.RadioMenuItem(first_child, lang)
                if enabled_track == i:
                    child.set_active(True)
                child.connect('activate', self.handle_subtitle_change, i)
                child.show()
                self._menu.append(child)
                if first_child == None:
                    first_child = child

            sep = gtk.SeparatorMenuItem()
            sep.show()
            self._menu.append(sep)

            child = gtk.RadioMenuItem(first_child, _("Disable Subtitles"))
            if enabled_track == -1:
                child.set_active(True)
            child.connect('activate', self.handle_disable_subtitles)
            child.show()
            self._menu.append(child)

        sep = gtk.SeparatorMenuItem()
        sep.show()
        self._menu.append(sep)

        child = gtk.MenuItem(_("Select a Subtitles file..."))
        child.set_sensitive(app.playback_manager.is_playing_video)
        child.connect('activate', self.handle_select_subtitle_file)
        child.show()
        self._menu.append(child)

        self._menu.popup(None, None, None, 1, gtk.get_current_event_time())

    def subtitles_menu_shown(self):
        return self._menu and self._menu.get_property('visible')

    def handle_disable_subtitles(self, widget):
        if widget.active:
            app.video_renderer.disable_subtitles()
            app.menu_manager.update_menus('playback-changed')
            self.rebuild_video_details()

    def handle_subtitle_change(self, widget, index):
        if widget.active:
            app.video_renderer.set_subtitle_track(index)
            app.menu_manager.update_menus('playback-changed')
            self.rebuild_video_details()

    def handle_select_subtitle_file(self, widget):
        app.playback_manager.open_subtitle_file()

    def handle_commentslink(self, widget, event):
        app.widgetapp.open_url(self.item_info.comments_link)

    def handle_share(self, widget, event):
        app.widgetapp.share_item(self.item_info)

    def handle_permalink(self, widget, event):
        app.widgetapp.open_url(self.item_info.permalink)

    def update_info(self, item_info):
        self.item_info = item_info
        self.rebuild_video_details()

    def set_video_details(self, item_info):
        """This gets called when the item is set to play.  It should make
        no assumptions about the state of the video details prior to being
        called.
        """
        self.update_info(item_info)

    def draw(self, context, layout):
        context.set_color(BLACK)
        context.rectangle(0, 0, context.width, context.height)
        context.fill()
        context.set_color((46.0 / 255.0, 46.0 / 255.0, 46.0 / 255.0))
        context.set_line_width(1)
        context.move_to(0, 0)
        context.rel_line_to(context.width, 0)
        context.stroke()

    def is_opaque(self):
        return True

    def reset(self):
        if self._delete_link:
            self._delete_link.on_leave_notify(None, None)
        if self._delete_image:
            self._delete_image.on_leave_notify(None, None)
        if self._keep_link:
            self._keep_link.on_leave_notify(None, None)
        if self._keep_image:
            self._keep_image.on_leave_notify(None, None)

class VideoPlayer(player.GTKPlayer, VBox):
    """Video renderer widget.

    Note: ``app.video_renderer`` must be initialized before
    instantiating this class.  If no renderers can be found, set
    ``app.video_renderer`` to ``None``.
    """
    HIDE_CONTROLS_TIMEOUT = 2000

    def __init__(self):
        player.GTKPlayer.__init__(self, app.video_renderer)
        VBox.__init__(self)

        self.overlay = None
        self.screensaver_manager = None

        self._video_widget = videoembed.VideoWidget(self.renderer)
        self.pack_start(self._video_widget, expand=True)

        self._video_details = VideoDetailsWidget()
        self.pack_start(self._video_details)

        self.hide_controls_timeout = None

        self._video_widget.connect('double-click', self.on_double_click)
        self._video_widget.connect('mouse-motion', self.on_mouse_motion)

    def teardown(self):
        # remove the our embedding widget from the hierarchy
        self.remove(self._video_widget)
        # now that we aren't showing a video widget, we can reset playback
        self.renderer.reset()
        self._video_widget.destroy()
        # remove callbacks
        self._video_widget.disconnect_all()
        # dereference VideoWidget
        self._video_widget = None

    def update_for_presentation_mode(self, mode):
        pass

    def set_item(self, item_info, success_callback, error_callback):
        self._video_details.set_video_details(item_info)
        self.renderer.select_file(item_info, success_callback, error_callback)

    def get_elapsed_playback_time(self):
        return self.renderer.get_current_time()

    def get_total_playback_time(self):
        return self.renderer.get_duration()

    def set_volume(self, volume):
        self.renderer.set_volume(volume)

    def play(self):
        self.renderer.play()
        # do this to trigger the overlay showing up for a smidge
        self.on_mouse_motion(None)

    def play_from_time(self, resume_time=0):
        # FIXME: this overrides the default implementation.  The reason
        # is going through the default implementation it requires the total
        # time and it may not be ready at this point.
        self.seek_to_time(resume_time)
        self.play()

    def pause(self):
        self.renderer.pause()

    def stop(self, will_play_another=False):
        self._video_details.reset()
        self.renderer.stop()

    def set_playback_rate(self, rate):
        self.renderer.set_rate(rate)

    def seek_to(self, position):
        duration = self.get_total_playback_time()
        if duration is None:
            return
        self.seek_to_time(duration * position)

    def seek_to_time(self, time_pos):
        self.renderer.set_current_time(time_pos)

    def enter_fullscreen(self):
        self.screensaver_manager = screensaver.create_manager(
                app.widgetapp.window._window)
        if self.screensaver_manager is not None:
            self.screensaver_manager.disable()
        self.rebuild_video_details()
        self._make_overlay()
        self.overlay._window.connect('motion-notify-event',
                self.on_motion_notify)
        if not app.playback_manager.detached_window:
            app.widgetapp.window.menubar._widget.hide()
        self.schedule_hide_controls(self.HIDE_CONTROLS_TIMEOUT)
        # Need to call set_decorated() before fullscreen.  See #10810.
        _window().set_decorated(False)
        _window().fullscreen()

    def _make_overlay(self):
        main_window = app.widgetapp.window
        main_window.main_vbox.remove(main_window.controls_hbox)
        self.overlay = VideoOverlay()
        self.remove(self._video_details)
        self.overlay.vbox.pack_start(self._video_details)
        self.overlay.vbox.pack_start(main_window.controls_hbox)
        self.overlay.position_on_screen()
        self.overlay.show()

    def _destroy_overlay(self):
        if self.overlay:
            main_window = app.widgetapp.window
            self.overlay.vbox.remove(self._video_details)
            self.overlay.vbox.remove(main_window.controls_hbox)
            self.pack_start(self._video_details)
            main_window.main_vbox.pack_start(main_window.controls_hbox)

            self.overlay.destroy()
            self.overlay = None

    def rebuild_video_details(self):
        self._video_details.rebuild_video_details()

    def prepare_switch_to_attached_playback(self):
        gobject.timeout_add(0, self.rebuild_video_details)

    def prepare_switch_to_detached_playback(self):
        gobject.timeout_add(0, self.rebuild_video_details)

    def on_double_click(self, widget):
        app.playback_manager.toggle_fullscreen()

    def on_motion_notify(self, widget, event):
        self.on_mouse_motion(widget)

    def on_mouse_motion(self, widget):
        if not self.overlay:
            return
        if not self.overlay.is_visible():
            show_it_all = False

            # NOTE: this code wasn't working when I went through the
            # windows overhaul, so I just left it commented out.  Will says we
            # should eventually implement this.
            #
            #if event is None:
                #show_it_all = True
            #else:
                # figures out the monitor that miro is fullscreened on and
                # gets the monitor geometry for that.
                # if app.playback_manager.detached_window is not None:
                    # gtkwindow = app.playback_manager.detached_window._window
                # else:
                    # gtkwindow = app.widgetapp.window._window
                # gdkwindow = gtkwindow.window
                # screen = gtkwindow.get_screen()

                # monitor = screen.get_monitor_at_window(gdkwindow)
                # monitor_geom = screen.get_monitor_geometry(monitor)
                # if event.y > monitor_geom.height - 200:
                    # show_it_all = True

                # Hack to fix #17213.  Eventually we should remove this and
                # uncomment the code above to implement #8655
                #show_it_all = True
            show_it_all = True

            if show_it_all:
                self.show_controls()
            else:
                self.show_mouse()
            self.schedule_hide_controls(self.HIDE_CONTROLS_TIMEOUT)
        else:
            self.last_motion_time = time.time()

    def hide_mouse(self):
        hidemouse.hide(_window().window)

    def show_mouse(self):
        hidemouse.unhide(_window().window)

    def show_controls(self):
        self.show_mouse()
        self.overlay.show()

    def hide_controls(self):
        self.hide_mouse()
        if self.overlay and self.overlay.is_visible():
            self.overlay.close()

    def on_hide_controls_timeout(self):
        # Check if the mouse moved before the timeout
        if self._video_details.subtitles_menu_shown():
            self.schedule_hide_controls(self.HIDE_CONTROLS_TIMEOUT)
            return

        time_since_motion = int((time.time() - self.last_motion_time) * 1000)
        timeout_left = self.HIDE_CONTROLS_TIMEOUT - time_since_motion
        if timeout_left <= 0:
            self.hide_controls()
            self.hide_controls_timeout = None
        else:
            self.schedule_hide_controls(timeout_left)

    def cancel_hide_controls(self):
        if self.hide_controls_timeout is not None:
            gobject.source_remove(self.hide_controls_timeout)

    def schedule_hide_controls(self, time):
        if self.hide_controls_timeout is not None:
            gobject.source_remove(self.hide_controls_timeout)
        self.hide_controls_timeout = gobject.timeout_add(time,
                self.on_hide_controls_timeout)
        self.last_motion_time = 0

    def exit_fullscreen(self):
        if self.screensaver_manager is not None:
            self.screensaver_manager.enable()
            self.screensaver_manager = None
        app.widgetapp.window.menubar._widget.show()
        self.rebuild_video_details()
        self._video_details.show()
        self._destroy_overlay()
        _window().unfullscreen()
        # Undo above call to set_decorated()
        _window().set_decorated(True)
        self.cancel_hide_controls()
        self.show_mouse()

    def select_subtitle_file(self, sub_path, handle_successful_select):
        app.video_renderer.select_subtitle_file(
            app.playback_manager.get_playing_item(),
            sub_path,
            handle_successful_select)

    def select_subtitle_encoding(self, encoding):
        app.video_renderer.select_subtitle_encoding(encoding)

    def get_subtitle_tracks(self):
        return self.renderer.get_subtitle_tracks()

    def get_enabled_subtitle_track(self):
        return self.renderer.get_enabled_audio_track()

    def set_subtitle_track(self, track_index):
        if track_index is not None:
            self.renderer.set_subtitle_track(track_index)
        else:
            self.renderer.disable_subtitles()
