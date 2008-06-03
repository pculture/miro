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

import time
import logging

import objc
from objc import YES, NO, nil, IBOutlet
from AppKit import *
from Foundation import *
from QTKit import QTMovieDidEndNotification

from miro import app
from miro import eventloop
from miro.plat import bundle
from miro.plat.filenames import filenameTypeToOSFilename
from miro.frontends.html.displaybase import VideoDisplayBase
from miro.frontends.html.templatedisplay import ModelActionHandler
from miro.plat.frontends.html import threads
from miro.frontends.html.playbackcontroller import PlaybackControllerBase
from miro.plat.frontends.html.MainFrame import Slider, handleKey
from miro.plat.renderers.QuicktimeRenderer import QuicktimeRenderer

###############################################################################
#### Dynamically link some specific Carbon functions which we need but     ####
###  which are not available in the default MacPython                      ####
###############################################################################

kUIModeNormal = 0
kUIModeAllHidden = 3

carbonPath = objc.pathForFramework('/System/Library/Frameworks/Carbon.framework')
carbonBundle = NSBundle.bundleWithPath_(carbonPath)
objc.loadBundleFunctions(carbonBundle, globals(), ((u'SetSystemUIMode', 'III'),))

OverallActivity = 0

coreServicesPath = objc.pathForFramework('/System/Library/Frameworks/CoreServices.framework')
coreServicesBundle = NSBundle.bundleWithPath_(coreServicesPath)
objc.loadBundleFunctions(coreServicesBundle, globals(), ((u'UpdateSystemActivity', 'IC'),))

###############################################################################

class PlaybackController (PlaybackControllerBase):
    
    def playItemExternallyByID(self, itemID):
        item = PlaybackControllerBase.playItemExternallyByID(self, itemID)
        moviePath = item.getVideoFilename()
        moviePath = filenameTypeToOSFilename(moviePath)

        ws = NSWorkspace.sharedWorkspace()
        ok, externalApp, movieType = ws.getInfoForFile_application_type_(moviePath)
        if ok:
            if externalApp == bundle.getBundlePath():
                print 'WARNING, trying to play movie externally with ourselves.'
                ok = False
            else:
                ok = ws.openFile_withApplication_andDeactivate_(moviePath, nil, YES)

        if not ok:
            logging.warn("movie %s could not be externally opened" % moviePath)

###############################################################################

class VideoDisplay (VideoDisplayBase):
    "Video player shown in a MainFrame's right-hand pane."

    def __init__(self):
        VideoDisplayBase.__init__(self)
        self.controller = VideoDisplayController.getInstance()
        self.controller.videoDisplay = self
        self.nextItem = None
        self.nextRenderer = None

    def initRenderers(self):
        app.renderers.append(QuicktimeRenderer(self.controller))

    def setRendererAndCallback(self, anItem, internal, external):
        for renderer in app.renderers:
            if renderer.canPlayFile(anItem.getVideoFilename()):
                self.selectItem(anItem, renderer)
                internal()
                return
        external()

    def setExternal(self, external):
        VideoDisplayBase.setExternal(self, external)
        if external:
            self.controller.enableExternalPlaybackControls()

    def selectItem(self, item, renderer):
        VideoDisplayBase.selectItem(self, item, renderer)
        # We can't select the item in the display controller
        # until we've initialized the display, so we store it here
        self.nextItem = item
        self.nextRenderer = renderer
 
    def play(self):
        VideoDisplayBase.play(self)
        self.controller.selectItem(self.nextItem, self.nextRenderer)
        self.controller.play()

    def playFromTime(self, startTime):
        VideoDisplayBase.playFromTime(self, startTime)
        self.controller.selectItem(self.nextItem, self.nextRenderer)
        self.controller.play()

    def pause(self):
        VideoDisplayBase.pause(self)
        self.controller.pause()

    def stop(self):
        VideoDisplayBase.stop(self)
        self.controller.stop()
    
    def goFullScreen(self):
        VideoDisplayBase.goFullScreen(self)
        self.controller.goFullScreen()

    def exitFullScreen(self):
        VideoDisplayBase.exitFullScreen(self)
        self.controller.exitFullScreen()

    def setVolume(self, level):
        VideoDisplayBase.setVolume(self, level)
        self.controller.setVolume(level)

    def muteVolume(self):
        VideoDisplayBase.muteVolume(self)
        self.controller.volumeSlider.setEnabled_(NO)

    def restoreVolume(self):
        VideoDisplayBase.restoreVolume(self)
        self.controller.volumeSlider.setEnabled_(YES)

    def onSelected(self, frame):
        VideoDisplayBase.onSelected(self, frame)
        self.controller.onSelected()

    def onDeselected(self, frame):
        VideoDisplayBase.onDeselected(self, frame)
        self.controller.onDeselected()

    def getView(self):
        return self.controller.rootView

