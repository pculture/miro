# Miro - an RSS based video player application
# Copyright (C) 2005-2009 Participatory Culture Foundation
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

import time

from objc import nil, YES, NO, IBOutlet
from AppKit import *
from Foundation import *
from PyObjCTools import AppHelper

from miro import app
from miro import messages
from miro.gtcache import gettext as _
from miro.plat import resources
from miro.plat.frontends.widgets import threads
from miro.plat.frontends.widgets import drawing

###############################################################################

class OverlayPaletteWindow (NSWindow):

    def initWithContentRect_styleMask_backing_defer_(self, rect, style, backing, defer):
        self = super(OverlayPaletteWindow, self).initWithContentRect_styleMask_backing_defer_(
            rect,
            NSBorderlessWindowMask,
            backing,
            defer )
        self.setBackgroundColor_(NSColor.clearColor())
        self.setAlphaValue_(1.0)
        self.setOpaque_(NO)
        return self

    def canBecomeKeyWindow(self):
        return NO

    def canBecomeMainWindow(self):
        return NO

###############################################################################

overlay = None

class OverlayPalette (NSWindowController):
    
    titleLabel          = IBOutlet('titleLabel')
    feedLabel           = IBOutlet('feedLabel')
    shareButton         = IBOutlet('shareButton')
    keepButton          = IBOutlet('keepButton')
    deleteButton        = IBOutlet('deleteButton')
    fsButton            = IBOutlet('fsButton')
    popInOutButton      = IBOutlet('popInOutButton')
    popInOutLabel       = IBOutlet('popInOutLabel')
    
    playbackControls    = IBOutlet('playbackControls')
    playPauseButton     = IBOutlet('playPauseButton')
    progressSlider      = IBOutlet('progressSlider')
    seekBackwardButton  = IBOutlet('seekBackwardButton')
    skipBackwardButton  = IBOutlet('skipBackwardButton')
    seekForwardButton   = IBOutlet('seekForwardButton')
    skipForwardButton   = IBOutlet('skipForwardButton')
    timeIndicator       = IBOutlet('timeIndicator')
    volumeSlider        = IBOutlet('volumeSlider')
    
    HOLD_TIME = 2

    @classmethod
    def get_instance(cls):
        global overlay
        if overlay is None:
            overlay = OverlayPalette.alloc().init()
        return overlay

    def init(self):
        self = super(OverlayPalette, self).initWithWindowNibName_owner_('OverlayPalette', self)
        self.item_info = None
        self.autoHidingTimer = nil
        self.updateTimer = nil
        self.holdStartTime = 0.0
        self.renderer = None
        self.wasPlaying = False
        self.revealing = False
        self.hiding = False
        self.anim = None
        self.in_fullscreen = False

        app.playback_manager.connect('will-play', self.video_will_play)
        app.playback_manager.connect('will-pause', self.video_will_pause)

        return self

    def awakeFromNib(self):
        self.shareButton.setImage_(getOverlayButtonImage(self.shareButton.bounds().size))
        self.shareButton.setAlternateImage_(getOverlayButtonAlternateImage(self.shareButton.bounds().size))
        self.shareButton.setTitle_(_("Share"))

        self.keepButton.setImage_(getOverlayButtonImage(self.keepButton.bounds().size))
        self.keepButton.setAlternateImage_(getOverlayButtonAlternateImage(self.keepButton.bounds().size))
        self.keepButton.setTitle_(_("Keep"))

        self.deleteButton.setImage_(getOverlayButtonImage(self.deleteButton.bounds().size))
        self.deleteButton.setAlternateImage_(getOverlayButtonAlternateImage(self.deleteButton.bounds().size))
        self.deleteButton.setTitle_(_("Delete"))

        self.seekForwardButton.setCell_(SkipSeekButtonCell.cellFromButtonCell_direction_delay_(self.seekForwardButton.cell(), 1, 0.0))
        self.seekForwardButton.cell().setAllowsSkipping(False)
        self.seekBackwardButton.setCell_(SkipSeekButtonCell.cellFromButtonCell_direction_delay_(self.seekBackwardButton.cell(), -1, 0.0))
        self.seekBackwardButton.cell().setAllowsSkipping(False)

        self.progressSlider.cursor = NSImage.imageNamed_(u'fs-progress-slider')
        self.progressSlider.sliderWasClicked = self.progressSliderWasClicked
        self.progressSlider.sliderWasDragged = self.progressSliderWasDragged
        self.progressSlider.sliderWasReleased = self.progressSliderWasReleased
        self.progressSlider.setShowCursor_(True)

        self.volumeSlider.cursor = NSImage.imageNamed_(u'fs-volume-slider')
        self.volumeSlider.sliderWasClicked = self.volumeSliderWasClicked
        self.volumeSlider.sliderWasDragged = self.volumeSliderWasDragged
        self.volumeSlider.setShowCursor_(True)

    def setup(self, item_info, renderer, video_window):
        from miro.frontends.widgets import widgetutil
        self.item_info = item_info
        self.renderer = renderer
        self.titleLabel.setStringValue_(item_info.name)
        try:
            self.feedLabel.setStringValue_(widgetutil.get_feed_info(item_info.feed_id).name)
        except:
            self.feedLabel.setStringValue_("")
        self.keepButton.setEnabled_(item_info.can_be_saved)
        self.shareButton.setEnabled_(item_info.has_sharable_url)
        self.adjustContent(video_window, False)
        self.update_(nil)
        self.suspendAutoHiding()
        self.reveal(video_window)

    def on_items_changed(self, changed):
        for item_info in changed:
            if item_info.id == self.item_info.id:
                self.keepButton.setEnabled_(item_info.can_be_saved)
                self.shareButton.setEnabled_(item_info.has_sharable_url)
                self.update_(nil)
                
    def enter_fullscreen(self, videoWindow):
        self.in_fullscreen = True
        if self.window().isVisible():
            self.adjustContent(videoWindow, True)
        else:
            NSCursor.setHiddenUntilMouseMoves_(YES)

    def exit_fullscreen(self, videoWindow):
        self.in_fullscreen = False
        if self.window().isVisible():
            self.adjustContent(videoWindow, True)

    def getHorizontalPosition(self, videoWindow, width):
        parentFrame = videoWindow.frame()
        return parentFrame.origin.x + ((parentFrame.size.width - width) / 2.0)

    def adjustPosition(self, videoWindow):
        parentFrame = videoWindow.frame()
        x = self.getHorizontalPosition(videoWindow, self.window().frame().size.width)
        y = parentFrame.origin.y + 60
        self.window().setFrameOrigin_(NSPoint(x, y))

    def adjustContent(self, videoWindow, animate):
        if videoWindow.is_fullscreen:
            self.popInOutButton.setHidden_(YES)
            self.popInOutLabel.setHidden_(YES)
            self.fsButton.setImage_(NSImage.imageNamed_('fs-button-exitfullscreen'))
            self.fsButton.setAlternateImage_(NSImage.imageNamed_('fs-button-exitfullscreen-alt'))
        else:
            if app.playback_manager.detached_window is None:
                image_path = resources.path('images/popout.png')
                label = _('Pop Out')
            else:
                image_path = resources.path('images/popin.png')
                label = _('Pop In')
            self.popInOutButton.setImage_(NSImage.alloc().initWithContentsOfFile_(image_path))
            self.popInOutButton.setHidden_(NO)
            self.popInOutLabel.setHidden_(NO)
            self.popInOutLabel.setStringValue_(label)
            self.fsButton.setImage_(NSImage.imageNamed_('fs-button-enterfullscreen'))
            self.fsButton.setAlternateImage_(NSImage.imageNamed_('fs-button-enterfullscreen-alt'))

        newFrame = self.window().frame() 
        if videoWindow.is_fullscreen or app.playback_manager.detached_window is not None: 
            self.titleLabel.setHidden_(NO)
            self.feedLabel.setHidden_(NO)
            newFrame.size.height = 198 
        else: 
            self.titleLabel.setHidden_(YES)
            self.feedLabel.setHidden_(YES)
            newFrame.size.height = 144
        newFrame.origin.x = self.getHorizontalPosition(videoWindow, newFrame.size.width)
        self.window().setFrame_display_animate_(newFrame, YES, animate)
        self.playbackControls.setNeedsDisplay_(YES)

    def fit_in_video_window(self, video_window):
        return self.window().frame().size.width <= video_window.frame().size.width

    def reveal(self, videoWindow):
        threads.warn_if_not_on_main_thread('OverlayPalette.reveal')
        self.resetAutoHiding()
        if (not self.window().isVisible() and not self.revealing) or (self.window().isVisible() and self.hiding):
            self.update_(nil)
            if self.renderer.movie is not None:
                self.volumeSlider.setFloatValue_(self.renderer.movie.volume())

            self.adjustPosition(videoWindow)
            self.adjustContent(videoWindow, False)

            if self.hiding and self.anim is not None:
                self.anim.stopAnimation()
                self.hiding = False
            else:
                self.window().setAlphaValue_(0.0)

            self.window().orderFront_(nil)
            videoWindow.parentWindow().addChildWindow_ordered_(self.window(), NSWindowAbove)

            self.revealing = True
            params = {NSViewAnimationTargetKey: self.window(), NSViewAnimationEffectKey: NSViewAnimationFadeInEffect}
            self.animate(params, 0.3)
        else:
            self.resumeAutoHiding()
    
    def hide(self):
        threads.warn_if_not_on_main_thread('OverlayPalette.hide')
        if not self.hiding:
            if self.autoHidingTimer is not nil:
                self.autoHidingTimer.invalidate()
                self.autoHidingTimer = nil

            if self.revealing and self.anim is not None:
                self.anim.stopAnimation()
                self.revealing = False

            self.hiding = True
            params = {NSViewAnimationTargetKey: self.window(), NSViewAnimationEffectKey: NSViewAnimationFadeOutEffect}
            self.animate(params, 0.5)
    
    def hideAfterDelay_(self, timer):
        if time.time() - self.holdStartTime > self.HOLD_TIME:
            self.hide()
    
    def resetAutoHiding(self):
        self.holdStartTime = time.time()
    
    def suspendAutoHiding(self):
        if self.autoHidingTimer is not nil:
            self.autoHidingTimer.invalidate()
            self.autoHidingTimer = nil
    
    def resumeAutoHiding(self):
        self.resetAutoHiding()
        if self.autoHidingTimer is None:
            self.autoHidingTimer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                1.0, self, 'hideAfterDelay:', nil, YES)
    
    def animate(self, params, duration):
        self.anim = NSViewAnimation.alloc().initWithDuration_animationCurve_(duration, 0)
        self.anim.setViewAnimations_(NSArray.arrayWithObject_(params))
        self.anim.setDelegate_(self)
        self.anim.startAnimation()

    def animationDidEnd_(self, anim):
        parent = self.window().parentWindow()
        if self.revealing:
            self.resumeAutoHiding()
            self.updateTimer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                0.5, self, 'update:', nil, YES)
            NSRunLoop.currentRunLoop().addTimer_forMode_(self.updateTimer, NSEventTrackingRunLoopMode)
            self.update_(nil)
            if parent is not None and self.in_fullscreen:
                NSCursor.setHiddenUntilMouseMoves_(NO)
        elif self.hiding:
            if parent is not None and self.in_fullscreen:
                NSCursor.setHiddenUntilMouseMoves_(YES)
            self.remove()

        self.anim = None
        self.revealing = False
        self.hiding = False
    
    def set_volume(self, volume):
        self.volumeSlider.setFloatValue_(volume)
    
    def keep_(self, sender):
        messages.KeepVideo(self.item_info.id).send_to_backend()
    
    def expireNow_(self, sender):
        item_info = self.item_info
        app.playback_manager.on_movie_finished()
        app.widgetapp.remove_items([item_info])
        
    def share_(self, sender):
        item_info = self.item_info
        app.widgetapp.share_item(item_info)
    
    def handleShareItem_(self, sender):
        pass

    def toggleFullScreen_(self, sender):
        app.playback_manager.toggle_fullscreen()

    def toggleAttachedDetached_(self, sender):
        app.playback_manager.toggle_detached_mode()

    def skipBackward_(self, sender):
        app.playback_manager.play_prev_movie()

    def fastBackward_(self, sender):
        self.fastSeek(-1)

    def skipForward_(self, sender):
        app.playback_manager.play_next_movie()

    def fastForward_(self, sender):
        self.fastSeek(1)

    def fastSeek(self, direction):
        rate = 3 * direction
        app.playback_manager.set_playback_rate(rate)
        self.suspendAutoHiding()

    def stopSeeking(self):
        rate = 1.0
        if app.playback_manager.is_paused:
            rate = 0.0
        app.playback_manager.set_playback_rate(rate)
        self.resumeAutoHiding()

    def stop_(self, sender):
        self.remove()
        app.playback_manager.stop()

    def playPause_(self, sender):
        app.playback_manager.play_pause()

    def update_(self, timer):
        if self.renderer.movie is None:
            return
        elapsed = self.renderer.get_elapsed_playback_time()
        total = self.renderer.get_total_playback_time()
        progress = u"%d:%02d" % divmod(int(round(elapsed)), 60)
        self.timeIndicator.setStringValue_(progress)
        self.progressSlider.setFloatValue_(elapsed / total)
            
    def progressSliderWasClicked(self, slider):
        if app.playback_manager.is_playing:
            self.wasPlaying = True
            self.renderer.pause()
        app.playback_manager.seek_to(slider.floatValue())
        self.resetAutoHiding()
        
    def progressSliderWasDragged(self, slider):
        app.playback_manager.seek_to(slider.floatValue())
        self.resetAutoHiding()
        
    def progressSliderWasReleased(self, slider):
        if self.wasPlaying:
            self.wasPlaying = False
            self.renderer.play()

    def volumeSliderWasDragged(self, slider):
        volume = slider.floatValue()
        app.playback_manager.set_volume(volume)
        app.widgetapp.window.videobox.volume_slider.set_value(volume)
        self.resetAutoHiding()

    def volumeSliderWasClicked(self, slider):
        self.volumeSliderWasDragged(slider)

    def video_will_play(self, obj, duration):
        self.playPauseButton.setImage_(NSImage.imageNamed_(u'fs-button-pause'))
        self.playPauseButton.setAlternateImage_(NSImage.imageNamed_(u'fs-button-pause-alt'))

    def video_will_pause(self, obj):
        self.playPauseButton.setImage_(NSImage.imageNamed_(u'fs-button-play'))
        self.playPauseButton.setAlternateImage_(NSImage.imageNamed_(u'fs-button-play-alt'))

    def remove(self):
        threads.warn_if_not_on_main_thread('OverlayPalette.remove')
        self.suspendAutoHiding()
        if self.updateTimer is not nil:
            self.updateTimer.invalidate()
            self.updateTimer = nil
        if self.window().parentWindow() is not nil:
            self.window().parentWindow().removeChildWindow_(self.window())
        self.window().orderOut_(nil)

