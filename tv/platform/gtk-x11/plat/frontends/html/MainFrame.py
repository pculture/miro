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

# FIXME - these should probably be moved to a central place along with
# similar statements in other platforms.
COPYRIGHT = """Copyright (c) 2005-2008.  See LICENSE file for details.
Miro and the Miro logo are trademarks of the Participatory Culture Foundation."""
WEBSITE = """http://www.getmiro.com/"""

from miro import app
import pygtk
pygtk.require('2.0')
import gtk
import gobject
import gtk.glade
import sets
import gconf
from miro import menubar
from miro.gtcache import gettext as _

from miro.plat import resources
from miro.plat.utils import confirmMainThread
from miro.plat.frontends.html import UIBackendDelegate
from miro.plat.frontends.html.gtk_queue import gtkAsyncMethod, gtkSyncMethod
from miro.plat.frontends.html.VideoDisplay import VideoDisplay
from miro.plat.frontends.html.callbackhandler import CallbackHandler
from miro.plat.frontends.html.mainwindowchanger import MainWindowChanger
from miro.plat.frontends.html import trayicon
from miro.plat.frontends.html.HTMLDisplay import HTMLDisplay
from miro.plat.config import gconf_lock
from miro import config
from miro import prefs
import logging

# Extent the ShortCut class to include a GTKString() function
def ShortCutMixin(self):
    GTK_MOD_STRINGS = {menubar.CTRL : '<Control>',
                       menubar.ALT:   '<Alt>',
                       menubar.SHIFT: '<Shift>'}
    GTK_KEY_STRINGS = {menubar.RIGHT_ARROW : 'Right',
                       menubar.LEFT_ARROW :   'Left',
                       menubar.UP_ARROW : 'Up',
                       menubar.DOWN_ARROW :   'Down',
                       menubar.SPACE : 'space',
                       menubar.ENTER: 'Enter',
                       menubar.DELETE: 'Delete',
                       menubar.BKSPACE: 'BackSpace',
                       menubar.F1: 'F1',
                       menubar.F2: 'F2',
                       menubar.F3: 'F3',
                       menubar.F4: 'F4',
                       menubar.F5: 'F5',
                       menubar.F6: 'F6',
                       menubar.F7: 'F7',
                       menubar.F8: 'F8',
                       menubar.F9: 'F9',
                       menubar.F10: 'F10',
                       menubar.F11: 'F11',
                       menubar.F12: 'F12',
                       }

    if self.key is None:
        return None
    output = []
    for modifier in self.modifiers:
        output.append(GTK_MOD_STRINGS[modifier])
    if isinstance(self.key, int):
        output.append(GTK_KEY_STRINGS[self.key])
    else:
        output.append(self.key)
    return ''.join(output)
menubar.ShortCut.GTKString = ShortCutMixin

def _getPref(key, getter_name):
    gconf_lock.acquire()
    try:
        client = gconf.client_get_default()
        fullkey = '/apps/miro/' + key
        value = client.get(fullkey)
        if value is not None:
            getter = getattr(value, getter_name)
            return getter()
        else:
            return None
    finally:
        gconf_lock.release()

def _setPref(key, setter_name, value):
    gconf_lock.acquire()
    try:
        client = gconf.client_get_default()
        fullkey = '/apps/miro/' + key
        setter = getattr(client, setter_name)
        setter(fullkey, value)
    finally:
        gconf_lock.release()

def getInt(key): return _getPref('window/' + key, 'get_int')
def getBool(key): return _getPref('window/' + key, 'get_bool')
def getPlayerInt(key): return _getPref(key, 'get_int')
def getPlayerBool(key): return _getPref(key, 'get_bool')

def setInt(key, value): return _setPref('window/' + key, 'set_int', value)
def setBool(key, value): return _setPref('window/' + key, 'set_bool', value)
def setPlayerInt(key, value): return _setPref(key, 'set_int', value)
def setPlayerBool(key, value): return _setPref(key, 'set_bool', value)

class WidgetTree(gtk.glade.XML):
    """Small helper class.  It's exactly like the gtk.glade.XML interface,
    except that it supports a mapping interface to get widgets.  If wt is a
    WidgetTree object, wt[name] is equivelent to wt.get_widget(name), but
    without all the typing.
    """

    def __getitem__(self, key):
        rv = self.get_widget(key)
        if rv is None:
            raise KeyError("No widget named %s" % key)
        else:
            return rv

