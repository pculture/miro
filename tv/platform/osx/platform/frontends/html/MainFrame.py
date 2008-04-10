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
import math
import logging

from objc import YES, NO, nil, IBOutlet
from AppKit import *
from Foundation import *

from miro import app
from miro import feed
from miro import prefs
from miro import views
from miro import config
from miro import folder
from miro import dialogs
from miro.frontends.html import keyboard
from miro import playlist
from miro.platform import resources
from miro import eventloop
from miro import searchengines
from miro.platform.frontends.html import threads

from miro.gtcache import gettext as _

###############################################################################

class MainFrame:

    def __init__(self, appl):
        self.channelsDisplay = None
        self.mainDisplay = None
        self.videoInfoDisplay = None
        # Do this in two steps so that self.controller is set when self.controler.init
        # is called. That way, init can turn around and call selectDisplay.
        self.controller = MainController.alloc()
        self.controller.initWithFrame_application_(self, appl)

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

class MainController (NSWindowController):

    channelsHostView        = IBOutlet('channelsHostView')
    mainHostView            = IBOutlet('mainHostView')
    splitView               = IBOutlet('splitView')
    videoDisplayController  = IBOutlet('videoDisplayController')
    videoInfoHostView       = IBOutlet('videoInfoHostView')

    def initWithFrame_application_(self, frame, appl):
        super(MainController, self).init()
        self.frame = frame
        self.appl = appl
        self.menuStrings = dict()
        self.actionGroups = dict()
        NSBundle.loadNibNamed_owner_(u"MainWindow", self)

        nc = NSNotificationCenter.defaultCenter()
        nc.addObserver_selector_name_object_(
            self,
            'appWillTerminate:',
            NSApplicationWillTerminateNotification,
            NSApplication.sharedApplication())

        return self

    def awakeFromNib(self):
        self.frame.channelsDisplay = self.channelsHostView
        self.frame.mainDisplay = self.mainHostView
        self.frame.videoInfoDisplay = self.videoInfoHostView
        self.frame.videoInfoDisplay.backgroundColor = NSColor.blackColor()
        self.restoreLayout()
        self.window().setTitle_(config.get(prefs.LONG_APP_NAME))
        self.showWindow_(nil)

    def appWillTerminate_(self, notification):
        self.saveLayout()

    def restoreLayout(self):
        if app.delegate.maximizeMainFrameWhenAvailable:
            app.delegate.doMaximizeWindow(self.window())
        else:
            windowFrame = config.get(prefs.MAIN_WINDOW_FRAME)
            if windowFrame is None:
                windowFrame = self.window().frame()
            else:
                windowFrame = NSRectFromString(windowFrame)
            screen = self.window().screen()
            if screen is not None:
                visibleFrame = screen.visibleFrame()
                if not NSContainsRect(visibleFrame, windowFrame):
                    logging.debug("Fitting window to screen size")
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
    
    def windowDidResignMain_(self, notification):
        self.window().display()

    def windowDidBecomeMain_(self, notification):
        self.window().display()
    
    ### Switching displays ###

    @threads.onMainThread
    def onSelectedTabChange(self, strings, actionGroups, guideURL, videoFilename):
        app.controller.setGuideURL(guideURL)
        self.menuStrings = strings
        self.actionGroups = actionGroups
        
        if actionGroups['VideoPlayable']:
            notification = u'notifyPlayable'
        else:
            notification = u'notifyNotPlayable'
        nc = NSNotificationCenter.defaultCenter()
        nc.postNotificationName_object_(notification, nil)

    def selectDisplay(self, display, area):
        if display is not None:
            # Tell the display area that the next display it will host once it's
            # ready is this one.
            area.setScheduledDisplay(display)
            # Tell the new display we want to switch to it. It'll call us
            # back when it's ready to display without flickering.
            display.callWhenReadyToDisplay(lambda: self.doSelectDisplay(display, area))

    @threads.onMainThreadWaitingUntilDone
    def doSelectDisplay(self, display, area):
        if area is not None:
            area.setDisplay(display, self.frame)

    def getDisplaySizeHint(self, area):
        return area.frame()

    ### Size constraints on splitview ###

    minimumTabListWidth = 160 # pixels
    minimumContentWidth = 500 # pixels

    # How far left can the user move the slider?
    def splitView_constrainMinCoordinate_ofSubviewAt_(self, sender, proposedMin, offset):
        return max(proposedMin, self.minimumTabListWidth)

    # How far right can the user move the slider?
    def splitView_constrainMaxCoordinate_ofSubviewAt_(self, sender, proposedMax, offset):
        return min(proposedMax, self.minimumContentWidth)

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
        if hasattr(app.controller, 'videoDisplay'):
            return self.channelsHostView.isDescendantOf_(subview) and app.htmlapp.videoDisplay.isSelected()
        else:
            return NO

    ### Events ###

    def keyDown_(self, event):
        handleKey(event)

    ### Actions ###

    # File menu #

    def removeVideos_(self, sender):
        eventloop.addIdle(app.controller.removeCurrentItems, "Remove Videos")

    def saveVideoAs_(self, sender):
        print "NOT IMPLEMENTED" # $$$$$$$$$$$$$$

    def copyVideoURL_(self, sender):
        eventloop.addIdle(app.htmlapp.copyCurrentItemURL, "Copy Video URL")

    # Edit menu #
    
    def deleteSelected_(self, sender):
        eventloop.addIdle(app.controller.removeCurrentSelection, "Copy Video URL")

    # Channels menu #

    def addChannel_(self, sender):
        def validationCallback(dialog):
            if dialog.choice == dialogs.BUTTON_OK:
                url = dialog.value
                eventloop.addUrgentCall(lambda:app.htmlapp.addAndSelectFeed(url), "Add Feed")
        title = _(u"Subscribe to Channel")
        description = _(u"Enter the URL of the channel you would like to subscribe to.")
        prefillCallback = app.delegate.getURLFromClipboard
        dlog = dialogs.TextEntryDialog(title, description, dialogs.BUTTON_OK, dialogs.BUTTON_CANCEL, prefillCallback)
        dlog.run(validationCallback)

    def createSearchChannel_(self, sender):
        eventloop.addIdle(lambda:app.htmlapp.addSearchFeed(), "Add Search Feed")

    def createChannelFolder_(self, sender):
        folder.createNewChannelFolder()

    def addGuide_(self, sender):
        eventloop.addIdle(lambda:app.htmlapp.addAndSelectGuide(), "Add Guide")

    def renameChannelFolder_(self, sender):
        eventloop.addIdle(app.controller.renameCurrentTab, "Rename Channel Tab")

    def removeChannel_(self, sender):
        eventloop.addIdle(app.controller.removeCurrentFeed, "Remove channel")

    def updateChannel_(self, sender):
        eventloop.addIdle(app.controller.updateCurrentFeed, "Update current feed")

    def updateAllChannels_(self, sender):
        eventloop.addIdle(app.controller.updateAllFeeds, "Update all channels")

    def tellAFriend_(self, sender):
        eventloop.addIdle(app.htmlapp.recommendCurrentFeed, "Recommend current feed")

    def copyChannelURL_(self, sender):
        eventloop.addIdle(app.htmlapp.copyCurrentFeedURL, "Copy channel URL")

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
        eventloop.addIdle(lambda:app.htmlapp.playbackController.skip(1), "Skip Video")

    def previousVideo_(self, sender):
        eventloop.addIdle(lambda:app.htmlapp.playbackController.skip(-1, False), "Skip Video")

    def toggleFullScreen_(self, sender):
        self.videoDisplayController.playFullScreen_(sender)

    # Help menu #

    def showHelp_(self, sender):
        helpURL = NSURL.URLWithString_(config.get(prefs.HELP_URL))
        NSWorkspace.sharedWorkspace().openURL_(helpURL)
    
    def reportBug_(self, sender):
        reportURL = NSURL.URLWithString_(config.get(prefs.BUG_REPORT_URL))
        NSWorkspace.sharedWorkspace().openURL_(reportURL)

    def goToTranslationSite_(self, sender):
        translateURL = NSURL.URLWithString_(config.get(prefs.TRANSLATE_URL))
        NSWorkspace.sharedWorkspace().openURL_(translateURL)

    def goToPlanetSite_(self, sender):
        translateURL = NSURL.URLWithString_(config.get(prefs.PLANET_URL))
        NSWorkspace.sharedWorkspace().openURL_(translateURL)

    ### Menu items validation ###

    def validateMenuItem_(self, item):
        action = item.action()
        display = self.frame.mainDisplay.hostedDisplay
        
        if action == 'removeVideos:':
            self.updateMenuItem(item, 'video_remove')
            return self.actionGroups['VideoSelected'] or self.actionGroups['VideosSelected']
        elif action == 'saveVideoAs:':
            return False
        elif action == 'copyVideoURL:':
            return self.actionGroups['VideoSelected']
        elif action == 'deleteSelected:':
            return (self.actionGroups['ChannelLikeSelected'] or
                    self.actionGroups['ChannelLikesSelected'] or
                    self.actionGroups['PlaylistLikeSelected'] or
                    self.actionGroups['PlaylistLikesSelected'] or
                    self.actionGroups['VideoSelected'] or
                    self.actionGroups['VideosSelected'])
        elif action == 'addChannel:':
            return True
        elif action == 'createSearchChannel:':
            return True
        elif action == 'createChannelFolder:':
            return True
        elif action == 'addGuide:':
            return True
        elif action == 'renameChannelFolder:':
            self.updateMenuItem(item, 'channel_rename')
            return self.actionGroups['ChannelLikeSelected']
        elif action == 'removeChannel:':
            self.updateMenuItem(item, 'channel_remove')
            return self.actionGroups['ChannelLikeSelected'] or self.actionGroups['ChannelLikesSelected']
        elif action == 'updateChannel:':
            self.updateMenuItem(item, 'channel_update')
            return self.actionGroups['ChannelLikeSelected'] or self.actionGroups['ChannelLikesSelected']
        elif action == 'updateAllChannels:':
            return True
        elif action == 'tellAFriend:':
            return self.actionGroups['ChannelSelected']
        elif action == 'copyChannelURL:':
            return self.actionGroups['ChannelSelected']
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
            return display is app.htmlapp.videoDisplay or self.actionGroups['VideoPlayable']
        elif action == 'stopVideo:':
            return display is app.htmlapp.videoDisplay
        elif action == 'nextVideo:':
            return display is app.htmlapp.videoDisplay
        elif action == 'previousVideo:':
            return display is app.htmlapp.videoDisplay
        elif action == 'toggleFullScreen:':
            return display is app.htmlapp.videoDisplay
        elif action == 'showHelp:':
            return True
        elif action in ('reportBug:', 'goToTranslationSite:', 'goToPlanetSite:'):
            return True
        return False

    def updateMenuItem(self, item, key):
        pass # Disabling this feature for now while I change the API --NN
        #if key in self.menuStrings:
        #    item.setTitle_(self.menuStrings[key].replace('_', ''))

