import math

from objc import YES, NO, nil
from AppKit import *
from Foundation import *
from PyObjCTools import NibClassBuilder

import app
import feed
import prefs
import config
import folder
import dialogs
import playlist
import eventloop
import platformutils

NibClassBuilder.extractClasses("MainWindow")

###############################################################################

class MainFrame:

    def __init__(self, appl):
        self.channelsDisplay = None
        self.mainDisplay = None
        self.videoInfoDisplay = None
        # Do this in two steps so that self.controller is set when self.controler.init
        # is called. That way, init can turn around and call selectDisplay.
        self.controller = MainController.alloc()
        self.controller.init(self, appl)

    def selectDisplay(self, display, area=None):
        """Install the provided 'display' in the requested area"""
        self.controller.selectDisplay(display, area)

    def getDisplay(self, area):
        return area.hostedDisplay

    # Internal use: return an estimate of the size of a given display area as
    # a Cocoa frame object.
    def getDisplaySizeHint(self, area):
        return self.controller.getDisplaySizeHint(area)

    def onSelectedTabChange(self, strings, actionGroups, guideURL,
            videoFilename):
        self.controller.onSelectedTabChange(strings, actionGroups, guideURL,
                videoFilename)

###############################################################################

class MainController (NibClassBuilder.AutoBaseClass):

    def init(self, frame, appl):
        super(MainController, self).init()
        self.frame = frame
        self.appl = appl
        self.menuStrings = dict()
        self.actionGroups = dict()
        NSBundle.loadNibNamed_owner_("MainWindow", self)

        nc = NSNotificationCenter.defaultCenter()
        nc.addObserver_selector_name_object_(
            self,
            'appWillTerminate:',
            NSApplicationWillTerminateNotification,
            NSApplication.sharedApplication())

        return self

    def awakeFromNib(self):
        from VideoDisplay import VideoDisplayController
        self.videoDisplayController = VideoDisplayController.getInstance()
        self.frame.channelsDisplay = self.channelsHostView
        self.frame.mainDisplay = self.mainHostView
        self.frame.videoInfoDisplay = self.videoInfoHostView
        self.frame.videoInfoDisplay.backgroundColor = NSColor.blackColor()
        self.restoreLayout()
        self.updateWindowTexture()
        self.showWindow_(nil)

    def appWillTerminate_(self, notification):
        self.saveLayout()

    def restoreLayout(self):
        windowFrame = config.get(prefs.MAIN_WINDOW_FRAME)
        if windowFrame is None:
            windowFrame = self.window().frame()
        else:
            windowFrame = NSRectFromString(windowFrame)
        screen = self.window().screen()
        if screen is not None:
            visibleFrame = screen.visibleFrame()
            if not NSContainsRect(visibleFrame, windowFrame):
                print "DTV: Fitting window to screen size"
                windowFrame = visibleFrame
        self.window().setFrame_display_(windowFrame, NO)

        leftFrame = config.get(prefs.LEFT_VIEW_SIZE)
        rightFrame = config.get(prefs.RIGHT_VIEW_SIZE)
        if leftFrame is not None and rightFrame is not None:
           leftFrame = NSRectFromString(leftFrame)
           rightFrame = NSRectFromString(rightFrame)
           self.splitView.subviews().objectAtIndex_(0).setFrame_(leftFrame)
           self.splitView.subviews().objectAtIndex_(1).setFrame_(rightFrame)
           self.splitView.adjustSubviews()

    def saveLayout(self):
        windowFrame = self.window().frame()
        windowFrame = NSStringFromRect(windowFrame)
        leftFrame = self.splitView.subviews().objectAtIndex_(0).frame()
        leftFrame = NSStringFromRect(leftFrame)
        rightFrame = self.splitView.subviews().objectAtIndex_(1).frame()
        rightFrame = NSStringFromRect(rightFrame)

        config.set(prefs.MAIN_WINDOW_FRAME, windowFrame)
        config.set(prefs.LEFT_VIEW_SIZE, leftFrame)
        config.set(prefs.RIGHT_VIEW_SIZE, rightFrame)
        config.save()

    def updateWindowTexture(self):
        bgTexture = NSImage.alloc().initWithSize_(self.window().frame().size)
        bgTexture.lockFocus()
                
        topImage = NSImage.imageNamed_(u'wtexture_top')
        topColor = NSColor.colorWithPatternImage_(topImage)
        topColor.set()
        NSGraphicsContext.currentContext().setPatternPhase_(bgTexture.size())
        NSRectFill(((0, bgTexture.size().height - topImage.size().height), (bgTexture.size().width, topImage.size().height)))
        
        bottomImage = NSImage.imageNamed_(u'wtexture_bottom')
        bottomColor = NSColor.colorWithPatternImage_(bottomImage)
        bottomColor.set()
        NSGraphicsContext.currentContext().setPatternPhase_(bottomImage.size())
        NSRectFill(((0, 0), (bgTexture.size().width, bottomImage.size().height)))

        bgColor = NSColor.colorWithCalibratedWhite_alpha_(195.0/255.0, 1.0)
        bgColor.set()
        NSRectFill(((0, bottomImage.size().height), (bgTexture.size().width, bgTexture.size().height -  bottomImage.size().height - topImage.size().height)))
        
        bgTexture.unlockFocus()
        
        self.window().setBackgroundColor_(NSColor.colorWithPatternImage_(bgTexture))
        
    ### Switching displays ###

    @platformutils.onMainThread
    def onSelectedTabChange(self, strings, actionGroups, guideURL,
            videoFilename):
        app.controller.setGuideURL(guideURL)
        self.menuStrings = strings
        self.actionGroups = actionGroups

    def selectDisplay(self, display, area):
        if display is not None:
            # Tell the display area that the next display it will host once it's
            # ready is this one.
            area.setScheduledDisplay(display)
            # Tell the new display we want to switch to it. It'll call us
            # back when it's ready to display without flickering.
            display.callWhenReadyToDisplay(lambda: self.doSelectDisplay(display, area))

    @platformutils.onMainThreadWaitingUntilDone
    def doSelectDisplay(self, display, area):
        if area is not None:
            area.setDisplay(display, self.frame)
            if isinstance(display, app.TemplateDisplay) and area == self.mainHostView:
                nc = NSNotificationCenter.defaultCenter()
                view = display.getWatchable()
                if view is not None:
                    nc.postNotificationName_object_userInfo_('displayIsWatchable', display, {'view': view})
                else:
                    nc.postNotificationName_object_('displayIsNotWatchable', display)

    def getDisplaySizeHint(self, area):
        return area.frame()

    ### Window resize handler

    def windowDidResize_(self, notification):
        self.updateWindowTexture()

    ### Size constraints on splitview ###

    minimumTabListWidth = 160 # pixels
    minimumContentWidth = 500 # pixels

    # How far left can the user move the slider?
    def splitView_constrainMinCoordinate_ofSubviewAt_(self, sender, proposedMin, offset):
        return proposedMin + self.minimumTabListWidth

    # How far right can the user move the slider?
    def splitView_constrainMaxCoordinate_ofSubviewAt_(self, sender, proposedMax, offset):
        return proposedMax - self.minimumContentWidth

    # The window was resized; compute new positions of the splitview
    # children. Rule: resizing the window doesn't change the size of
    # the tab list unless it's necessary to shrink it to obey the
    # minimum content area size constraint.
    def splitView_resizeSubviewsWithOldSize_(self, sender, oldSize):
        tabBox = self.channelsHostView.superview()
        contentBox = self.mainHostView.superview()

        splitViewSize = sender.frame().size
        tabSize = tabBox.frame().size
        contentSize = contentBox.frame().size
        dividerWidth = sender.dividerThickness()

        tabSize.height = contentSize.height = splitViewSize.height

        contentSize.width = splitViewSize.width - dividerWidth - tabSize.width
        if contentSize.width < self.minimumContentWidth:
            contentSize.width = self.minimumContentWidth
        tabSize.width = splitViewSize.width - dividerWidth - contentSize.width

        tabBox.setFrameSize_(tabSize)
        tabBox.setFrameOrigin_(NSZeroPoint)
        contentBox.setFrameSize_(contentSize)
        contentBox.setFrameOrigin_((tabSize.width + dividerWidth, 0))

    def splitView_canCollapseSubview_(self, sender, subview):
        return self.channelsHostView.isDescendantOf_(subview) and app.controller.videoDisplay.isSelected()

    ### Events ###

    def keyDown_(self, event):
        if self.frame.mainDisplay.hostedDisplay is app.controller.videoDisplay and event.characters().characterAtIndex_(0) == 0x20:
            app.controller.playbackController.playPause()

    ### Actions ###

    # File menu #

    def removeVideos_(self, sender):
        eventloop.addIdle(app.controller.removeCurrentItems, "Remove Videos")

    def saveVideoAs_(self, sender):
        print "NOT IMPLEMENTED" # $$$$$$$$$$$$$$

    def copyVideoURL_(self, sender):
        eventloop.addIdle(app.controller.copyCurrentItemURL, "Copy Video URL")

    # Edit menu #
    
    def deleteSelected_(self, sender):
        eventloop.addIdle(app.controller.removeCurrentSelection, "Copy Video URL")

    # Channels menu #

    def addChannel_(self, sender):
        def validationCallback(dialog):
            if dialog.choice == dialogs.BUTTON_OK:
                url = dialog.value
                eventloop.addUrgentCall(lambda:app.controller.addAndSelectFeed(url), "Add Feed")
        title = "Subscribe to Channel"
        description = "Enter the URL of the channel you would like to subscribe to."
        prefillCallback = app.delegate.getURLFromClipboard
        dlog = dialogs.TextEntryDialog(title, description, dialogs.BUTTON_OK, dialogs.BUTTON_CANCEL, prefillCallback)
        dlog.run(validationCallback)

    def createChannelFolder_(self, sender):
        folder.createNewChannelFolder()

    def addGuide_(self, sender):
        eventloop.addIdle(lambda:app.controller.addAndSelectGuide(), "Add Guide")

    def renameChannelFolder_(self, sender):
        eventloop.addIdle(app.controller.renameCurrentChannel, "Rename Channel Tab")

    def removeChannel_(self, sender):
        eventloop.addIdle(app.controller.removeCurrentFeed, "Remove channel")

    def updateChannel_(self, sender):
        eventloop.addIdle(app.controller.updateCurrentFeed, "Update current feed")

    def updateAllChannels_(self, sender):
        eventloop.addIdle(app.controller.updateAllFeeds, "Update all channels")

    def tellAFriend_(self, sender):
        print "NOT IMPLEMENTED" # $$$$$$$$$$$$$$

    def copyChannelURL_(self, sender):
        eventloop.addIdle(app.controller.copyCurrentFeedURL, "Copy channel URL")

    # Playlists menu # 

    def createPlaylist_(self, sender):
        playlist.createNewPlaylist()

    def createPlaylistFolder_(self, sender):
        folder.createNewPlaylistFolder()

    def renamePlaylist_(self, sender):
        eventloop.addIdle(app.controller.renameCurrentPlaylist, "Rename Playlist")

    def removePlaylist_(self, sender):
        eventloop.addIdle(app.controller.removeCurrentPlaylist, "Remove Playlist")

    # Playback menu #

    def playPause_(self, sender):
        self.videoDisplayController.playPause_(sender)

    def stopVideo_(self, sender):
        self.videoDisplayController.stop_(sender)

    def nextVideo_(self, sender):
        eventloop.addIdle(lambda:app.controller.playbackController.skip(1), "Skip Video")

    def previousVideo_(self, sender):
        eventloop.addIdle(lambda:app.controller.playbackController.skip(-1, False), "Skip Video")

    def playFullScreen_(self, sender):
        self.videoDisplayController.playFullScreen_(sender)

    # Help menu #

    def showHelp_(self, sender):
        helpURL = NSURL.URLWithString_(config.get(prefs.HELP_URL))
        NSWorkspace.sharedWorkspace().openURL_(helpURL)

    ### Menu items validation ###

    def validateMenuItem_(self, item):
        result = False
        action = item.action()
        display = self.frame.mainDisplay.hostedDisplay
        
        if action == 'removeVideos:':
            self.updateMenuItem(item, 'video_remove')
            result = self.actionGroups['VideoSelected'] or self.actionGroups['VideosSelected']
        elif action == 'saveVideoAs:':
            result = False
        elif action == 'copyVideoURL:':
            result = self.actionGroups['VideoSelected']
        elif action == 'deleteSelected:':
            result = (self.actionGroups['ChannelLikeSelected'] or
                      self.actionGroups['ChannelLikesSelected'] or
                      self.actionGroups['PlaylistLikeSelected'] or
                      self.actionGroups['PlaylistLikesSelected'] or
                      self.actionGroups['VideoSelected'] or
                      self.actionGroups['VideosSelected'])
        elif action == 'addChannel:':
            result = True
        elif action == 'createChannelFolder:':
            result = True
        elif action == 'addGuide:':
            result = True
        elif action == 'renameChannelFolder:':
            self.updateMenuItem(item, 'channel_rename')
            result = self.actionGroups['ChannelFolderSelected']
        elif action == 'removeChannel:':
            self.updateMenuItem(item, 'channel_remove')
            result = self.actionGroups['ChannelLikeSelected'] or self.actionGroups['ChannelLikesSelected']
        elif action == 'updateChannel:':
            self.updateMenuItem(item, 'channel_update')
            result = self.actionGroups['ChannelLikeSelected'] or self.actionGroups['ChannelLikesSelected']
        elif action == 'updateAllChannels:':
            result = True
        elif action == 'tellAFriend:':
            result = self.actionGroups['ChannelSelected']
        elif action == 'copyChannelURL:':
            result = self.actionGroups['ChannelSelected']
        elif action == 'createPlaylist:':
            return True
        elif action == 'createPlaylistFolder:':
            return True
        elif action == 'renamePlaylist:':
            self.updateMenuItem(item, 'playlist_rename')
            return self.actionGroups['PlaylistLikeSelected']
        elif action == 'removePlaylist:':
            self.updateMenuItem(item, 'playlist_remove')
            return self.actionGroups['PlaylistLikeSelected'] or self.actionGroups['PlaylistLikesSelected']
        elif action == 'playPause:':
            return display is app.controller.videoDisplay
        elif action == 'stopVideo:':
            return display is app.controller.videoDisplay
        elif action == 'nextVideo:':
            return display is app.controller.videoDisplay
        elif action == 'previousVideo:':
            return display is app.controller.videoDisplay
        elif action == 'playFullScreen:':
            return display is app.controller.videoDisplay
        elif action == 'showHelp:':
            return True
        return result

    def updateMenuItem(self, item, key):
        if key in self.menuStrings:
            item.setTitle_(self.menuStrings[key].replace('_', ''))