###############################################################################

class VideoDisplayController (NSObject):

    backwardButton      = IBOutlet('backwardButton')
    forwardButton       = IBOutlet('forwardButton')
    muteButton          = IBOutlet('muteButton')
    playPauseButton     = IBOutlet('playPauseButton')
    stopButton          = IBOutlet('stopButton')
    progressDisplayer   = IBOutlet('progressDisplayer')
    rootView            = IBOutlet('rootView')
    volumeSlider        = IBOutlet('volumeSlider')
    videoAreaView       = IBOutlet('videoAreaView')

    _instance = nil

    @classmethod
    def getInstance(self):
        assert VideoDisplayController._instance is not nil
        return VideoDisplayController._instance

    def awakeFromNib(self):
        VideoDisplayController._instance = self
        self.forwardButton.setCell_(SkipSeekButtonCell.cellFromButtonCell_direction_delay_(self.forwardButton.cell(), 1, 0.5))
        self.backwardButton.setCell_(SkipSeekButtonCell.cellFromButtonCell_direction_delay_(self.backwardButton.cell(), -1, 0.5))
        self.muteButton.setEnabled_(YES)
        self.volumeSlider.setEnabled_(YES)
        nc = NSNotificationCenter.defaultCenter()
        nc.addObserver_selector_name_object_(
            self, 
            'handleWatchableDisplayNotification:', 
            u'notifyPlayable', 
            nil)
        nc.addObserver_selector_name_object_(
            self, 
            'handleNonWatchableDisplayNotification:', 
            u'notifyNotPlayable', 
            nil)
        self.systemActivityUpdaterTimer = nil
        self.reset()

    @threads.onMainThread
    def onSelected(self):
        self.enableSecondaryControls(YES)
        self.preventSystemSleep(True)
        NSNotificationCenter.defaultCenter().postNotificationName_object_('VideoDisplayWasSelected', nil)

    @threads.onMainThread
    def onDeselected(self):
        self.enableSecondaryControls(NO)
        self.preventSystemSleep(False)
        self.videoAreaView.teardown()
        self.progressDisplayer.teardown()
        self.reset()
        NSNotificationCenter.defaultCenter().postNotificationName_object_('VideoDisplayWasDeselected', nil)

    def selectItem(self, item, renderer):
        self.videoAreaView.setup(item, renderer)
        self.progressDisplayer.setup(renderer)

    def reset(self):
        self.currentWatchableDisplay = None

    def preventSystemSleep(self, prevent):
        if prevent and self.systemActivityUpdaterTimer is nil:
            logging.debug("Launching system activity updater timer")
            self.systemActivityUpdaterTimer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(30, self, 'updateSystemActivity:', nil, YES)
        elif self.systemActivityUpdaterTimer is not nil:
            logging.debug("Stopping system activity updater timer")
            self.systemActivityUpdaterTimer.invalidate()
            self.systemActivityUpdaterTimer = nil

    def updateSystemActivity_(self, timer):
        UpdateSystemActivity(OverallActivity)

    def enablePrimaryControls(self, enabled):
        self.playPauseButton.setEnabled_(enabled)

    def enableSecondaryControls(self, enabled, allowFastSeeking=YES):
        self.backwardButton.setEnabled_(enabled)
        self.backwardButton.cell().setAllowsFastSeeking(allowFastSeeking)
        self.stopButton.setEnabled_(enabled or app.htmlapp.videoDisplay.isExternal)
        self.forwardButton.setEnabled_(enabled)
        self.forwardButton.cell().setAllowsFastSeeking(allowFastSeeking)

    def enableExternalPlaybackControls(self):
        self.stopButton.setEnabled_(True)
        self.playPauseButton.setEnabled_(False)
        self.backwardButton.setEnabled_(False)
        self.forwardButton.setEnabled_(False)

    def updatePlayPauseButton(self, prefix):
        self.playPauseButton.setImage_(NSImage.imageNamed_(u'%s' % prefix))
        self.playPauseButton.setAlternateImage_(NSImage.imageNamed_(u'%s_active' % prefix))

    def playPause_(self, sender):
        eventloop.addUrgentCall(lambda:app.htmlapp.playbackController.playPause(), "Play Video")

    @threads.onMainThread
    def play(self):
        nc = NSNotificationCenter.defaultCenter()
        nc.postNotificationName_object_(u'videoWillPlay', nil)
        self.enablePrimaryControls(YES)
        self.enableSecondaryControls(YES)
        self.updatePlayPauseButton('pause')

    @threads.onMainThread
    def pause(self):
        nc = NSNotificationCenter.defaultCenter()
        nc.postNotificationName_object_(u'videoWillPause', nil)
        self.updatePlayPauseButton('play')

    def stop_(self, sender):
        eventloop.addUrgentCall(lambda:app.htmlapp.playbackController.stop(), "Stop Video")
    
    @threads.onMainThread
    def stop(self):
        nc = NSNotificationCenter.defaultCenter()
        nc.postNotificationName_object_(u'videoWillStop', nil)
        self.updatePlayPauseButton('play')

    def playFullScreen_(self, sender):
        def performInEventLoop():
            if not app.htmlapp.videoDisplay.isPlaying:
                app.htmlapp.playbackController.playPause()
            self.videoDisplay.goFullScreen()
        eventloop.addUrgentCall(lambda:performInEventLoop(), "Play Video Fullscreen")

    def toggleFullScreen_(self, sender):
        self.videoAreaView.toggleFullScreen_(sender)

    @threads.onMainThread
    def goFullScreen(self):
        self.videoAreaView.enterFullScreen()

    def exitFullScreen_(self, sender):
        self.exitFullScreen()

    @threads.onMainThread
    def exitFullScreen(self):
        self.videoAreaView.exitFullScreen()

    def skipForward_(self, sender):
        eventloop.addUrgentCall(lambda:app.htmlapp.playbackController.skip(1), "Skip Forward")

    def fastForward_(self, sender):
        self.fastSeek(1)

    def skipBackward_(self, sender):
        eventloop.addUrgentCall(lambda:app.htmlapp.playbackController.skip(-1), "Skip Backward")

    def fastBackward_(self, sender):
        self.fastSeek(-1)

    def fastSeek(self, direction):
        if not self.videoDisplay.isPlaying:
            self.updatePlayPauseButton('pause')
        rate = 3 * direction
        self.videoDisplay.activeRenderer.setRate(rate)

    def stopSeeking(self):
        rate = 1.0
        if not self.videoDisplay.isPlaying:
            rate = 0.0
            self.updatePlayPauseButton('play')
        if self.videoDisplay.activeRenderer is not None:
            self.videoDisplay.activeRenderer.setRate(rate)

    def setVolume_(self, sender):
        self.videoDisplay.setVolume(sender.floatValue())

    @threads.onMainThread
    def setVolume(self, level):
        if self.muteButton.state() == NSOnState:
            self.volumeSlider.setFloatValue_(level)
            self.videoAreaView.videoWindow.palette.volumeSlider.setFloatValue_(level)

    def muteUnmuteVolume_(self, sender):
        if sender.state() is NSOffState:
            self.videoDisplay.muteVolume()
        else:
            self.videoDisplay.restoreVolume()

    def handleWatchableDisplayNotification_(self, notification):
        self.enablePrimaryControls(YES)
        self.enableSecondaryControls(self.videoDisplay.isPlaying)

    def handleNonWatchableDisplayNotification_(self, notification):
        self.enablePrimaryControls(NO)
        self.enableSecondaryControls(NO)
    
    def handleMovieNotification_(self, notification):
        renderer = self.videoDisplay.activeRenderer
        if notification.name() == QTMovieDidEndNotification and not renderer.interactivelySeeking:
            eventloop.addUrgentCall(lambda:app.htmlapp.playbackController.onMovieFinished(), "Movie Finished Callback")

