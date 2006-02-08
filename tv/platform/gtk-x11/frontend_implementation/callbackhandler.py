"""Frontend callback handler.  Responsible for handling all GUI actions."""

import app
import gobject
import gtk
import os
import shutil

class CallbackHandler(object):
    """This is where everything happens.  The method names for this class
    correspond to the event handler that they implement.  The event handler
    name's are chosen in glade.  We use the underscored_method_name convention
    here, because that's the default for glade.
    """

    def __init__(self, mainFrame):
        self.mainFrame = mainFrame
        self.mainApp = app.Controller.instance
        self.videoDisplay = self.mainApp.videoDisplay
        self.playbackController = self.mainApp.playbackController

    def on_main_destroy(self, event):
        gtk.main_quit()

    def on_play_pause_button_clicked(self, event):
        app.Controller.instance.playbackController.playPause()
        self.mainFrame.updatePlayPauseButton()

    def on_previous_button_clicked(self, event):
        self.playbackController.skip(-1)

    def on_next_button_clicked(self, event):
        self.playbackController.skip(1)

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

    def on_video_time_scale_change_value(self, range, scroll, value):
        renderer = self.videoDisplay.activeRenderer
        if renderer:
            renderer.setCurrentTime(value)
        return True

    def on_volume_scale_value_changed(self, scale):
        self.videoDisplay.setVolume(scale.get_value())

    def on_save_video_activate(self, event):
        # I think the following is the best way to get the current playlist
        # item, but I'm not sure it will work all the time so I wrapped it in
        # a try, except.  This is pretty ugly, IMHO.  Someone who knows more
        # than me about the system should fix this.
        try:
            item = self.playbackController.currentPlaylist.cur()
            videoPath = item.getPath()
        except:
            return
        self.videoDisplay.pause()
        chooser = gtk.FileChooserDialog("Save Video As...",
                self.mainFrame.mainWindow,
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
        if self.playbackController.currentDisplay == self.videoDisplay:
            self.videoDisplay.play()
        else:
            self.playbackController.enterPlayback()

    def on_stop_activate(self, event):
        if self.playbackController.currentDisplay == self.videoDisplay:
            self.videoDisplay.pause()
        else:
            pass
            # I think this will happen if we play an item externally.  Not
            # sure what to do here.

    def on_quit_activate(self, event):
        gtk.main_quit()

    def on_update_channel_activate(self, event):
        pass
        # this is what's in the OS X version, but it'l not working because I'm
        # not sure what self.appl should be
        #
        #feedID = self.mainApp.currentSelectedTab.feedID()
        #if feedID is not None:
        #    backEndDelegate = self.appl.getBackendDelegate()
        #    app.ModelActionHandler(backEndDelegate).updateFeed(feedID)
