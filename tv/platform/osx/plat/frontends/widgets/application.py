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

import os
import re
import sys
import struct
import logging
import urlparse
import traceback
import time

from objc import YES, NO, nil, signature
from AppKit import *
from Foundation import *
from PyObjCTools import Conversion
from ExceptionHandling import NSExceptionHandler, NSLogAndHandleEveryExceptionMask, NSStackTraceKey

from miro import app
from miro import prefs
from miro import config
from miro import downloader
from miro import messages
from miro import filetypes
from miro import eventloop
from miro import commandline
from miro.frontends.widgets import menus
from miro.frontends.widgets.application import Application
from miro.plat import utils
from miro.plat import growl
from miro.plat import bundle
from miro.plat import _growlImage
from miro.plat import migrateappname
from miro.plat.utils import ensureDownloadDaemonIsTerminated, filename_type_to_os_filename, os_filename_to_filename_type
from miro.plat.frontends.widgets import quicktime, osxmenus, sparkleupdater, threads
from miro.plat.frontends.widgets.rect import Rect
from miro.gtcache import gettext as _

GROWL_GENERIC_NOTIFICATION = u'Misc'
GROWL_DOWNLOAD_COMPLETE_NOTIFICATION = u'Download Complete'

class OSXApplication(Application):

    def __init__(self):
        Application.__init__(self)
        self.gotQuit = False

    def run(self):
        self.app_controller = AppController.alloc().initWithApp_(self)
        NSApplication.sharedApplication().setDelegate_(self.app_controller)
        NSApplicationMain(sys.argv)        

    def connect_to_signals(self):
        Application.connect_to_signals(self)
        eventloop.connect('thread-will-start', self.beginLoop)
        eventloop.connect('thread-did-start', self.endLoop)
        eventloop.connect('begin-loop', self.beginLoop)
        eventloop.connect('end-loop', self.endLoop)
        config.add_change_callback(self.on_pref_changed)

    def startup_ui(self):
        migrateappname.migrateVideos('Democracy', 'Miro')
        osxmenus.populate_menu()
        Application.startup_ui(self)
        app.menu_manager.connect('enabled-changed', osxmenus.on_menu_change)
        quicktime.register_components()

    # This callback should only be called once, after startup is done.
    # (see superclass implementation)
    def on_window_show(self, window):
        Application.on_window_show(self, window)
        self.app_controller.finish_startup()
        
    def on_pref_changed(self, key, value):
        if key == prefs.RUN_AT_STARTUP.key:
            self.set_launch_at_startup(bool(value))

    ### eventloop (our own one, not the Cocoa one) delegate methods
    def beginLoop(self, loop):
        loop.pool = NSAutoreleasePool.alloc().init()

    def endLoop(self, loop):
        del loop.pool

    def do_quit(self):
        if self.window is not None:
            windowFrame = self.window.nswindow.frame()
            windowFrame.size.height -= 22
            config.set(prefs.LEFT_VIEW_SIZE, self.window.splitter.get_left_width())
            config.set(prefs.MAIN_WINDOW_FRAME, NSStringFromRect(windowFrame))
            config.save()
        Application.do_quit(self)

    def quit_ui(self):
        self.gotQuit = True
        NSApplication.sharedApplication().terminate_(nil)

    def get_clipboard_text(self):
        return NSPasteboard.generalPasteboard().stringForType_(NSStringPboardType)

    def copy_text_to_clipboard(self, text):
        pb = NSPasteboard.generalPasteboard()
        pb.declareTypes_owner_([NSStringPboardType], self)
        pb.setString_forType_(text, NSStringPboardType)

    def open_url(self, url):
        # We could use Python's webbrowser.open() here, but
        # unfortunately, it doesn't have the same semantics under UNIX
        # as under other OSes. Sometimes it blocks, sometimes it doesn't.
        if url is not None:
            NSWorkspace.sharedWorkspace().openURL_(NSURL.URLWithString_(url))

    def reveal_file(self, fn):
        filename = filename_type_to_os_filename(fn)
        NSWorkspace.sharedWorkspace().selectFile_inFileViewerRootedAtPath_(filename, nil)
    
    def open_file(self, fn):
        filename = filename_type_to_os_filename(fn)
        ws = NSWorkspace.sharedWorkspace()
        if utils.get_pyobjc_major_version() == 2:
            ok, externalApp, movieType = ws.getInfoForFile_application_type_(filename, None, None)
        else:
            ok, externalApp, movieType = ws.getInfoForFile_application_type_(filename)
        if ok:
            if externalApp == bundle.getBundlePath():
                logging.warn('trying to play movie externally with ourselves.')
                ok = False
            else:
                ok = ws.openFile_withApplication_andDeactivate_(filename, nil, YES)
        if not ok:
            logging.warn("movie %s could not be externally opened" % fn)
    
    def get_main_window_dimensions(self):
        windowFrame = config.get(prefs.MAIN_WINDOW_FRAME)
        if windowFrame is None:
            windowFrame = (0,0,800,600)
        else:
            rect = NSRectFromString(windowFrame)
            windowFrame = (rect.origin.x, rect.origin.y, rect.size.width, rect.size.height)
        return Rect(*windowFrame)

    def send_notification(self, title, body,
                          timeout=5000, attach_trayicon=True):
        self.app_controller.growl_notifier.notify(GROWL_GENERIC_NOTIFICATION, title, body)

    def handle_download_complete(self, obj, item):
        title = _('Download Completed')
        body = _('Download of video \'%s\' is finished.') % item.get_title()
        icon = _growlImage.Image.imageFromPath(item.get_thumbnail())
        self.app_controller.growl_notifier.notify(GROWL_DOWNLOAD_COMPLETE_NOTIFICATION, title, body, icon=icon)

    def handle_unwatched_count_changed(self):
        try:
            appIcon = NSImage.imageNamed_(u'NSApplicationIcon')
            badgedIcon = NSImage.alloc().initWithSize_(appIcon.size())
            badgedIcon.lockFocus()
        except:
            pass
        else:
            try:
                appIcon.compositeToPoint_operation_((0,0), NSCompositeSourceOver)
                if self.unwatched_count > 0:
                    digits = len(str(self.unwatched_count))
                    badge = nil
                    if digits <= 2:
                        badge = NSImage.imageNamed_(u'dock_badge_1_2.png')
                    elif digits <= 5:
                        badge = NSImage.imageNamed_(u'dock_badge_%d.png' % digits)
                    else:
                        logging.warn("Wow, that's a whole lot of new items!")
                    if badge is not nil:
                        appIconSize = appIcon.size()
                        badgeSize = badge.size()
                        badgeLoc = (appIconSize.width - badgeSize.width, appIconSize.height - badgeSize.height)
                        badge.compositeToPoint_operation_(badgeLoc, NSCompositeSourceOver)
                        badgeLabel = NSString.stringWithString_(u'%d' % self.unwatched_count)
                        badgeLabelFont = NSFont.boldSystemFontOfSize_(24)
                        badgeLabelColor = NSColor.whiteColor()
                        badgeParagraphStyle = NSMutableParagraphStyle.alloc().init()
                        badgeParagraphStyle.setAlignment_(NSCenterTextAlignment)
                        badgeLabelAttributes = {NSFontAttributeName: badgeLabelFont, 
                                                NSForegroundColorAttributeName: badgeLabelColor,
                                                NSParagraphStyleAttributeName: badgeParagraphStyle}
                        badgeLabelLoc = (badgeLoc[0], badgeLoc[1]-10)
                        badgeLabel.drawInRect_withAttributes_((badgeLabelLoc, badgeSize), badgeLabelAttributes)
            finally:
                badgedIcon.unlockFocus()
            appl = NSApplication.sharedApplication()
            threads.call_on_ui_thread(appl.setApplicationIconImage_, badgedIcon)
        
    def set_launch_at_startup(self, launch):
        defaults = NSUserDefaults.standardUserDefaults()
        lwdomain = defaults.persistentDomainForName_('loginwindow')
        lwdomain = Conversion.pythonCollectionFromPropertyList(lwdomain)
        if lwdomain is None:
            lwdomain = dict()
        if 'AutoLaunchedApplicationDictionary' not in lwdomain:
            lwdomain['AutoLaunchedApplicationDictionary'] = list()
        launchedApps = lwdomain['AutoLaunchedApplicationDictionary']
        ourPath = NSBundle.mainBundle().bundlePath()
        ourEntry = None
        for entry in launchedApps:
            if entry.get('Path') == ourPath:
                ourEntry = entry
                break

        if launch and ourEntry is None:
            launchInfo = dict(Path=ourPath, Hide=NO)
            launchedApps.append(launchInfo)
        elif ourEntry is not None:
            launchedApps.remove(ourEntry)

        lwdomain = Conversion.propertyListFromPythonCollection(lwdomain)
        defaults.setPersistentDomain_forName_(lwdomain, 'loginwindow')
        defaults.synchronize()

    def handle_update_available(self, obj, item):
        sparkleupdater.handleNewUpdate(item)


