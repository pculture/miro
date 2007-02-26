"""Frontend callback handler.  Responsible for handling all GUI actions."""

import app
import gobject
import gtk
import gtk.gdk
import os
import shutil
import frontend
import config
import prefs
import resources
import MainFrame
import singleclick
import eventloop
import math
import dialogs
import folder
import playlist
import platformutils
import startup
import logging
from gtcache import gettext as _
 
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
        self.mainApp = app.controller

    def actionGroups (self):
        platformutils.confirmMainThread()
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
            ('SaveVideo', gtk.STOCK_SAVE, _('Save Video _As...'), '<Control>s', _('Save this video'), self.on_save_video_activate),
            ('CopyVideoURL', None, _('_Copy Video URL'), None, None, self.on_copy_video_link_activate),
            ])
        actionGroups["VideosSelected"].add_actions ([
            ('RemoveVideos', None, _('_Remove Video'), None, None, self.on_remove_video_activate),
            ])
        actionGroups["VideoPlaying"].add_actions ([
            ('Fullscreen', fullscreen, _('_Fullscreen'), '<Control>f', None, self.on_fullscreen_button_clicked),
            ('StopVideo', None, _('_Stop Video'), None, None, self.on_stop_activate),
            ('NextVideo', None, _('_Next Video'), '<Alt>Right', None, self.on_next_button_clicked),
            ('PreviousVideo', None, _('_Previous Video'), '<Alt>Left', None, self.on_previous_button_clicked),
            ])
        actionGroups["VideoPlayable"].add_actions ([
            ('PlayPauseVideo', gtk.STOCK_MEDIA_PLAY, _('_Play / Pause'), '<Control>space', None, self.on_play_pause_button_clicked),
            ])
        actionGroups["ChannelSelected"].add_actions ([
            ('CopyChannelURL', None, _("Copy Channel _Link"), None, None, self.on_copy_channel_link_activate),
            ('MailChannel', None, _("_Send this channel to a friend"), None, None, self.on_mail_channel_link_activate),
            ])
        actionGroups["ChannelsSelected"].add_actions ([
            ('UpdateChannels', None, _("_Update Channel"), None, None, self.on_update_channel_activate),
            ])
        actionGroups["ChannelLikeSelected"].add_actions ([
            ('RenameChannel', None, _("Re_name Channel"), None, None, self.on_rename_channel_activate),
            ])
        actionGroups["ChannelLikesSelected"].add_actions ([
            ('RemoveChannels', None, _("_Remove Channel"), None, None, self.on_remove_channel_activate),
            ])
        actionGroups["PlaylistLikeSelected"].add_actions ([
            ('RenamePlaylist', None, _("Re_name Playlist"), None, None, self.on_rename_playlist_activate),
            ])
        actionGroups["PlaylistLikesSelected"].add_actions ([
            ('RemovePlaylists', None, _("_Remove Playlist"), None, None, self.on_remove_playlist_activate),
            ])
        actionGroups["Ubiquitous"].add_actions ([
            ('Video', None, _('_Video')),
            ('Channels', None, _('_Channels')),
            ('Playlists', None, _('_Playlists')),
            ('Playback', None, _('P_layback')),
            ('Open', gtk.STOCK_OPEN, _('_Open...'), '<Control>o', _('Open various files'), self.on_open_video_activate),

            ('NewPlaylist', None, _('New _Playlist...'), None, _('Create new playlist'), self.on_new_playlist_activate),
            ('NewPlaylistFolder', None, _('New Playlist _Folder...'), None, _('Create new playlist folder'), self.on_new_playlist_folder_activate),
            ('NewChannelFolder', None, _('New Channel _Folder...'), None, _('Create new channel folder'), self.on_new_channel_folder_activate),
            ('NewChannel', None, _("Add _Channel..."), None, None, self.on_add_channel_button_clicked),
            ('NewSearchChannel', None, _("New Searc_h Channel..."), None, None, self.on_add_search_channel_button_clicked),
            ('NewGuide', None, _("New Channel _Guide..."), None, None, self.on_add_guide_button_clicked),

            ('EditPreferences', gtk.STOCK_PREFERENCES, _('P_references'), None, None, self.on_preference),
            ('Quit', gtk.STOCK_QUIT, _('_Quit'), '<Control>q', _('Quit the Program'), self.on_quit_activate),
            ('UpdateAllChannels', None, _("U_pdate All Channels"), None, None, self.on_update_all_channels_activate),
            ('Help', None, _('_Help')),
            ('About', gtk.STOCK_ABOUT, None, None, None, self.on_about_clicked),
            ('Donate', None, _("_Donate"), None, None, self.on_donate_clicked),

            ('Delete', None, _('Delete selection'), 'Delete', None, self.on_delete),
            ('Backspace', None, _('Delete selection'), 'BackSpace', None, self.on_delete),
            ])
        return actionGroups

    def on_main_delete(self, *args):
        platformutils.confirmMainThread()
        app.controller.quit()
        return True

    def on_play_pause_button_clicked(self, event = None):
        videoDisplay = self.mainApp.videoDisplay
        if videoDisplay.isPlaying:
            videoDisplay.pause()
        else:
            videoDisplay.play(-1)
        self.mainFrame.windowChanger.updatePlayPauseButton()

    def on_previous_button_clicked(self, event):
        eventloop.addIdle(lambda:app.controller.playbackController.skip(-1), "Skip to previous track")

    def on_next_button_clicked(self, event):
        eventloop.addIdle(lambda:app.controller.playbackController.skip(1), "Skip to next track")

    def on_video_time_scale_button_press_event(self, scale, event):
        scale.buttonsDown.add(event.button)

    def on_video_time_scale_button_release_event(self, scale, event):
        platformutils.confirmMainThread()
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
            logging.info ("saving %r to %r", videoPath, savePath)
            shutil.copyfile(videoPath, savePath)
        CallbackHandler.current_folder = chooser.get_current_folder()
        chooser.destroy()

    def on_play_activate(self, event):
        currentDisplay = self.mainApp.playbackController.currentDisplay
        if currentDisplay == self.mainApp.videoDisplay:
            self.mainApp.videoDisplay.play()
        else:
            self.mainApp.playbackController.enterPlayback()

    def on_stop_activate(self, event):
        currentDisplay = self.mainApp.playbackController.currentDisplay
        if currentDisplay == self.mainApp.videoDisplay:
            self.mainApp.videoDisplay.pause()
        else:
            pass
            # I think this will happen if we play an item externally.  Not
            # sure what to do here.

    def on_quit_activate(self, event):
        app.controller.quit()

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
        eventloop.addIdle (app.controller.copyCurrentFeedURL, "Copy feed URL")

    def on_mail_channel_link_activate(self, event = None):
        print "Mail Chanel Link unimplemented"

    def on_copy_video_link_activate(self, event = None):
        print "Copy Video Link unimplemented"

    def on_add_channel_button_clicked(self, event = None):
        eventloop.addIdle(lambda:app.controller.addAndSelectFeed(), "Add Channel")

    def on_add_search_channel_button_clicked(self, event = None):
        eventloop.addIdle(lambda:app.controller.addSearchFeed(), "Add SearchChannel")

    def on_add_guide_button_clicked(self, event = None):
        eventloop.addIdle(lambda:app.controller.addAndSelectGuide(), "Add Guide")

    def on_new_playlist_activate(self, event=None):
        playlist.createNewPlaylist()

    def on_new_playlist_folder_activate(self, event=None):
        folder.createNewPlaylistFolder()

    def on_new_channel_folder_activate(self, event=None):
        folder.createNewChannelFolder()

    def on_preference(self, event = None):
        import autodler
        # get our add channel dialog
        movie_dir = config.get(prefs.MOVIES_DIRECTORY)
        widgetTree = MainFrame.WidgetTree(resources.path('democracy.glade'), 'dialog-preferences', 'democracyplayer')
        dialog = widgetTree['dialog-preferences']
        dialog.integerWidgets = []
        dialog.floatWidgets = []
        mainWindow = self.mainFrame.widgetTree['main-window']
        dialog.set_transient_for(mainWindow)
        AttachBoolean (dialog, widgetTree['checkbutton-limit'], prefs.LIMIT_UPSTREAM, widgetTree['spinbutton-limit'])
        AttachBoolean (dialog, widgetTree['checkbutton-padding'], prefs.PRESERVE_DISK_SPACE, widgetTree['spinbutton-padding'])
        AttachBoolean (dialog, widgetTree['checkbutton-autorun'], prefs.RUN_DTV_AT_STARTUP)
        AttachInteger (dialog, widgetTree['spinbutton-limit'], prefs.UPSTREAM_LIMIT_IN_KBS)
        AttachInteger (dialog, widgetTree['spinbutton-bt-min-port'], prefs.BT_MIN_PORT)
        AttachInteger (dialog, widgetTree['spinbutton-bt-max-port'], prefs.BT_MAX_PORT)
        AttachInteger (dialog, widgetTree['spinbutton-max-manual'], prefs.MAX_MANUAL_DOWNLOADS)
        AttachFloat   (dialog, widgetTree['spinbutton-padding'], prefs.PRESERVE_X_GB_FREE)
        AttachCombo   (dialog, widgetTree['combobox-poll'], prefs.CHECK_CHANNELS_EVERY_X_MN, (30, 60, -1))
        AttachCombo   (dialog, widgetTree['combobox-expiration'], prefs.EXPIRE_AFTER_X_DAYS, (1, 3, 6, 10, 30, -1))
        AttachBooleanRadio (dialog, widgetTree['radiobutton-playback-one'], widgetTree['radiobutton-playback-all'], prefs.SINGLE_VIDEO_PLAYBACK_MODE)

        try:
            os.makedirs (movie_dir)
        except:
            pass
        chooser = widgetTree['filechooserbutton-movies-directory']
        chooser.set_filename (movie_dir + "/")
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
            migrate_widgetTree = MainFrame.WidgetTree(resources.path('democracy.glade'), 'dialog-migrate', 'democracyplater')
            migrate_dialog = migrate_widgetTree['dialog-migrate']
            response = migrate_dialog.run()
            app.changeMoviesDirectory(new_movie_dir, 
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

    def on_about_clicked(self, event = None):
        self.mainFrame.about()

    def on_donate_clicked(self, event = None):
        print "Donate unimplemented"

    def on_delete(self, event = None):
        eventloop.addUrgentCall(app.controller.removeCurrentSelection, 
                "remove current selection")

    def on_button_chrome_search_go_clicked (self, event=None):
        widgetTree = self.mainFrame.widgetTree
        term = widgetTree["entry-chrome-search-term"].get_text()
        iter = widgetTree["combobox-chrome-search-engine"].get_active_iter()
        (engine,) = widgetTree["combobox-chrome-search-engine"].get_model().get(iter, 0)
        eventloop.addIdle (lambda:app.controller.performSearch (engine, term), "Search for %s on %s" % (term, engine))
