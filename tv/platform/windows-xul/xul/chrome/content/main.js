/*****************************************************************************
 Watching for application exit
 *****************************************************************************/

var pybridge = Components.classes["@participatoryculture.org/dtv/pybridge;1"].
                getService(Components.interfaces.pcfIDTVPyBridge);

function quitObserver()
{
  this.register();
}

quitObserver.prototype = {
  observe: function(subject, topic, data) {
    pybridge.onShutdown();
  },
  register: function() {
    var observerService = Components.classes["@mozilla.org/observer-service;1"]
                          .getService(Components.interfaces.nsIObserverService);
    observerService.addObserver(this, "quit-application", false);
  },
  unregister: function() {
    var observerService = Components.classes["@mozilla.org/observer-service;1"]
                            .getService(Components.interfaces.nsIObserverService);
    observerService.removeObserver(this, "quit-application");
  }
}

function setVideoInfoDisplayHidden(value) {
  videoInfo = document.getElementById("videoInfoDisplay");
  videoInfo.setAttribute("collasped", value);
}

/*****************************************************************************
 Volume Knob 
 *****************************************************************************/

var knobDragStart = 0;
var knobPos = 98;

function volumeKnobMove(event) {
  if (knobDragStart > 0) {
    var left = 25;
    var right= 98;
    var knob = document.getElementById("knob");
    knobPos += event.clientX - knobDragStart;
    if (knobPos < left) knobPos = left;
    if (knobPos > right) knobPos = right;
    knobDragStart = event.clientX;
    knob.style.left = knobPos +"px";
    pybridge.setVolume((knobPos - left)/(right-left));
  }
}
function volumeKnobDown(event) {
  knobDragStart = event.clientX;
}
function volumeKnobOut(event) {
  /* Ignore a move from the knob to the slider or vice-versa */
  if (!((event.target.getAttribute("id") == "knob" &&
        event.currentTarget.getAttribute("id") == "volume") ||
        (event.target.getAttribute("id") == "volume" &&
         event.currentTarget.getAttribute("id") == "volume")))
  {
    knobDragStart = 0;
  }
  event.stopPropagation();
}
function volumeKnobUp(event) {
  knobDragStart = 0;
}

/*****************************************************************************
 Video Progress Slider
 *****************************************************************************/

var progressDragStart = 0;
var progressPos = 61;

var progressDragEnabled = false;
var progressDragging = false;

function twoDigits(data) {
    if (data < 10) return "0" + data;
    else return ""+data;
}

function videoProgressUpdate(elapsed, len) {
    //FIXME: these are stored in two places
    var left = 61;
    var right = 204;
    if (len < 1) len = 1;
    if (elapsed < 0) elapsed = 0;
    if (elapsed > len) elapsed = len;
    if (progressDragStart == 0) {
        var hours = Math.floor(elapsed/3600);
        var mins = Math.floor((elapsed - hours*3600)/60);
        var secs = elapsed - hours*3600 - mins*60;
        var sliderText = document.getElementById("progress-text");
        sliderText.childNodes[0].nodeValue = twoDigits(hours)+":"+twoDigits(mins)+":"+twoDigits(secs);

        var slider = document.getElementById("progress-slider");
        var newSliderPos = Math.floor(left + (elapsed/len)*(right-left));
        slider.style.left = newSliderPos+"px";
    }
}

