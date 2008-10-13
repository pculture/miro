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

class VideoOpener (object):

    def __init__(self):
        self.cached_movie = None

    def can_open_file(self, path):
        threads.warn_if_not_on_main_thread('VideoOpener.can_open_file')
        can_open = False
        qtmovie = self.get_movie_from_file(path)

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
        if self.cached_movie is not None and self.cached_movie.attributeForKey_(QTMovieURLAttribute) == url:
            qtmovie = self.cached_movie
        else:
            if utils.get_pyobjc_major_version() == 2:
                qtmovie, error = QTMovie.alloc().initWithURL_error_(url, None)
            else:
                qtmovie, error = QTMovie.alloc().initWithURL_error_(url)
            self.cached_movie = qtmovie
        return qtmovie

    def reset(self):
        self.cached_movie = None

video_opener = VideoOpener()

###############################################################################

def can_play_file(path, yes_callback, no_callback):
    threads.warn_if_not_on_main_thread('video.can_play_file')
    if video_opener.can_open_file(path):
        yes_callback()
    else:
        no_callback()

###############################################################################

class VideoRenderer (Widget):

    def __init__(self):
        Widget.__init__(self)
        frame = ((0,0),(200,200))

        self.view = NSView.alloc().initWithFrame_(frame)

        self.video_view = QTMovieView.alloc().initWithFrame_(frame)
        self.video_view.setFillColor_(NSColor.blackColor())
        self.video_view.setControllerVisible_(NO)
        self.video_view.setEditable_(NO)
        self.video_view.setPreservesAspectRatio_(YES)

        self.video_window = VideoWindow.alloc().initWithContentRect_styleMask_backing_defer_(frame, NSBorderlessWindowMask, NSBackingStoreBuffered, NO)
        self.video_window.setContentView_(self.video_view)

        self.movie = None
        self.system_activity_updater_timer = None

    def calc_size_request(self):
        return (200,200)

    def place(self, rect, containing_view):
        Widget.place(self, rect, containing_view)
        self.view.window().addChildWindow_ordered_(self.video_window, NSWindowAbove)
        self.video_window.orderFront_(nil)
        self.adjust_video_frame()
        self.prevent_system_sleep(True)

    def teardown(self):
        self.reset()
        self.prevent_system_sleep(False)
        self.view.window().removeChildWindow_(self.video_window)
        self.video_window.close()
        self.video_window = None

    def reset(self):
        threads.warn_if_not_on_main_thread('VideoRenderer.reset')
        video_opener.reset()
        self.video_view.setMovie_(nil)
        self.movie_notifications = None
        self.movie = None

    def get_video_frame(self):
        frame = self.view.frame()
        frame.origin = self.view.convertPoint_toView_(NSZeroPoint, nil)
        frame.origin.x = 0
        frame.origin = self.view.window().convertBaseToScreen_(frame.origin)
        frame.size = (self.view.window().frame().size.width, frame.size.height)
        return frame

    def adjust_video_frame(self):
        frame = self.get_video_frame()
        self.video_window.setFrame_display_(frame, YES)

    def set_movie_item(self, item_info):
        threads.warn_if_not_on_main_thread('VideoRenderer.set_movie_item')
        qtmovie = video_opener.get_movie_from_file(item_info.video_path)
        self.reset()
        if qtmovie is not nil:
            self.movie = qtmovie
            self.video_view.setMovie_(self.movie)
            self.video_view.setNeedsDisplay_(YES)
            self.video_window.palette.setup(item_info, self)
            self.movie_notifications = NotificationForwarder.create(self.movie)
            self.movie_notifications.connect(self.handle_movie_notification, QTMovieDidEndNotification)

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
        self.movie.setVolume_(volume)
        self.video_window.palette.set_volume(volume)

    def play(self):
        threads.warn_if_not_on_main_thread('VideoRenderer.play')
        self.video_view.play_(nil)
        self.video_view.setNeedsDisplay_(YES)

    def play_from_time(self, resume_time=0):
        self.seek_to(resume_time / movieDuration(self.movie))
        self.play()

    def pause(self):
        threads.warn_if_not_on_main_thread('VideoRenderer.pause')
        self.video_view.pause_(nil)

    def stop(self):
        threads.warn_if_not_on_main_thread('VideoRenderer.stop')
        self.video_view.pause_(nil)
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
        self.palette = overlay.OverlayPalette.get_instance()
        self.setAcceptsMouseMovedEvents_(YES)
        self.is_fullscreen = False
        return self

    def close(self):
        self.palette.window().orderOut_(nil)
        self.palette = None
        super(VideoWindow, self).close()

    def canBecomeMainWindow(self):
        return NO

    def canBecomeKeyWindow(self):
        return NO

    def setFrame_display_(self, frame, display):
        super(VideoWindow, self).setFrame_display_(frame, display)
        if self.palette.window().isVisible():
            self.palette.adjustPosition(self)

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
        if event.type() == NSMouseMoved:
            if NSPointInRect(NSEvent.mouseLocation(), self.frame()):
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