###############################################################################

class DisplayHostView (NibClassBuilder.AutoBaseClass):
    
    def initWithFrame_(self, frame):
        self = super(DisplayHostView, self).initWithFrame_(frame)
        self.scheduledDisplay = None
        self.hostedDisplay = None
        self.hostedView = nil
        self.backgroundColor = NSColor.whiteColor()
        return self

    def drawRect_(self, rect):
        self.backgroundColor.set()
        NSRectFill(rect)

    def setScheduledDisplay(self, display):
        if self.scheduledDisplay is not None:
            self.scheduledDisplay.cancel()
        self.scheduledDisplay = display
    
    def setDisplay(self, display, owner):
        platformutils.warnIfNotOnMainThread('DisplayHostView.setDisplay')
        self.scheduledDisplay = None

        # Send notification to old display if any
        if self.hostedDisplay is not None:
            self.hostedDisplay.onDeselected_private(owner)
            self.hostedDisplay.onDeselected(owner)
        oldView = self.hostedView

        # Switch to new display
        self.hostedDisplay = display
        if display is not None:
            self.hostedView = display.getView()
        else:
            self.hostedView = nil
        if display is None:
            return

        # Figure out where to put the content area
        # NEEDS: clean up outlet names/types in nib
        frame = self.bounds()
        mask = self.autoresizingMask()

        # Arrange to cover the template that marks the content area
        self.hostedView.setFrame_(frame)
        self.addSubview_(self.hostedView)
        self.hostedView.setAutoresizingMask_(mask)

        # Mark as needing display
        self.setNeedsDisplayInRect_(frame)
        self.hostedView.setNeedsDisplay_(YES)

        # Wait until now to clean up the old view, to reduce flicker
        # (doesn't actually work all that well, sadly -- possibly what
        # we want to do is wait until notification comes from the new
        # view that it's been fully loaded to even show it)
        if oldView and (not (oldView is self.hostedView)):
            oldView.removeFromSuperview()

        # Send notification to new display
        display.onSelected_private(owner)
        display.onSelected(owner)

