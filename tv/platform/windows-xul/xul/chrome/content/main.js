/*****************************************************************************
 Watching for application exit
 *****************************************************************************/

var pybridge = Components.classes["@participatoryculture.org/dtv/pybridge;1"].
                getService(Components.interfaces.pcfIDTVPyBridge);
var jsbridge = Components.classes["@participatoryculture.org/dtv/jsbridge;1"].
                getService(Components.interfaces.pcfIDTVJSBridge);
var vlcrenderer = Components.classes["@participatoryculture.org/dtv/vlc-renderer;1"].
                getService(Components.interfaces.pcfIDTVVLCRenderer);

var minimizer = Components.classes["@participatoryculture.org/dtv/minimize;1"].
                getService(Components.interfaces.pcfIDTVMinimize);

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

function getPageCoords (element) {
  var coords = {x : 0, y : 0};
  while (element) {
    coords.x += element.offsetLeft;
    coords.y += element.offsetTop;
    element = element.offsetParent;
  }
  return coords;
}

/*****************************************************************************
 Volume Knob 
 *****************************************************************************/

var VOLUME_SLIDER_LEFT = 25;
var VOLUME_SLIDER_RIGHT = 98;
var VOLUME_SLIDER_WIDTH = VOLUME_SLIDER_RIGHT - VOLUME_SLIDER_LEFT;
var VOLUME_KNOB_OFFSET = 6;


function translateToVolumeX(event) 
{
  var bottomVolume = document.getElementById("volume");
  var slider = document.getElementById("knob");
  var x = event.screenX - bottomVolume.boxObject.screenX;
  x = x - VOLUME_KNOB_OFFSET;
  return Math.max(VOLUME_SLIDER_LEFT, Math.min(VOLUME_SLIDER_RIGHT, x));
}

function volumeKnobDown(event) {
  var slider = document.getElementById("knob");
  slider.beingDragged = true;
  slider.left = translateToVolumeX(event);
}

function doVol() {
  var slider = document.getElementById("knob");
  var x = slider.left;
  pybridge.setVolume((x - VOLUME_SLIDER_LEFT) / VOLUME_SLIDER_WIDTH);
}

function volumeKnobOut(event) {
  var slider = document.getElementById("knob");
  if(event.relatedTarget.id != 'volume' && 
        event.relatedTarget.id != "knob" &&
        slider.beingDragged) {
    doVol();
    slider.beingDragged = false;
  }
}

function volumeKnobMove(event) {
  var slider = document.getElementById("knob");
  if (slider.beingDragged) {
    var x = translateToVolumeX(event);
    slider.left = x;
    doVol();
  }
}

function volumeKnobUp(event) {
  var slider = document.getElementById("knob");
  if (slider.beingDragged) {
    doVol();
    slider.beingDragged = false;
  }
}

/*****************************************************************************
 Video Progress Slider
 *****************************************************************************/

var PROGRESS_SLIDER_LEFT = 61;
var PROGRESS_SLIDER_RIGHT = 204;
var PROGRESS_SLIDER_WIDTH = PROGRESS_SLIDER_RIGHT - PROGRESS_SLIDER_LEFT;
var PROGRESS_KNOB_OFFSET = 2;


function translateToProgressX(event) 
{
  var bottomProgress = document.getElementById("bottom-progress");
  var x = event.screenX - bottomProgress.boxObject.screenX;
  x = x - PROGRESS_KNOB_OFFSET;
  return Math.max(PROGRESS_SLIDER_LEFT, Math.min(PROGRESS_SLIDER_RIGHT, x));
}

var videoWasPlaying = false;

function videoProgressDown(event) {
  var slider = document.getElementById("progress-slider");
  slider.beingDragged = true;
  slider.left = translateToProgressX(event);
  videoWasPlaying = vlc.playlist.isPlaying;
  if(videoWasPlaying) vlcrenderer.pauseForDrag();
}

function doSeek() {
  var slider = document.getElementById("progress-slider");
  var x = slider.left;
  var fractionDone = (x - PROGRESS_SLIDER_LEFT) / PROGRESS_SLIDER_WIDTH;
  var totalTime = vlc.input.length;
  var seekTime = Math.round(totalTime * fractionDone);
  vlc.input.time = seekTime;
  if(videoWasPlaying) vlcrenderer.play();
  slider.beingDragged = false;
}

