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

"""Frontend callback handler.  Responsible for handling all GUI actions."""

from miro import app
import gobject
import gtk
import gtk.gdk
import gtk.keysyms
import os
import shutil
from miro import config
from miro import prefs
from miro.platform import resources
import MainFrame
from miro import singleclick
from miro import eventloop
import math
from miro import folder
from miro import playlist
from miro.platform.utils import confirmMainThread, makeURLSafe, filenameToUnicode
from miro.platform.frontends.html import startup
import logging
from miro import feed
from miro import views
from miro import database
from miro.menubar import menubar
from miro.frontends.html import keyboard

from gtk_queue import gtkAsyncMethod
from miro.gtcache import gettext as _
 
def AttachBoolean (dialog, widget, descriptor, sensitive_widget = None):
    def BoolChanged (widget):
         config.set (descriptor, widget.get_active())
         if (sensitive_widget != None):
             sensitive_widget.set_sensitive (widget.get_active())

    widget.set_active (config.get(descriptor))
    if (sensitive_widget != None):
        sensitive_widget.set_sensitive (widget.get_active())
    widget.connect ('toggled', BoolChanged)
 
def AttachBooleanRadio (dialog, widget_true, widget_false, descriptor, sensitive_widget = None):
    def BoolChanged (widget):
         config.set (descriptor, widget.get_active())
         if (sensitive_widget != None):
             sensitive_widget.set_sensitive (widget.get_active())

    if config.get(descriptor):
        widget_true.set_active (True)
    else:
        widget_false.set_active (True)
    if (sensitive_widget != None):
        sensitive_widget.set_sensitive (widget_true.get_active())
    widget_true.connect ('toggled', BoolChanged)

def AttachInteger (dialog, widget, descriptor):
    def IntegerChanged (widget):
        try:
            config.set (descriptor, widget.get_value_as_int())
        except:
            pass

    dialog.integerWidgets.append ((descriptor, widget))
    widget.set_value (config.get(descriptor))
    widget.connect ('value_changed', IntegerChanged)

def AttachFloat (dialog, widget, descriptor):
    def FloatChanged (widget):
        try:
            config.set (descriptor, widget.get_value())
        except:
            pass

    dialog.floatWidgets.append ((descriptor, widget))
    widget.set_value (config.get(descriptor))
    widget.connect ('value_changed', FloatChanged)

def AttachCombo (dialog, widget, descriptor, values):
    def ComboChanged (widget):
        config.set (descriptor, values[widget.get_active()])
    value = config.get (descriptor)
    widget.set_active (-1)
    for i in xrange (len (values)):
        if values[i] == value:
            widget.set_active (i)
            break
    widget.connect ('changed', ComboChanged)

