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

import os
import glob
import logging

from objc import YES, NO, nil, pathForFramework, loadBundleFunctions
from Foundation import *
from AppKit import *
from QTKit import *

from miro import app
from miro.plat import utils
from miro.plat import bundle
from miro.plat import qtcomp
from miro.plat.utils import filenameTypeToOSFilename
from miro.plat.frontends.widgets import threads
from miro.plat.frontends.widgets import overlay
from miro.plat.frontends.widgets import wrappermap
from miro.plat.frontends.widgets.base import Widget
from miro.plat.frontends.widgets.helpers import NotificationForwarder

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

def register_quicktime_components():
    bundlePath = bundle.getBundlePath()
    componentsDirectoryPath = os.path.join(bundlePath, 'Contents', 'Components')
    components = glob.glob(os.path.join(componentsDirectoryPath, '*.component'))
    for component in components:
        cmpName = os.path.basename(component)
        ok = qtcomp.register(component.encode('utf-8'))
        if ok:
            logging.info('Successfully registered embedded component: %s' % cmpName)
        else:
            logging.warn('Error while registering embedded component: %s' % cmpName)

###############################################################################

SUPPORTED_VIDEO_MEDIA_TYPES = (QTMediaTypeVideo, QTMediaTypeMPEG, QTMediaTypeMovie, QTMediaTypeFlash)
SUPPORTED_AUDIO_MEDIA_TYPES = (QTMediaTypeSound, QTMediaTypeMusic)
ALL_SUPPORTED_MEDIA_TYPES   = SUPPORTED_VIDEO_MEDIA_TYPES + SUPPORTED_AUDIO_MEDIA_TYPES

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