###############################################################################

class VideoAreaView (NSView):
    
    videoWindow = IBOutlet('videoWindow')
    
    def setup(self, item, renderer):
        if not self.videoWindow.isFullScreen:
            self.adjustVideoWindowFrame()
        self.window().setAcceptsMouseMovedEvents_(YES)
        self.videoWindow.setup(renderer, item)
        self.activateVideoWindow()
        nc = NSNotificationCenter.defaultCenter()
        nc.addObserver_selector_name_object_(self, 
                                             'windowDidMove:', 
                                             NSWindowDidMoveNotification, 
                                             self.window())
        nc.addObserver_selector_name_object_(self, 
                                             'windowWillClose:', 
                                             NSWindowWillCloseNotification, 
                                             self.window())
        nc.addObserver_selector_name_object_(self, 
                                             'windowDidBecomeKey:', 
                                             NSWindowDidBecomeKeyNotification, 
                                             self.window())
        
    def teardown(self):
        threads.warnIfNotOnMainThread('VideoAreaView.teardown')
        nc = NSNotificationCenter.defaultCenter()
        nc.removeObserver_name_object_(self, nil, nil)
        if self.videoWindow.isFullScreen:
            self.videoWindow.exitFullScreen()
        self.window().setAcceptsMouseMovedEvents_(NO)
        self.window().removeChildWindow_(self.videoWindow)
        self.videoWindow.orderOut_(nil)
        self.videoWindow.teardown()

    def keyDown_(self, event):
        handleKey(event)

    def mouseMoved_(self, event):
        self.videoWindow.sendEvent_(event)

    @threads.onMainThreadWaitingUntilDone
    def activateVideoWindow(self):
        if self.window().isMiniaturized():
            self.window().deminiaturize_(nil)
        self.window().orderFront_(nil)
        self.window().makeFirstResponder_(self)
        if self.videoWindow.parentWindow() is nil:
            self.window().addChildWindow_ordered_(self.videoWindow, NSWindowAbove)
        self.videoWindow.orderFront_(nil)
    
    def drawRect_(self, rect):
        NSColor.blackColor().set()
        NSRectFill(rect)
    
    @threads.onMainThreadWaitingUntilDone
    def adjustVideoWindowFrame(self):
        if self.window() is nil:
            return
        frame = self.frame()
        frame.origin = self.convertPoint_toView_(NSZeroPoint, nil)
        frame.origin.x = 0
        frame.origin = self.window().convertBaseToScreen_(frame.origin)
        frame.size = NSSize(self.window().frame().size.width, frame.size.height)
        self.videoWindow.setFrame_display_(frame, YES)
        
    def setFrame_(self, frame):
        super(VideoAreaView, self).setFrame_(frame)
        self.adjustVideoWindowFrame()

    def windowDidMove_(self, notification):
        self.adjustVideoWindowFrame()
    
    def windowWillClose_(self, notification):
        eventloop.addUrgentCall(app.htmlapp.videoDisplay.pause, "Pause Playback")
        self.window().removeChildWindow_(self.videoWindow)
        self.videoWindow.orderOut_(nil)
    
    def windowDidBecomeKey_(self, notification):
        if not self.videoWindow.isFullScreen:
            self.adjustVideoWindowFrame()
        self.window().makeKeyAndOrderFront_(nil)
    
    def toggleFullScreen_(self, sender):
        self.videoWindow.toggleFullScreen_(sender)
    
    @threads.onMainThread
    def enterFullScreen(self):
        self.adjustVideoWindowFrame()
        if self.window() is not nil:
            self.videoWindow.enterFullScreen(self.window().screen())

    @threads.onMainThread
    def exitFullScreen(self):
        if self.videoWindow.isFullScreen:
            self.videoWindow.exitFullScreen()
            self.window().makeKeyWindow()
    