###############################################################################
#### Initialization code: window classes, invisible toplevel parent        ####
###############################################################################


###############################################################################
#### Main window                                                           ####
###############################################################################

# Strategy: We create an EventBox for each display change the children on
# selectDisplay().  Each Display class has a getWidget() call that returns a
# widget to place inside the EventBoxes.  The choice of EventBox as the widget
# is pretty much arbitrary -- any container would do.  
#
class MainFrame:
    def __init__(self, appl):
        # Symbols by other parts of the program as as arguments
        # to selectDisplay
        self.mainDisplay = "mainDisplay"
        self.channelsDisplay = "channelsDisplay"
        self.collectionDisplay = "collectionDisplay"
        self.videoInfoDisplay = "videoInfoDisplay"
        self.selectedDisplays = {}
        self.videoLength = None
        self.callbackHandler = CallbackHandler(self)
        self.isFullscreen = False
        self.aboutWidget = None
        self.currentVideoFilename = None
        self.playable = False
        self.videoLoaded = False

        from miro import views
        from miro import util
        from miro import indexes
        engines = []
        for engine in views.searchEngines:
            engines.append((engine.name, engine.title))
        searchFeed = util.getSingletonDDBObject (views.feeds.filterWithIndex(indexes.feedsByURL, 'dtv:search'))
        default_engine = searchFeed.lastEngine

        self._gtkInit(engines, default_engine)

    @gtkAsyncMethod
    def _gtkInit(self, engines, default_engine):
        # Create the widget tree, and remember important widgets
        confirmMainThread()
        self.widgetTree = WidgetTree(resources.path('miro.glade'), 'main-window', 'miro')
        self.displayBoxes = {
            self.mainDisplay : self.widgetTree['main-box'],
            self.channelsDisplay : self.widgetTree['channels-box'],
            self.videoInfoDisplay : self.widgetTree['video-info-box'],
        }

        UIBackendDelegate.dialogParent = self.widgetTree['main-window']

        self.widgetTree['main-window'].set_icon_from_file (resources.sharePath('pixmaps/miro-128x128.png'))
        self.widgetTree['main-window'].set_title(config.get(prefs.LONG_APP_NAME))

        # create the buttonsDown attribute to the video time scale.  It will
        # track which mouse buttons are currently pressed.  This is usefull
        # because we don't want to update widget when the user is in the
        # middle of draging it.
        self.widgetTree['video-time-scale'].buttonsDown = sets.Set()
        # connect all signals
        self.widgetTree.signal_autoconnect(self.callbackHandler)
        # disable menu item's that aren't implemented yet