class VideoRenderer (Widget):

    def __init__(self):
        Widget.__init__(self)
        frame = ((0,0),(200,200))

        self.view = NSView.alloc().initWithFrame_(frame)

        self.video_view = MiroMovieView.alloc().initWithFrame_(frame)
        self.video_view.setFillColor_(NSColor.blackColor())
        self.video_view.setControllerVisible_(NO)
        self.video_view.setEditable_(NO)
        self.video_view.setPreservesAspectRatio_(YES)

        self.movie = None
        self.system_activity_updater_timer = None
        self.window_moved_handler = None
        self.item_changed_handler = None

    def calc_size_request(self):
        return (200,200)

    def viewport_created(self):
        self.video_window = VideoWindow.alloc().initWithContentRect_styleMask_backing_defer_(self.view.frame(), NSBorderlessWindowMask, NSBackingStoreBuffered, NO)
        self.video_window.setContentView_(self.video_view)

        self.view.window().addChildWindow_ordered_(self.video_window, NSWindowAbove)
        self.video_window.orderFront_(nil)
        self.adjust_video_frame()
        self.window_moved_handler = wrappermap.wrapper(self.view.window()).connect('did-move', self.on_window_moved)
        self.item_changed_handler = app.info_updater.connect('items-changed', self.on_items_changed)

    def place(self, rect, containing_view):
        Widget.place(self, rect, containing_view)
        self.adjust_video_frame()

    def on_window_moved(self, window):
        self.adjust_video_frame()

    def on_items_changed(self, controller, changed_items):
        self.video_window.on_items_changed(changed_items)
        
    def remove_viewport(self):
        app.info_updater.disconnect(self.item_changed_handler)
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
        threads.warn_if_not_on_main_thread('VideoRenderer.reset')
        self.video_view.setMovie_(nil)
        self.movie_notifications = None
        self.movie = None

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

    def can_open_file(self, qtmovie):
        threads.warn_if_not_on_main_thread('VideoRenderer.can_open_file')
        can_open = False

        # Purely referential movies have a no duration, no track and need to be
        # streamed first. Since we don't support this yet, we delegate the
        # streaming to the standalone QT player to avoid any problem (like the
        # crash in #944) by simply declaring that we can't play the corresponding item.
        # Note that once the movie is fully streamed and cached by QT, DTV will
        # be able to play it internally just fine -- luc

        # [UPDATE - 26 Feb, 2006]
        # Actually, streaming movies *can* have tracks as shown in #1124. We
        # therefore need to drill down and find out if we have a zero length
        # video track/media.

        if qtmovie is not nil and qtmovie.duration().timeValue > 0:
            allTracks = qtmovie.tracks()
            if len(qtmovie.tracks()) > 0:
                # First make sure we have at least one video track with a non zero length
                allMedia = [track.media() for track in allTracks]
                for media in allMedia:
                    mediaType = media.attributeForKey_(QTMediaTypeAttribute)
                    mediaDuration = media.attributeForKey_(QTMediaDurationAttribute).QTTimeValue().timeValue
                    if mediaType in ALL_SUPPORTED_MEDIA_TYPES and mediaDuration > 0:
                        can_open = True
                        break

        return can_open

    def get_movie_from_file(self, path):
        osfilename = filenameTypeToOSFilename(path)
        url = NSURL.fileURLWithPath_(osfilename)
        if utils.get_pyobjc_major_version() == 2:
            qtmovie, error = QTMovie.movieWithURL_error_(url, None)
        else:
            qtmovie, error = QTMovie.movieWithURL_error_(url)
        if not self.can_open_file(qtmovie):
            return nil
        return qtmovie

    def set_movie_item(self, item_info, callback, errback):
        threads.warn_if_not_on_main_thread('VideoRenderer.set_movie_item')
        self.video_window.setup(item_info, self)
        qtmovie = self.get_movie_from_file(item_info.video_path)
        self.reset()
        if qtmovie is not nil:
            self.movie = qtmovie
            self.video_view.setMovie_(self.movie)
            self.video_view.setNeedsDisplay_(YES)
            self.movie_notifications = NotificationForwarder.create(self.movie)
            self.movie_notifications.connect(self.handle_movie_notification, QTMovieDidEndNotification)
            callback()
        else:
            errback()

    def get_elapsed_playback_time(self):
        qttime = self.movie.currentTime()
        return _qttime2secs(qttime)

    def get_total_playback_time(self):
        return movieDuration(self.movie)

    def skip_forward(self):
        current = self.get_elapsed_playback_time()
        duration = self.get_total_playback_time()
        pos = min(duration, current + 30.0)
        self.seek_to(pos / duration)

    def skip_backward(self):
        current = self.get_elapsed_playback_time()
        duration = self.get_total_playback_time()
        pos = max(0, current - 15.0)
        self.seek_to(pos / duration)

    def set_volume(self, volume):
        if self.movie:
            self.movie.setVolume_(volume)
        if self.video_window:
            self.video_window.palette.set_volume(volume)

    def play(self):
        threads.warn_if_not_on_main_thread('VideoRenderer.play')
        self.video_view.play_(nil)
        self.video_view.setNeedsDisplay_(YES)
        self.prevent_system_sleep(True)

    def play_from_time(self, resume_time=0):
        self.seek_to(resume_time / movieDuration(self.movie))
        self.play()

    def pause(self):
        threads.warn_if_not_on_main_thread('VideoRenderer.pause')
        self.video_view.pause_(nil)
        self.prevent_system_sleep(True)

    def stop(self):
        threads.warn_if_not_on_main_thread('VideoRenderer.stop')
        self.prevent_system_sleep(True)
        self.video_view.pause_(nil)
        if self.video_window:
            self.video_window.palette.remove()
        self.reset()

    def set_playback_rate(self, rate):
        self.movie.setRate_(rate)

    def seek_to(self, position):
        qttime = self.movie.duration()
        qttime.timeValue = qttime.timeValue * position
        self.movie.setCurrentTime_(qttime)

    def enter_fullscreen(self):
        self.video_window.enter_fullscreen()

    def exit_fullscreen(self):
        frame = self.get_video_frame()
        self.video_window.exit_fullscreen(frame)

    def prepare_switch_to_attached_playback(self):
        app.widgetapp.window.nswindow.makeKeyAndOrderFront_(nil)

    def prepare_switch_to_detached_playback(self):
        pass

    def handle_movie_notification(self, notification):
        if notification.name() == QTMovieDidEndNotification and not app.playback_manager.is_suspended:
            app.playback_manager.on_movie_finished()

    def prevent_system_sleep(self, prevent):
        if prevent and self.system_activity_updater_timer is None:
            logging.debug("Launching system activity updater timer")
            self.system_activity_updater_timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                30,
                self.video_window,
                'updateSystemActivity:',
                nil,
                YES)
        elif self.system_activity_updater_timer is not None:
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

    def on_items_changed(self, changed_items):
        self.palette.on_items_changed(changed_items)

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

def _qttime2secs(qttime):
    if qttime.timeScale == 0:
        return 0.0
    return qttime.timeValue / float(qttime.timeScale)

def movieDuration(qtmovie):
    if qtmovie is nil:
        return 0
    qttime = qtmovie.duration()
    return _qttime2secs(qttime)