def SetupDirList (widgetTree, toggleRenderer):
    def SelectionChanged (selection):
        if selection.count_selected_rows() > 0:
            widgetTree["button-collection-dirs-remove"].set_sensitive (True)
        else:
            widgetTree["button-collection-dirs-remove"].set_sensitive (False)

    @eventloop.asIdle
    def removeFeeds (ids):
        feeds = []
        for id in ids:
            try:
                feeds.append(database.defaultDatabase.getObjectByID (id))
            except:
                pass
        app.controller.removeFeeds (feeds)

    @eventloop.asIdle
    def addFeed (filename):
        feed.Feed (u"dtv:directoryfeed:%s" % (makeURLSafe(filename),))

    @eventloop.asIdle
    def toggleFeed (id):
        try:
            feed = database.defaultDatabase.getObjectByID (id)
            feed.setVisible (not feed.visible)
        except:
            pass
        
    def RemoveClicked (widget):
        model, rows = selection.get_selected_rows()
        ids = [model.get_value(model.get_iter(row), 0) for row in rows]
        removeFeeds (ids)

    def AddClicked (widget):
        dialog = gtk.FileChooserDialog("View this folder in the Library",
                                       widgetTree["dialog-preferences"],
                                       gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
                                       (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, 
                                        gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
        response = dialog.run()
        if response == gtk.RESPONSE_ACCEPT:
            filename = dialog.get_filename()
            if filename:
                addFeed (filename)
        dialog.destroy()

    def toggled (renderer, path):
        model = widgetTree["treeview-collection-dirs"].get_model()
        iter = model.get_iter (path)
        if iter:
            id = model.get_value (iter, 0)
            toggleFeed(id)
        

    selection = widgetTree["treeview-collection-dirs"].get_selection()
    selection.connect ("changed", SelectionChanged)
    selection.set_mode (gtk.SELECTION_MULTIPLE)
    SelectionChanged(selection)

    button = widgetTree["button-collection-dirs-remove"]
    button.connect ("clicked", RemoveClicked)

    button = widgetTree["button-collection-dirs-add"]
    button.connect ("clicked", AddClicked)

    model = widgetTree["treeview-collection-dirs"].get_model()
    mediator = Mediator(model)
    toggleRenderer.connect("toggled", toggled)

class Mediator:

    def __init__(self, model):
        self.model = model
        self.fillIn()

    @eventloop.asIdle
    def unlink (self):
        views.feeds.removeChangeCallback(self.changeCallback)
        views.feeds.removeAddCallback(self.changeCallback)
        views.feeds.removeRemoveCallback(self.removeCallback)

    @gtkAsyncMethod
    def changeDirectory (self, id, dir, visible):
        iter = self.model.get_iter_first()
        while (iter):
            val = self.model.get_value (iter, 0)
            if val == id:
                break
            iter = self.model.iter_next (iter)
        if iter is None:
            iter = self.model.append(None)
        self.model.set (iter, 0, id, 1, filenameToUnicode (dir), 2, visible)

    @gtkAsyncMethod
    def removeDirectory (self, id):
        iter = self.model.get_iter_first()
        while (iter):
            val = self.model.get_value (iter, 0)
            if val == id:
                break
            iter = self.model.iter_next (iter)
        if iter is not None:
            self.model.remove (iter)

    @eventloop.asIdle
    def fillIn (self):
        for f in views.feeds:
            print f, f.actualFeed
            if isinstance (f.actualFeed, feed.DirectoryWatchFeedImpl):
                self.changeDirectory (f.getID(), f.dir, f.visible)
        views.feeds.addChangeCallback(self.changeCallback)
        views.feeds.addAddCallback(self.changeCallback)
        views.feeds.addRemoveCallback(self.removeCallback)

    def changeCallback(self, mapped, id):
        if isinstance (mapped.actualFeed, feed.DirectoryWatchFeedImpl):
            self.changeDirectory (id, mapped.dir, mapped.visible)

    def removeCallback(self, mapped, id):
        print mapped, mapped.actualFeed, id
        if isinstance (mapped.actualFeed, feed.DirectoryWatchFeedImpl):
            self.removeDirectory (id)

def _buildAction(action):
    impl = menubar.getImpl(action)
    if impl:
        return (action, None, menubar.getLabel(action), menubar.getShortcut(action).GTKString(), None, lambda event: eventloop.addIdle(impl, action))
    else:
        return (action, None, menubar.getLabel(action), menubar.getShortcut(action).GTKString(), None, None)
        
    

class CallbackHandler(object):
    """Class to handle menu item activation, button presses, etc.  The method
    names for this class correspond to the event handler that they implement.
    The event handler name's are chosen in glade.  CallbackHandler uses the
    underscored_method_name convention for its methods, because that's the
    default for glade.
    """

    current_folder = None

    def __init__(self, mainFrame):
        self.mainFrame = mainFrame
        self.mainApp = app.htmlapp

    def actionGroups (self):
        confirmMainThread()
        actionGroups = {}
        actionGroups["VideoSelected"] = gtk.ActionGroup("VideoSelected")
        actionGroups["VideosSelected"] = gtk.ActionGroup("VideosSelected")
        actionGroups["VideoPlaying"] = gtk.ActionGroup("VideoPlaying")
        actionGroups["VideoPlayable"] = gtk.ActionGroup("VideoPlayable")
        actionGroups["ChannelSelected"] = gtk.ActionGroup("ChannelSelected")
        actionGroups["ChannelsSelected"] = gtk.ActionGroup("ChannelsSelected")
        actionGroups["ChannelFolderSelected"] = gtk.ActionGroup("ChannelFolderSelected")
        actionGroups["ChannelLikeSelected"] = gtk.ActionGroup("ChannelLikeSelected")
        actionGroups["ChannelLikesSelected"] = gtk.ActionGroup("ChannelLikesSelected")
        actionGroups["PlaylistLikeSelected"] = gtk.ActionGroup("PlaylistLikeSelected")
        actionGroups["PlaylistLikesSelected"] = gtk.ActionGroup("PlaylistLikesSelected")
        actionGroups["Ubiquitous"] = gtk.ActionGroup("Ubiquitous")

        try:
            fullscreen = gtk.STOCK_FULLSCREEN
        except:
            fullscreen = None

        actionGroups["VideoSelected"].add_actions ([
            ('SaveVideo', gtk.STOCK_SAVE, menubar.getLabel('SaveVideo'), menubar.getShortcut('SaveVideo').GTKString(), None, self.on_save_video_activate),
            ('CopyVideoURL', None, menubar.getLabel('CopyVideoURL'), menubar.getShortcut('CopyVideoURL').GTKString(), None, self.on_copy_video_link_activate),
            ])
        actionGroups["VideosSelected"].add_actions ([
            ('RemoveVideos', None, menubar.getLabel('RemoveVideos'), menubar.getShortcut('RemoveVideos').GTKString(), None, self.on_remove_video_activate),
            ])
        actionGroups["VideoPlaying"].add_actions ([
            ('Fullscreen', fullscreen, menubar.getLabel('Fullscreen'), menubar.getShortcut('Fullscreen').GTKString(), None, self.on_fullscreen_button_clicked),
            ('StopVideo', None, menubar.getLabel('StopVideo'), menubar.getShortcut('StopVideo').GTKString(), None, self.on_stop_activate),
            ('NextVideo', None, menubar.getLabel('NextVideo'), menubar.getShortcut('NextVideo').GTKString(), None, self.on_next_button_clicked),
            ('PreviousVideo', None, menubar.getLabel('PreviousVideo'), menubar.getShortcut('PreviousVideo').GTKString(), None, self.on_previous_button_clicked),
            ])
        actionGroups["VideoPlayable"].add_actions ([
            ('PlayPauseVideo', gtk.STOCK_MEDIA_PLAY, menubar.getLabel('PlayPauseVideo'),menubar.getShortcut('PlayPauseVideo').GTKString(), None, self.on_play_pause_button_clicked),
            ])
        actionGroups["ChannelSelected"].add_actions ([
            ('CopyChannelURL', None, menubar.getLabel('CopyChannelURL'), menubar.getShortcut('CopyChannelURL').GTKString(), None, self.on_copy_channel_link_activate),
            ('MailChannel', None, menubar.getLabel('MailChannel'), menubar.getShortcut('MailChannel').GTKString(), None, self.on_mail_channel_link_activate),
            ])
        actionGroups["ChannelsSelected"].add_actions ([
            ('UpdateChannels', None, menubar.getLabel('UpdateChannels'), menubar.getShortcut('UpdateChannels').GTKString(), None, self.on_update_channel_activate),
            ])
        actionGroups["ChannelLikeSelected"].add_actions ([
            ('RenameChannel', None, menubar.getLabel('RenameChannel'), menubar.getShortcut('RenameChannel').GTKString(), None, self.on_rename_channel_activate),
            ])
        actionGroups["ChannelLikesSelected"].add_actions ([
            ('RemoveChannels', None, menubar.getLabel('RemoveChannels'), menubar.getShortcut('RemoveChannels').GTKString(), None, self.on_remove_channel_activate),
            ])
        actionGroups["PlaylistLikeSelected"].add_actions ([
            ('RenamePlaylist', None, menubar.getLabel('RenamePlaylist'), menubar.getShortcut('RenamePlaylist').GTKString(), None, self.on_rename_playlist_activate),
            ])
        actionGroups["PlaylistLikesSelected"].add_actions ([
            ('RemovePlaylists', None, menubar.getLabel('RemovePlaylists'), menubar.getShortcut('RemovePlaylists').GTKString(), None, self.on_remove_playlist_activate),
            ])
        actionGroups["Ubiquitous"].add_actions ([
            ('toplevel-Video', None, menubar.getLabel('Video')),
            ('toplevel-Channels', None, menubar.getLabel('Channels')),
            ('toplevel-Playlists', None, menubar.getLabel('Playlists')),
            ('toplevel-Playback', None, menubar.getLabel('Playback')),
            ('toplevel-Help', None, menubar.getLabel('Help')),

            ('Open', gtk.STOCK_OPEN, menubar.getLabel('Open'), menubar.getShortcut('Open').GTKString(), None, self.on_open_video_activate),
            ('NewPlaylist', None, menubar.getLabel('NewPlaylist'), menubar.getShortcut('NewPlaylist').GTKString(), None, self.on_new_playlist_activate),
            ('NewPlaylistFolder', None, menubar.getLabel('NewPlaylistFolder'), menubar.getShortcut('NewPlaylistFolder').GTKString(), None, self.on_new_playlist_folder_activate),
            ('NewChannelFolder', None, menubar.getLabel('NewChannelFolder'), menubar.getShortcut('NewChannelFolder').GTKString(), None, self.on_new_channel_folder_activate),
            ('NewChannel', None, menubar.getLabel('NewChannel'), menubar.getShortcut('NewChannel').GTKString(), None, self.on_add_channel_button_clicked),
            ('NewSearchChannel', None, menubar.getLabel('NewSearchChannel'), menubar.getShortcut('NewSearchChannel').GTKString(), None, self.on_add_search_channel_button_clicked),
            ('NewGuide', None, _("New Channel _Guide..."), None, None, self.on_add_guide_button_clicked),
            _buildAction('NewDownload'),
            _buildAction('ImportChannels'),
            _buildAction('ExportChannels'),

            ('EditPreferences', gtk.STOCK_PREFERENCES, menubar.getLabel('EditPreferences'), menubar.getShortcut('EditPreferences').GTKString(), None, self.on_preference),
            ('Quit', gtk.STOCK_QUIT, menubar.getLabel('Quit'), menubar.getShortcut('Quit').GTKString(), None, self.on_quit_activate),
            ('UpdateAllChannels', None, menubar.getLabel('UpdateAllChannels'), menubar.getShortcut('UpdateAllChannels').GTKString(), None, self.on_update_all_channels_activate),
            ('Help', None, menubar.getLabel('Help'), menubar.getShortcut('Help').GTKString(), None, self.on_help_clicked),
            ('ReportBug', None, menubar.getLabel('ReportBug'), menubar.getShortcut('ReportBug').GTKString(), None, self.on_report_bug_clicked),
            ('About', gtk.STOCK_ABOUT, menubar.getLabel('About'), menubar.getShortcut('About').GTKString(), None, self.on_about_clicked),
            ('Donate', None, menubar.getLabel('Donate'), menubar.getShortcut('Donate').GTKString(), None, self.on_donate_clicked),

            ('Delete', None, menubar.getLabel('Delete'), menubar.getShortcut('Delete').GTKString(), None, self.on_delete),
            ('Backspace', None, menubar.getLabel('Backspace'), menubar.getShortcut('Backspace').GTKString(), None, self.on_delete),
            ])
        return actionGroups

    def on_main_delete(self, *args):
        confirmMainThread()
        app.htmlapp.quit()
        return True

    def on_main_window_key_press_event(self, widget, event):
        portable_keys_mapping = {
            gtk.keysyms.Down: keyboard.DOWN,
            gtk.keysyms.Up: keyboard.UP,
            gtk.keysyms.Right: keyboard.RIGHT,
            gtk.keysyms.Left: keyboard.LEFT,
        }
        if event.keyval in portable_keys_mapping:
            control = shift = False
            if event.state & gtk.gdk.SHIFT_MASK:
                shift = True
            if event.state & gtk.gdk.CONTROL_MASK:
                control = True
            key = portable_keys_mapping[event.keyval]
            searchBox = self.mainFrame.widgetTree['entry-chrome-search-term']
            if (key in (keyboard.RIGHT, keyboard.LEFT) and 
                    (self.mainApp.videoDisplay.currentFrame is None or
                    searchBox.is_focus())):
                # hack to make sure the search box gets RIGHT/LEFT key events.
                return False
            keyboard.handleKey(key, shift, control)
            return True
        else:
            return False

    def on_play_pause_button_clicked(self, event = None):
        eventloop.addUrgentCall(app.htmlapp.playbackController.playPause,
                'play/pause video')

    def on_previous_button_clicked(self, event):
        eventloop.addIdle(lambda:app.htmlapp.playbackController.skip(-1), "Skip to previous track")

    def on_next_button_clicked(self, event):
        eventloop.addIdle(lambda:app.htmlapp.playbackController.skip(1), "Skip to next track")

    def on_video_time_scale_button_press_event(self, scale, event):
        scale.buttonsDown.add(event.button)

    def on_video_time_scale_button_release_event(self, scale, event):
        confirmMainThread()
        # we want to remove the button from the buttonsDown set, but we can't
        # yet, because we haven't run the default signal handler yet, which
        # will emit the value-changed signal.  So we use use idle_add, to
        # remove the buttons once we're done with signal processing.
        button = event.button
        def remove():
            try:
                scale.buttonsDown.remove(button)
            except KeyError:
                pass
        gobject.idle_add(remove)

    def on_video_time_scale_value_changed(self, videoTimeScale):
        videoDisplay = self.mainApp.videoDisplay
        renderer = videoDisplay.activeRenderer
        if videoDisplay.isPlaying and renderer and videoTimeScale.buttonsDown:
            renderer.seek(videoTimeScale.get_value())
        return True

    def on_video_time_scale_format_value(self, scale, seconds):
        videoLength = self.mainFrame.videoLength
        if videoLength is None or videoLength <= 0:
            return ""
        def formatTime(seconds):
            mins, secs = divmod(seconds, 60)
            hours, mins = divmod(mins, 60)
            if hours > 0:
                return "%02d:%02d:%02d" % (hours, mins, secs)
            else:
                return "%02d:%02d" % (mins, secs)
        return "%s / %s" % (formatTime(seconds), formatTime(videoLength))

    def on_volume_scale_value_changed(self, scale):
        try:
            self.mainApp.videoDisplay.setVolume(scale.get_value())
        except AttributeError:
            logging.warn("Volume changed before videoDisplay created")

    def on_open_video_activate(self, event = None):
        chooser = gtk.FileChooserDialog("Open Files...",
                self.mainFrame.widgetTree['main-window'],
                gtk.FILE_CHOOSER_ACTION_OPEN,
                (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, 
                    gtk.STOCK_OPEN, gtk.RESPONSE_ACCEPT))
        chooser.set_select_multiple(True)
        if (CallbackHandler.current_folder):
            chooser.set_current_folder(CallbackHandler.current_folder)
        if chooser.run() == gtk.RESPONSE_ACCEPT:
            files = chooser.get_filenames()
            eventloop.addIdle(lambda:singleclick.parseCommandLineArgs (files), "Open Files")
        CallbackHandler.current_folder = chooser.get_current_folder()
        chooser.destroy()
            

    def on_save_video_activate(self, event = None):
        videoPath = self.mainFrame.currentVideoFilename
        if videoPath is None:
            return
        self.mainApp.videoDisplay.pause()
        chooser = gtk.FileChooserDialog("Save Video As...",
                self.mainFrame.widgetTree['main-window'],
                gtk.FILE_CHOOSER_ACTION_SAVE,
                (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, 
                    gtk.STOCK_SAVE, gtk.RESPONSE_ACCEPT))
        chooser.set_current_name(os.path.basename(videoPath))
        if (CallbackHandler.current_folder):
            chooser.set_current_folder(CallbackHandler.current_folder)
        if chooser.run() == gtk.RESPONSE_ACCEPT:
            savePath = chooser.get_filename()
            def getExt(path):
                return os.path.splitext(path)[1]
            if getExt(savePath) == '':
                savePath += getExt(videoPath)
            app.controller.saveVideo(videoPath, savePath)
        CallbackHandler.current_folder = chooser.get_current_folder()
        chooser.destroy()

    def on_stop_activate(self, event):
        eventloop.addUrgentCall(app.htmlapp.playbackController.stop,
                "stop playback")

    def on_quit_activate(self, event):
        app.htmlapp.quit()

    def on_fullscreen_activate(self, event):
        self.mainFrame.setFullscreen(True)

    def on_leave_fullscreen_activate(self, event):
        self.mainFrame.setFullscreen(False)

    def on_fullscreen_button_clicked(self, event = None):
        if self.mainFrame.isFullscreen:
            self.mainFrame.setFullscreen(False)
        else:
            self.mainFrame.setFullscreen(True)

    def on_remove_channel_activate(self, event = None):
        eventloop.addIdle (app.controller.removeCurrentFeed, "Remove Channel")

    def on_rename_channel_activate(self, event = None):
        eventloop.addIdle (app.controller.renameCurrentTab, "Rename Tab")

    def on_remove_playlist_activate(self, event = None):
        eventloop.addIdle (app.controller.removeCurrentPlaylist, "Remove Playlist")

    def on_remove_video_activate(self, event = None):
        eventloop.addIdle (app.controller.removeCurrentItems, "Remove Videos")

    def on_rename_playlist_activate(self, event = None):
        eventloop.addIdle (app.controller.renameCurrentTab, "Rename Tab")

    def on_update_channel_activate(self, event = None):
        eventloop.addIdle (app.controller.updateCurrentFeed, "Update Channel")

    def on_update_all_channels_activate(self, event = None):
        eventloop.addIdle (app.controller.updateAllFeeds, "Update All Channels")

    def on_copy_channel_link_activate(self, event = None):
        eventloop.addIdle (app.htmlapp.copyCurrentFeedURL, "Copy feed URL")

    def on_mail_channel_link_activate(self, event = None):
        eventloop.addIdle (app.htmlapp.recommendCurrentFeed, "Copy feed URL")

    def on_copy_video_link_activate(self, event = None):
        eventloop.addIdle(lambda:app.htmlapp.copyCurrentItemURL, "Copy Item URL")

    def on_add_channel_button_clicked(self, event = None):
        eventloop.addIdle(lambda:app.htmlapp.addAndSelectFeed(), "Add Channel")

    def on_add_search_channel_button_clicked(self, event = None):
        eventloop.addIdle(lambda:app.htmlapp.addSearchFeed(), "Add SearchChannel")

    def on_add_guide_button_clicked(self, event = None):
        eventloop.addIdle(lambda:app.htmlapp.addAndSelectGuide(), "Add Guide")

    def on_new_playlist_activate(self, event=None):
        playlist.createNewPlaylist()

    def on_new_playlist_folder_activate(self, event=None):
        folder.createNewPlaylistFolder()

    def on_new_channel_folder_activate(self, event=None):
        folder.createNewChannelFolder()

    def on_preference(self, event = None):
        from miro import autodler
        # get our add channel dialog
        movie_dir = config.get(prefs.MOVIES_DIRECTORY)
        widgetTree = MainFrame.WidgetTree(resources.path('miro.glade'), 'dialog-preferences', 'miro')
        dialog = widgetTree['dialog-preferences']
        widgetTree['prefs-notebook'].set_property("homogeneous", True)
        dialog.integerWidgets = []
        dialog.floatWidgets = []
        mainWindow = self.mainFrame.widgetTree['main-window']
        dialog.set_transient_for(mainWindow)
        AttachBoolean (dialog, widgetTree['checkbutton-limit'], prefs.LIMIT_UPSTREAM, widgetTree['spinbutton-limit'])
        AttachBoolean (dialog, widgetTree['checkbutton-padding'], prefs.PRESERVE_DISK_SPACE, widgetTree['spinbutton-padding'])
        AttachBoolean (dialog, widgetTree['checkbutton-autorun'], prefs.RUN_DTV_AT_STARTUP)
        AttachInteger (dialog, widgetTree['spinbutton-limit'], prefs.UPSTREAM_LIMIT_IN_KBS)
        AttachBoolean (dialog, widgetTree['checkbutton-down-limit'], prefs.LIMIT_DOWNSTREAM_BT, widgetTree['spinbutton-down-limit'])
        AttachInteger (dialog, widgetTree['spinbutton-down-limit'], prefs.DOWNSTREAM_BT_LIMIT_IN_KBS)
        AttachInteger (dialog, widgetTree['spinbutton-bt-min-port'], prefs.BT_MIN_PORT)
        AttachInteger (dialog, widgetTree['spinbutton-bt-max-port'], prefs.BT_MAX_PORT)
        AttachInteger (dialog, widgetTree['spinbutton-max-manual'], prefs.MAX_MANUAL_DOWNLOADS)
        AttachInteger (dialog, widgetTree['spinbutton-max-auto'], prefs.DOWNLOADS_TARGET)
        AttachFloat   (dialog, widgetTree['spinbutton-padding'], prefs.PRESERVE_X_GB_FREE)
        AttachCombo   (dialog, widgetTree['combobox-poll'], prefs.CHECK_CHANNELS_EVERY_X_MN, (30, 60, -1))
        AttachCombo   (dialog, widgetTree['combobox-auto-setting'], prefs.CHANNEL_AUTO_DEFAULT, ("new", "all", "off"))
        AttachCombo   (dialog, widgetTree['combobox-expiration'], prefs.EXPIRE_AFTER_X_DAYS, (1, 3, 6, 10, 30, -1))
        AttachBooleanRadio (dialog, widgetTree['radiobutton-playback-one'], widgetTree['radiobutton-playback-all'], prefs.SINGLE_VIDEO_PLAYBACK_MODE)
        AttachBoolean (dialog, widgetTree['checkbutton-resumemode'], prefs.RESUME_VIDEOS_MODE)
        AttachBoolean (dialog, widgetTree['checkbutton-warnonquit'], prefs.WARN_IF_DOWNLOADING_ON_QUIT)
        AttachBoolean (dialog, widgetTree['checkbutton-bt-autoforward'], prefs.USE_UPNP)
        AttachBoolean (dialog, widgetTree['checkbutton-bt-enc-req'], prefs.BT_ENC_REQ)

        treeview = widgetTree['treeview-collection-dirs']
        listmodel = gtk.TreeStore(gobject.TYPE_INT, gobject.TYPE_STRING, gobject.TYPE_BOOLEAN)
        treeview.set_model(listmodel)
        
        renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn()
        column.pack_start(renderer)
        column.add_attribute (renderer, "text", 1)
        column.set_title (_("Folder Location"))
        column.set_expand (True)
        column.set_alignment(0.0)
        treeview.append_column(column)

        toggle_renderer = gtk.CellRendererToggle()
        column = gtk.TreeViewColumn()
        column.pack_start(toggle_renderer)
        column.add_attribute (toggle_renderer, "active", 2)
        column.set_title (_("Show as Channel"))
        column.set_expand (False)
        column.set_alignment(0.5)
        treeview.append_column(column)

        SetupDirList (widgetTree, toggle_renderer)

        try:
            os.makedirs (movie_dir)
        except:
            pass
        chooser = widgetTree['filechooserbutton-movies-directory']
        chooser.set_filename (movie_dir + "/")
        chooser.set_current_folder (movie_dir)
        # run the dialog
        response = dialog.run()
        for descriptor, widget in dialog.integerWidgets:
            widget.update()
            try:
                config.set (descriptor, widget.get_value_as_int())
            except:
                pass
        for descriptor, widget in dialog.floatWidgets:
            widget.update()
            try:
                config.set (descriptor, widget.get_value())
            except:
                pass

        new_movie_dir = widgetTree['filechooserbutton-movies-directory'].get_filename()
        if (movie_dir != new_movie_dir):
            print "NEW: %r" % new_movie_dir
            migrate_widgetTree = MainFrame.WidgetTree(resources.path('miro.glade'), 'dialog-migrate', 'miro')
            migrate_dialog = migrate_widgetTree['dialog-migrate']
            response = migrate_dialog.run()
            app.controller.changeMoviesDirectory(new_movie_dir, 
                    response == gtk.RESPONSE_YES)

            migrate_dialog.destroy()
        dialog.destroy()
        if config.get(prefs.BT_MAX_PORT) < config.get(prefs.BT_MIN_PORT):
            config.set(prefs.BT_MAX_PORT, config.get(prefs.BT_MIN_PORT))
        startup.updateAutostart()
        if config.get(prefs.PRESERVE_DISK_SPACE):
            new_disk = config.get(prefs.PRESERVE_X_GB_FREE)
        else:
            new_disk = 0

    def on_report_bug_clicked(self, event=None):
        app.delegate.openExternalURL(config.get(prefs.BUG_REPORT_URL))

    def on_about_clicked(self, event = None):
        self.mainFrame.about()

    def on_help_clicked(self, event=None):
        app.delegate.openExternalURL(config.get(prefs.HELP_URL))

    def on_donate_clicked(self, event = None):
        app.delegate.openExternalURL(config.get(prefs.DONATE_URL))

    def on_delete(self, event = None):
        eventloop.addUrgentCall(app.controller.removeCurrentSelection, 
                "remove current selection")

    def on_search_activate (self, event=None):
        widgetTree = self.mainFrame.widgetTree
        term = widgetTree["entry-chrome-search-term"].get_text()
        iter = widgetTree["combobox-chrome-search-engine"].get_active_iter()
        (engine,) = widgetTree["combobox-chrome-search-engine"].get_model().get(iter, 0)
        eventloop.addIdle (lambda:app.htmlapp.performSearch (engine.decode('utf-8','replace'), term.decode('utf-8','replace')), "Search for %s on %s" % (term.decode('utf-8','replace'), engine.decode('utf-8','replace')))
