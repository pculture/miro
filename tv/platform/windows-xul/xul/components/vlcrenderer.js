const VLCRENDERER_CONTRACTID = "@participatoryculture.org/dtv/vlc-renderer;1";
const VLCRENDERER_CLASSID = Components.ID("{F9F01D99-9D3B-4A69-BD5F-285FFD360079}");

var pybridge = Components.classes["@participatoryculture.org/dtv/pybridge;1"].
        getService(Components.interfaces.pcfIDTVPyBridge);
var jsbridge = Components.classes["@participatoryculture.org/dtv/jsbridge;1"].
        getService(Components.interfaces.pcfIDTVJSBridge);

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

  init: function(window) {
    this.document = window.document;
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
    this.extractMode = false;
    this.url_extract = null;
    this.timer_extract = Components.classes["@mozilla.org/timer;1"].
	      createInstance(Components.interfaces.nsITimer);
    var extractionBrowser = this.document.getElementById("mainExtractionVideo");
    this.vlc_extract = extractionBrowser.contentDocument.getElementById("video2");
    this.switchToExtractMode();
  },

  switchToExtractMode: function() {
      if (this.extractMode) {
          return;
      }
      pybridge.printOut("switchToExtractMode");
      this.vlc_extract.audio.mute = true;
      this.extractMode = true;
      this.timer.cancel();
      this.timer2.cancel();
      if (this.url_extract != null) {
          this.extractMovieDataStepStart();
      }
  },

  switchToPlayMode: function() {
       if (!this.extractMode) {
          return;
      }
      pybridge.printOut("switchToPlayMode");
      this.vlc_extract.playlist.stop();
      this.timer_extract.cancel();
      this.vlc.audio.mute = false;
      this.vlc.audio.volume = this.volume;
      this.extractMode = false;
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
     jsbridge.setSliderText(0);
     jsbridge.moveSlider(0);
  },

  showPauseButton: function() {
    var playButton = this.document.getElementById("bottom-buttons-play");
    playButton.className = "bottom-buttons-pause";
    var playMenuItem = this.document.getElementById('menuitem-playpausevideo');
    playMenuItem.label = playMenuItem.getAttribute("pause-label");
  },

  showPlayButton: function() {
    var playButton = this.document.getElementById("bottom-buttons-play");
    playButton.className = "bottom-buttons-play";
    var playMenuItem = this.document.getElementById('menuitem-playpausevideo');
    playMenuItem.label = playMenuItem.getAttribute("play-label");
  },

  reset: function() {
      // We don't need these, and stops seem to cause problems, so I'm
      // commenting them out --NN
      // this.stop();
      // this.vlc.playlist.items.clear();
      this.showPlayButton();
      this.resetVideoControls();
      this.switchToExtractMode();
  },

  canPlayURL: function(url) {
    return true;
  },

  selectURL: function(url) {
      this.switchToPlayMode();

      if (this.vlc.playlist.items.count > 0) {
          this.stop();
          this.vlc.playlist.items.clear();
      }
      this.item = this.vlc.playlist.add(url);
  },

  setCurrentTime: function(time) {
      this.switchToPlayMode();

      try {
	  this.vlc.input.time = time * 1000;
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
      this.switchToPlayMode();

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
      this.switchToPlayMode();

      this.scheduleUpdates = false;
      this.active = false;
      if (this.vlc.playlist.isPlaying) {
	  if (this.vlc.playlist.items.count > 0) {
	      this.vlc.playlist.togglePause();
	  }
      }
      this.showPlayButton();
  },

  pauseForDrag: function() {
      this.switchToPlayMode();

      this.scheduleUpdates = false;
      this.active = false;
      if (this.vlc.playlist.isPlaying) {
	  if (this.vlc.playlist.items.count > 0) {
	      this.vlc.playlist.togglePause();
	  }
      }
  },

  stop: function() {
      this.scheduleUpdates = false;
      this.active = false;
      if (this.vlc.playlist.items.count > 0) {
	  this.vlc.playlist.stop();
      }
      this.showPlayButton();
      this.resetVideoControls();
      this.switchToExtractMode();
  },

  goToBeginningOfMovie: function() {
    this.setCurrentTime(0);
  },

  getDuration: function() {
    try {
      rv = this.vlc.input.length;
    } catch (e) {
      rv = -1;
    }
    return rv;
  },

  getCurrentTime: function() {
      var rv;
      rv = this.vlc.input.time;
      return rv / 1000.0;
  },

  setVolume: function(level) {
      this.volume = level * 200;
      if (!this.extractMode) {
	  this.vlc.audio.mute = false;
	  this.vlc.audio.volume = this.volume;
      }
  },

  goFullscreen: function() {
    this.vlc.video.fullscreen = true;
  },

  extractMovieDataDone: function (success) {
      pybridge.printOut("Step extractMovieDataDone");
      this.url_extract = null;
      pybridge.extractFinish (this.duration_extract, success);
  },

  extractMovieDataStepSnapshot: function () {
      pybridge.printOut("Step Snapshot");
      try {
          pybridge.printOut("Calling takeSnapshot");
	  this.vlc_extract.video.takeSnapshot (this.screenshot_filename_extract);
          pybridge.printOut("takeSnapshot returned");
	  var callback = {
	      notify: function(timer) {
		  this.parent.extractMovieDataDone(true);
                  return;
	      }
	  };
	  callback.parent = this;
	  this.vlc_extract.playlist.stop();
	  this.timer_extract.initWithCallback(callback, 4000,
					      Components.interfaces.nsITimer.TYPE_ONE_SHOT);
          pybridge.printOut("Step Finish Queued");
      } catch (e) {
          pybridge.printOut("Step Snapshot Error");
	    if (this.vlc_extract.input.state == 0) {
		this.extractMovieDataDone(false);
		return;
	    }
	    if (this.vlc_extract.playlist.items.count == 0) {
		this.extractMovieDataDone(true);
                return;
	    } else {
	        pybridge.printOut("Step Snapshot Retrying");
		this.extract_errors ++;
		if (this.extract_errors > 100) {
		    this.extractMovieDataDone(true);
                    return;
		}
		var callback = {
		    notify: function(timer) {
			this.parent.extractMovieDataStepSnapshot();
		    }
		};
		callback.parent = this;
		this.timer_extract.initWithCallback(callback, 100,
						    Components.interfaces.nsITimer.TYPE_ONE_SHOT);
	    }
      }
  },
  
  extractMovieDataStepWaitForJump: function () {
      pybridge.printOut("Step Wait For Jump");
      pybridge.printOut(this.vlc_extract.input.time);
      //      this.extractMovieDataStepSnapshot();
//	return;
//	} catch (e) {
//	}
//	if (this.vlc_extract.playlist.items.count == 0) {
//	    this.extractMovieDataDone(false);
//            return;
//	} else {
      var callback = {
	  notify: function(timer) {
	      this.parent.extractMovieDataStepSnapshot();
	  }
      };
      callback.parent = this;
      this.timer_extract.initWithCallback(callback, 500,
					  Components.interfaces.nsITimer.TYPE_ONE_SHOT);
//	}
  },

  extractMovieDataStepJump: function () {
      pybridge.printOut("Step Jump");
      try {
	  this.vlc_extract.input.time = this.duration_extract / 2.0;
          this.extractMovieDataStepWaitForJump();
      } catch (e) {
	  if (this.vlc_extract.playlist.items.count == 0) {
	      this.extractMovieDataDone(true);
              return;
	  } else {
	      this.extract_errors ++;
	      if (this.extract_errors > 100) {
		  this.extractMovieDataDone(true);
                  return;
	      }
	      var callback = {
		  notify: function(timer) {
		      this.parent.extractMovieDataStepJump();
		  }
	      };
	      callback.parent = this;
	      this.timer_extract.initWithCallback(callback, 100,
						  Components.interfaces.nsITimer.TYPE_ONE_SHOT);
	  }
      }

  },

  extractMovieDataStepLength: function () {
      pybridge.printOut("Step Length");
//	if (this.testing_extract) {
//	    this.extractMovieDataDone(false);
//	    return;
//	}
      try {
	  this.duration_extract = this.vlc_extract.input.length;
//          this.extractMovieDataStepJump();
	  this.extractMovieDataDone(true);
	  return
      } catch (e) {
	  if (this.vlc_extract.playlist.items.count == 0) {
	      this.extractMovieDataDone(true);
              return;
	  } else {
	      this.extract_errors ++;
	      if (this.extract_errors > 100) {
		  this.extractMovieDataDone(false);
                  return;
	      }
	      var callback = {
		  notify: function(timer) {
		      this.parent.extractMovieDataStepLength();
		  }
	      };
	      callback.parent = this;
	      this.timer_extract.initWithCallback(callback, 10,
						  Components.interfaces.nsITimer.TYPE_ONE_SHOT);
	  }
      }
  },


  extractMovieDataStepWaitPlay: function () {
      pybridge.printOut("Step Wait Play");
      pybridge.printOut(this.vlc_extract.input.state);
      pybridge.printOut(this.vlc_extract.playlist.items.count);
      try {
	  if (this.vlc_extract.input.state == 3) {
	      this.extractMovieDataStepLength();
	      return;
	  }
      } catch (e) {
      }	
      if (this.vlc_extract.playlist.items.count == 0) {
	  this.extractMovieDataDone(true);
	  return;
      }
      this.extract_errors ++;
      if (this.extract_errors > 100) {
	  this.extractMovieDataDone(false);
          return;
      }
      var callback = {
	  notify: function(timer) {
	      this.parent.extractMovieDataStepWaitPlay();
	  }
      };
      callback.parent = this;
      this.timer_extract.initWithCallback(callback, 100,
					  Components.interfaces.nsITimer.TYPE_ONE_SHOT);
  },

  extractMovieDataStepAdd: function () {
      var item;
      pybridge.printOut("Step Add");
      item = this.vlc_extract.playlist.add(this.url_extract);
      this.vlc_extract.playlist.playItem (item);
      this.extractMovieDataStepWaitPlay();
  },

  extractMovieDataStepWaitStop: function () {
      pybridge.printOut("Step Wait Stop");
      try {
	  if (this.vlc_extract.input.state == 0) {
	      this.extractMovieDataStepAdd();
	      return;
	  }
      } catch (e) {
      }
      this.extract_errors ++;
      if (this.extract_errors > 100) {
	  this.extractMovieDataDone(false);
          return;
      }
      var callback = {
	  notify: function(timer) {
	      this.parent.extractMovieDataStepWaitStop();
	  }
      };
      callback.parent = this;
      this.timer_extract.initWithCallback(callback, 100,
					  Components.interfaces.nsITimer.TYPE_ONE_SHOT);
  },

  extractMovieDataStepStart: function () {
      pybridge.printOut("Step Start");
      if (this.vlc_extract.playlist.items.count > 0) {
	  this.vlc_extract.playlist.stop();
          this.vlc_extract.playlist.items.clear();
      }
      this.extractMovieDataStepWaitStop()
  },

  extractMovieData: function (url, screenshot_filename) {
      this.screenshot_filename_extract = screenshot_filename;
      this.url_extract = url;
      this.extract_errors = 0;
      this.duration_extract = -1;
      this.testing_extract = false;
      if (this.extractMode) {
	  this.extractMovieDataStepStart();
      }
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