###############################################################################

class RootView (NSView):
    
    def awakeFromNib(self):
        texture = NSImage.imageNamed_("wtexture.png")
        self.textureHeight = texture.size().height
        self.textureColor = NSColor.colorWithPatternImage_(texture)
        self.separatorColor = NSColor.colorWithDeviceWhite_alpha_(170.0/255.0, 1.0)
        self.highlightColorLeft = NSColor.colorWithDeviceWhite_alpha_(212.0/255.0, 1.0)
        self.highlightColorTop = NSColor.colorWithDeviceWhite_alpha_(218.0/255.0, 1.0)

        textureInactive = NSImage.imageNamed_("wtexture_inactive.png")
        self.textureHeightInactive = textureInactive.size().height
        self.textureColorInactive = NSColor.colorWithPatternImage_(textureInactive)
        self.separatorColorInactive = NSColor.colorWithDeviceWhite_alpha_(170.0/255.0, 1.0)
        self.highlightColorLeftInactive = NSColor.colorWithDeviceWhite_alpha_(212.0/255.0, 1.0)
        self.highlightColorTopInactive = NSColor.colorWithDeviceWhite_alpha_(239.0/255.0, 1.0)

    def isOpaque(self):
        return YES

    def drawRect_(self, rect):
        if self.window().isMainWindow():
            textureColor = self.textureColor
            textureHeight = self.textureHeight
            highlightColorLeft = self.highlightColorLeft
            highlightColorTop = self.highlightColorTop
            separatorColor = self.separatorColor
        else:
            textureColor = self.textureColorInactive
            textureHeight = self.textureHeightInactive
            highlightColorLeft = self.highlightColorLeftInactive
            highlightColorTop = self.highlightColorTopInactive
            separatorColor = self.separatorColorInactive

        textureColor.set()
        NSRectFill(rect)
    
        p1 = NSPoint(0.5, 0)
        p2 = NSPoint(0.5, textureHeight + 0.5)
        highlightColorLeft.set()
        NSBezierPath.strokeLineFromPoint_toPoint_(p1, p2)
    
        p1 = NSPoint(0, textureHeight + 0.5)
        p2 = NSPoint(self.bounds().size.width, textureHeight + 0.5)
        highlightColorTop.set()
        NSBezierPath.strokeLineFromPoint_toPoint_(p1, p2)

        p1.y += 1.0
        p2.y += 1.0
        separatorColor.set()
        NSBezierPath.strokeLineFromPoint_toPoint_(p1, p2)
            
