const JSBRIDGE_CONTRACTID = "@participatoryculture.org/dtv/jsbridge;1";
const JSBRIDGE_CLASSID    = Components.ID("{421AA951-F53D-4499-B362-E432CAE920F4}");

var pybridge = Components.classes["@participatoryculture.org/dtv/pybridge;1"].
        getService(Components.interfaces.pcfIDTVPyBridge);
var minimizer = Components.classes["@participatoryculture.org/dtv/minimize;1"].
        getService(Components.interfaces.pcfIDTVMinimize);

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
    this.searchEngineTitles = this.searchEngineNames = null;

    var self = this;
    self.lastMouseDownX = self.lastMouseDownY = 0;
    var saveMousedownPosition = function(event) { 
        self.lastMouseDownX = event.screenX;
        self.lastMouseDownY = event.screenY;
    }
    this.document.addEventListener('mousedown', saveMousedownPosition, true);

 if (this.window.outerWidth < 800) {
    this.window.outerWidth=800;
  }
 if (this.window.outerHeight < 500) {
    this.window.outerHeight=500;
  }
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
  showSearchMenu: function() {
    if(!this.searchEngineNames || !this.searchEngineTitles) return;

    var popup = this.document.getElementById('searchMenu');
    while (popup.firstChild) {
      popup.removeChild(popup.firstChild);
    }
    for (var i = 0; i < this.searchEngineNames.length; i++) {
        var newItem = this.document.createElement('menuitem');
        newItem.setAttribute("label", this.searchEngineTitles[i]);
        newItem.setAttribute("image", "chrome://dtv/content/images/search_icon_" + this.searchEngineNames[i] + ".png");
        newItem.setAttribute("class", "menuitem-iconic");
        newItem.setAttribute("oncommand", 
           "jsbridge.setSearchEngine('" + this.searchEngineNames[i] + "');");
        popup.appendChild(newItem);
    }
    var textbox = this.document.getElementById('search-textbox');
    popup.showPopup(textbox, -1, -1, "popup", "bottomleft", "topleft");
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

  showSearchChannelDialog: function(id, channels, engines, defaultTerm, defaultStyle, defaultChannel, defaultEngine, defaultURL) {
    var params = { "id": id, "channels" : channels, "engines" : engines,
		   "defaultTerm": defaultTerm, "defaultStyle": defaultStyle,
		   "defaultChannel": defaultChannel, "defaultEngine": defaultEngine,
		   "defaultURL": defaultURL, "Out" : -1};
    this.window.openDialog("chrome://dtv/content/searchchannel.xul",
            "dialog", "chrome,dependent,centerscreen,modal", params);
  },

  showUpdateAvailableDialog: function(id, title, description, defaultLabel,
  otherLabel, releaseNotes) {
    var params = { "id": id, "title": title, "description": description,
        "defaultLabel": defaultLabel, "otherLabel": otherLabel, 
        "releaseNotes": releaseNotes }
    this.window.openDialog("chrome://dtv/content/update_available_dialog.xul",
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
  xulChangeAttribute: function(area, id, name, value) {
    var document = this.getDocument(area);
    var elt = document.getElementById(id);
    elt.setAttribute(name, value);
  },
  xulRemoveAttribute: function(area, id, name) {
    var document = this.getDocument(area);
    var elt = document.getElementById(id);
    elt.removeAttribute(name);
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
       if(!elt) continue;
       if(!enabled) {
         elt.setAttribute('disabled', true);
       } else {
         elt.removeAttribute('disabled');
       }
     }
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

  performStartupTasks: function() {
    var wwatch = Components.classes["@mozilla.org/embedcomp/window-watcher;1"]
                .getService(Components.interfaces.nsIWindowWatcher);
    var startupTasksURL = "chrome://dtv/content/startup.xul";
    this.startup = wwatch.openWindow(null, startupTasksURL, 
            "DemocracyPlayerStartup", "chrome,dialog=yes,all", null);
  },

  updateSearchProgress: function (message) {
    this.startup.updateSearchProgress (message);
  },

  searchFinished: function (message) {
    writelog(message);
    this.startup.searchFinished (message);
  },

  searchCancelled: function (message) {
    this.startup.searchCancelled (message);
  },

  setSliderText: function(elapsed) {
    elapsed = Math.floor(elapsed / 1000);
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

  setSearchEngineInfo: function(names, titles) {
    this.searchEngineNames = names;
    this.searchEngineTitles = titles;
  },

  setSearchEngine: function(engine) {
    var searchIcon = this.document.getElementById("search-icon");
    searchIcon.setAttribute("src",'images/search_icon_' + engine + '.png');
  },
  updateMenus: function (states) {

     // Strings with new labels
     var removeChannels = new Object();
     var updateChannels = new Object();
     var removePlaylists = new Object();
     var removeVideos = new Object();
     pybridge.getLabel("RemoveChannels","",0,0,0,removeChannels);
     pybridge.getLabel("UpdateChannels","",0,0,0,updateChannels);
     pybridge.getLabel("RemovePlaylists","",0,0,0,removePlaylists);
     pybridge.getLabel("RemoveVideos","",0,0,0,removeVideos);

     states = states.QueryInterface(Components.interfaces.nsICollection);

     for (var i=0;i<states.Count();i++) {
         var state = states.GetElementAt(i);
         state = state.QueryInterface(Components.interfaces.nsICollection);
         var stateName = state.GetElementAt(0).QueryInterface(Components.interfaces.nsIVariant);

         var actions = state.GetElementAt(1);
         actions.QueryInterface(Components.interfaces.nsICollection);
         for (var j=0;j<actions.Count();j++) {
             var action = actions.GetElementAt(j).QueryInterface(Components.interfaces.nsIVariant)

             if (action == "RemoveChannels")
                 pybridge.getLabel("RemoveChannels",stateName,0,0,0,
                                   removeChannels);
             if (action == "UpdateChannels")
                 pybridge.getLabel("UpdateChannels",stateName,0,0,0,
                                   updateChannels);
             if (action == "RemovePlaylists")
                 pybridge.getLabel("RemovePlaylists",stateName,0,0,0,
                                   removePlaylists);
             if (action == "RemoveVideos")
                 pybridge.getLabel("RemoveVideos",stateName,0,0,0,
                                   removeVideos);
         }
         
     }

     var ele = this.document.getElementById("menuitem-removechannels");
     ele.setAttribute("label", removeChannels.value);
     ele = this.document.getElementById("menuitem-updatechannels");
     ele.setAttribute("label", updateChannels.value);
     ele = this.document.getElementById("menuitem-removeplaylists");
     ele.setAttribute("label", removePlaylists.value);
     ele = this.document.getElementById("menuitem-removevideos");
     ele.setAttribute("label", removeVideos.value);

  },
  updateTrayMenus: function (unwatched, downloading, paused) {
      var playUnwatched = new Object();
      var pauseDownloads = new Object();
      var restoreDownloads = new Object();
      var restoreWindow = new Object();
      var minstate = "";

      if (minimizer.isMinimized()){
          minstate = "restore";
      }
      

     // Tray menu strings that get updated periodically
     pybridge.getLabel("PlayUnwatched","",unwatched, downloading, paused, playUnwatched);
     pybridge.getLabel("PauseDownloads","",unwatched, downloading, paused,pauseDownloads);
     pybridge.getLabel("ResumeDownloads","",unwatched, downloading, paused, restoreDownloads);
     pybridge.getLabel("RestoreWindow",minstate,unwatched, downloading, paused, restoreWindow);

     var ele = this.document.getElementById("traymenu-playunwatched");
     ele.setAttribute("label", playUnwatched.value);
     ele = this.document.getElementById("traymenu-pausedownloads");
     ele.setAttribute("label", pauseDownloads.value);
     ele = this.document.getElementById("traymenu-resumedownloads");
     ele.setAttribute("label", restoreDownloads.value);
     ele = this.document.getElementById("traymenu-restorewindow");
     ele.setAttribute("label", restoreWindow.value);

  },
  setPrefDocument: function (document) {
    this.prefDocument = document;
  },

  directoryWatchAdded: function (id, dirname, shown) {
    if (this.prefDocument == null) {
      return;
    }

    var setVals = function (xulDirectory) {
      xulDirectory.getElementsByAttribute('role', 'directory')[0]
	.setAttribute('value', dirname);
      xulDirectory.getElementsByAttribute('role', 'shown')[0]
	.setAttribute('checked', shown);
      xulDirectory.getElementsByAttribute('role', 'shown')[0]
	.setAttribute('folder_id', id);
    }

    var xulListBox = this.prefDocument.getElementById('movies-collection-listbox');
    var oldChildList = xulListBox.getElementsByAttribute('folder_id', id);
    if (oldChildList.length > 0) {
	setVals(oldChildList[0]);
    } else {
      var xulDirectory = this.prefDocument.getElementById('blueprints')
	.getElementsByAttribute('role', 'movies-collection-directory')[0].cloneNode(true);
      setVals(xulDirectory);
      xulDirectory.setAttribute('folder_id', id);
      xulListBox.appendChild(xulDirectory);
    }
  },

  directoryWatchRemoved: function (id) {
    if (this.prefDocument == null) {
      return;
    }
    var xulListBox = this.prefDocument.getElementById('movies-collection-listbox');
    var oldChildList = xulListBox.getElementsByAttribute('folder_id', id);
    if (oldChildList.length > 0) {
      xulListBox.removeChild(oldChildList[0]);
    }
    this.prefDocument.selectDirectoryWatch(true);
  },
  showPopup: function(x, y) {
      // show popup and adjust position once we know width / height
      // Based on core.js from Firefox minimizetotray extension
      var screenwidth = this.window.screen.width;
      var screenheight = this.window.screen.height;
      var document = this.document;

      popup = document.getElementById('traypopup');

      function minimize_onshown(event, x, y, screenWidth, screenHeight, document) {

          var popup = event.target;
          popup.removeEventListener("popupshown",
                                    popup._minimizetotray_onshown,
                                    true);
        
          var box = popup.popupBoxObject;
          if (x + box.width > screenWidth)
          x = x - box.width;
          if (y + box.height > screenHeight)
          y = y - box.height;
        
          // re-show the popup in the right position
          popup.hidePopup();
          document.popupNode = null;
          popup.showPopup(
                          document.documentElement,
                          x, y,
                          "context",
                          "", "");
      }
      popup._minimizetotray_onshown = function(event){ return minimize_onshown(event, x, y, screenwidth, screenheight, document); };
      popup.addEventListener("popupshown",
                             popup._minimizetotray_onshown,
                             true);

      popup.showPopup(document.documentElement,   // anchoring element
                      -10000,                    // x
                      -10000,                    // y
                      "context",                  // type
                      "",                         // popupanchor (ignored)
                      "");

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
  },
};

function NSGetModule(compMgr, fileSpec) {
  return Module;
}