function videoProgressOut(event) {
  var slider = document.getElementById("progress-slider");
  if(event.relatedTarget.id != 'bottom-progress' && 
        event.relatedTarget.id != "progress-text" &&
        event.relatedTarget.id != "progress-slider" &&
        slider.beingDragged) {
    doSeek();
  }
}

function videoProgressMove(event) {
  var slider = document.getElementById("progress-slider");
  if (slider.beingDragged) {
    var x = translateToProgressX(event);
    slider.left = x;
    var fractionDone = (x - PROGRESS_SLIDER_LEFT) / PROGRESS_SLIDER_WIDTH;
    var totalTime = vlc.input.length;
    var seekTime = Math.round(totalTime * fractionDone);
    jsbridge.setSliderText(seekTime);
  }
}

function videoProgressUp(event) {
  var slider = document.getElementById("progress-slider");
  if (slider.beingDragged) {
    doSeek();
  }
}

/*****************************************************************************
 Main functions
 *****************************************************************************/

var vlc = null;

function buttonIsActive(buttonId) {
    var elt = document.getElementById(buttonId);
    return (elt.className.indexOf('inactive') == -1);
}

function onLoad() {
    jsdump("onLoad running.");

    pybridge.addMenubar(document);

    // Start watching for application exit.
    // NEEDS: should this move out of onLoad() and be global?
    var qo = new quitObserver();

    // Bring up Python environment.
    pybridge.onStartup(window, document);

    // Get a reference te tho vlc plugin
    var videoBrowser = document.getElementById("mainDisplayVideo");
    vlc = videoBrowser.contentDocument.getElementById("video1");

    setupHandlers();
    jsdump("onload done");
}

function setSearchEngine(engine) {
    var searchIcon = document.getElementById("search-icon");
    searchIcon.setAttribute("src",'images/search_icon_' + engine + '.png');
}

// SeekButton is used for both the rewind/previous and fast forward/next
// buttons.  If clicked, they skip to the next/previous button.  If held downl
// they do a fast forward/rewind.  direction should be 1 for forward, -1 for
// backward.
function setupSeekButton(direction, buttonId) {
  var didSeek = false;
  var timeoutId = null;
  var element = document.getElementById(buttonId);
  var handleTimeout = function() {
    var seekAmount = direction * 3 - 0.5;
    // we want to seek at 3X speed in our current direction (-1 for back, 1
    // for forward).  We also need to take into account that we've played back
    // 0.5 seconds worth of video before the timeout.
    vlc.input.time = vlc.input.time + seekAmount * 1000;
    didSeek = true;
    timeoutId = setTimeout(handleTimeout, 500);
  }
  element.onmousedown = function() { 
    didSeek = false;
    timeoutId = setTimeout(handleTimeout, 500);
    return false;
  }
  element.onmouseup = function() { 
    if(timeoutId) {
        clearTimeout(timeoutId);
        timeoutId = null;
    }
    if(!didSeek) pybridge.skip(direction);
    return false;
  }
  element.onmouseout = function() { 
    if(timeoutId) {
        clearTimeout(timeoutId);
        timeoutId = null;
    }
    return false;
  }
}

function setupHandlers() {
    var knob = document.getElementById("volume");
    knob.onmousemove = volumeKnobMove;
    knob.onmousedown = volumeKnobDown;
    knob.onmouseout = volumeKnobOut;
    knob.onmouseup = volumeKnobUp;

    // Set up listeners for the progress slider
    var progress = document.getElementById("bottom-progress");
    progress.onmousedown = videoProgressDown;
    progress.onmouseout = videoProgressOut;
    progress.onmousemove = videoProgressMove;
    progress.onmouseup = videoProgressUp;

    document.getElementById("bottom-buttons-play").onclick = function() {
        if(buttonIsActive("bottom-buttons-play")) pybridge.playPause();
    };
    document.getElementById("bottom-buttons-stop").onclick = function() {
        if(buttonIsActive("bottom-buttons-stop")) pybridge.stop();
    };
    document.getElementById("bottom-buttons-fullscreen").onclick = function() { 
        if(buttonIsActive("bottom-buttons-fullscreen")) jsbridge.toggleFullscreen();
    }
    setupSeekButton(-1, "bottom-buttons-previous");
    setupSeekButton(1, "bottom-buttons-next");
}