function videoEnableControls() {
    //jsdump('Enabling controls');
    progressDragEnabled = true;
    progressDragStart = 0;
    var prevButton = document.getElementById("bottom-buttons-previous");
    prevButton.className = "bottom-buttons-previous";
    var stopButton = document.getElementById("bottom-buttons-stop");
    stopButton.className = "bottom-buttons-stop";
    var playButton = document.getElementById("bottom-buttons-play");
    playButton.className = "bottom-buttons-pause";
    var fullButton = document.getElementById("bottom-buttons-fullscreen");
    fullButton.className = "bottom-buttons-fullscreen";
    var nextButton = document.getElementById("bottom-buttons-next");
    nextButton.className = "bottom-buttons-next";

    var slider = document.getElementById("progress-slider");
    slider.className = "progress-slider";
}
function videoDisableControls() {
    //jsdump('Disabling Controls');
    progressDragEnabled = false;
    progressDragStart = 0;
    videoProgressUpdate(0,1);
    var prevButton = document.getElementById("bottom-buttons-previous");
    prevButton.className = "bottom-buttons-previous-inactive";
    var stopButton = document.getElementById("bottom-buttons-stop");
    stopButton.className = "bottom-buttons-stop-inactive";
    var playButton = document.getElementById("bottom-buttons-play");
    playButton.className = "bottom-buttons-play";
    var fullButton = document.getElementById("bottom-buttons-fullscreen");
    fullButton.className = "bottom-buttons-fullscreen-inactive";
    var nextButton = document.getElementById("bottom-buttons-next");
    nextButton.className = "bottom-buttons-next-inactive";
    var slider = document.getElementById("progress-slider");
    slider.className = "progress-slider-inactive";
}

function videoEnablePauseButton() {
    var playButton = document.getElementById("bottom-buttons-play");
    playButton.className = "bottom-buttons-pause";
}

function videoDisablePauseButton() {
    var playButton = document.getElementById("bottom-buttons-play");
    playButton.className = "bottom-buttons-play";
}

function setVideoProgress(percent) {
  //jsdump("Video now at "+percent);
  eventURL(getCookieFromBrowserId('mainDisplay'),'action:setVideoProgress?pos='+percent);
}

function videoProgressMove(event) {
  //jsdump("Video progress move");
  if (progressDragStart > 0) {
    var left = 61;
    var right= 204;
    var slider = document.getElementById("progress-slider");
    progressPos += event.clientX - progressDragStart;
    if (progressPos < left) progressPos = left;
    if (progressPos > right) progressPos = right;
    progressDragStart = event.clientX;
    slider.style.left = progressPos +"px";
    setVideoProgress((progressPos - left)/(right-left));
  }
}
function videoProgressDown(event) {
  //jsdump("Video progress down");
  if (progressDragEnabled) {
    progressDragStart = event.clientX;
  }
}
function videoProgressOut(event) {
  //jsdump("Video progress out: "+event.target.getAttribute("id")+" "+event.currentTarget.getAttribute("id"));
  /* Ignore a move from the knob to the slider or vice-versa */
  if (!((event.target.getAttribute("id") == "progress-slider" &&
        event.currentTarget.getAttribute("id") == "progress") ||
        (event.target.getAttribute("id") == "progress" &&
         event.currentTarget.getAttribute("id") == "progress") ||
        (event.target.getAttribute("id") == "progress-text" &&
         event.currentTarget.getAttribute("id") == "progress")))
  {
    progressDragStart = 0;
  }
  event.stopPropagation();
}
function videoProgressUp(event) {
  //jsdump("Video progress up");
  progressDragStart = 0;
}

/*****************************************************************************
 Main functions
 *****************************************************************************/

function onLoad() {
    jsdump("onLoad running.");

    // Start watching for application exit.
    // NEEDS: should this move out of onLoad() and be global?
    var qo = new quitObserver();

    // Bring up Python environment.
    pybridge.onStartup(document);

    // Set up listeners for the volume knobby
    var knob = document.getElementById("volume");
    knob.onmousemove = volumeKnobMove;
    knob.onmousedown = volumeKnobDown;
    knob.onmouseout = volumeKnobOut;

    // Set up listeners for the progress slider
    var progress = document.getElementById("progress");
    progress.onmousemove = videoProgressMove;
    progress.onmousedown = videoProgressDown;
    progress.onmouseout = videoProgressOut;

    window.onmouseup = windowMouseUp;
}

function windowMouseUp(event) {
  volumeKnobUp(event);
  videoProgressUp(event);
}

function onUnload() {
    jsdump("onUnload running.");
    // Make sure the app exits (even if there is still another window
    // open such as the Javascript console, for example)
    closeApp();
}

function jsdump(str) {
    Components.classes['@mozilla.org/consoleservice;1']
	.getService(Components.interfaces.nsIConsoleService)	
	.logStringMessage(str);
}

