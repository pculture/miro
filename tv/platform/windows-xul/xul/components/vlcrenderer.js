/*
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
*/


const VLCRENDERER_CONTRACTID = "@participatoryculture.org/dtv/vlc-renderer;1";
const VLCRENDERER_CLASSID = Components.ID("{F9F01D99-9D3B-4A69-BD5F-285FFD360079}");

function writelog(str) {
    Components.classes['@mozilla.org/consoleservice;1']
        .getService(Components.interfaces.nsIConsoleService)        
        .logStringMessage(str);
}

function VLCRenderer() { 
  this.scheduleUpdates = false;
}

VLCRenderer.prototype = {
  QueryInterface: function(iid) {
    if (iid.equals(Components.interfaces.pcfIDTVVLCRenderer) ||
      iid.equals(Components.interfaces.nsISupports))
      return this;
    throw Components.results.NS_ERROR_NO_INTERFACE;
  },
  hasVLC: function(func, param1, param2, param3) {
    if (this.vlc == null) {
      writelog("VLC Missing!");
      return false; 
    } else {
      return true;
    }
  },
  init: function(win) {
      this.document = win.document;
      var videoBrowser = this.document.getElementById("mainDisplayVideo");
      this.vlc = videoBrowser.contentDocument.getElementById("video1");
      this.timer = Components.classes["@mozilla.org/timer;1"].
          createInstance(Components.interfaces.nsITimer);
      this.timer2 = Components.classes["@mozilla.org/timer;1"].
          createInstance(Components.interfaces.nsITimer);
      this.active = false;
      this.startedPlaying = false;
      this.item = null;
      this.playTime = 0;
      this.volume = 0;
      var x = this.vlc.playlist.isPlaying; // Check to see if it's REALLY initialized
  },

  doScheduleUpdates: function() {
      var callback = {
          notify: function(timer) { this.parent.updateVideoControls()}
      };
      callback.parent = this;
      this.timer.initWithCallback(callback, 500,
                                  Components.interfaces.nsITimer.TYPE_ONE_SHOT);
  },

  updateVideoControls: function() {
    var pybridge = Components.classes["@participatoryculture.org/dtv/pybridge;1"].getService(Components.interfaces.pcfIDTVPyBridge);
    var jsbridge = Components.classes["@participatoryculture.org/dtv/jsbridge;1"].getService(Components.interfaces.pcfIDTVJSBridge);
    if (!this.hasVLC()) return;

    try {
      var elapsed = 0;
      var len = 1;
      if (this.active) {
        if(this.vlc.playlist.isPlaying) {
          this.startedPlaying = true;
          elapsed = this.vlc.input.time;
          len = this.vlc.input.length;
          if (len < 1) len = 1;
          if (elapsed < 0) elapsed = 0;
          if (elapsed > len) elapsed = len;
        } else if (this.startedPlaying) {
          // hit the end of the playlist
          this.active = false;
          this.scheduleUpdates = false;
          pybridge.onMovieFinished();
        }
  
        var progressSlider = this.document.getElementById("progress-slider");
        if(!progressSlider.beingDragged) {
          jsbridge.setSliderText(elapsed);
          jsbridge.setDuration(len);
          jsbridge.moveSlider(elapsed/len);
        }
      }
      if(this.scheduleUpdates) {
        this.doScheduleUpdates();

      }
    } catch (e) {
      if (this.startedPlaying) {
        // probably hit the end of the playlist in the middle of this function
        this.scheduleUpdates = false;
        this.active = false;
        pybridge.onMovieFinished();
      } else if(this.scheduleUpdates) {
          this.doScheduleUpdates();
      }
    }
  },

  resetVideoControls: function () {
     var jsbridge = Components.classes["@participatoryculture.org/dtv/jsbridge;1"].getService(Components.interfaces.pcfIDTVJSBridge);
     jsbridge.setSliderText(0);
     jsbridge.setDuration(-1);
     jsbridge.moveSlider(0);
  },

  showPauseButton: function() {
    // I think this is ok not to wrap in a proxy since vlcrenderer
    // is always in the Mozilla thread --NN
    //
    var pybridge = Components.classes["@participatoryculture.org/dtv/pybridge;1"].getService(Components.interfaces.pcfIDTVPyBridge);
    var playButton = this.document.getElementById("bottom-buttons-play");
    playButton.className = "bottom-buttons-pause";
    var playMenuItem = this.document.getElementById('menuitem-playpausevideo');
    var label = new Object();
    pybridge.getLabel("PlayPauseVideo", "pause",0 ,0 ,0,label);
    playMenuItem.label = label.value;
  },

  showPlayButton: function() {
    // I think this is ok not to wrap in a proxy since vlcrenderer
    // is always in the Mozilla thread --NN

    var pybridge = Components.classes["@participatoryculture.org/dtv/pybridge;1"].getService(Components.interfaces.pcfIDTVPyBridge);
    var playButton = this.document.getElementById("bottom-buttons-play");
    playButton.className = "bottom-buttons-play";
    var playMenuItem = this.document.getElementById('menuitem-playpausevideo');
    var label = new Object();
    pybridge.getLabel("PlayPauseVideo", "play",0 ,0 ,0,label);
    playMenuItem.label = label.value;
  },

  reset: function() {
    // We don't need these, and stops seem to cause problems, so I'm
    // commenting them out --NN
    // this.stop();
    // this.vlc.playlist.items.clear();
    this.showPlayButton();
    this.resetVideoControls();
  },

  selectURL: function(url) {
    if (!this.hasVLC()) return;

    if (this.vlc.playlist.items.count > 0) {
      this.stop();
      this.vlc.playlist.items.clear();
    }
    this.item = this.vlc.playlist.add(url);
  },

  setCurrentTime: function(time) {
    if (!this.hasVLC()) return;

    try {
      this.vlc.input.time = time;
    } catch (e) {
      var callback = {
        notify: function(timer) {
          this.parent.setCurrentTime(this.parent.playTime);
        }
      };
      callback.parent = this;
      this.playTime = time;
      this.timer2.initWithCallback(callback, 10,
                                   Components.interfaces.nsITimer.TYPE_ONE_SHOT);
    }
  },
  
  play: function() {
    // I think this is ok not to wrap in a proxy since vlcrenderer
    // is always in the Mozilla thread --NN
    var pybridge = Components.classes["@participatoryculture.org/dtv/pybridge;1"].getService(Components.interfaces.pcfIDTVPyBridge);
    if (!this.hasVLC()) return;

    if (this.vlc.playlist.items.count > 0) {
      if(!this.vlc.playlist.isPlaying) {
        if (this.item != null) {
          this.vlc.playlist.playItem(this.item);
          this.item = null;
        } else {
          this.vlc.playlist.play();
        }
      } 
      this.scheduleUpdates = true;
      this.active = true;
      this.startedPlaying = false;
      this.doScheduleUpdates();
      this.showPauseButton();
    } else {
      this.active = false;
      this.scheduleUpdates = false;
      pybridge.onMovieFinished();
    }
  },

  playFromTime: function(time) {
    this.play();
    this.setCurrentTime(time);
  },

  pause: function() {
    if (!this.hasVLC()) return;
    this.scheduleUpdates = false;
    this.active = false;
    if (this.vlc.playlist.isPlaying) {
        if (this.vlc.playlist.items.count > 0) {
            this.vlc.playlist.togglePause();
        }
    }
    this.showPlayButton();
  },
  // This should NEVER be called from Python code
  isPlayingJSONLY: function () {
    return this.vlc.playlist.isPlaying;
  },

  pauseForDrag: function() {
    if (!this.hasVLC()) return;
    this.scheduleUpdates = false;
    this.active = false;
    if (this.vlc.playlist.isPlaying) {
      if (this.vlc.playlist.items.count > 0) {
        this.vlc.playlist.togglePause();
      }
    }
  },

  stop: function() {
    if (!this.hasVLC()) return;
    this.scheduleUpdates = false;
    this.active = false;
    if (this.vlc.playlist.items.count > 0) {
      this.vlc.playlist.stop();
    }
    this.showPlayButton();
    this.resetVideoControls();
  },

  goToBeginningOfMovie: function() {
    this.setCurrentTime(0);
  },

  getDuration: function(pyCallback) {
    if (!this.hasVLC()) return;
    try {
      rv = this.vlc.input.length;
    } catch (e) {
      rv = -1;
    }
    pyCallback.makeCallbackFloat(rv);
  },

  // To avoid threading troubles, only call this from JavaScript
  getDurationJSONLY: function() {
    if (!this.hasVLC()) return;
    try {
      rv = this.vlc.input.length;
    } catch (e) {
      rv = -1;
    }
    return rv;
  },

  getCurrentTime: function(pyCallback) {
    if (!this.hasVLC()) return;
    var rv;
    rv = this.vlc.input.time;
    pyCallback.makeCallbackFloat(rv);
  },

  getCurrentTimeJSONLY: function() {
    if (!this.hasVLC()) return;
    var rv;
    rv = this.vlc.input.time;
    return rv;
  },

  setVolume: function(level) {
    if (!this.hasVLC()) return;
    this.volume = level * 200;
    if (!this.extractMode) {
      this.vlc.audio.mute = false;
      this.vlc.audio.volume = this.volume;
    }
  },

  goFullscreen: function() {
    if (!this.hasVLC()) return;
    this.vlc.video.fullscreen = true;
  },

  extractMovieData: function (url, screenshot_filename) {
    // I think this is ok not to wrap in a proxy since vlcrenderer
    // is always in the Mozilla thread --NN

    var pybridge = Components.classes["@participatoryculture.org/dtv/pybridge;1"].getService(Components.interfaces.pcfIDTVPyBridge);
    // Disabled until the external helper application works.
    pybridge.extractFinish (-1, false);
  },
};

