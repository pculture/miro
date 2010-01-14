# Miro - an RSS based video player application
# Copyright (C) 2005-2010 Participatory Culture Foundation
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

import logging

from objc import YES, NO, nil, pathForFramework, loadBundleFunctions
from Foundation import *
from AppKit import *
from QTKit import *

from miro import app
from miro.plat.frontends.widgets import mediatypes
from miro.plat.frontends.widgets import threads
from miro.plat.frontends.widgets import overlay
from miro.plat.frontends.widgets import quicktime
from miro.plat.frontends.widgets import wrappermap
from miro.plat.frontends.widgets.base import Widget

###############################################################################
#### Dynamically link some specific Carbon functions which we need but     ####
###  which are not available in the default MacPython                      ####
###############################################################################

kUIModeNormal = 0
kUIModeAllHidden = 3

carbonPath = pathForFramework('/System/Library/Frameworks/Carbon.framework')
carbonBundle = NSBundle.bundleWithPath_(carbonPath)
loadBundleFunctions(carbonBundle, globals(), ((u'SetSystemUIMode', 'III'),))

OverallActivity = 0

coreServicesPath = pathForFramework('/System/Library/Frameworks/CoreServices.framework')
coreServicesBundle = NSBundle.bundleWithPath_(coreServicesPath)
loadBundleFunctions(coreServicesBundle, globals(), ((u'UpdateSystemActivity', 'IC'),))

###############################################################################

SUPPORTED_MEDIA_TYPES = mediatypes.VIDEO_MEDIA_TYPES

###############################################################################

class MiroMovieView (QTMovieView):
    
    def movieBounds(self):
        movie = self.movie()
        if movie is not None and app.playback_manager.presentation_mode != 'fit-to-bounds':
            my_bounds = self.bounds()
            natural_size = movie.attributeForKey_(QTMovieNaturalSizeAttribute).sizeValue()

            if app.playback_manager.presentation_mode == 'natural-size':
                movie_size = natural_size
            elif app.playback_manager.presentation_mode == 'half-size':
                movie_size = NSSize(natural_size.width/2, natural_size.height/2)
            elif app.playback_manager.presentation_mode == 'double-size':
                movie_size = NSSize(natural_size.width*2, natural_size.height*2)
            if movie_size.width > my_bounds.size.width or movie_size.height > my_bounds.size.height:
                return QTMovieView.movieBounds(self)

            movie_origin = NSPoint(int((my_bounds.size.width - movie_size.width) / 2), 
                                   int((my_bounds.size.height - movie_size.height) / 2))
            return NSRect(movie_origin, movie_size)

        return QTMovieView.movieBounds(self)

###############################################################################

class VideoPlayer (Widget, quicktime.Player):

    def __init__(self):
        quicktime.Player.__init__(self, SUPPORTED_MEDIA_TYPES)
        Widget.__init__(self)

        frame = ((0,0),(200,200))

        self.view = NSView.alloc().initWithFrame_(frame)

        self.video_view = MiroMovieView.alloc().initWithFrame_(frame)
        self.video_view.setFillColor_(NSColor.blackColor())
        self.video_view.setControllerVisible_(NO)
        self.video_view.setEditable_(NO)
        self.video_view.setPreservesAspectRatio_(YES)

        self.movie = None
        self.movie_notifications = None
        self.system_activity_updater_timer = None
        self.window_moved_handler = None
        self.item_changed_handler = None

    def calc_size_request(self):
        return (200,200)

    def viewport_created(self):
        self.video_window = VideoWindow.alloc().initWithContentRect_styleMask_backing_defer_(self.view.frame(), NSBorderlessWindowMask, NSBackingStoreBuffered, NO)
        self.video_window.setContentView_(self.video_view)

        self.adjust_video_frame()
        self.view.window().addChildWindow_ordered_(self.video_window, NSWindowAbove)
        self.video_window.orderFront_(nil)
        self.window_moved_handler = wrappermap.wrapper(self.view.window()).connect('did-move', self.on_window_moved)
        app.info_updater.item_changed_callbacks.add('manual', 'playback-list', self.on_items_changed)

    def place(self, rect, containing_view):
        Widget.place(self, rect, containing_view)
        self.adjust_video_frame()

    def on_window_moved(self, window):
        self.adjust_video_frame()

    def on_items_changed(self, message):
        if self.video_window is not None:
            self.video_window.on_items_changed(message.changed)
        
    def remove_viewport(self):
        app.info_updater.item_changed_callbacks.remove('manual', 'playback-list', self.on_items_changed)
        self.item_changed_handler = None
        self.prevent_system_sleep(False)
        self.detach_from_parent_window()
        self.video_window.close()
        self.video_window = None
        Widget.remove_viewport(self)

    def teardown(self):
        pass

    def detach_from_parent_window(self):
        window = self.view.window()
        window.removeChildWindow_(self.video_window)
        wrappermap.wrapper(window).disconnect(self.window_moved_handler)
        self.window_moved_handler = None

    def reset(self):
        self.video_view.setMovie_(nil)
        quicktime.Player.reset(self)

    def get_video_frame(self):
        frame = self.view.frame()
        frame.origin = self.view.convertPoint_toView_(NSZeroPoint, nil)
        frame.origin.x = 0
        frame.origin = self.view.window().convertBaseToScreen_(frame.origin)
        frame.size = NSSize(self.view.window().frame().size.width, frame.size.height)
        return frame

    def adjust_video_frame(self):
        frame = self.get_video_frame()
        self.video_window.setFrame_display_(frame, YES)

    def update_for_presentation_mode(self, mode):
        frame = self.video_view.frame()
        self.video_view.setFrame_(NSOffsetRect(frame, 1, 1))
        self.video_view.setFrame_(frame)

    def set_item(self, item_info, callback, errback):
        def callback2():
            self.video_view.setMovie_(self.movie)
            self.video_view.setNeedsDisplay_(YES)
            self.video_window.setup(item_info, self)
            callback()
        quicktime.Player.set_item(self, item_info, callback2, errback)

    def set_volume(self, volume):
        quicktime.Player.set_volume(self, volume)
        if self.video_window:
            self.video_window.palette.set_volume(volume)

    def play(self):
        threads.warn_if_not_on_main_thread('VideoPlayer.play')
        self.video_view.play_(nil)
        self.video_view.setNeedsDisplay_(YES)
        self.prevent_system_sleep(True)

    def pause(self):
        threads.warn_if_not_on_main_thread('VideoPlayer.pause')
        self.video_view.pause_(nil)
        self.prevent_system_sleep(True)

    def stop(self, will_play_another=False):
        threads.warn_if_not_on_main_thread('VideoPlayer.stop')
        self.prevent_system_sleep(True)
        self.video_view.pause_(nil)
        if self.video_window and not will_play_another:
            self.video_window.palette.remove()
        self.reset()

    def enter_fullscreen(self):
        self.video_window.enter_fullscreen()

    def exit_fullscreen(self):
        frame = self.get_video_frame()
        self.video_window.exit_fullscreen(frame)

    def prepare_switch_to_attached_playback(self):
        self.video_window.palette.remove()
        app.widgetapp.window.nswindow.makeKeyAndOrderFront_(nil)

    def prepare_switch_to_detached_playback(self):
        self.video_window.palette.remove()

    def prevent_system_sleep(self, prevent):
        if prevent and self.system_activity_updater_timer is None:
            logging.debug("Launching system activity updater timer")
            self.system_activity_updater_timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                30,
                self.video_window,
                'updateSystemActivity:',
                nil,
                YES)
        elif not prevent and self.system_activity_updater_timer is not None:
            logging.debug("Stopping system activity updater timer")
            self.system_activity_updater_timer.invalidate()
            self.system_activity_updater_timer = None