###############################################################################

class OverlayPaletteView (NSView):

    def drawRect_(self, rect):
        radius = 8
        lineWidth = 2
        rect = NSInsetRect(self.frame(), radius+lineWidth, radius+lineWidth)
        
        path = NSBezierPath.bezierPath()
        path.appendBezierPathWithArcWithCenter_radius_startAngle_endAngle_(NSPoint(NSMinX(rect), NSMinY(rect)), radius, 180.0, 270.0)
        path.appendBezierPathWithArcWithCenter_radius_startAngle_endAngle_(NSPoint(NSMaxX(rect), NSMinY(rect)), radius, 270.0, 360.0)
        path.appendBezierPathWithArcWithCenter_radius_startAngle_endAngle_(NSPoint(NSMaxX(rect), NSMaxY(rect)), radius,   0.0,  90.0)
        path.appendBezierPathWithArcWithCenter_radius_startAngle_endAngle_(NSPoint(NSMinX(rect), NSMaxY(rect)), radius,  90.0, 180.0)
        path.closePath()
        
        transform = NSAffineTransform.transform()
        transform.translateXBy_yBy_(0.5, 0.5)
        path.transformUsingAffineTransform_(transform)
        
        NSColor.colorWithDeviceWhite_alpha_(0.0, 0.6).set()
        path.fill()
        
        NSColor.colorWithDeviceWhite_alpha_(1.0, 0.6).set()
        path.setLineWidth_(lineWidth)
        path.stroke()

