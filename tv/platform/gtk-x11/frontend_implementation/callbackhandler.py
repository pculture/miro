"""Frontend callback handler.  Responsible for handling all GUI actions."""

import app
import gobject
import gtk
import os
import shutil
import frontend
import config
import resource
import MainFrame
from gettext import gettext as _
 
def AttachBoolean (widget, descriptor, sensitive_widget = None):
    def BoolChanged (widget):
         config.set (descriptor, widget.get_active())
         if (sensitive_widget != None):
             sensitive_widget.set_sensitive (widget.get_active())

    widget.set_active (config.get(descriptor))
    if (sensitive_widget != None):
        sensitive_widget.set_sensitive (widget.get_active())
    widget.connect ('toggled', BoolChanged)

def AttachInteger (widget, descriptor):
    def IntegerChanged (widget):
        try:
            config.set (descriptor, int(widget.get_text()))
        except:
            pass

    widget.set_text (str(config.get(descriptor)))
    widget.connect ('changed', IntegerChanged)

def AttachCombo (widget, descriptor, values):
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

    def __init__(self, mainFrame):
        self.mainFrame = mainFrame
        self.mainApp = app.controller

    def actionGroups (self):
        actionGroups = {}
        actionGroups["VideoPlayback"] = gtk.ActionGroup("VideoPlayback")
        actionGroups["ChannelSelected"] = gtk.ActionGroup("ChannelSelected")
        actionGroups["Ubiquitous"] = gtk.ActionGroup("Ubiquitous")

        try:
            fullscreen = gtk.STOCK_FULLSCREEN
        except:
            fullscreen = None

        actionGroups["VideoPlayback"].add_actions ([
            ('SaveVideo', gtk.STOCK_SAVE, _('_Save Video'), '<Control>s', _('Save this video'), self.on_save_video_activate),
            ('PlayPauseVideo', gtk.STOCK_MEDIA_PLAY, _('_Play / Pause'), 'p', None, self.on_play_pause_button_clicked),
            ('Fullscreen', fullscreen, _('_Fullscreen'), 'f', None, self.on_fullscreen_button_clicked)
            ])
        actionGroups["ChannelSelected"].add_actions ([
            ('RemoveChannel', None, _("_Remove Channel"), None, None, self.on_remove_channel_activate),
            ('UpdateChannel', None, _("_Update Channel"), None, None, self.on_update_channel_activate),
            ('CopyChannelURL', None, _("Copy Channel _Link"), None, None, self.on_copy_channel_link_activate)
            ])
        actionGroups["Ubiquitous"].add_actions ([
            ('Video', None, _('_Video')),
            ('EditPreferences', gtk.STOCK_PREFERENCES, _('P_references'), None, None, self.on_preference),
            ('Quit', gtk.STOCK_QUIT, _('_Quit'), '<Control>q', _('Quit the Program'), self.on_quit_activate),
            ('Channel', None, _('_Channel')),
            ('AddChannel', None, _("_Add Channel"), None, None, self.on_add_channel_button_clicked),
            ('UpdateAllChannels', None, _("U_pdate All Channels"), None, None, self.on_update_all_channels_activate),
            ('Help', None, _('_Help')),
            ('About', gtk.STOCK_ABOUT, None, None, None, self.on_about_clicked)
            ])
        return actionGroups

    def on_main_destroy(self, event):
        gtk.main_quit()

    def on_play_pause_button_clicked(self, event = None):
        videoDisplay = self.mainApp.videoDisplay
        if videoDisplay.isPlaying:
            videoDisplay.pause()
        else:
            videoTimeScale = self.mainFrame.widgetTree['video-time-scale']
            videoDisplay.play(videoTimeScale.get_value())
        self.mainFrame.windowChanger.updatePlayPauseButton()

    def on_previous_button_clicked(self, event):
        self.mainApp.playbackController.skip(-1)

    def on_next_button_clicked(self, event):
        self.mainApp.playbackController.skip(1)

    def on_video_time_scale_button_press_event(self, scale, event):
        scale.buttonsDown.add(event.button)

    def on_video_time_scale_button_release_event(self, scale, event):
        # we want to remove the button from the buttonsDown set, but we can't
        # yet, because we haven't run the default signal handler yet, which
        # will emit the value-changed signal.  So we use use idle_add, to
        # remove the buttons once we're done with signal processing.
        button = event.button 
        gobject.idle_add(lambda: scale.buttonsDown.remove(button))

    def on_video_time_scale_value_changed(self, videoTimeScale):
        videoDisplay = self.mainApp.videoDisplay
        renderer = videoDisplay.activeRenderer
        if videoDisplay.isPlaying and renderer and videoTimeScale.buttonsDown:
            renderer.playFromTime(videoTimeScale.get_value())
        return True

    def on_video_time_scale_format_value(self, scale, seconds):
        videoLength = self.mainFrame.videoLength
        if videoLength is None:
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
        self.mainApp.videoDisplay.setVolume(scale.get_value())

    def on_save_video_activate(self, event = None):
        # I think the following is the best way to get the current playlist
        # item, but I'm not sure it will work all the time so I wrapped it in
        # a try, except.  This is pretty ugly, IMHO.  Someone who knows more
        # than me about the system should fix this.
        try:
            item = self.mainApp.playbackController.currentPlaylist.cur()
            videoPath = item.getPath()
        except:
            return
        self.mainApp.videoDisplay.pause()
        chooser = gtk.FileChooserDialog("Save Video As...",
                self.mainFrame.widgetTree['main-window'],
                gtk.FILE_CHOOSER_ACTION_SAVE,
                (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, 
                    gtk.STOCK_SAVE, gtk.RESPONSE_ACCEPT))
        if chooser.run() == gtk.RESPONSE_ACCEPT:
            savePath = chooser.get_filename()
            def getExt(path):
                return os.path.splitext(path)[1]
            if getExt(savePath) == '':
                savePath += getExt(videoPath)
            print "saving %r to %r" % (videoPath, savePath)
            shutil.copyfile(videoPath, savePath)
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
        gtk.main_quit()

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
        app.ModelActionHandler(frontend.UIBackendDelegate()).removeCurrentFeed()

    def on_update_channel_activate(self, event = None):
        app.ModelActionHandler(frontend.UIBackendDelegate()).updateCurrentFeed()

    def on_update_all_channels_activate(self, event = None):
        app.ModelActionHandler(frontend.UIBackendDelegate()).updateAllFeeds()

    def on_copy_channel_link_activate(self, event = None):
        app.ModelActionHandler(frontend.UIBackendDelegate()).copyCurrentFeedURL()

    def on_add_channel_button_clicked(self, event = None):
        # get our add channel dialog
        widgetTree = MainFrame.WidgetTree(resource.path('democracy.glade'), 'add-channel-dialog', 'democracyplayer')
        dialog = widgetTree['add-channel-dialog']
        mainWindow = self.mainFrame.widgetTree['main-window']
        dialog.set_transient_for(mainWindow)
        # run the dialog
        response = dialog.run()

        if response == gtk.RESPONSE_OK:
            channel = widgetTree['add-channel-entry'].get_text()
            app.controller.addAndSelectFeed(channel)

        dialog.destroy()

    def on_preference(self, event = None):
        # get our add channel dialog
        movie_dir = config.get(config.MOVIES_DIRECTORY)
        widgetTree = MainFrame.WidgetTree(resource.path('democracy.glade'), 'dialog-preferences', 'democracyplayer')
        dialog = widgetTree['dialog-preferences']
        mainWindow = self.mainFrame.widgetTree['main-window']
        dialog.set_transient_for(mainWindow)
        AttachBoolean (widgetTree['checkbutton-limit'], config.LIMIT_UPSTREAM, widgetTree['entry-limit'])
        AttachBoolean (widgetTree['checkbutton-padding'], config.PRESERVE_DISK_SPACE, widgetTree['entry-padding'])
        AttachInteger (widgetTree['entry-limit'], config.UPSTREAM_LIMIT_IN_KBS)
        AttachInteger (widgetTree['entry-padding'], config.PRESERVE_X_GB_FREE)
        AttachCombo (widgetTree['combobox-poll'], config.CHECK_CHANNELS_EVERY_X_MN, (30, 60, -1))
        AttachCombo (widgetTree['combobox-expiration'], config.EXPIRE_AFTER_X_DAYS, (1, 3, 6, 10, 30, -1))

        chooser = widgetTree['filechooserbutton-movies-directory']
        chooser.set_filename (movie_dir + "/")
        # run the dialog
        response = dialog.run()
        new_movie_dir = widgetTree['filechooserbutton-movies-directory'].get_filename()
        if (movie_dir != new_movie_dir):
            migrate_widgetTree = MainFrame.WidgetTree(resource.path('democracy.glade'), 'dialog-migrate', 'democracyplater')
            migrate_dialog = migrate_widgetTree['dialog-migrate']
            response = migrate_dialog.run()
            migrate = "0"
            if (response == gtk.RESPONSE_YES):
                migrate = "1"
            app.ModelActionHandler(frontend.UIBackendDelegate()).changeMoviesDirectory (new_movie_dir, migrate)
            migrate_dialog.destroy()
        dialog.destroy()

    def on_about_clicked(self, event = None):
        self.mainFrame.about()
