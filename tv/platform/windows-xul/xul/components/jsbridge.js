const JSBRIDGE_CONTRACTID = "@participatoryculture.org/dtv/jsbridge;1";
const JSBRIDGE_CLASSID    = Components.ID("{421AA951-F53D-4499-B362-E432CAE920F4}");

var pybridge = Components.classes["@participatoryculture.org/dtv/pybridge;1"].
        getService(Components.interfaces.pcfIDTVPyBridge);

function writelog(str) {
    Components.classes['@mozilla.org/consoleservice;1']
	.getService(Components.interfaces.nsIConsoleService)	
	.logStringMessage(str);
}

function twoDigits(data) {
    if (data < 10) return "0" + data;
    else return ""+data;
}

function LoadFinishedListener(area)
{
    this.area = area;
}

var actionGroupCommands = {
  'ChannelSelected': Array('copychannellink', 'recommendcurrentchannel'),
  'ChannelFolderSelected': Array(),
  'VideoSelected': Array('copyvideourl', 'savevideoas'),
  'VideosSelected': Array('removevideo'),
  'PlaylistLikeSelected': Array('renameplaylist'),
  'PlaylistLikesSelected': Array('removeplaylist'),
  'ChannelLikesSelected': Array(),
  'ChannelLikeSelected': Array('renamechannel', 'removechannel', 'updatechannel'),
  'ChannelsSelected': Array(),
  'VideoPlayable': Array(),
}

LoadFinishedListener.prototype =
{
  QueryInterface : function(aIID)
  {
    if (aIID.equals(Components.interfaces.nsIWebProgressListener) ||
        aIID.equals(Components.interfaces.nsISupportsWeakReference) ||
        aIID.equals(Components.interfaces.nsISupports))
    {
      return this;
    }
    throw Components.results.NS_NOINTERFACE;
  },

  onStateChange : function(aWebProgress, aRequest, aStateFlags, aStatus)
  {
    var allFlags = (Components.interfaces.nsIWebProgressListener.STATE_STOP |
        Components.interfaces.nsIWebProgressListener.STATE_IS_WINDOW);
    if((aStateFlags & allFlags) == allFlags) {
      pybridge.pageLoadFinished(this.area, aRequest.name);
    }
  },
  onProgressChange : function(aWebProgress, aRequest, aCurSelfProgress,
aMaxSelfProgress, aCurTotalProgress, aMaxTotalProgress) { },
  onLocationChange : function(aWebProgress, aRequest, aLocation) { },
  onStatusChange : function(aWebProgress, aRequest, aStatus, aMessage) { },
  onSecurityChange : function(aWebProgress, aRequest, aState) { }
} 

// Reference to the progress listeners we create, addProgressListener uses a
// weak reference, so we need to keep a real reference around or else they
// will magically disapear
var progressListeners = {}

function jsBridge() { }