###############################################################################

class OverlayPaletteControlsView (NSView):

    def drawRect_(self, rect):
        bounds = self.bounds()
        NSColor.colorWithDeviceWhite_alpha_(1.0, 0.6).set()

        path = NSBezierPath.bezierPath()
        path.moveToPoint_(NSPoint(0.5, 0.5))
        path.relativeLineToPoint_(NSPoint(bounds.size.width, 0))
        path.setLineWidth_(2)
        path.stroke()

        if app.playback_manager.is_fullscreen or app.playback_manager.detached_window is not None:
            path = NSBezierPath.bezierPath()
            path.moveToPoint_(NSPoint(0.5, bounds.size.height-1.5))
            path.relativeLineToPoint_(NSPoint(bounds.size.width, 0))
            path.setLineWidth_(2)
            path.stroke()
        
    def hitTest_(self, point):
        # Our buttons have transparent parts, but we still want mouse clicks
        # to be detected if they happen there, so we override hit testing and
        # simply test for button frames.
        for subview in self.subviews():
            if NSPointInRect(self.convertPoint_fromView_(point, nil), subview.frame()):
                return subview
        return self

###############################################################################

class Slider (NSView):

    def initWithFrame_(self, frame):
        self = super(Slider, self).initWithFrame_(frame)
        self.value = 0.0
        self.showCursor = False
        self.dragging = False
        self.sliderWasClicked = None
        self.sliderWasDragged = None
        self.sliderWasReleased = None
        return self

    def setFloatValue_(self, value):
        threads.warn_if_not_on_main_thread('Slider.setFloatValue_')
        self.value = value
        self.setNeedsDisplay_(YES)
        
    def floatValue(self):
        return self.value

    def setShowCursor_(self, showCursor):
        self.showCursor = showCursor

    def drawRect_(self, rect):
        if self.showCursor:
            self.drawTrack()
            self.drawCursor()

    def drawTrack(self):
        pass

    def drawCursor(self):
        x = self.getCursorPosition()
        self.cursor.compositeToPoint_operation_((abs(x)+0.5, 0), NSCompositeSourceOver)

    def getCursorPosition(self):
        return (self.bounds().size.width - self.cursor.size().width) * self.value

    def mouseDown_(self, event):
        if self.showCursor:
            location = self.convertPoint_fromView_(event.locationInWindow(), nil)
            if NSPointInRect(location, self.bounds()):
                self.dragging = True
                self.setFloatValue_(self.getValueForClickLocation(location))
                if self.sliderWasClicked is not None:
                    self.sliderWasClicked(self)

    def mouseDragged_(self, event):
        if self.showCursor and self.dragging:
            location = self.convertPoint_fromView_(event.locationInWindow(), nil)
            self.setFloatValue_(self.getValueForClickLocation(location))
            if self.sliderWasDragged is not None:
                self.sliderWasDragged(self)

    def mouseUp_(self, event):
        if self.showCursor:
            self.dragging = False
            if self.sliderWasReleased is not None:
                self.sliderWasReleased(self)
            self.setNeedsDisplay_(YES)

    def getValueForClickLocation(self, location):
        min = self.cursor.size().width / 2.0
        max = self.bounds().size.width - min
        span = max - min
        offset = location.x
        if offset < min:
            offset = min
        elif offset > max:
            offset = max
        return (offset - min) / span