function onClose()
{
    pybridge.handleCloseButton();
    return false;
}

function minimizeOrRestore()
{
    minimizer.minimizeOrRestore();
    return false;
}

function onUnload() {
    pybridge.printOut("onUnload"); 
    if (vlc.playlist.items.count > 0) { 
        vlc.playlist.stop(); 
    } 
    closeApp();
    minimizer.delTrayIcon();
}

function jsdump(str) {
    Components.classes['@mozilla.org/consoleservice;1']
	.getService(Components.interfaces.nsIConsoleService)	
	.logStringMessage(str);
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

function searchUpForElementWithAttribute(element, attributeName) {
    while (1) {
	if (element.nodeType == 1 && element.getAttribute(attributeName)) {
            return element;
	}
	if (element.parentNode) {
	    element = element.parentNode;
        } else {
            return null;
        }
    }

    // Satisfy Mozilla that the function always returns a
    // value. Otherwise, we get an error if strict mode is enabled,
    // ultimately preventing us from getting the state change event
    // indicating that the load succeeded.
    return null;
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

function onFullscreenActivate() {
    var fullscreenButton = document.getElementById("bottom-buttons-fullscreen");
    if(fullscreenButton.className.indexOf('-inactive') == -1) {
      jsbridge.toggleFullscreen();
    }
}

function getClipboardCommands() {
  // This is a really strange way to get an nsIClipboardCommands object, but
  // it's the only way I could make things work -- Ben
  var req = window.QueryInterface(Components.interfaces.nsIInterfaceRequestor);
  var nav = req.getInterface(Components.interfaces.nsIWebNavigation);
  return nav.QueryInterface(Components.interfaces.nsIClipboardCommands);
}

function clipboardCopy() {
  getClipboardCommands().copySelection();
}

function clipboardCut() {
  getClipboardCommands().cutSelection();
}

function clipboardPaste() {
  getClipboardCommands().paste();
}

function openFile() {
    var fp = Components.classes["@mozilla.org/filepicker;1"]
            .createInstance(Components.interfaces.nsIFilePicker);
    var openMenuItem = document.getElementById('menuitem-open');
    fp.init(window, openMenuItem.getAttribute('label'),
        Components.interfaces.nsIFilePicker.modeOpen);
    var res = fp.show();
    if (res == Components.interfaces.nsIFilePicker.returnOK){
        pybridge.openFile(fp.file.path);
    }
}

function handleExit() {
    pybridge.quit();
}

/* This is where the search on chrome events come to hang out */
function onSearchKeyDown(event) {
  if(event.keyCode == 13) {
    /* hack to get engine from the UI */
    var searchIcon = document.getElementById("search-icon");
    var iconURL = searchIcon.getAttribute("src")
    var name = iconURL.substring(19, iconURL.length - 4);

    pybridge.performSearch(name, event.target.value);
  }
}

/* key presses in the main window.  This is a hack to workaround the fact that
 * XUL doesn't fire events for a couple keys (Enter, Space)
 */
function runCommand(commandId) {
  var command = document.getElementById(commandId);
  if(command) command.doCommand();
}

function runMenuItemCommand(menuitemid) {
  var menuitem = document.getElementById(menuitemid);
  if(menuitem.getAttribute('disabled')) return;
  runCommand(menuitem.getAttribute('command'))
}
function onKeyDown(event) {
  if(event.keyCode == 13 && event.altKey) { 
    // Alt+Enter
    runMenuItemCommand('menuitem-fullscreen');
  } else if(event.keyCode == 32) {
    // Space
    runMenuItemCommand('menuitem-playpausevideo');
  } else if((event.keyCode == 8 && event.ctrlKey) || event.keyCode == 46) {
    // Ctrl-Backspace or Delete
    runCommand("RemoveCurrentSelection");
  } else if(event.keyCode >= 37 && event.keyCode <= 40) {
    // Arrow keys
    pybridge.handleKeyPress(event.keyCode, event.shiftKey, event.ctrlKey);
  } else if(event.keyCode == 27) {
    // Escape
    jsbridge.leaveFullscreen();
  } 
}