#        self.widgetTree.get_widget('update-channel').set_sensitive(False)
#        self.widgetTree.get_widget('update-all-channels').set_sensitive(False)
#        self.widgetTree.get_widget('tell-a-friend').set_sensitive(False)
#        self.widgetTree.get_widget('channel-rename').set_sensitive(False)
#        self.widgetTree.get_widget('channel-copy-url').set_sensitive(False)
#        self.widgetTree.get_widget('channel-add').set_sensitive(False)
#        self.widgetTree.get_widget('channel-remove').set_sensitive(False)
#        self.widgetTree.get_widget('delete-video').set_sensitive(False)

        self.uiManager = gtk.UIManager()

        self.actionGroups = self.callbackHandler.actionGroups ()
        actions = {} # Names of actions handled by the GTK UI
        i = 0

        for actionGroup in self.actionGroups.values():
            actionlist = actionGroup.list_actions()
            for action in actionlist:
                actions[action.get_name()] = True
            self.uiManager.insert_action_group (actionGroup, i)
            i = i + 1

        # Generate menus
        ui_string = "<ui>\n"
        ui_string += "  <menubar>\n"
        for menu in menubar.menubar:
            if actions.has_key('toplevel-%s' % menu.action):
                ui_string += '  <menu action="toplevel-%s">\n' % menu.action
                for menuitem in menu.menuitems:
                    if isinstance(menuitem, menubar.Separator):
                        ui_string += '      <separator/>\n'
                    elif actions.has_key(menuitem.action):
                        ui_string += '      <menuitem action="%s"/>\n' %(
                            menuitem.action)
                    else:
                        logging.warn('Menu item action "%s" not implemented' % menuitem.action)
                ui_string += '  </menu>\n'
            else:
                logging.warn('Menu action "%s" not implemented' % menu.action)
        ui_string += "</menubar>\n"
        ui_string += "</ui>\n"

        self.uiManager.add_ui_from_string(ui_string)
        
        self.widgetTree['menubar-box'].add (self.uiManager.get_widget('/menubar'))
        self.widgetTree['main-window'].add_accel_group(self.uiManager.get_accel_group())

        self.widgetTree['volume-scale'].set_value (config.get(prefs.VOLUME_LEVEL))

        store = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
        select_iter = None
        for name, title in engines:
            iter = store.append((name, title))
            if select_iter is None or default_engine == name:
                select_iter = iter
        cell = gtk.CellRendererText()
        combo = self.widgetTree["combobox-chrome-search-engine"]
        combo.pack_start(cell, True)
        combo.add_attribute(cell, 'text', 1)
        combo.set_model (store)
        combo.set_active_iter(select_iter)

        self.windowChanger = MainWindowChanger(self.widgetTree, self,
                MainWindowChanger.BROWSING)

        width = getInt ("width")
        height = getInt ("height")
        x = getInt ("x")
        y = getInt ("y")
        if (x != None and y != None):
            self.widgetTree['main-window'].move (x, y);
        if (width != None and height != None):
            self.widgetTree['main-window'].resize (width, height);

        maximized = getBool ("maximized")
        if maximized != None:
            if maximized:
                self.widgetTree['main-window'].maximize()
            else:
                self.widgetTree['main-window'].unmaximize()

        if getPlayerBool("showTrayicon") and trayicon.trayicon_is_supported:
            self.trayicon = trayicon.Trayicon(resources.sharePath("pixmaps/miro-24x24.png"), self)
            self.trayicon.set_visible(True)

        self.widgetTree['main-window'].connect ("configure-event", self.configureEvent)
        self.widgetTree['main-window'].connect ("window-state-event", self.stateEvent)

        self.widgetTree['main-window'].show_all()

    def configureEvent(self, widget, event):
        confirmMainThread()
        (x, y) = self.widgetTree['main-window'].get_position ()
        (width, height) = self.widgetTree['main-window'].get_size()
        setInt ("width", width)
        setInt ("height", height)
        setInt ("x", x)
        setInt ("y", y)
        return False

    def stateEvent (self, widget, event):
        confirmMainThread()
        maximized = (event.new_window_state & gtk.gdk.WINDOW_STATE_MAXIMIZED) != 0
        setBool ("maximized", maximized)

    def onVideoLoadedChange (self, videoLoaded):
        self.videoLoaded = videoLoaded
        self.actionGroups['VideoPlayable'].set_sensitive(self.playable or self.videoLoaded)
        
    @gtkAsyncMethod
    def onSelectedTabChange(self, states, actionGroups, guideURL,
            videoFilename):
        app.controller.setGuideURL(guideURL)
        self.currentVideoFilename = videoFilename

        for actionGroup, setting in actionGroups.iteritems():
            self.actionGroups[actionGroup].set_sensitive(setting)

        self.playable = actionGroups['VideoPlayable']
        self.actionGroups['VideoPlayable'].set_sensitive(self.playable or self.videoLoaded)


        removeChannels = menubar.menubar.getLabel("RemoveChannels")
        updateChannels = menubar.menubar.getLabel("UpdateChannels")
        removePlaylists = menubar.menubar.getLabel("RemovePlaylists")
        removeVideos = menubar.menubar.getLabel("RemoveVideos")

        for state, actions in states.items():
            if "RemoveChannels" in actions:
                removeChannels = menubar.menubar.getLabel("RemoveChannels",state)
            if "UpdateChannels" in actions:
                updateChannels = menubar.menubar.getLabel("UpdateChannels",state)
            if "RemovePlaylists" in actions:
                removePlaylists = menubar.menubar.getLabel("RemovePlaylists",state)
            if "RemoveVideos" in actions:
                removeVideos = menubar.menubar.getLabel("RemoveVideos",state)

        self.actionGroups["ChannelLikesSelected"].get_action("RemoveChannels").set_property("label", removeChannels)

        self.actionGroups["ChannelsSelected"].get_action("UpdateChannels").set_property("label", updateChannels)

        self.actionGroups["PlaylistLikesSelected"].get_action("RemovePlaylists").set_property("label", removePlaylists)

        self.actionGroups["VideosSelected"].get_action("RemoveVideos").set_property("label", removeVideos)

    @gtkAsyncMethod
    def selectDisplay(self, newDisplay, area):
        """Install the provided 'newDisplay' in the requested area"""

        confirmMainThread()
        if area == self.collectionDisplay:
            print "TODO: Collection Display not implemented on gtk/x11"
            return

        displayBox = self.displayBoxes[area]
        oldDisplay = self.selectedDisplays.get(area)
        if oldDisplay:
            oldDisplay.onDeselected(self)
            if oldDisplay.getWidget(area) != newDisplay.getWidget(area):
                displayBox.remove(oldDisplay.getWidget(area))
                displayBox.add(newDisplay.getWidget(area))
            newDisplay.onSelected(self)
        else:
            displayBox.add(newDisplay.getWidget(area))
            newDisplay.onSelected(self)

        self.selectedDisplays[area] = newDisplay
        # show the video info display when we are showing a movie.
        if area == self.mainDisplay:
            try:
                if isinstance(newDisplay, VideoDisplay):
                    self.windowChanger.changeState(self.windowChanger.VIDEO)
                else:
                    self.windowChanger.changeState(self.windowChanger.BROWSING)
            except AttributeError:
                logging.warn("Display selected before window changer created")
            if isinstance(newDisplay, HTMLDisplay):
                newDisplay.getWidget(area).child.grab_focus()

    @gtkSyncMethod
    def getDisplay(self, area):
        confirmMainThread()
        return self.selectedDisplays.get(area)

    @gtkAsyncMethod
    def about(self):
        confirmMainThread()
        if (self.aboutWidget is None):
            self.aboutWidget = gtk.AboutDialog()
            self.aboutWidget.set_name(config.get(prefs.SHORT_APP_NAME))
            self.aboutWidget.set_version( "%s (r%s)" % \
                                          (config.get(prefs.APP_VERSION), 
                                           config.get(prefs.APP_REVISION_NUM)))
            self.aboutWidget.set_website(WEBSITE)
            self.aboutWidget.set_copyright(COPYRIGHT)
            def delete_event_cb(widget, event):
                widget.hide()
                return True
            def response_cb(widget, id):
                widget.hide()
                return True
            self.aboutWidget.connect ("delete_event", delete_event_cb)
            self.aboutWidget.connect ("response", response_cb)
            self.aboutWidget.set_transient_for (self.widgetTree['main-window'])
        self.aboutWidget.present()

    @gtkSyncMethod
    def updateVideoTime(self):
        def CTCallback(videoTimeScale, videoLength, currentTime):
            # None is less than both 0 and 1, so these will handle None.
            if videoLength < 1:
                videoLength = 1
            if currentTime < 0:
                currentTime = 0
            if currentTime > videoLength:
                currentTime = videoLength
            videoTimeScale.set_range(0, videoLength)
            videoTimeScale.set_value(currentTime)

        renderer = app.htmlapp.videoDisplay.activeRenderer
        videoTimeScale = self.widgetTree['video-time-scale']
        if renderer and not videoTimeScale.buttonsDown:
            try:
                self.videoLength = renderer.getDuration()
            except:
                self.videoLength = 0
            videoLength = self.videoLength
            renderer.getCurrentTime(lambda x :CTCallback(videoTimeScale, videoLength, x))
        return True

    @gtkAsyncMethod
    def setFullscreen(self, fullscreen):
        self.windowChanger.changeFullScreen (fullscreen)
        self.isFullscreen = fullscreen

    # Internal use: return an estimate of the size of a given display area
    # as a (width, height) pair, or None if no information's available.
    @gtkSyncMethod
    def getDisplaySizeHint(self, area):
        display = self.selectedDisplays.get(area)
        if display is None:
            return None
        allocation = display.getWidget().get_allocation()
        return allocation.width, allocation.height

    def unlink(self):
        pass
    
    def __del__(self):
        self.unlink()

###############################################################################
###############################################################################