class OverlayPaletteSlider (Slider):

    def drawTrack(self):
        from miro.frontends.widgets import widgetutil
        rect = self.bounds()
        ctx = drawing.DrawingContext(self, rect, rect)
        ctx.set_color((1,1,1), 0.4)
        widgetutil.circular_rect(ctx, 0, 2, rect.size.width, rect.size.height - 4)
        ctx.fill()

###############################################################################

class SkipSeekButtonCell (NSButtonCell):

    @classmethod
    def cellFromButtonCell_direction_delay_(self, cell, direction, delay):
        newCell = SkipSeekButtonCell.alloc().initWithPrimaryAction_direction_delay_(cell.action(), direction, delay)
        newCell.setType_(cell.type())
        newCell.setBezeled_(cell.isBezeled())
        newCell.setBezelStyle_(cell.bezelStyle())
        newCell.setBordered_(cell.isBordered())
        newCell.setTransparent_(cell.isTransparent())
        newCell.setImage_(cell.image())
        newCell.setAlternateImage_(cell.alternateImage())
        newCell.setState_(cell.state())
        newCell.setHighlightsBy_(cell.highlightsBy())
        newCell.setShowsStateBy_(cell.showsStateBy())
        newCell.setEnabled_(cell.isEnabled())
        newCell.setTarget_(cell.target())
        newCell.setAction_(nil)
        return newCell
    
    def initWithPrimaryAction_direction_delay_(self, action, direction, delay):
        self = NSButtonCell.init(self)
        self.primaryAction = action
        self.direction = direction
        self.seekTimer = nil
        self.seekDelay = delay
        self.allowSkipping = True
        self.allowSeeking = True
        return self
    
    def setAllowsFastSeeking(self, allow):
        self.allowSeeking = allow
    
    def setAllowsSkipping(self, allow):
        self.allowSkipping = allow
    
    def trackMouse_inRect_ofView_untilMouseUp_(self, event, frame, control, untilMouseUp):
        if self.allowSeeking:
            if self.seekDelay > 0.0:
                self.seekTimer = NSTimer.timerWithTimeInterval_target_selector_userInfo_repeats_(self.seekDelay, self, 'fastSeek:', nil, NO)
                NSRunLoop.currentRunLoop().addTimer_forMode_(self.seekTimer, NSEventTrackingRunLoopMode)
            else:
                self.fastSeek_(nil)

        mouseIsUp = NSButtonCell.trackMouse_inRect_ofView_untilMouseUp_(self, event, frame, control, YES)

        if self.seekTimer is not nil or not self.allowSeeking:
            self.resetSeekTimer()
            control.sendAction_to_(self.primaryAction, self.target())
        else:
            self.target().stopSeeking()
            
        return mouseIsUp

    def fastSeek_(self, timer):
        self.target().fastSeek(self.direction)
        self.resetSeekTimer()
    
    def resetSeekTimer(self):
        if self.seekTimer is not nil:
            self.seekTimer.invalidate()
            self.seekTimer = nil