###############################################################################

class VideoWindow (NSWindow):

    def initWithContentRect_styleMask_backing_defer_(self, rect, style, backing, defer):
        self = super(VideoWindow, self).initWithContentRect_styleMask_backing_defer_(rect,  style, backing, defer)
        self.setBackgroundColor_(NSColor.blackColor())
        self.setReleasedWhenClosed_(NO)
        self.setAcceptsMouseMovedEvents_(YES)
        self.palette = overlay.OverlayPalette.get_instance()
        self.is_fullscreen = False
        return self

    def close(self):
        self.palette.window().orderOut_(nil)
        self.palette = None
        super(VideoWindow, self).close()

    def on_items_changed(self, changed):
        if self.palette is not None:
            self.palette.on_items_changed(changed)

    def canBecomeMainWindow(self):
        return NO

    def canBecomeKeyWindow(self):
        return NO

    def setFrame_display_(self, frame, display):
        super(VideoWindow, self).setFrame_display_(frame, display)
        if self.palette.window().isVisible():
            self.palette.adjustPosition(self)
            if not self.palette.fit_in_video_window(self):
                self.palette.remove()

    def setup(self, item_info, renderer):
        self.palette.setup(item_info, renderer, self)

    def enter_fullscreen(self):
        NSCursor.setHiddenUntilMouseMoves_(YES)
        screens = NSScreen.screens()
        if len(screens) > 0:
            screenWithMenuBar = screens[0]
            if self.screen() == screenWithMenuBar:
                SetSystemUIMode(kUIModeAllHidden, 0)
        self.setFrame_display_animate_(self.screen().frame(), YES, YES)
        self.is_fullscreen = True
        self.palette.enter_fullscreen(self)

    def exit_fullscreen(self, frame):
        NSCursor.setHiddenUntilMouseMoves_(NO)
        self.is_fullscreen = False
        self.palette.exit_fullscreen(self)
        self.setFrame_display_animate_(frame, YES, YES)
        SetSystemUIMode(kUIModeNormal, 0)

    def updateSystemActivity_(self, timer):
        UpdateSystemActivity(OverallActivity)

    def sendEvent_(self, event):
        if self.parentWindow() is None:
            # We've been detached since the event was fired.  Just ignore it.
            return

        if event.type() == NSMouseMoved:
            if NSPointInRect(event.locationInWindow(), self.contentView().bounds()) and self.palette.fit_in_video_window(self):
                self.palette.reveal(self)
        elif event.type() == NSLeftMouseDown:
            if NSApplication.sharedApplication().isActive():
                if event.clickCount() > 1:
                    app.playback_manager.toggle_fullscreen()
                elif not self.parentWindow().isMainWindow():
                    self.parentWindow().makeKeyAndOrderFront_(nil)
            else:
                NSApplication.sharedApplication().activateIgnoringOtherApps_(YES)
        else:
            #super(VideoWindow, self).sendEvent_(event)
            self.parentWindow().sendEvent_(event)

###############################################################################