###############################################################################

class PlacardView (NSView):

    splitView = IBOutlet("splitView")

    def awakeFromNib(self):
        self.background = NSImage.imageNamed_("left_bar_background.png")
        self.backgroundColor = NSColor.colorWithPatternImage_(self.background)
        self.dragHandle = NSImage.imageNamed_("left_bar_drag_handle.png")
        self.separatorColor = NSColor.colorWithDeviceRed_green_blue_alpha_(188.0/255.0, 196.0/255.0, 215.0/255.0, 1.0)
        self.inDragArea = False
        self.dragOffset = 0.0

    def isOpaque(self):
        return YES

    def getDragHandlePosition(self):
        return NSPoint(self.frame().size.width - self.dragHandle.size().width ,0)

    def getDragHandleFrame(self):
        return NSRect(self.getDragHandlePosition(), self.dragHandle.size())

    def drawRect_(self, rect):
        self.backgroundColor.set()
        NSGraphicsContext.currentContext().setPatternPhase_((0,2))
        NSRectFill(rect)

        self.dragHandle.compositeToPoint_operation_(self.getDragHandlePosition(), NSCompositeSourceOver)

        self.separatorColor.set()
        NSBezierPath.strokeLineFromPoint_toPoint_((0,21.5), (rect.size.width, 21.5))

    def resetCursorRects(self):
        self.addCursorRect_cursor_(self.getDragHandleFrame(), NSCursor.resizeLeftRightCursor())

    def mouseDown_(self, event):
        clickLocation = self.convertPoint_fromView_(event.locationInWindow(), nil)
        self.inDragArea = NSPointInRect(clickLocation, self.getDragHandleFrame())

        if not self.inDragArea:
            return

    	clickLocation = self.convertPoint_fromView_(event.locationInWindow(), self.superview())
    	self.dragOffset = NSWidth(self.superview().frame()) - clickLocation.x;
    
    def mouseDragged_(self, event):
        if not self.inDragArea:
            return
        
        NSNotificationCenter.defaultCenter().postNotificationName_object_(NSSplitViewWillResizeSubviewsNotification, self.splitView)

        clickLocation = self.convertPoint_fromView_(event.locationInWindow(), self.superview())
        newFrame = self.superview().frame()
        newFrame.size.width = clickLocation.x + self.dragOffset

        delegate = self.splitView.delegate()
        if delegate is not None:
            if delegate.respondsToSelector_('splitView:constrainSplitPosition:ofSubviewAt:'):
                neww = delegate.splitView_constrainSplitPosition_ofSubviewAt_(self.splitView, newFrame, 0)
                newFrame.size.width = neww
            if delegate.respondsToSelector_('splitView:constrainMinCoordinate:ofSubviewAt:'):
                minw = delegate.splitView_constrainMinCoordinate_ofSubviewAt_(self.splitView, 0, 0)
                newFrame.size.width = max(minw, newFrame.size.width)
            if delegate.respondsToSelector_('splitView:constrainMaxCoordinate:ofSubviewAt:'):
                maxw = delegate.splitView_constrainMaxCoordinate_ofSubviewAt_(self.splitView, self.window().frame().size.width, 0)
                newFrame.size.width = min(maxw, newFrame.size.width)

        self.superview().setFrame_(newFrame)
        self.splitView.adjustSubviews()

        NSNotificationCenter.defaultCenter().postNotificationName_object_(NSSplitViewDidResizeSubviewsNotification, self.splitView)
    