###############################################################################

class NullDisplay (app.Display):
    "Represents an empty right-hand area."

    def __init__(self):
        app.Display.__init__(self)
        self.view = NSView.alloc().init().retain()

    def getView(self):
        return self.view

###############################################################################

class DTVSplitView (NibClassBuilder.AutoBaseClass):
    
    def awakeFromNib(self):
        self.background = NSImage.imageNamed_('splitview_divider_background')
        self.backgroundRect = ((0,0), self.background.size())
        self.dimple = NSImage.imageNamed_('splitview_divider_dimple')
        
    def dividerThickness(self):
        return 10.0
        
    def drawDividerInRect_(self, rect):
        dividerOrigin = (rect.origin.x, 12)
        dividerSize = (rect.size.width, rect.size.height - 58 - 12)
        dividerRect = (dividerOrigin, dividerSize)
        self.background.drawInRect_fromRect_operation_fraction_(dividerRect, self.backgroundRect, NSCompositeSourceOver, 1.0)
        dimplePosition = (rect.origin.x, (dividerSize[1] - self.dimple.size().height) / 2)
        self.dimple.compositeToPoint_operation_(dimplePosition, NSCompositeSourceOver)

###############################################################################

class ProgressDisplayView (NibClassBuilder.AutoBaseClass):

    def awakeFromNib(self):
        self.progressSlider.sliderWasClicked = self.progressSliderWasClicked
        self.progressSlider.sliderWasDragged = self.progressSliderWasDragged
        self.progressSlider.sliderWasReleased = self.progressSliderWasReleased
        self.backgroundLeft = NSImage.imageNamed_( "display_left" )
        self.backgroundLeftWidth = self.backgroundLeft.size().width
        self.backgroundRight = NSImage.imageNamed_( "display_right" )
        self.backgroundRightWidth = self.backgroundRight.size().width
        self.backgroundCenter = NSImage.imageNamed_( "display_center" )
        self.backgroundCenterWidth = self.backgroundCenter.size().width
        self.renderer = None
        self.updateTimer = nil
        self.wasPlaying = False

    @platformutils.onMainThread
    def setup(self, renderer):
        if self.renderer != renderer:
            self.renderer = renderer
            if renderer is not nil:
                self.updateTimer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(1.0, self, 'refresh:', nil, YES)
                NSRunLoop.currentRunLoop().addTimer_forMode_(self.updateTimer, NSEventTrackingRunLoopMode)
            elif self.updateTimer is not nil:
                self.updateTimer.invalidate()
                self.updateTimer = nil
        self.refresh_(nil)
        self.setNeedsDisplay_(YES)

    def teardown(self):
        self.setup(None)

    def refresh_(self, timer):
        if self.renderer is not None:
            self.progressSlider.setShowCursor_(True)
            self.progressSlider.setFloatValue_(self.renderer.getProgress())
            self.timeIndicator.setStringValue_(self.renderer.getDisplayTime())
        else:
            self.progressSlider.setShowCursor_(False)
            self.progressSlider.setFloatValue_(0.0)
            self.timeIndicator.setStringValue_(app.VideoRenderer.DEFAULT_DISPLAY_TIME)

    def drawRect_(self, rect):
        self.backgroundLeft.compositeToPoint_operation_( (0,0), NSCompositeSourceOver )
        x = self.bounds().size.width - self.backgroundRightWidth
        self.backgroundRight.compositeToPoint_operation_( (x, 0), NSCompositeSourceOver )
        emptyWidth = self.bounds().size.width - (self.backgroundRightWidth + self.backgroundLeftWidth)
        emptyRect = ((self.backgroundLeftWidth, 0), (emptyWidth, self.bounds().size.height))
        NSGraphicsContext.currentContext().saveGraphicsState()
        NSBezierPath.clipRect_(emptyRect)
        tiles = math.ceil(emptyWidth / float(self.backgroundCenterWidth))
        for i in range(0, int(tiles)):
            x = self.backgroundLeftWidth + (i * self.backgroundCenterWidth)
            self.backgroundCenter.compositeToPoint_operation_( (x, 0), NSCompositeSourceOver )
        NSGraphicsContext.currentContext().restoreGraphicsState()

    def progressSliderWasClicked(self, slider):
        if app.controller.videoDisplay.isPlaying:
            self.wasPlaying = True
            self.renderer.pause()
        self.renderer.setProgress(slider.floatValue())
        self.renderer.interactivelySeeking = True
        self.refresh_(nil)
        
    def progressSliderWasDragged(self, slider):
        self.renderer.setProgress(slider.floatValue())
        self.refresh_(nil)
        
    def progressSliderWasReleased(self, slider):
        self.renderer.interactivelySeeking = False
        if self.wasPlaying:
            self.wasPlaying = False
            self.renderer.play()

