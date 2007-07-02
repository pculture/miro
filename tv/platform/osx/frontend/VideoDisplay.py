import time
import logging

from objc import YES, NO, nil
from AppKit import *
from Foundation import *
from PyObjCTools import NibClassBuilder

import app
import eventloop
import platformcfg
import platformutils

from QuicktimeRenderer import QuicktimeRenderer
from QTKit import QTMovieDidEndNotification

###############################################################################
#### Dynamically link some specific Carbon functions which we need but     ####
###  which are not available in the default MacPython                      ####
###############################################################################

import objc

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

class PlaybackController (app.PlaybackControllerBase):
    
    def playItemExternally(self, itemID):
        item = app.PlaybackControllerBase.playItemExternally(self, itemID)
        moviePath = item.getVideoFilename()
        moviePath = platformutils.filenameTypeToOSFilename(moviePath)

        ws = NSWorkspace.sharedWorkspace()
        ok, externalApp, movieType = ws.getInfoForFile_application_type_(moviePath)
        if ok:
            if externalApp == platformcfg.getBundlePath():
                print 'WARNING, trying to play movie externally with ourselves.'
                ok = False
            else:
                ok = ws.openFile_withApplication_andDeactivate_(moviePath, nil, YES)

        if not ok:
            logging.warn("movie %s could not be externally opened" % moviePath)

###############################################################################

class VideoDisplay (app.VideoDisplayBase):
    "Video player shown in a MainFrame's right-hand pane."

    def __init__(self):
        app.VideoDisplayBase.__init__(self)
        self.controller = VideoDisplayController.getInstance()
        self.controller.videoDisplay = self

    def initRenderers(self):
        self.renderers.append(QuicktimeRenderer(self.controller))

    def setExternal(self, external):
        app.VideoDisplayBase.setExternal(self, external)
        if external:
            self.controller.enableExternalPlaybackControls()

    def selectItem(self, item, renderer):
        app.VideoDisplayBase.selectItem(self, item, renderer)
        self.controller.selectItem(item, renderer)
 
    def play(self):
        app.VideoDisplayBase.play(self)
        self.controller.play()

    def playFromTime(self, startTime):
        app.VideoDisplayBase.playFromTime(self, startTime)
        self.controller.play()

    def pause(self):
        app.VideoDisplayBase.pause(self)
        self.controller.pause()

    def stop(self):
        app.VideoDisplayBase.stop(self)
        self.controller.stop()
    
    def goFullScreen(self):
        app.VideoDisplayBase.goFullScreen(self)
        self.controller.goFullScreen()

    def exitFullScreen(self):
        app.VideoDisplayBase.exitFullScreen(self)
        self.controller.exitFullScreen()

    def setVolume(self, level):
        app.VideoDisplayBase.setVolume(self, level)
        self.controller.setVolume(level)

    def muteVolume(self):
        app.VideoDisplayBase.muteVolume(self)
        self.controller.volumeSlider.setEnabled_(NO)

    def restoreVolume(self):
        app.VideoDisplayBase.restoreVolume(self)
        self.controller.volumeSlider.setEnabled_(YES)

    def onSelected(self, frame):
        app.VideoDisplayBase.onSelected(self, frame)
        self.controller.onSelected()

    def onDeselected(self, frame):
        app.VideoDisplayBase.onDeselected(self, frame)
        self.controller.onDeselected()

    def getView(self):
        return self.controller.rootView

###############################################################################