jsBridge.prototype = {
  QueryInterface: function(iid) {
    if (iid.equals(Components.interfaces.pcfIDTVJSBridge) ||
      iid.equals(Components.interfaces.nsISupports))
      return this;
    throw Components.results.NS_ERROR_NO_INTERFACE;
  },

  init: function(window) {
    this.window = window;
    this.document = window.document;
    this.initBrowser("mainDisplay");
    this.initBrowser("videoInfoDisplay");
    this.initBrowser("channelsDisplay");
    this.hideVideoControlsTimer = Components.classes["@mozilla.org/timer;1"].
          createInstance(Components.interfaces.nsITimer);
    this.videoFilename = null;

    var self = this;
    self.lastMouseDownX = self.lastMouseDownY = 0;
    var saveMousedownPosition = function(event) { 
        self.lastMouseDownX = event.screenX;
        self.lastMouseDownY = event.screenY;
    }
    this.document.addEventListener('mousedown', saveMousedownPosition, true);
  },

  closeWindow: function() {
    this.window.close();
  },

  initBrowser: function(area) {
    var browser = this.document.getElementById(area);
    var listener = new LoadFinishedListener(area);
    browser.addProgressListener(listener);
    progressListeners[area] = listener;
  },

  copyTextToClipboard: function(text) {
    var gClipboardHelper = Components.classes["@mozilla.org/widget/clipboardhelper;1"].getService(Components.interfaces.nsIClipboardHelper);
    gClipboardHelper.copyString(text);
  },

  showContextMenu: function(menuItems) {
    var popup = this.document.getElementById('contextPopup');
    while (popup.firstChild) {
      popup.removeChild(popup.firstChild);
    }
    menu = menuItems.split("\n");
    for(var i = 0; i < menu.length; i++) {
      if(menu[i]) {
        var newItem = this.document.createElement('menuitem');
        if(menu[i].charAt(0) != '_') {
          newItem.setAttribute("label", menu[i]);
        } else {
          newItem.setAttribute("label", menu[i].substr(1));
          newItem.setAttribute("disabled", "true");
        }
        newItem.setAttribute("oncommand", 
           "pybridge.handleContextMenu(" + i + ");");
      } else {
        var newItem = this.document.createElement('menuseparator');
      }
      popup.appendChild(newItem);
    }
    popup.showPopup(this.document.documentElement, this.lastMouseDownX,
        this.lastMouseDownY, "popup", null, null);
  },

  showChoiceDialog: function(id, title, description, defaultLabel, otherLabel) {
    var params = { "id": id, "title": title, "description" : description, 
        "defaultLabel": defaultLabel, "otherLabel": otherLabel, "out" : -1};
    this.window.openDialog("chrome://dtv/content/choice_dialog.xul",
            "dialog", "chrome,dependent,centerscreen,modal", params);
  },

  showThreeChoiceDialog: function(id, title, description, defaultLabel,
                        secondLabel, thirdLabel) {
    var params = { "id": id, "title": title, "description" : description, 
        "defaultLabel": defaultLabel, "secondLabel": secondLabel, 
        "thirdLabel": thirdLabel, "out" : -1};
    this.window.openDialog("chrome://dtv/content/three_choice_dialog.xul",
            "dialog", "chrome,dependent,centerscreen,modal", params);
  },

  showMessageBoxDialog: function(id, title, description) {
    var params = { "id": id, "title": title, "description" : description,
            "out" : -1};
    this.window.openDialog("chrome://dtv/content/message_box_dialog.xul",
            "dialog", "chrome,dependent,centerscreen,modal", params);
  },

  showHTTPAuthDialog: function(id, description, prefillUser, prefillPassword) {
    var params = {"id": id, "text" : description, "prefillUser": prefillUser,
        "prefillPassword": prefillPassword, "out" : null};
    this.window.openDialog("chrome://dtv/content/password.xul",
            "dialog", "chrome,dependent,centerscreen,modal", params);
  },

  showBugReportDialog: function(when, report) {
    var params = {"when" : when, "report": report};
    this.window.openDialog("chrome://dtv/content/bugreport.xul",
            "choice", "chrome,dependent,centerscreen,modal", params);
  },

  showTextEntryDialog: function(id, title, description, defaultLabel, 
                                otherLabel, prefillText) {
    var params = { "id": id, "title": title, "description" : description, 
        "defaultLabel": defaultLabel, "otherLabel": otherLabel, 
        "prefillText": prefillText, "out" : -1};
    this.window.openDialog("chrome://dtv/content/text_entry_dialog.xul",
            "dialog", "chrome,dependent,centerscreen,modal", params);
  },

  showSearchChannelDialog: function(id) {
    var params = { "id": id, "out" : -1};
    this.window.openDialog("chrome://dtv/content/searchchannel.xul",
            "dialog", "chrome,dependent,centerscreen,modal", params);
  },

  setCollapsed: function(id, value) {
    var elt = this.document.getElementById(id);
    elt.setAttribute("collapsed", value);
  },

  setActive: function(id, active) {
    var elt = this.document.getElementById(id);
    if(active) elt.className = id;
    else elt.className = id + "-inactive";
  },

  showVideoDisplay: function() {
    this.setCollapsed("video-box", "false");
    this.setCollapsed("mainDisplay", "true");
    this.setActive("bottom-buttons-previous", true);
    this.setActive("bottom-buttons-stop", true);
    this.setActive("bottom-buttons-play", true);
    this.setActive("bottom-buttons-fullscreen", true);
    this.setActive("bottom-buttons-next", true);
    this.setActive("progress-slider", true);
  },

  hideVideoDisplay: function() {
    this.setCollapsed("video-box", "true");
    this.setCollapsed("mainDisplay", "false");
    this.setActive("bottom-buttons-previous", false);
    this.setActive("bottom-buttons-stop", false);
    this.setActive("bottom-buttons-play", false);
    this.setActive("bottom-buttons-fullscreen", false);
    this.setActive("bottom-buttons-next", false);
    this.setActive("progress-slider", false);
  },

  positionVolumeSlider: function(volume) {
    var left = 25;
    var right= 98;
    var position = left + (right-left) * volume;
    position = Math.min(right, Math.max(left, position));
    this.document.getElementById("knob").left = position;
  },

  hideForFullscreen: Array('channelsDisplay', 'mainSplitter',
        'resizer-left', 'bottom-left', 'resizer-bottom-right'),
  showForFullscreen: Array('bottom-left-blank', 'bottom-right-blank'),

  toggleFullscreen: function() {
    if(this.window.fullScreen) this.leaveFullscreen();
    else this.enterFullscreen();
  },

  enterFullscreen: function() {
    if(this.window.fullScreen) return;
    this.window.fullScreen = true;
    for(var i = 0; i < this.hideForFullscreen.length; i++) {
          var elt = this.document.getElementById(this.hideForFullscreen[i]);
          elt.collapsed = true;
    }
    for(var i = 0; i < this.showForFullscreen.length; i++) {
          var elt = this.document.getElementById(this.showForFullscreen[i]);
          elt.collapsed = false;
    }


    var self = this;
    this.mousedown = false;
    this.mousemoveListener = function(event) { 
        if(!self.mousedown) self.onMouseMoveFullscreen(); 
    }
    this.mousedownListener = function(event) { 
        self.mousedown = true;
        self.hideVideoControlsTimer.cancel();
    }
    this.mouseupListener = function(event) { 
        self.mousedown = false;
        self.startHideVideoControlsTimer();
    }
    this.document.addEventListener('mousemove', this.mousemoveListener, true);
    this.document.addEventListener('mousedown', this.mousedownListener, true);
    this.document.addEventListener('mouseup', this.mouseupListener, true);
    this.startHideVideoControlsTimer();
  },

  leaveTotallyFullscreen: function() {
    this.document.getElementById('titlebar').collapsed = false;
    this.document.getElementById('bottom').collapsed = false;
    this.document.getElementById('videoInfoDisplay').collapsed = false;
    this.hideVideoControlsTimer.cancel();
    pybridge.showCursor(true);
  },

  onMouseMoveFullscreen: function() {
      this.leaveTotallyFullscreen();
      this.startHideVideoControlsTimer();
  },

  startHideVideoControlsTimer: function() {
    var bottom = this.document.getElementById('bottom')
    var videoInfoDisplay = this.document.getElementById('videoInfoDisplay')
    var titlebar = this.document.getElementById('titlebar');
    var callback = {notify: function() {
        titlebar.collapsed = videoInfoDisplay.collapsed = bottom.collapsed = true;
        pybridge.showCursor(false);
    }};
    this.hideVideoControlsTimer.initWithCallback(callback, 3000,
            Components.interfaces.nsITimer.TYPE_ONE_SHOT);
  },


  leaveFullscreen: function() {
    if(!this.window.fullScreen) return;
    this.window.fullScreen = false;
    for(var i = 0; i < this.hideForFullscreen.length; i++) {
          var elt = this.document.getElementById(this.hideForFullscreen[i]);
          elt.collapsed = false;
    }
    for(var i = 0; i < this.showForFullscreen.length; i++) {
          var elt = this.document.getElementById(this.showForFullscreen[i]);
          elt.collapsed = true;
    }
    this.leaveTotallyFullscreen();
    this.document.removeEventListener('mousemove', this.mousemoveListener, true);
    this.document.removeEventListener('mouseup', this.mouseupListener, true);
    this.document.removeEventListener('mousedown', this.mousedownListener, true);
  },

  xulNavigateDisplay: function(area, uri) {
    var browser = this.document.getElementById(area);
    browser.contentDocument.location = uri;
  },

  getDocument: function(area) {
    var browser = this.document.getElementById(area);
    return browser.contentDocument;
  },

  createNode: function(document, xml) {
    var r = document.createRange();
    r.selectNode(document.documentElement);
    return r.createContextualFragment(xml);
  },

  xulAddElementAtEnd: function(area, xml, id) {
    var document = this.getDocument(area);
    var elt = document.getElementById(id);
    elt.insertBefore(this.createNode(document, xml), null);
  },
  xulAddElementBefore: function(area, xml, id) {
    var document = this.getDocument(area);
    var elt = document.getElementById(id);
    elt.parentNode.insertBefore(this.createNode(document, xml), elt);
  },
  xulRemoveElement: function(area, id) {
    var document = this.getDocument(area);
    var elt = document.getElementById(id);
    elt.parentNode.removeChild(elt);
  },
  xulChangeElement: function(area, id, xml) {
    var document = this.getDocument(area);
    var elt = document.getElementById(id);
    var next = elt.nextSibling;
    elt.parentNode.removeChild(elt);
    next.parentNode.insertBefore(this.createNode(document, xml), next);
  },
  xulHideElement: function(area, id) {
    var document = this.getDocument(area);
    var elt = document.getElementById(id);
    elt.style.display = 'none';
  },
  xulShowElement: function(area, id) {
    var document = this.getDocument(area);
    var elt = document.getElementById(id);
    elt.style.display = '';
  },

  setActionGroupEnabled: function(group, enabled) {
     var elements = actionGroupCommands[group];
     if(group == 'VideoPlayable') {
       this.setActive("bottom-buttons-play", enabled);
     }
     for(var i = 0; i < elements.length; i++) {
       var elt = this.document.getElementById(elements[i]);
       if(!enabled) {
         elt.setAttribute('disabled', true);
       } else {
         elt.removeAttribute('disabled');
       }
     }
  },
  updateLabel: function(id, label) {
    var menuitem = this.document.getElementById(id);
    menuitem.setAttribute('label', label);
  },
  updateVideoFilename: function(newFilename) {
    if(newFilename) this.videoFilename = newFilename;
    else this.videoFilename = null;
  },
  saveVideo: function() {
    if(this.videoFilename == null) return;

    var fp = Components.classes["@mozilla.org/filepicker;1"]
            .createInstance(Components.interfaces.nsIFilePicker);
    var saveMenuItem = this.document.getElementById('menuitem-video-save');
    fp.init(this.window, saveMenuItem.getAttribute('label'),
        Components.interfaces.nsIFilePicker.modeSave);
    fp.defaultString = this.videoFilename;
    var res = fp.show();
    if (res == Components.interfaces.nsIFilePicker.returnOK){
        pybridge.saveVideoFile(fp.file.path);
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
    var left = 61;
    var right = 204;
    var newSliderPos = Math.floor(left + fractionDone*(right-left));
    var progressSlider = this.document.getElementById("progress-slider");
    progressSlider.left = newSliderPos;
  },
};

var Module = {
  _classes: {
      jsBridge: {
          classID: JSBRIDGE_CLASSID,
          contractID: JSBRIDGE_CONTRACTID,
          className: "DTV Javascript helpers",
          factory: {
              createInstance: function(delegate, iid) {
                  if (delegate)
                      throw Components.results.NS_ERROR_NO_AGGREGATION;
                  return new jsBridge().QueryInterface(iid);
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
