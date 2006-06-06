const VLCRENDERER_CONTRACTID = "@participatoryculture.org/dtv/vlc-renderer;1";
const VLCRENDERER_CLASSID = Components.ID("{F9F01D99-9D3B-4A69-BD5F-285FFD360079}");

var pybridge = Components.classes["@participatoryculture.org/dtv/pybridge;1"].
        getService(Components.interfaces.pcfIDTVPyBridge);

function writelog(str) {
    Components.classes['@mozilla.org/consoleservice;1']
	.getService(Components.interfaces.nsIConsoleService)	
	.logStringMessage(str);
}

function VLCRenderer() { 
  this.scheduleUpdates = false;
}

function twoDigits(data) {
    if (data < 10) return "0" + data;
    else return ""+data;
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
  },

  updateVideoControls: function() {
    var elapsed = this.vlc.get_time();
    var len = this.vlc.get_length();
    if (len < 1) len = 1;
    if (elapsed < 0) elapsed = 0;
    if (elapsed > len) elapsed = len;
    this.setSliderText(elapsed);
    this.moveSlider(elapsed/len);
    var pos = this.vlc.get_position();
    if(this.startedPlaying && pos < 0) {
        // hit the end of the playlist
        this.scheduleUpdates = false;
        pybridge.skip(1);
    } else if(pos >=0) {
      this.startedPlaying = true;
    }
    if(this.scheduleUpdates) {
        var callback = {
          notify: function(timer) { this.parent.updateVideoControls()}
        };
        callback.parent = this;
        this.timer.initWithCallback(callback, 500,
                  Components.interfaces.nsITimer.TYPE_ONE_SHOT);
      }
  },

  setSliderText: function(elapsed) {
    var hours = Math.floor(elapsed/3600);
    var mins = Math.floor((elapsed - hours*3600)/60);
    var secs = elapsed - hours*3600 - mins*60;
    var text = twoDigits(hours)+":"+twoDigits(mins)+":"+twoDigits(secs);
    var sliderText = this.document.getElementById("progress-text");
    sliderText.childNodes[0].nodeValue = text;
  },

  moveSlider: function(fractionDone) {
    var progressSlider = this.document.getElementById("progress-slider");
    if(progressSlider.beingDragged) return;
    var left = 61;
    var right = 204;
    var newSliderPos = Math.floor(left + fractionDone*(right-left));
    progressSlider.style.left = newSliderPos+"px";
  },

  showPauseButton: function() {
    var playButton = this.document.getElementById("bottom-buttons-play");
    playButton.className = "bottom-buttons-pause";
  },

  showPlayButton: function() {
    var playButton = this.document.getElementById("bottom-buttons-play");
    playButton.className = "bottom-buttons-play";
  },

  reset: function() {
    this.stop();
    this.vlc.clear_playlist();
    this.showPlayButton();
  },

  canPlayURL: function(url) {
    return true;
  },

  selectURL: function(url) {
    this.vlc.stop();
    this.vlc.clear_playlist();
    this.vlc.add_item(url);
  },

  play: function() {
    this.vlc.play(0);
    this.scheduleUpdates = true;
    this.startedPlaying = false;
    this.updateVideoControls();
    this.showPauseButton();
  },

  pause: function() {
    this.scheduleUpdates = false;
    this.vlc.pause();
    this.showPlayButton();
  },

  stop: function() {
    this.scheduleUpdates = false;
    this.vlc.stop();
    this.showPlayButton();
  },

  goToBeginningOfMovie: function() {
    this.vlc.seek(0, 0);
  },

  getDuration: function() {
    rv = this.vlc.get_length();
    return rv;
  },

  getCurrentTime: function() {
    rv = this.vlc.get_time();
    return rv;
  },

  setVolume: function(level) {
    this.vlc.set_volume(level*200);
  },

  goFullscreen: function() {
    this.vlc.fullscreen();
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