class VideoDisplayController (NibClassBuilder.AutoBaseClass):

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

    @platformutils.onMainThread
    def onSelected(self):
        self.enableSecondaryControls(YES)
        self.preventSystemSleep(True)

    @platformutils.onMainThread
    def onDeselected(self):
        self.enableSecondaryControls(NO)
        self.preventSystemSleep(False)
        self.videoAreaView.teardown()
        self.progressDisplayer.teardown()
        self.reset()

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
        self.fullscreenButton.setEnabled_(enabled)

    def enableSecondaryControls(self, enabled, allowFastSeeking=YES):
        self.backwardButton.setEnabled_(enabled)
        self.backwardButton.cell().setAllowsFastSeeking(allowFastSeeking)
        self.stopButton.setEnabled_(enabled or app.controller.videoDisplay.isExternal)
        self.forwardButton.setEnabled_(enabled)
        self.forwardButton.cell().setAllowsFastSeeking(allowFastSeeking)

    def enableExternalPlaybackControls(self):
        self.stopButton.setEnabled_(True)
        self.playPauseButton.setEnabled_(False)
        self.fullscreenButton.setEnabled_(False)
        self.backwardButton.setEnabled_(False)
        self.forwardButton.setEnabled_(False)

    def updatePlayPauseButton(self, prefix):
        self.playPauseButton.setImage_(NSImage.imageNamed_(u'%s' % prefix))
        self.playPauseButton.setAlternateImage_(NSImage.imageNamed_(u'%s_blue' % prefix))

    def playPause_(self, sender):
        eventloop.addUrgentCall(lambda:app.controller.playbackController.playPause(), "Play Video")

    @platformutils.onMainThread
    def play(self):
        nc = NSNotificationCenter.defaultCenter()
        nc.postNotificationName_object_(u'videoWillPlay', nil)
        self.enablePrimaryControls(YES)
        self.enableSecondaryControls(YES)
        self.updatePlayPauseButton('pause')

    @platformutils.onMainThread
    def pause(self):
        nc = NSNotificationCenter.defaultCenter()
        nc.postNotificationName_object_(u'videoWillPause', nil)
        self.updatePlayPauseButton('play')

    def stop_(self, sender):
        eventloop.addUrgentCall(lambda:app.controller.playbackController.stop(), "Stop Video")
    
    @platformutils.onMainThread
    def stop(self):
        nc = NSNotificationCenter.defaultCenter()
        nc.postNotificationName_object_(u'videoWillStop', nil)
        self.updatePlayPauseButton('play')

    def playFullScreen_(self, sender):
        def performInEventLoop():
            if not app.controller.videoDisplay.isPlaying:
                app.controller.playbackController.playPause()
            self.videoDisplay.goFullScreen()
        eventloop.addUrgentCall(lambda:performInEventLoop(), "Play Video Fullscreen")

    @platformutils.onMainThread
    def goFullScreen(self):
        self.videoAreaView.enterFullScreen()

    def exitFullScreen_(self, sender):
        self.exitFullScreen()

    @platformutils.onMainThread
    def exitFullScreen(self):
        self.videoAreaView.exitFullScreen()

    def skipForward_(self, sender):
        eventloop.addUrgentCall(lambda:app.controller.playbackController.skip(1), "Skip Forward")

    def fastForward_(self, sender):
        self.fastSeek(1)

    def skipBackward_(self, sender):
        eventloop.addUrgentCall(lambda:app.controller.playbackController.skip(-1), "Skip Backward")

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

    @platformutils.onMainThread
    def setVolume(self, level):
        if self.muteButton.state() == NSOnState:
            self.volumeSlider.setFloatValue_(level)

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
            eventloop.addUrgentCall(lambda:app.controller.playbackController.onMovieFinished(), "Movie Finished Callback")

###############################################################################