###############################################################################

class Slider (NibClassBuilder.AutoBaseClass):

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
        self.value = value
        self.setNeedsDisplay_(YES)
        
    def floatValue(self):
        return self.value

    def setShowCursor_(self, showCursor):
        self.showCursor = showCursor

    def drawRect_(self, rect):
        self.drawTrack()
        if self.showCursor:
            self.drawCursor()

    def drawTrack(self):
        pass

    def drawCursor(self):
        x = (self.bounds().size.width - self.cursor.size().width) * self.value
        self.cursor.compositeToPoint_operation_((abs(x)+0.5, 0), NSCompositeSourceOver)

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

###############################################################################

class ProgressSlider (NibClassBuilder.AutoBaseClass):
    
    def initWithFrame_(self, frame):
        self = super(ProgressSlider, self).initWithFrame_(frame)
        self.grooveContourColor = NSColor.colorWithCalibratedWhite_alpha_( 0.1, 0.3 )
        self.grooveFillColor = NSColor.colorWithCalibratedWhite_alpha_( 0.5, 0.3 )
        self.cursor = NSImage.alloc().initWithSize_((10,10))
        self.cursor.lockFocus()
        path = NSBezierPath.bezierPath()
        path.moveToPoint_((0, 4.5))
        path.lineToPoint_((4, 8))
        path.lineToPoint_((8, 4.5))
        path.lineToPoint_((4, 1))
        path.closePath()
        NSColor.colorWithCalibratedWhite_alpha_( 51/255.0, 1.0 ).set()
        path.fill()
        self.cursor.unlockFocus()
        return self
                
    def drawTrack(self):
        rect = self.bounds()
        rect = NSOffsetRect(rect, 0.5, 0.5)
        rect.size.width -= 1
        rect.size.height -= 1
        self.grooveFillColor.set()
        NSBezierPath.fillRect_(rect)
        self.grooveContourColor.set()
        NSBezierPath.strokeRect_(rect)        