###############################################################################

class VideoWindow (NSWindow):
    
    palette = IBOutlet('palette')
    
    def initWithContentRect_styleMask_backing_defer_(self, rect, style, backing, defer):
        self = super(VideoWindow, self).initWithContentRect_styleMask_backing_defer_(
            rect,
            NSBorderlessWindowMask,
            backing,
            defer )
        self.setBackgroundColor_(NSColor.blackColor())
        self.isFullScreen = NO
        return self

    def setFrame_display_(self, frame, display):
        super(VideoWindow, self).setFrame_display_(frame, display)
        if self.palette.isVisible():
            self.palette.adjustPosition(self)

    def setup(self, renderer, item):
        self.installRendererView_(renderer.view)
        self.palette.setup(item, renderer)
    
    def teardown(self):
        threads.warnIfNotOnMainThread('VideoWindow.teardown')
        self.palette.remove()
        self.setContentView_(nil)

    @threads.onMainThreadWaitingUntilDone
    def installRendererView_(self, view):
        if self.contentView() is not nil:
            self.contentView().removeFromSuperviewWithoutNeedingDisplay()
        self.setContentView_(view)

    def canBecomeMainWindow(self):
        return NO
    
    def canBecomeKeyWindow(self):
        return NO

    def enterFullScreen(self, screen):
        threads.warnIfNotOnMainThread('VideoWindow.enterFullScreen')
        screens = NSScreen.screens()
        if len(screens) > 0:
            screenWithMenuBar = screens[0]
            if screen == screenWithMenuBar:
                SetSystemUIMode(kUIModeAllHidden, 0)
        self.isFullScreen = YES
        self.previousFrame = self.frame()
        self.setFrame_display_animate_(screen.frame(), YES, YES)
        self.palette.enterFullScreen(self)

    def exitFullScreen(self):
        threads.warnIfNotOnMainThread('VideoWindow.exitFullScreen')
        NSCursor.setHiddenUntilMouseMoves_(NO)
        self.isFullScreen = NO
        self.palette.exitFullScreen(self)
        self.setFrame_display_animate_(self.previousFrame, YES, YES)
        SetSystemUIMode(kUIModeNormal, 0)
        
    def toggleFullScreen_(self, sender):
        if self.isFullScreen:
            app.htmlapp.videoDisplay.exitFullScreen()
        else:
            app.htmlapp.videoDisplay.goFullScreen()

    def nextVideo_(self, sender):
        eventloop.addIdle(lambda:app.htmlapp.playbackController.skip(1), "Skip Video")

    def previousVideo_(self, sender):
        eventloop.addIdle(lambda:app.htmlapp.playbackController.skip(-1, False), "Skip Video")

    def stopVideo_(self, sender):
        eventloop.addIdle(lambda:app.htmlapp.playbackController.stop(), "Stop Video")

    def sendEvent_(self, event):
        if event.type() == NSMouseMoved:
            if NSPointInRect(NSEvent.mouseLocation(), self.frame()):
                self.palette.reveal(self)
        elif event.type() == NSLeftMouseDown:
            if NSApplication.sharedApplication().isActive():
                if event.clickCount() > 1:
                    if self.isFullScreen:
                        app.htmlapp.videoDisplay.exitFullScreen()
                    else:
                        app.htmlapp.videoDisplay.goFullScreen()
                elif not self.parentWindow().isMainWindow():
                    self.parentWindow().makeKeyAndOrderFront_(nil)
            else:
                NSApplication.sharedApplication().activateIgnoringOtherApps_(YES)
        else:
            super(VideoWindow, self).sendEvent_(event)
    