class VideoAreaView (NibClassBuilder.AutoBaseClass):
    
    def setup(self, item, renderer):
        if not self.videoWindow.isFullScreen:
            self.adjustVideoWindowFrame()
        self.videoWindow.setup(renderer, item)
        self.activateVideoWindow()
        nc = NSNotificationCenter.defaultCenter()
        nc.addObserver_selector_name_object_(self, 
                                             'handleWindowNotifications:', 
                                             NSWindowDidMoveNotification, 
                                             self.window())
        
    def teardown(self):
        platformutils.warnIfNotOnMainThread('VideoAreaView.teardown')
        nc = NSNotificationCenter.defaultCenter()
        nc.removeObserver_name_object_(self, NSWindowDidMoveNotification, nil)
        if self.videoWindow.isFullScreen:
            self.videoWindow.exitFullScreen()
        self.window().removeChildWindow_(self.videoWindow)
        self.videoWindow.orderOut_(nil)
        self.videoWindow.teardown()

    @platformutils.onMainThreadWaitingUntilDone
    def activateVideoWindow(self):
        if self.window().isMiniaturized():
            self.window().deminiaturize_(nil)
        self.window().orderFront_(nil)
        self.videoWindow.orderFront_(nil)
        if self.videoWindow.parentWindow() is nil:
            self.window().addChildWindow_ordered_(self.videoWindow, NSWindowAbove)
    
    def drawRect_(self, rect):
        NSColor.blackColor().set()
        NSRectFill(rect)
    
    @platformutils.onMainThreadWaitingUntilDone
    def adjustVideoWindowFrame(self):
        if self.window() is nil:
            return
        frame = self.frame()
        frame.origin = self.convertPoint_toView_(NSZeroPoint, nil)
        frame.origin = self.window().convertBaseToScreen_(frame.origin)
        self.videoWindow.setFrame_display_(frame, YES)
        
    def setFrame_(self, frame):
        super(VideoAreaView, self).setFrame_(frame)
        self.adjustVideoWindowFrame()

    def handleWindowNotifications_(self, notification):
        self.adjustVideoWindowFrame()
    
    @platformutils.onMainThread
    def enterFullScreen(self):
        self.adjustVideoWindowFrame()
        if self.window() is not nil:
            self.videoWindow.enterFullScreen(self.window().screen())
            self.window().removeChildWindow_(self.videoWindow)
            self.window().orderOut_(nil)

    @platformutils.onMainThread
    def exitFullScreen(self):
        if self.videoWindow.isFullScreen:
            self.window().addChildWindow_ordered_(self.videoWindow, NSWindowAbove)
            self.window().makeKeyAndOrderFront_(nil)
            self.videoWindow.exitFullScreen()
    

###############################################################################

class VideoWindow (NibClassBuilder.AutoBaseClass):
    
    def initWithContentRect_styleMask_backing_defer_(self, rect, style, backing, defer):
        self = super(VideoWindow, self).initWithContentRect_styleMask_backing_defer_(
            rect,
            NSBorderlessWindowMask,
            backing,
            defer )
        self.setAcceptsMouseMovedEvents_(YES)
        self.setBackgroundColor_(NSColor.blackColor())
        self.isFullScreen = NO
        return self

    def setup(self, renderer, item):
        self.installRendererView_(renderer.view)
        self.palette.setup(item, renderer)
        if self.isFullScreen:
            platformutils.callOnMainThreadAfterDelay(0.5, self.palette.reveal, self)
    
    def teardown(self):
        platformutils.warnIfNotOnMainThread('VideoWindow.teardown')
        self.setContentView_(nil)

    @platformutils.onMainThreadWaitingUntilDone
    def installRendererView_(self, view):
        if self.contentView() is not nil:
            self.contentView().removeFromSuperviewWithoutNeedingDisplay()
        self.setContentView_(view)

    def canBecomeMainWindow(self):
        return self.isFullScreen
    
    def canBecomeKeyWindow(self):
        return self.isFullScreen

    def enterFullScreen(self, screen):
        platformutils.warnIfNotOnMainThread('VideoWindow.enterFullScreen')
        screens = NSScreen.screens()
        if len(screens) > 0:
            screenWithMenuBar = screens[0]
            if screen == screenWithMenuBar:
                SetSystemUIMode(kUIModeAllHidden, 0)
        NSCursor.setHiddenUntilMouseMoves_(YES)
        self.isFullScreen = YES
        self.previousFrame = self.frame()
        self.setFrame_display_animate_(screen.frame(), YES, YES)
        self.makeKeyAndOrderFront_(nil)

    def exitFullScreen(self):
        platformutils.warnIfNotOnMainThread('VideoWindow.exitFullScreen')
        NSCursor.setHiddenUntilMouseMoves_(NO)
        self.isFullScreen = NO
        self.palette.remove()
        self.setFrame_display_animate_(self.previousFrame, YES, YES)
        SetSystemUIMode(kUIModeNormal, 0)
        
    def toggleFullScreen_(self, sender):
        app.controller.videoDisplay.exitFullScreen()

    def nextVideo_(self, sender):
        eventloop.addIdle(lambda:app.controller.playbackController.skip(1), "Skip Video")

    def previousVideo_(self, sender):
        eventloop.addIdle(lambda:app.controller.playbackController.skip(-1, False), "Skip Video")

    def sendEvent_(self, event):
        if self.isFullScreen:
            if event.type() == NSLeftMouseDown:
                if NSApplication.sharedApplication().isActive():
                    app.controller.videoDisplay.exitFullScreen()
                else:
                    NSApplication.sharedApplication().activateIgnoringOtherApps_(YES)
            elif event.type() == NSKeyDown:
                if event.characters().characterAtIndex_(0) == 0x1B:
                    app.controller.videoDisplay.exitFullScreen()
                elif event.characters().characterAtIndex_(0) == 0x20:
                    eventloop.addUrgentCall(lambda:app.controller.playbackController.playPause(), "Play/Pause")
            elif event.type() == NSMouseMoved:
                if not self.palette.isVisible():
                    self.palette.reveal(self)
                else:
                    self.palette.resetAutoConceal()
        else:
            if event.type() == NSLeftMouseDown:
                if NSApplication.sharedApplication().isActive():
                    app.controller.videoDisplay.goFullScreen()
                else:
                    NSApplication.sharedApplication().activateIgnoringOtherApps_(YES)

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