###############################################################################

class DisplayHostView (NSView):
    
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
        threads.warnIfNotOnMainThread('DisplayHostView.setDisplay')
        self.scheduledDisplay = None

        # Send notification to old display if any
        if self.hostedDisplay is not None:
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
        display.onSelected(owner)

###############################################################################

class DTVSplitView (NSSplitView):
    
    def awakeFromNib(self):
        self.color = NSColor.colorWithDeviceWhite_alpha_(148.0/255.0, 1.0)
        self.leftPane = nil
        self.collapsed = False
        NSNotificationCenter.defaultCenter().addObserver_selector_name_object_(self, 'videoDisplayWasSelected:', 'VideoDisplayWasSelected', nil)
        NSNotificationCenter.defaultCenter().addObserver_selector_name_object_(self, 'videoDisplayWasDeselected:', 'VideoDisplayWasDeselected', nil)

    def dividerThickness(self):
        if self.collapsed:
            return 0.0
        return 1.0
        
    def drawDividerInRect_(self, rect):
        p1 = rect.origin
        p1.x += 0.5
        p2 = NSPoint(p1.x, rect.size.height)
        self.color.set()
        NSBezierPath.strokeLineFromPoint_toPoint_(p1, p2)
    
    def videoDisplayWasSelected_(self, notification):
        self.collapseLeftPane()
    
    def collapseLeftPane(self):
        self.leftPane = self.subviews().objectAtIndex_(0)
        self.collapsed = True
        tempView = NSView.alloc().initWithFrame_(NSZeroRect)
        self.replaceSubview_with_(self.leftPane, tempView)
        self.adjustSubviews()

    def videoDisplayWasDeselected_(self, notification):
        self.revealLeftPane()
    
    def revealLeftPane(self):
        leftPane = self.subviews().objectAtIndex_(0)
        self.collapsed = False
        self.replaceSubview_with_(leftPane, self.leftPane)
        self.adjustSubviews()
        self.leftPane = nil