function addChannel(url) {
    pybridge.addChannel(url);
}

function maximizeOrRestore() {
  if (window.windowState == window.STATE_MAXIMIZED) {
    window.restore();
  } else {
    window.maximize();
  }
}

function closeApp() {
  var startup = Components.classes["@mozilla.org/toolkit/app-startup;1"].
       getService(Components.interfaces.nsIAppStartup);
  startup.quit(startup.eAttemptQuit);
}

/*****************************************************************************
 Context menus
 *****************************************************************************/

// FIXME: Duplicated from dynamic.js
function getContextClickMenu(element) {
    while (1) {
	if (element.nodeType == 1 && element.getAttribute('t:contextMenu')) {
	    var ret = element.getAttribute('t:contextMenu');
	    ret = ret.replace(/\\n/g,"\n");
	    ret = ret.replace(/\\\\/g,"\\");
	    return ret;
	}
	if (element.parentNode)
	    element = element.parentNode;
	else
	    return "";
    }

    // Satisfy Mozilla that the function always returns a
    // value. Otherwise, we get an error if strict mode is enabled,
    // ultimately preventing us from getting the state change event
    // indicating that the load succeeded.
    return "";
}

function getCookieFromElement(element) {
  while (element != null) {
    if (element.tagName == "HTML")
      return element.getAttribute('eventCookie');
    else {
      element = element.parentNode;
    }
  }
  return "";
}

function getCookieFromBrowserId(elementId) {
  try {
    return document.getElementById(elementId).contentWindow.document.getElementsByTagName('html')[0].getAttribute('eventCookie');
  } catch(e) {
  return "";
  }
}

function xulcontexthandler(event) {
  var itemsAdded = 0;
  var menu = getContextClickMenu(event.target);
  var cookie = getCookieFromElement(event.target);
  var popup = document.getElementById('contextPopup');
  while (popup.firstChild) {
    popup.removeChild(popup.firstChild);
  }
  menu = menu.split("\n");
  while (menu.length > 0) {
    var line = menu.shift().split('|');
    if (line.length > 1) {
      var newItem = document.createElement('menuitem');
      newItem.setAttribute('label',line[1]);
      newItem.setAttribute('oncommand','eventURL("'+cookie+'","'+line[0]+'");');
      popup.appendChild(newItem);
      itemsAdded++;
    } else {
      var newItem = document.createElement('menuseparator');
      popup.appendChild(newItem);
    }
  }
  return (itemsAdded > 0); // Return false if there are no items in the menu
                           // This should hide empty menus, but
                           // apparently doesn't...

}

function doResize(event) {
 if (window.outerWidth < 800) {
    window.outerWidth=800;
  }
 if (window.outerHeight < 500) {
    window.outerHeight=500;
  }
  return true;  
}

function showIsScrapeAllowedDialog(cookie,text) {
  var params = {"in" : text, "out" : null};
  window.openDialog('chrome://dtv/content/canscrape.xul','canscrape','chrome,dependent,centerscreen,modal',params);
  delegateReturnURL(cookie, params.out);
}

function showYesNoDialog(cookie,title, text) {
  var params = {"text" : text, "title": title, "out" : null};
  window.openDialog('chrome://dtv/content/yesno.xul','yesno','chrome,dependent,centerscreen,modal',params);
  delegateReturnURL(cookie, params.out);
}

function showChoiceDialog(cookie, title, text, defaultButton, otherButton) {
  var params = {"text" : text, "title": title, "defaultButton": defaultButton, 
  "otherButton": otherButton, "out" : null};
  window.openDialog('chrome://dtv/content/choice_dialog.xul', 'choice', 
          'chrome,dependent,centerscreen,modal', params);
  delegateReturnURL(cookie, params.out);
}

function showPasswordDialog(cookie,text) {
  var params = {"in" : text, "out" : null};
  window.openDialog('chrome://dtv/content/password.xul','password','chrome,dependent,centerscreen,modal',params);
  delegateReturnURL(cookie, params.out);
}