class FullScreenPalette (NibClassBuilder.AutoBaseClass):
    
    HOLD_TIME = 2
    
    def initWithContentRect_styleMask_backing_defer_(self, rect, style, backing, defer):
        self = super(FullScreenPalette, self).initWithContentRect_styleMask_backing_defer_(
            rect,
            NSBorderlessWindowMask,
            backing,
            defer )
        nc = NSNotificationCenter.defaultCenter()
        nc.addObserver_selector_name_object_(self, 'videoWillPlay:', u'videoWillPlay', nil)
        nc.addObserver_selector_name_object_(self, 'videoWillPause:', u'videoWillPause', nil)
        self.setBackgroundColor_(NSColor.clearColor())
        self.setAlphaValue_(1.0)
        self.setOpaque_(NO)
        self.autoConcealTimer = nil
        self.updateTimer = nil
        self.holdStartTime = 0.0
        self.renderer = None
        self.wasPlaying = False
        return self

    def awakeFromNib(self):
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
        self.titleLabel.setStringValue_(unicode(item.getTitle()))
        self.feedLabel.setStringValue_(unicode(item.getFeed().getTitle()))
        self.donationLabel.setStringValue_(u'')
        self.renderer = renderer
        self.update_(nil)

    def reveal(self, parent):
        platformutils.warnIfNotOnMainThread('FullScreenPalette.reveal')
        if not self.isVisible():
            self.update_(nil)
            self.volumeSlider.setFloatValue_(app.controller.videoDisplay.getVolume())
            screenOrigin = parent.screen().frame().origin
            screenSize = parent.screen().frame().size
            height = self.frame().size.height
            frame = ((screenOrigin.x, screenOrigin.y-height), (screenSize.width, height))
            self.setFrame_display_(frame, NO)        
            parent.addChildWindow_ordered_(self, NSWindowAbove)
            self.orderFront_(nil)
            frame = (screenOrigin, (screenSize.width, height))
            self.setFrame_display_animate_(frame, YES, YES)
            self.holdStartTime = time.time()
            self.autoConcealTimer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                1.0, self, 'concealAfterDelay:', nil, YES)
            self.updateTimer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                1.0, self, 'update:', nil, YES)
            NSRunLoop.currentRunLoop().addTimer_forMode_(self.updateTimer, NSEventTrackingRunLoopMode)
            self.update_(nil)
    
    def conceal(self):
        platformutils.warnIfNotOnMainThread('FullScreenPalette.conceal')
        if self.autoConcealTimer is not nil:
            self.autoConcealTimer.invalidate()
            self.autoConcealTimer = nil
        if self.updateTimer is not nil:
            self.updateTimer.invalidate()
            self.updateTimer = nil
        frame = self.frame()
        frame.origin.y = -frame.size.height
        self.setFrame_display_animate_(frame, YES, YES)
        self.remove()
        NSCursor.setHiddenUntilMouseMoves_(YES)
    
    def concealAfterDelay_(self, timer):
        if time.time() - self.holdStartTime > self.HOLD_TIME:
            self.conceal()
    
    def resetAutoConceal(self):
        self.holdStartTime = time.time()
        
    def expireNow_(self, sender):
        pass
        
    def tellAFriend_(self, sender):
        pass
        
    def update_(self, timer):
        self.timeIndicator.setStringValue_(unicode(self.renderer.getDisplayTime()))
        self.progressSlider.setFloatValue_(self.renderer.getProgress())
            
    def progressSliderWasClicked(self, slider):
        if app.controller.videoDisplay.isPlaying:
            self.wasPlaying = True
            self.renderer.pause()
        self.renderer.setProgress(slider.floatValue())
        self.renderer.interactivelySeeking = True
        self.resetAutoConceal()
        
    def progressSliderWasDragged(self, slider):
        self.renderer.setProgress(slider.floatValue())
        self.resetAutoConceal()
        
    def progressSliderWasReleased(self, slider):
        self.renderer.interactivelySeeking = False
        if self.wasPlaying:
            self.wasPlaying = False
            self.renderer.play()

    def volumeSliderWasDragged(self, slider):
        app.controller.videoDisplay.setVolume(slider.floatValue())
        self.resetAutoConceal()

    def videoWillPlay_(self, notification):
        self.playPauseButton.setImage_(NSImage.imageNamed_(u'fs-button-pause'))
        self.playPauseButton.setAlternateImage_(NSImage.imageNamed_(u'fs-button-pause-alt'))

    def videoWillPause_(self, notification):
        self.playPauseButton.setImage_(NSImage.imageNamed_(u'fs-button-play'))
        self.playPauseButton.setAlternateImage_(NSImage.imageNamed_(u'fs-button-play-alt'))

    def remove(self):
        platformutils.warnIfNotOnMainThread('FullScreenPalette.remove')
        if self.parentWindow() is not nil:
            self.parentWindow().removeChildWindow_(self)
        self.orderOut_(nil)