###############################################################################

class OverlayPalette (NSWindow):
    
    titleLabel          = IBOutlet('titleLabel')
    feedLabel           = IBOutlet('feedLabel')
    shareButton         = IBOutlet('shareButton')
    shareMenu           = IBOutlet('shareMenu')
    keepButton          = IBOutlet('keepButton')
    deleteButton        = IBOutlet('deleteButton')
    fsButton            = IBOutlet('fsButton')
    
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
    
    def initWithContentRect_styleMask_backing_defer_(self, rect, style, backing, defer):
        self = super(OverlayPalette, self).initWithContentRect_styleMask_backing_defer_(
            rect,
            NSBorderlessWindowMask,
            backing,
            defer )
        nc = NSNotificationCenter.defaultCenter()
        nc.addObserver_selector_name_object_(self, 'videoWillPlay:', u'videoWillPlay', nil)
        nc.addObserver_selector_name_object_(self, 'videoWillPause:', u'videoWillPause', nil)
        self.playingItem = None
        self.setBackgroundColor_(NSColor.clearColor())
        self.setAlphaValue_(1.0)
        self.setOpaque_(NO)
        self.autoHidingTimer = nil
        self.updateTimer = nil
        self.holdStartTime = 0.0
        self.renderer = None
        self.wasPlaying = False
        self.revealing = False
        self.hiding = False
        self.anim = None
        self.videoWindow = None
        return self

    def awakeFromNib(self):
        self.shareButton.setImage_(getOverlayButtonImage(self.shareButton.bounds().size))
        self.shareButton.setAlternateImage_(getOverlayButtonAlternateImage(self.shareButton.bounds().size))

        self.keepButton.setImage_(getOverlayButtonImage(self.keepButton.bounds().size))
        self.keepButton.setAlternateImage_(getOverlayButtonAlternateImage(self.keepButton.bounds().size))

        self.deleteButton.setImage_(getOverlayButtonImage(self.deleteButton.bounds().size))
        self.deleteButton.setAlternateImage_(getOverlayButtonAlternateImage(self.deleteButton.bounds().size))

        self.seekForwardButton.setCell_(SkipSeekButtonCell.cellFromButtonCell_direction_delay_(self.seekForwardButton.cell(), 1, 0.0))
        self.seekForwardButton.cell().setAllowsSkipping(False)
        self.seekBackwardButton.setCell_(SkipSeekButtonCell.cellFromButtonCell_direction_delay_(self.seekBackwardButton.cell(), -1, 0.0))
        self.seekBackwardButton.cell().setAllowsSkipping(False)

        self.progressSlider.track = NSImage.imageNamed_(u'fs-progress-background')
        self.progressSlider.cursor = NSImage.imageNamed_(u'fs-progress-slider')
        self.progressSlider.sliderWasClicked = self.progressSliderWasClicked
        self.progressSlider.sliderWasDragged = self.progressSliderWasDragged
        self.progressSlider.sliderWasReleased = self.progressSliderWasReleased
        self.progressSlider.setShowCursor_(True)

        self.volumeSlider.track = NSImage.imageNamed_(u'fs-volume-background')
        self.volumeSlider.cursor = NSImage.imageNamed_(u'fs-volume-slider')
        self.volumeSlider.sliderWasDragged = self.volumeSliderWasDragged
        self.volumeSlider.setShowCursor_(True)

    def canBecomeKeyWindow(self):
        return NO

    def canBecomeMainWindow(self):
        return NO

    def setup(self, item, renderer):
        self.playingItem = item
        self.renderer = renderer
        def fetchItemValues(item):
            title = item.getTitle()
            feedTitle = item.getFeed().getTitle()
            keep = item.showSaveButton()
            share = item.hasSharableURL()
            threads.callOnMainThread(finishSetup, title, feedTitle, keep, share)
        def finishSetup(title, feedTitle, keep, share):
            self.titleLabel.setStringValue_(title)
            self.feedLabel.setStringValue_(feedTitle)
            self.keepButton.setEnabled_(keep)
            self.shareButton.setEnabled_(share)
            self.update_(nil)
        eventloop.addUrgentCall(lambda:fetchItemValues(item), "Fetching item values")

    def enterFullScreen(self, videoWindow):
        if self.isVisible():
            newFrame = self.frame()
            newFrame.size.width = 824
            newFrame.origin.x = self.getHorizontalPosition(self, newFrame.size.width)
            self.setFrame_display_animate_(newFrame, YES, YES)
            self.adjustContent(videoWindow, True)
            self.fsButton.setImage_(NSImage.imageNamed_('fs-button-exitfullscreen'))
            self.fsButton.setAlternateImage_(NSImage.imageNamed_('fs-button-exitfullscreen-alt'))
        else:
            NSCursor.setHiddenUntilMouseMoves_(YES)

    def exitFullScreen(self, videoWindow):
        if self.isVisible():
            self.adjustContent(videoWindow, True)
            self.fsButton.setImage_(NSImage.imageNamed_('fs-button-enterfullscreen'))
            self.fsButton.setAlternateImage_(NSImage.imageNamed_('fs-button-enterfullscreen-alt'))

    def getHorizontalPosition(self, videoWindow, width):
        parentFrame = videoWindow.frame()
        return parentFrame.origin.x + ((parentFrame.size.width - width) / 2.0)

    def adjustPosition(self, videoWindow):
        parentFrame = videoWindow.frame()
        x = self.getHorizontalPosition(videoWindow, self.frame().size.width)
        y = parentFrame.origin.y + 60
        self.setFrameOrigin_(NSPoint(x, y))

    def adjustContent(self, videoWindow, animate):
        newFrame = self.frame()
        if videoWindow.isFullScreen:
            self.playbackControls.setHidden_(NO)
            newFrame.size.width = 824
        else:
            self.playbackControls.setHidden_(YES)
            newFrame.size.width = 516
        newFrame.origin.x = self.getHorizontalPosition(videoWindow, newFrame.size.width)
        if animate:
            self.setFrame_display_animate_(newFrame, YES, YES)
        else:
            self.setFrame_display_(newFrame, YES)

    def reveal(self, videoWindow):
        threads.warnIfNotOnMainThread('OverlayPalette.reveal')
        self.resetAutoHiding()
        if (not self.isVisible() and not self.revealing) or (self.isVisible() and self.hiding):
            self.update_(nil)
            app.htmlapp.videoDisplay.getVolume(lambda v: self.volumeSlider.setFloatValue_(v))

            self.videoWindow = videoWindow
            self.adjustPosition(videoWindow)
            self.adjustContent(videoWindow, False)

            if self.hiding and self.anim is not None:
                self.anim.stopAnimation()
                self.hiding = False
            else:
                self.setAlphaValue_(0.0)

            self.orderFront_(nil)
            videoWindow.parentWindow().addChildWindow_ordered_(self, NSWindowAbove)

            self.revealing = True
            params = {NSViewAnimationTargetKey: self, NSViewAnimationEffectKey: NSViewAnimationFadeInEffect}
            self.animate(params, 0.3)
    
    def hide(self):
        threads.warnIfNotOnMainThread('OverlayPalette.hide')
        if not self.hiding:
            if self.autoHidingTimer is not nil:
                self.autoHidingTimer.invalidate()
                self.autoHidingTimer = nil

            if self.revealing and self.anim is not None:
                self.anim.stopAnimation()
                self.revealing = False

            self.hiding = True
            params = {NSViewAnimationTargetKey: self, NSViewAnimationEffectKey: NSViewAnimationFadeOutEffect}
            self.animate(params, 0.5)
    
    def hideAfterDelay_(self, timer):
        if time.time() - self.holdStartTime > self.HOLD_TIME:
            self.hide()
    
    def resetAutoHiding(self):
        self.holdStartTime = time.time()
        
    def animate(self, params, duration):
        self.anim = NSViewAnimation.alloc().initWithDuration_animationCurve_(duration, 0)
        self.anim.setViewAnimations_(NSArray.arrayWithObject_(params))
        self.anim.setDelegate_(self)
        self.anim.startAnimation()

    def animationDidEnd_(self, anim):
        parent = self.parentWindow()
        if self.revealing:
            self.holdStartTime = time.time()
            self.autoHidingTimer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                1.0, self, 'hideAfterDelay:', nil, YES)
            self.updateTimer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                0.5, self, 'update:', nil, YES)
            NSRunLoop.currentRunLoop().addTimer_forMode_(self.updateTimer, NSEventTrackingRunLoopMode)
            self.update_(nil)
            if parent is not None and self.videoWindow.isFullScreen:
                NSCursor.setHiddenUntilMouseMoves_(NO)
        elif self.hiding:
            if parent is not None and self.videoWindow.isFullScreen:
                NSCursor.setHiddenUntilMouseMoves_(YES)
            self.remove()

        self.anim = None
        self.revealing = False
        self.hiding = False
        
    def keep_(self, sender):
        def doKeep(item):
            ModelActionHandler().keepItem(self.playingItem.getID())
            sender.setEnabled_(NO)
        eventloop.addUrgentCall(lambda:doKeep(self.playingItem), "Keeping Video")
    
    def expireNow_(self, sender):
        def doExpire(item):
            ModelActionHandler().expirePlayingItem(self.playingItem.getID())
        eventloop.addUrgentCall(lambda:doExpire(self.playingItem), "Expiring Video")
        
    def share_(self, sender):
        event = NSApplication.sharedApplication().currentEvent()
        NSMenu.popUpContextMenu_withEvent_forView_(self.shareMenu, event, sender)
    
    def handleShareItem_(self, sender):
        def doShare(item):
            if sender.tag() == 1: # Post to Video Bomb
                ModelActionHandler().videoBombExternally(item.getID())
            else:
                if sender.tag() == 0:   # Email to friend
                    url = "http://www.videobomb.com/index/democracyemail?url=%s&title=%s" % (item.getQuotedURL(), item.getQuotedTitle())
                elif sender.tag() == 2: # Post to del.icio.us
                    url = "http://del.icio.us/post?v=4&noui&jump=close&url=%s&title=%s" % (item.getQuotedURL(), item.getQuotedTitle())
                elif sender.tag() == 3: # Post to digg
                    url = "http://www.digg.com/submit?phrase=2&url=%s" % item.getQuotedURL()
                elif sender.tag() == 4: # Post to Reddit
                    url = "http://reddit.com/submit?url=%s&title=%s" % (item.getQuotedURL(), item.getQuotedTitle())
                NSWorkspace.sharedWorkspace().openURL_(NSURL.URLWithString_(url))

        eventloop.addUrgentCall(lambda:doShare(self.playingItem), "Sharing Video")
    
    def update_(self, timer):
        self.renderer.getDisplayTime(lambda t: self.timeIndicator.setStringValue_(unicode(t)))
        self.renderer.getProgress(lambda p: self.progressSlider.setFloatValue_(p))
            
    def progressSliderWasClicked(self, slider):
        if app.htmlapp.videoDisplay.isPlaying:
            self.wasPlaying = True
            self.renderer.pause()
        self.renderer.setProgress(slider.floatValue())
        self.renderer.interactivelySeeking = True
        self.resetAutoHiding()
        
    def progressSliderWasDragged(self, slider):
        self.renderer.setProgress(slider.floatValue())
        self.resetAutoHiding()
        
    def progressSliderWasReleased(self, slider):
        self.renderer.interactivelySeeking = False
        if self.wasPlaying:
            self.wasPlaying = False
            self.renderer.play()

    def volumeSliderWasDragged(self, slider):
        app.htmlapp.videoDisplay.setVolume(slider.floatValue())
        self.resetAutoHiding()

    def videoWillPlay_(self, notification):
        self.playPauseButton.setImage_(NSImage.imageNamed_(u'fs-button-pause'))
        self.playPauseButton.setAlternateImage_(NSImage.imageNamed_(u'fs-button-pause-alt'))

    def videoWillPause_(self, notification):
        self.playPauseButton.setImage_(NSImage.imageNamed_(u'fs-button-play'))
        self.playPauseButton.setAlternateImage_(NSImage.imageNamed_(u'fs-button-play-alt'))

    def remove(self):
        threads.warnIfNotOnMainThread('OverlayPalette.remove')
        if self.autoHidingTimer is not nil:
            self.autoHidingTimer.invalidate()
            self.autoHidingTimer = nil
        if self.updateTimer is not nil:
            self.updateTimer.invalidate()
            self.updateTimer = nil
        if self.parentWindow() is not nil:
            self.parentWindow().removeChildWindow_(self)
        self.orderOut_(nil)

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
        
        NSColor.colorWithCalibratedWhite_alpha_(0.0, 0.6).set()
        path.fill()
        
        NSColor.colorWithCalibratedWhite_alpha_(1.0, 0.6).set()
        path.setLineWidth_(lineWidth)
        path.stroke()

###############################################################################

class OverlayPaletteControlsView (NSView):
        
    def hitTest_(self, point):
        # Our buttons have transparent parts, but we still want mouse clicks
        # to be detected if they happen there, so we override hit testing and
        # simply test for button frames.
        for subview in self.subviews():
            if NSPointInRect(self.convertPoint_fromView_(point, nil), subview.frame()):
                return subview
        return self


###############################################################################

class OverlayPaletteSlider (Slider):

    def drawTrack(self):
        self.track.compositeToPoint_operation_((0, 2), NSCompositeSourceOver)

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
    fillColor = NSColor.colorWithCalibratedWhite_alpha_(190.0/255.0, 0.8)
    strokeColor = NSColor.colorWithCalibratedWhite_alpha_(76.0/255.0, 0.8)
    return makeOverlayButtonImage(size, fillColor, strokeColor)

def getOverlayButtonAlternateImage(size):
    fillColor = NSColor.colorWithCalibratedWhite_alpha_(220.0/255.0, 0.8)
    strokeColor = NSColor.colorWithCalibratedWhite_alpha_(106.0/255.0, 0.8)
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