class AppController(NSObject):

    def initWithApp_(self, application):
        self.init()

        sparkleupdater.setup()
        
        self.application = application
        self.growl_notifier = None
        self.open_after_startup = None
        self.startup_done = False
        self.pausedDownloaders = list()
        return self

    def setup_growl_notifier(self):
        app_name = config.get(prefs.LONG_APP_NAME)
        notifications = [GROWL_GENERIC_NOTIFICATION, GROWL_DOWNLOAD_COMPLETE_NOTIFICATION]
        self.growl_notifier = growl.GrowlNotifier(app_name, notifications)
        self.growl_notifier.register()

    def applicationWillFinishLaunching_(self, notification):
        NSExceptionHandler.defaultExceptionHandler().setExceptionHandlingMask_(NSLogAndHandleEveryExceptionMask)
        NSExceptionHandler.defaultExceptionHandler().setDelegate_(self)

        man = NSAppleEventManager.sharedAppleEventManager()
        man.setEventHandler_andSelector_forEventClass_andEventID_(
            self,
            "openURL:withReplyEvent:",
            struct.unpack(">i", "GURL")[0],
            struct.unpack(">i", "GURL")[0])

        ws = NSWorkspace.sharedWorkspace()
        wsnc = ws.notificationCenter()
        wsnc.addObserver_selector_name_object_(self, 'workspaceWillSleep:', NSWorkspaceWillSleepNotification, nil)
        wsnc.addObserver_selector_name_object_(self, 'workspaceDidWake:',   NSWorkspaceDidWakeNotification,   nil)

    def applicationDidFinishLaunching_(self, notification):
        try:
            self.setup_growl_notifier()
            self.application.startup()
        except:
            traceback.print_exc()
            NSApplication.sharedApplication().terminate_(nil)

    def finish_startup(self):
        if self.open_after_startup is not None:
            self.do_open_files(self.open_after_startup)
        self.startup_done = True

    def applicationShouldTerminate_(self, sender):
        # External termination requests (through Dock menu or AppleScript) call
        # [NSApplication terminate:] directly, which breaks our shutdown sequence.
        # To fix this we simply check an internal flag which is only True when 
        # the correct shutdown call is made. Otherwise we cancel the current
        # shutdown process and schedule the correct one.
        result = NSTerminateNow
        if not self.application.gotQuit:
            self.application.quit()
            result = NSTerminateLater
        return result

    def downloaderDaemonDidTerminate_(self, notification):
        task = notification.object()
        status = task.terminationStatus()
        logging.info("Downloader daemon has been terminated (status: %d)" % status)

    def applicationWillTerminate_(self, notification):
        # Reset the application icon to its default state
        defaultAppIcon = NSImage.imageNamed_(u'NSApplicationIcon')
        NSApplication.sharedApplication().setApplicationIconImage_(defaultAppIcon)

        ensureDownloadDaemonIsTerminated()    
        app.controller.on_shutdown()

    def exceptionHandler_shouldLogException_mask_(self, handler, exception, mask):
        logging.warn("Unhandled exception: %s", exception.name())
        if os.path.exists("/usr/bin/atos"):
            stack = exception.userInfo().objectForKey_(NSStackTraceKey)
            if stack is None:
                print "No stack available"
            else:
                pid = NSNumber.numberWithInt_(NSProcessInfo.processInfo().processIdentifier()).stringValue()
                args = NSMutableArray.arrayWithCapacity_(20)
                args.addObject_("-p")
                args.addObject_(pid);
                args.addObjectsFromArray_(stack.componentsSeparatedByString_("  "))
            
                task = NSTask.alloc().init()
                task.setLaunchPath_("/usr/bin/atos");
                task.setArguments_(args);
                task.launch();
        else:
            import traceback
            traceback.print_stack()
        return NO

    def applicationShouldHandleReopen_hasVisibleWindows_(self, appl, flag):
        if app.widgetapp is not None and app.widgetapp.window is not None:
            mainWindow = app.widgetapp.window.nswindow
            if mainWindow is not None:
                if not flag:
                    app.widgetapp.window.nswindow.makeKeyAndOrderFront_(nil)
                if mainWindow.isMiniaturized():
                    mainWindow.deminiaturize_(appl)            
        return NO

    def application_openFiles_(self, nsapp, filenames):
        filenames = [os_filename_to_filename_type(f) for f in filenames]
        if self.startup_done:
            self.do_open_files(filenames)
        else:
            self.open_after_startup = filenames
        nsapp.replyToOpenOrPrint_(NSApplicationDelegateReplySuccess)

    def do_open_files(self, filenames):
        messages.OpenIndividualFiles(filenames).send_to_backend()

    def workspaceWillSleep_(self, notification):
        def pauseRunningDownloaders(self=self):
            self.pausedDownloaders = list()
            for dl in downloader.RemoteDownloader.make_view():
                if dl.get_state() == 'downloading':
                    self.pausedDownloaders.append(dl)
            dlCount = len(self.pausedDownloaders)
            if dlCount > 0:
                logging.info("System is going to sleep, suspending %d download(s)." % dlCount)
                for dl in self.pausedDownloaders:
                    dl.pause()
        dc = eventloop.addUrgentCall(lambda:pauseRunningDownloaders(), "Suspending downloaders for sleep")
        # Until we can get proper delayed call completion notification, we're
        # just going to wait a few seconds here :)
        time.sleep(3)
        #dc.waitCompletion()

    def workspaceDidWake_(self, notification):
        def restartPausedDownloaders(self=self):
            dlCount = len(self.pausedDownloaders)
            if dlCount > 0:
                logging.info("System is awake from sleep, resuming %s download(s)." % dlCount)
                try:
                    for dl in self.pausedDownloaders:
                        dl.start()
                finally:
                    self.pausedDownloaders = list()
        eventloop.addUrgentCall(lambda:restartPausedDownloaders(), "Resuming downloaders after sleep")

    @signature('v@:@@')
    def openURL_withReplyEvent_(self, event, replyEvent):
        keyDirectObject = struct.unpack(">i", "----")[0]
        url = event.paramDescriptorForKeyword_(keyDirectObject).stringValue().encode('utf8')

        eventloop.addIdle(lambda: commandline.parse_command_line_args([url]), "Open URL")

    def validateUserInterfaceItem_(self, menuitem):
        action = menuitem.representedObject()
        group_names = menus.osx_menu_structure.get(action).groups
        for group_name in group_names:
            if group_name in app.menu_manager.enabled_groups:
                return True
        return False

    def handleMenuItem_(self, sender):
        action = sender.representedObject()
        if action == "PresentActualSize":
            self.present_movie('natural-size')
        elif action == "PresentDoubleSize":
            self.present_movie('double-size')
        elif action == "PresentHalfSize":
            self.present_movie('half-size')
        elif action == "ShowMain":
            app.widgetapp.window.nswindow.makeKeyAndOrderFront_(sender)
        else:
            handler = menus.lookup_handler(action)
            if handler is not None:
                handler()
            else:
                logging.warn("No handler for %s" % action)
    
    def present_movie(self, mode):
        if app.playback_manager.is_playing:
            app.playback_manager.set_presentation_mode(mode)
        else:
            app.item_list_controller_manager.play_selection(mode)