###############################################################################

class FullScreenPaletteView (NibClassBuilder.AutoBaseClass):

    def awakeFromNib(self):
        self.background = NSImage.imageNamed_(u'fs-background')
        self.backgroundRect = NSRect((0,0), self.background.size())
        self.topLine = NSImage.imageNamed_(u'fs-topline')
        self.topLineRect = NSRect((0,0), self.topLine.size())

    def drawRect_(self, rect):
        width = self.bounds().size.width
        bgRect = ((0,0), (width, self.backgroundRect.size.height))
        self.background.drawInRect_fromRect_operation_fraction_(bgRect, self.backgroundRect, NSCompositeSourceOver, 1.0)
        tlRect1 = ((0,self.backgroundRect.size.height), (width-135, self.topLineRect.size.height))
        self.topLine.drawInRect_fromRect_operation_fraction_(tlRect1, self.topLineRect, NSCompositeSourceOver, 1.0)
        tlRect2 = ((width-25,self.backgroundRect.size.height), (25, self.topLineRect.size.height))
        self.topLine.drawInRect_fromRect_operation_fraction_(tlRect2, self.topLineRect, NSCompositeSourceOver, 1.0)

###############################################################################

class FullScreenControlsView (NibClassBuilder.AutoBaseClass):
    
    def awakeFromNib(self):
        self.background = NSImage.imageNamed_(u'fs-controls-background')
        self.backgroundRect = NSRect((0,0), self.background.size())

    def drawRect_(self, rect):
        self.background.compositeToPoint_operation_((0, 0), NSCompositeSourceOver)
        
    def hitTest_(self, point):
        # Our buttons have transparent parts, but we still want mouse clicks
        # to be detected if they happen there, so we override hit testing and
        # simply test for button frames.
        for subview in self.subviews():
            if NSPointInRect(self.convertPoint_fromView_(point, nil), subview.frame()):
                return subview
        return self


###############################################################################

class FullScreenSlider (NibClassBuilder.AutoBaseClass):

    def drawTrack(self):
        self.track.compositeToPoint_operation_((0, 2), NSCompositeSourceOver)

###############################################################################