###############################################################################

class MetalSlider (NibClassBuilder.AutoBaseClass):

    def awakeFromNib(self):
        oldCell = self.cell()
        newCell = MetalSliderCell.alloc().init()
        newCell.setState_(oldCell.state())
        newCell.setEnabled_(oldCell.isEnabled())
        newCell.setFloatValue_(oldCell.floatValue())
        newCell.setTarget_(oldCell.target())
        newCell.setAction_(oldCell.action())
        self.setCell_(newCell)

###############################################################################

class MetalSliderCell (NSSliderCell):

    def init(self):
        self = super(MetalSliderCell, self).init()
        self.knob = NSImage.imageNamed_('volume_knob')
        self.knobSize = self.knob.size()
        return self

    def knobRectFlipped_(self, flipped):
        value = self.floatValue()
        course = self.controlView().bounds().size.width - self.knobSize.width
        origin = NSPoint(course * value, 0)
        return ( origin, (self.knobSize.width, self.controlView().bounds().size.height) )

    def drawKnob_(self, rect):
        self.controlView().lockFocus()
        location = NSPoint(rect.origin.x, rect.origin.y + rect.size.height + 1)
        if self.isEnabled():
            self.knob.compositeToPoint_operation_(location, NSCompositeSourceOver)
        else:
            self.knob.dissolveToPoint_fraction_(location, 0.5)
        self.controlView().unlockFocus()

###############################################################################