function showBugReportDialog(when, report) {
    var params = {"when" : when, "report": report};
    window.openDialog('chrome://dtv/content/bugreport.xul','bugreport','chrome,dependent,centerscreen,modal',params);

    //  var params = {"in" : when, "out" : null};
    //  window.openDialog('chrome://dtv/content/bugreport.xul','password','chrome,dependent,centerscreen,modal',params);
}

function clipboardCopy() {
  clip = Components.classes["@mozilla.org/webshell;1"].getService();
  clip.QueryInterface(Components.interfaces.nsIClipboardCommands);
  clip.copySelection()
}

function clipboardCut() {
  clip = Components.classes["@mozilla.org/webshell;1"].getService();
  clip.QueryInterface(Components.interfaces.nsIClipboardCommands);
  clip.cutSelection()
}

function clipboardPaste() {
  clip = Components.classes["@mozilla.org/webshell;1"].getService();
  clip.QueryInterface(Components.interfaces.nsIClipboardCommands);
  clip.paste()
}

var dtvFFMode = false;
var dtvWillFF = false;
var dtvLastTimeout = 0;

function startFastForward() {
    dump("\n\nFF\n\n");
    if (dtvWillFF) {
    dump("\n\nin FF\n\n");
      dtvFFMode = true;
      eventURL(getCookieFromBrowserId('mainDisplay'),'action:setRate?rate=3.0');
    }
}

function fastForwardMouseDown() {
  dump("\n\nMouse Down\n\n");
  dtvFFMode = false;
  dtvWillFF = true;
  eventURL(getCookieFromBrowserId('mainDisplay'),'action:setRate?rate=1.0');
  dtvLastTimeout = setTimeout(startFastForward,500);
}

function fastForwardMouseUp() {
    dump("\n\nMouse Up\n\n");
    clearTimeout(dtvLastTimeout);
    dtvWillFF = false;
    if (!dtvFFMode) {
      dump("\n\nNext\n\n");
      eventURL(getCookieFromBrowserId('mainDisplay'),'action:videoNext');
    }
    eventURL(getCookieFromBrowserId('mainDisplay'),'action:setRate?rate=1.0');
    dtvFFMode = false;
}

function startRewind() {
    dump("\n\nFF\n\n");
    if (dtvWillFF) {
    dump("\n\nin FF\n\n");
      dtvFFMode = true;
      eventURL(getCookieFromBrowserId('mainDisplay'),'action:setRate?rate=-3.0');
    }
}

function rewindMouseDown() {
  dump("\n\nMouse Down\n\n");
  dtvFFMode = false;
  dtvWillFF = true;
  eventURL(getCookieFromBrowserId('mainDisplay'),'action:setRate?rate=1.0');
  dtvLastTimeout = setTimeout(startRewind,500);
}

function rewindMouseUp() {
    dump("\n\nMouse Up\n\n");
    clearTimeout(dtvLastTimeout);
    dtvWillFF = false;
    if (!dtvFFMode) {
      dump("\n\nNext\n\n");
      eventURL(getCookieFromBrowserId('mainDisplay'),'action:videoPrev');
    }
    eventURL(getCookieFromBrowserId('mainDisplay'),'action:setRate?rate=1.0');
    dtvFFMode = false;
}

function rewindFFMouseOut() {
    dump("\n\nMouse Out\n\n");
    clearTimeout(dtvLastTimeout);
    dtvWillFF = false;
    eventURL(getCookieFromBrowserId('mainDisplay'),'action:setRate?rate=1.0');
    dtvFFMode = false;
}

function openFile() {
    var fp = Components.classes["@mozilla.org/filepicker;1"]
            .createInstance(Components.interfaces.nsIFilePicker);
    fp.init(window, "Open File",
            Components.interfaces.nsIFilePicker.modeGetFile);
    var res = fp.show();
    if (res == Components.interfaces.nsIFilePicker.returnOK){
            eventURL(getCookieFromBrowserId('channelsDisplay'),
            'action:openFile?path=' + escape(fp.file.path));
    }
}

function handleExit() {
    pybridge.quit();
}