###############################################################################

def getOverlayButtonImage(size):
    fillColor = NSColor.colorWithDeviceWhite_alpha_(190.0/255.0, 0.8)
    strokeColor = NSColor.colorWithDeviceWhite_alpha_(76.0/255.0, 0.8)
    return makeOverlayButtonImage(size, fillColor, strokeColor)

def getOverlayButtonAlternateImage(size):
    fillColor = NSColor.colorWithDeviceWhite_alpha_(220.0/255.0, 0.8)
    strokeColor = NSColor.colorWithDeviceWhite_alpha_(106.0/255.0, 0.8)
    return makeOverlayButtonImage(size, fillColor, strokeColor)

def makeOverlayButtonImage(size, fillColor, strokeColor):
    radius = (size.height-1) / 2.0
    path = NSBezierPath.bezierPath()
    path.appendBezierPathWithArcWithCenter_radius_startAngle_endAngle_(NSPoint(radius+1.5, radius+0.5), radius, 90.0, 270.0)
    path.appendBezierPathWithArcWithCenter_radius_startAngle_endAngle_(NSPoint(size.width - radius - 1.5, radius+0.5), radius, 270.0, 90.0)
    path.closePath()

    image = NSImage.alloc().initWithSize_(size)
    image.lockFocus()
    
    fillColor.set()
    path.fill()
    strokeColor.set()
    path.stroke()
    
    image.unlockFocus()
    return image