###############################################################################

class ProgressDisplayView (NSView):

    progressSlider          = IBOutlet('progressSlider')
    timeIndicator           = IBOutlet('timeIndicator')
    remainingTimeIndicator  = IBOutlet('remainingTimeIndicator')

    def awakeFromNib(self):
        self.progressSlider.sliderWasClicked = self.progressSliderWasClicked
        self.progressSlider.sliderWasDragged = self.progressSliderWasDragged
        self.progressSlider.sliderWasReleased = self.progressSliderWasReleased
        self.backgroundLeft = NSImage.imageNamed_(u"display_left" )
        self.backgroundRight = NSImage.imageNamed_(u"display_right" )
        self.backgroundCenter = NSImage.imageNamed_(u"display_center" )
        self.renderer = None
        self.updateTimer = nil
        self.wasPlaying = False
        self.displayRemaining = False
        self.remainingIndicatorAttributes = {
            NSFontAttributeName:            self.timeIndicator.font(), 
            NSForegroundColorAttributeName: self.timeIndicator.textColor()}
        
        self.refresh_(nil)

    @threads.onMainThread
    def setup(self, renderer):
        if self.renderer != renderer:
            self.renderer = renderer
            if renderer is not nil:
                self.updateTimer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(0.5, self, 'refresh:', nil, YES)
                NSRunLoop.currentRunLoop().addTimer_forMode_(self.updateTimer, NSEventTrackingRunLoopMode)
            elif self.updateTimer is not nil:
                self.updateTimer.invalidate()
                self.updateTimer = nil
        self.refresh_(nil)
        self.setNeedsDisplay_(YES)

    def teardown(self):
        self.setup(None)

    def refresh_(self, timer):
        if self.renderer is None:
            self.progressSlider.setShowCursor_(False)
            self.progressSlider.setFloatValue_(0.0)
            self.timeIndicator.setStringValue_('')
            self.updateRemainingTimeIndicator('')
        else:
            self.progressSlider.setShowCursor_(True)
            self.renderer.getProgress(lambda p: self.progressSlider.setFloatValue_(p))
            self.renderer.getDisplayTime(lambda t: self.timeIndicator.setStringValue_(unicode(t)))
            if self.displayRemaining:
                self.renderer.getDisplayRemainingTime(lambda t: self.updateRemainingTimeIndicator(t))
            else:
                self.renderer.getDisplayDuration(lambda t: self.updateRemainingTimeIndicator(t))
    
    def updateRemainingTimeIndicator(self, content):
        title = NSAttributedString.alloc().initWithString_attributes_(unicode(content), self.remainingIndicatorAttributes)
        self.remainingTimeIndicator.setAttributedTitle_(title)

    def drawRect_(self, rect):
        fraction = 1.0
        if self.renderer is None:
            fraction = 0.4
        drawThreePartsWidget(self.backgroundLeft, self.backgroundCenter, self.backgroundRight, self.bounds(), fraction)

    def toggleRemainingTimeIndicator_(self, sender):
        self.displayRemaining = not self.displayRemaining
        self.refresh_(nil)

    def progressSliderWasClicked(self, slider):
        if app.htmlapp.videoDisplay.isPlaying:
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

    @threads.onMainThread
    def setFloatValue_(self, value):
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

