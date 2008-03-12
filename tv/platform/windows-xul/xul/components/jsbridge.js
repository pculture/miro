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

const JSBRIDGE_CONTRACTID = "@participatoryculture.org/dtv/jsbridge;1";
const JSBRIDGE_CLASSID    = Components.ID("{421AA951-F53D-4499-B362-E432CAE920F4}");

// These are direct JavaScript translations of xulhelper.py
//
// Unfortunately, I don't see a way around having a Python version, a
// XUL/JS version, and a Chrome/JS version of all of these.
//
// See also xulhelper.js

var proxyManager = Components.classes["@mozilla.org/xpcomproxy;1"].createInstance(Components.interfaces.nsIProxyObjectManager);

try {
    // XULRunner 1.8 version
    var eventQueueService = Components.classes["@mozilla.org/event-queue-service;1"].getService(Components.interfaces.nsIEventQueueService);
    var xulEventQueue = eventQueueService.getSpecialEventQueue(Components.interfaces.nsIEventQueueService.UI_THREAD_EVENT_QUEUE);
} catch (e) {
    // XULRunner 1.9 version
    var threadMan = Components.classes["@mozilla.org/thread-manager;1"].getService(Components.interfaces.nsIThreadManager);
    var xulEventQueue = threadMan.mainThread;
}

function proxify(obj, iid, sync) {
    if (sync === false) {
        var flags = Components.interfaces.nsIProxyObjectManager.INVOKE_ASYNC | Components.interfaces.nsIProxyObjectManager.FORCE_PROXY_CREATION;
    } else {
        var flags = Components.interfaces.nsIProxyObjectManager.INVOKE_SYNC | Components.interfaces.nsIProxyObjectManager.FORCE_PROXY_CREATION;
    }
    return proxyManager.getProxyForObject(xulEventQueue, iid, obj, flags);
}

function makeComp(clsid, iid, makeProxy, sync) {
    if (makeProxy === null) {
      throw("makeComp() requires three arguments. Only two set");
    }
    var obj = Components.classes[clsid].createInstance(iid);
    if (makeProxy) obj = proxify(obj, iid, sync);
    return obj;
}

function makeService(clsid, iid, makeProxy, sync) {
    if (makeProxy === null) {
      throw("makeService() requires three arguments. Only two set");
    }
    var obj = Components.classes[clsid].getService(iid);
    if (makeProxy) obj = proxify(obj, iid, sync);
    return obj;
}

// We do this so often, we might as well make a function
function getPyBridge() {
    return makeService("@participatoryculture.org/dtv/pybridge;1",Components.interfaces.pcfIDTVPyBridge, false);
}

function writelog(str) {
    makeService('@mozilla.org/consoleservice;1',Components.interfaces.nsIConsoleService,false).logStringMessage(str);
}

function twoDigits(data) {
    if (data < 10) return "0" + data;
    else return ""+data;
}


function formatTime(milliseconds) {
    if(milliseconds < 0) milliseconds = 0;
    total_seconds = Math.floor(milliseconds / 1000);
    var hours = Math.floor(total_seconds/3600);
    var mins = Math.floor((total_seconds - hours*3600)/60);
    var secs = total_seconds - hours*3600 - mins*60;
    return twoDigits(hours)+":"+twoDigits(mins)+":"+twoDigits(secs);
}

function makeLocalFile(path) {
    var file = makeComp("@mozilla.org/file/local;1",Components.interfaces.nsILocalFile, false);
    file.initWithPath(path);
    return file;
}

function pickSavePath(window, title, defaultDirectory, defaultFilename) {
    var nsIFilePicker = Components.interfaces.nsIFilePicker;
    var fp = makeComp("@mozilla.org/filepicker;1",nsIFilePicker, false);
    fp.init(window, title, nsIFilePicker.modeSave);
    if(defaultDirectory) {
       fp.setDefaultDirectory(makeLocalFile(defaultDirectory));
    }
    if(defaultFilename) {
      fp.defaultString = defaultFilename;
    }
    var returncode = fp.show();
    if (returncode == nsIFilePicker.returnOK || 
            returncode == nsIFilePicker.returnReplace) {
       return fp.file.path;
    }  else {
       return null;
    }
}