var Module = {
  _classes: {
      VLCRenderer: {
          classID: VLCRENDERER_CLASSID,
          contractID: VLCRENDERER_CONTRACTID,
          className: "DTV VLC Renderer",
          factory: {
              createInstance: function(delegate, iid) {
                  if (delegate)
                      throw Components.results.NS_ERROR_NO_AGGREGATION;
                  return new VLCRenderer().QueryInterface(iid);
              }
          }
      }
  },

  registerSelf: function(compMgr, fileSpec, location, type) {
      var reg = compMgr.QueryInterface(
          Components.interfaces.nsIComponentRegistrar);

      for (var key in this._classes) {
          var c = this._classes[key];
          reg.registerFactoryLocation(c.classID, c.className, c.contractID,
                                      fileSpec, location, type);
      }
  },

  getClassObject: function(compMgr, cid, iid) {
      if (!iid.equals(Components.interfaces.nsIFactory))
          throw Components.results.NS_ERROR_NO_INTERFACE;

      for (var key in this._classes) {
          var c = this._classes[key];
          if (cid.equals(c.classID))
              return c.factory;
      }

      throw Components.results.NS_ERROR_NOT_IMPLEMENTED;
  },

  canUnload: function (aComponentManager) {
      return true;
  }
};

function NSGetModule(compMgr, fileSpec) {
  return Module;
}