###############################################################################

class ChromeProgressSlider (Slider):

    def initWithFrame_(self, frame):
        self = super(ChromeProgressSlider, self).initWithFrame_(frame)
        self.cursor = NSImage.imageNamed_(u'playback_cursor')
        self.trackLeft = NSImage.imageNamed_(u'playback_track_left')
        self.trackCenter = NSImage.imageNamed_(u'playback_track_center')
        self.trackRight = NSImage.imageNamed_(u'playback_track_right')
        self.trackProgressLeft = NSImage.imageNamed_(u'playback_track_progress_left')
        self.trackProgressCenter = NSImage.imageNamed_(u'playback_track_progress_center')
        self.trackProgressRight = NSImage.imageNamed_(u'playback_track_progress_right')
        return self
    
    def drawTrack(self):
        drawThreePartsWidget(self.trackLeft, self.trackCenter, self.trackRight, self.bounds())
        progressBounds = self.bounds()
        cursorPos = self.getCursorPosition()
        progressBounds.size.width = cursorPos + (self.cursor.size().width / 2.0)
        drawThreePartsWidget(self.trackProgressLeft, self.trackProgressCenter, self.trackProgressRight, progressBounds)
        
###############################################################################

class ProgressSlider (Slider):
    
    def initWithFrame_(self, frame):
        self = super(ProgressSlider, self).initWithFrame_(frame)
        self.grooveContourColor = NSColor.colorWithDeviceWhite_alpha_( 0.1, 0.3 )
        self.grooveFillColor = NSColor.colorWithDeviceWhite_alpha_( 0.5, 0.3 )
        self.cursor = NSImage.alloc().initWithSize_((10,10))
        self.cursor.lockFocus()
        path = NSBezierPath.bezierPath()
        path.moveToPoint_((0, 4.5))
        path.lineToPoint_((4, 8))
        path.lineToPoint_((8, 4.5))
        path.lineToPoint_((4, 1))
        path.closePath()
        NSColor.colorWithDeviceWhite_alpha_( 51/255.0, 1.0 ).set()
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