function LoadFinishedListener(area)
{
    this.area = area;
}

var actionGroupCommands = {
  'ChannelSelected': Array('menuitem-copychannelurl', 'menuitem-mailchannel'),
  'ChannelFolderSelected': Array(),
  'VideoSelected': Array('menuitem-copyvideourl', 'menuitem-savevideo'),
  'VideosSelected': Array('menuitem-removevideos'),
  'PlaylistLikeSelected': Array('menuitem-renameplaylist'),
  'PlaylistLikesSelected': Array('menuitem-removeplaylists'),
  'ChannelLikesSelected': Array(),
  'ChannelLikeSelected': Array('menuitem-renamechannel',
                  'menuitem-removechannels', 'menuitem-updatechannels'),
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
      var pybridge = getPyBridge();
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
    this.hideVideoControlsTimer = makeComp("@mozilla.org/timer;1",Components.interfaces.nsITimer, false);
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
 
  maximizeWindow: function () {
    this.window.maximize();
    this.window.maximized = true;
  },

  initBrowser: function(area) {
    var browser = this.document.getElementById(area);
    var listener = new LoadFinishedListener(area);
    browser.addProgressListener(listener);
    progressListeners[area] = listener;
  },

  copyTextToClipboard: function(text) {
    var gClipboardHelper = makeService("@mozilla.org/widget/clipboardhelper;1", Components.interfaces.nsIClipboardHelper,false);
    gClipboardHelper.copyString(text);
  },

  showContextMenu: function(menuItems) {
    var pybridge = getPyBridge();
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
  fillSearchMenu: function() {
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
  },

  showChoiceDialog: function(id, title, description, defaultLabel, otherLabel) {
    var params = { "id": id, "title": title, "description" : description, 
        "defaultLabel": defaultLabel, "otherLabel": otherLabel, "out" : -1};
    this.window.openDialog("chrome://dtv/content/choice_dialog.xul",
            "dialog", "chrome,dependent,centerscreen,modal", params);
  },

  showCheckboxDialog: function(id, title, description, defaultLabel,
              otherLabel, checkboxText, checkboxValue) {
    var params = { "id": id, "title": title, "description" : description, 
        "defaultLabel": defaultLabel, "otherLabel": otherLabel, 
        "checkboxText": checkboxText, "checkboxValue": checkboxValue,
        "out" : -1};
    this.window.openDialog("chrome://dtv/content/checkbox_dialog.xul",
            "dialog", "chrome,dependent,centerscreen,modal", params);
  },
  showCheckboxTextboxDialog: function(id, title, description, defaultLabel,
              otherLabel, checkboxText, checkboxValue, textboxValue) {
    var params = { "id": id, "title": title, "description" : description, 
        "defaultLabel": defaultLabel, "otherLabel": otherLabel, 
        "checkboxText": checkboxText, "checkboxValue": checkboxValue,
        "out" : -1, "textboxValue": textboxValue};
    this.window.openDialog("chrome://dtv/content/checkboxtextbox_dialog.xul",
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
            "dialog", "chrome,dependent,centerscreen,modal,resizable", params);
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

  setExternalVideoDisplay: function() {
    this.setActive("bottom-buttons-stop", true);
  },

  positionVolumeSlider: function(volume) {
    var left = 25;
    var right= 98;
    var position = left + (right-left) * volume;
    position = Math.min(right, Math.max(left, position));
    this.document.getElementById("knob").left = position;
  },

  hideForFullscreen: Array('channelsDisplay', 'mainSplitter',
        'resizer-left', 'bottom-left', 'resizer-bottom-right','titlebar'),
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
    this.justResized = false;
    this.mousemoveListener = function(event) {
        if((!self.mousedown) && (!self.justResized)) self.onMouseMoveFullscreen(); 
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
      var pybridge = getPyBridge();
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
    var self = this;
    // If we don't have this second callback, we ALWAYs immediately
    // get a mouse move event in Vista and go out of "totally
    // fullscreen" mode as soon as we go into it
    var callback2 = {notify: function() {
        self.justResized = false;
    }};
    var callback = {notify: function() {
        var pybridge = getPyBridge();
        self.justResized = true;
        videoInfoDisplay.collapsed = bottom.collapsed = true;
        pybridge.showCursor(false);
        self.hideVideoControlsTimer.initWithCallback(callback2, 100,
                          Components.interfaces.nsITimer.TYPE_ONE_SHOT);

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
    browser.loadURI(uri);
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
       var commandID = elt.getAttribute('command');
       if(!commandID) continue;
       var command = this.document.getElementById(commandID);
       if(!command) continue;
       if(!enabled) {
         command.setAttribute('disabled', true);
       } else {
         command.removeAttribute('disabled');
       }
     }
  },
  updateVideoFilename: function(newFilename) {
    if(newFilename) this.videoFilename = newFilename;
    else this.videoFilename = null;
  },

  saveVideo: function() {
      var pybridge = getPyBridge();
    if(this.videoFilename == null) return;
    var saveMenuItem = this.document.getElementById('menuitem-savevideo');
    var picked = pickSavePath(this.window, saveMenuItem.getAttribute('label'),
            null, this.videoFilename);
    if (picked) pybridge.saveVideoFile(picked);
  },

  performStartupTasks: function() {
      var wwatch = makeService("@mozilla.org/embedcomp/window-watcher;1",Components.interfaces.nsIWindowWatcher,false);
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
    var sliderText = this.document.getElementById("progress-text");
    sliderText.childNodes[0].nodeValue = formatTime(elapsed);
  },

  setDuration: function(duration) {
    var sliderText = this.document.getElementById("duration-text");
    sliderText.childNodes[0].nodeValue = formatTime(duration);
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
    var searchTextBox = this.document.getElementById("search-textbox");
    searchTextBox.select();
    searchTextBox.focus();
  },
  updateMenus: function (states) {
      var pybridge = getPyBridge();
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
      var pybridge = getPyBridge();
      var minimizer = makeService("@participatoryculture.org/dtv/minimize;1",Components.interfaces.pcfIDTVMinimize, false);
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
      var window = this.window;

      this.popup = document.getElementById('traypopup');
      var self = this;

      function minimize_onshown(event, x, y, screenWidth, screenHeight, document) {
          var minimizer = makeService("@participatoryculture.org/dtv/minimize;1",Components.interfaces.pcfIDTVMinimize, false);
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
          minimizer.contextMenuHack();
          popup.showPopup(
                          document.documentElement,
                          x, y,
                          "context",
                          "", "");
          minimizer.contextMenuHack2();
      }
      this.popup._minimizetotray_onshown = function(event){ return minimize_onshown(event, x, y, screenwidth, screenheight, document); };
      this.popup.addEventListener("popupshown",
                             this.popup._minimizetotray_onshown,
                             true);

      this.popup.showPopup(document.documentElement,   // anchoring element
                      -10000,                    // x
                      -10000,                    // y
                      "context",                  // type
                      "",                         // popupanchor (ignored)
                      "");

  },

  showOpenDialog: function (id, title, defaultDirectory, typeString, types) {
      var pybridge = getPyBridge();
      var nsIFilePicker = Components.interfaces.nsIFilePicker;
      var fp = Components.classes["@mozilla.org/filepicker;1"]
                      .createInstance(nsIFilePicker);
      fp.init(this.window, title, nsIFilePicker.modeOpen);
      if(defaultDirectory) {
          fp.setDefaultDirectory(makeLocalFile(defaultDirectory));
      }
      if(types) {
        var filters = new Array();
        for(var i = 0; i < types.length; i++) {
          filters[i] = "*." + types[i];
        }
        fp.appendFilter(typeString, filters.join(";"));
      }
      fp.appendFilters(nsIFilePicker.filterAll);
      if (fp.show() == nsIFilePicker.returnOK){
        pybridge.handleFileDialog(id, fp.file.path);
    }
  },

  showSaveDialog: function (id, title, defaultDirectory, defaultFilename) {
      var pybridge = getPyBridge();
      var picked = pickSavePath(this.window, title, defaultDirectory, defaultFilename);
      if (picked) pybridge.handleFileDialog(id, picked);
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