class MetalSlider (NSSlider):

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
        self.track = NSImage.imageNamed_(u'volume_track')
        self.trackSize = self.track.size()
        self.knob = NSImage.imageNamed_(u'volume_knob')
        self.knobSize = self.knob.size()
        return self

    def drawBarInside_flipped_(self, rect, flipped):
        location = NSPoint(rect.origin.x, 2 + (rect.size.height - self.trackSize.height) / 2)
        if self.isEnabled():
            self.track.compositeToPoint_operation_(location, NSCompositeSourceOver)
        else:
            self.track.dissolveToPoint_fraction_(location, 0.5)

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

class VideoSearchField (NSSearchField):

    def awakeFromNib(self):
        self.setCell_(VideoSearchFieldCell.alloc().initWithCell_(self.cell()))
        self.setTarget_(self)
        self.setAction_('search:')
        self.initFromLastEngine()
        
    def search_(self, sender):
        engine = self.selectedEngine()
        query = unicode(self.stringValue())
        if query != '':
            eventloop.addIdle(lambda:app.htmlapp.performSearch(engine, query), 'Performing chrome search')

    def initFromLastEngine(self):
        self.setStringValue_("")
        lastEngine = searchengines.getLastEngine()
        for engine in views.searchEngines:
            if engine.name == lastEngine:
                menu = self.searchMenuTemplate()
                index = menu.indexOfItemWithRepresentedObject_(engine)
                menu.performActionForItemAtIndex_(index)
                return

    def selectedEngine(self):
        return self.cell().currentItem.representedObject().name
        
###############################################################################

class VideoSearchFieldCell (NSSearchFieldCell):
    
    def initWithCell_(self, cell):
        self = super(VideoSearchFieldCell, self).initTextCell_('')
        self.setBezeled_(cell.isBezeled())
        self.setBezelStyle_(cell.bezelStyle())
        self.setEnabled_(cell.isEnabled())
        self.setPlaceholderString_(cell.placeholderString())
        self.setEditable_(cell.isEditable())
        self.setSearchButtonCell_(cell.searchButtonCell())
        self.setCancelButtonCell_(cell.cancelButtonCell())
        self.cancelButtonCell().setTarget_(self)
        self.setSearchMenuTemplate_(self.makeSearchMenuTemplate())
        self.setSendsWholeSearchString_(YES)
        self.setScrollable_(YES)
        self.currentItem = nil
        return self
    
    def makeSearchMenuTemplate(self):
        menu = NSMenu.alloc().init()
        for engine in reversed(views.searchEngines):
            nsitem = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(engine.title, 'selectEngine:', '')
            nsitem.setTarget_(self)
            nsitem.setImage_(_getEngineIcon(engine))
            nsitem.setRepresentedObject_(engine)
            menu.insertItem_atIndex_(nsitem, 0)
        return menu

    def selectEngine_(self, sender):
        if self.currentItem is not nil:
            self.currentItem.setState_(NSOffState)
        self.currentItem = sender
        sender.setState_(NSOnState)
        engine = sender.representedObject()
        self.searchButtonCell().setImage_(_getSearchIcon(engine))
    
    def searchButtonRectForBounds_(self, bounds):
        return NSRect(NSPoint(8.0, 3.0), NSSize(25.0, 16.0))
        
    def searchTextRectForBounds_(self, bounds):
        cancelButtonBounds = super(VideoSearchFieldCell, self).cancelButtonRectForBounds_(bounds)
        searchButtonBounds = self.searchButtonRectForBounds_(bounds)
        x = searchButtonBounds.origin.x + searchButtonBounds.size.width + 2
        width = bounds.size.width - x - cancelButtonBounds.size.width
        return ((x, 3.0), (width, 16.0))

###############################################################################

def drawThreePartsWidget(left, center, right, bounds, fraction=1.0):
    NSGraphicsContext.currentContext().saveGraphicsState()
    NSBezierPath.clipRect_(bounds)

    leftWidth = left.size().width
    centerWidth = center.size().width
    rightWidth = right.size().width

    def drawPart(image, at, fraction):
        if fraction == 1.0:
            image.compositeToPoint_operation_(at, NSCompositeSourceOver)
        else:
            image.dissolveToPoint_fraction_(at, fraction)
    
    drawPart(left, (0,0), fraction)
    if bounds.size.width > leftWidth:
        x = bounds.size.width - rightWidth
        drawPart(right, (x, 0), fraction)
        if bounds.size.width > leftWidth + centerWidth:
            emptyWidth = bounds.size.width - (rightWidth + leftWidth)
            emptyRect = ((leftWidth, 0), (emptyWidth, bounds.size.height))
            NSGraphicsContext.currentContext().saveGraphicsState()
            NSBezierPath.clipRect_(emptyRect)
            tiles = math.ceil(emptyWidth / float(centerWidth))
            for i in range(0, int(tiles)):
                x = leftWidth + (i * centerWidth)
                drawPart(center, (x,0), fraction)
            NSGraphicsContext.currentContext().restoreGraphicsState()

    NSGraphicsContext.currentContext().restoreGraphicsState()

###############################################################################

def _getEngineIcon(engine):
    engineIconPath = resources.path('images/search_icon_%s.png' % engine.name)
    if not os.path.exists(engineIconPath):
        return nil
    return NSImage.alloc().initByReferencingFile_(engineIconPath)

searchIcons = dict()
def _getSearchIcon(engine):
    if engine.name not in searchIcons:
        searchIcons[engine.name] = _makeSearchIcon(engine)
    return searchIcons[engine.name]        

def _makeSearchIcon(engine):
    popupRectangle = NSImage.imageNamed_(u'search_popup_rectangle')
    popupRectangleSize = popupRectangle.size()

    engineIconPath = resources.path('images/search_icon_%s.png' % engine.name)
    if not os.path.exists(engineIconPath):
        return nil
    engineIcon = NSImage.alloc().initByReferencingFile_(engineIconPath)
    engineIconSize = engineIcon.size()

    searchIconSize = (engineIconSize.width + popupRectangleSize.width + 2, engineIconSize.height)
    searchIcon = NSImage.alloc().initWithSize_(searchIconSize)
    
    searchIcon.lockFocus()
    try:
        engineIcon.compositeToPoint_operation_((0,0), NSCompositeSourceOver)
        popupRectangleX = engineIconSize.width + 2
        popupRectangleY = (engineIconSize.height - popupRectangleSize.height) / 2
        popupRectangle.compositeToPoint_operation_((popupRectangleX, popupRectangleY), NSCompositeSourceOver)
    finally:
        searchIcon.unlockFocus()

    return searchIcon

###############################################################################
#### KEYBOARD MAP                                                          ####
###############################################################################

KEYMAP = {
    0x20:   keyboard.SPACE,
    0x1B:   keyboard.ESCAPE,
    0xF700: keyboard.UP,
    0xF701: keyboard.DOWN,
    0xF702: keyboard.LEFT,
    0xF703: keyboard.RIGHT,
}

def mapKey(event):
    chars = event.characters()
    if chars == '':
        return keyboard.UNSUPPORTED
    try:
        key = chars.characterAtIndex_(0)
        return KEYMAP[key]
    except KeyError:
        return keyboard.UNSUPPORTED

def handleKey(event):
    key = mapKey(event)
    shift = event.modifierFlags() & NSShiftKeyMask
    control = event.modifierFlags() & NSControlKeyMask
    keyboard.handleKey(key, shift, control)
