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

var PROGRESS_SLIDER_LEFT = 61;
var PROGRESS_SLIDER_RIGHT = 204;
var PROGRESS_SLIDER_WIDTH = PROGRESS_SLIDER_RIGHT - PROGRESS_SLIDER_LEFT;


function translateToProgressX(pageX) 
{
  var progressSliderPageCoords = getPageCoords(
        document.getElementById("progress"));
  var x = pageX - progressSliderPageCoords['x'];
  return Math.max(PROGRESS_SLIDER_LEFT, Math.min(PROGRESS_SLIDER_RIGHT, x));
}

function videoProgressDown(event) {
  var slider = document.getElementById("progress-slider");
  slider.beingDragged = true;
}

function videoProgressOut(event) {
  if(event.target.id == 'progress' && 
        event.relatedTarget.id != "progress-text" &&
        event.relatedTarget.id != "progress-slider") {
    var slider = document.getElementById("progress-slider");
    slider.beingDragged = false;
  }
}

function videoProgressMove(event) {
  //jsdump("Video progress move");
  var slider = document.getElementById("progress-slider");
  if (slider.beingDragged) {
    slider.style.left = translateToProgressX(event.pageX) + 'px';
  }
}

function videoProgressUp(event) {
  var slider = document.getElementById("progress-slider");
  if (slider.beingDragged) {
    var x = translateToProgressX(event.pageX);
    var fractionDone = (x - PROGRESS_SLIDER_LEFT) / PROGRESS_SLIDER_WIDTH;
    var totalTime = vlc.get_length();
    var seekTime = Math.round(totalTime * fractionDone);
    vlc.seek(seekTime, 0);
    slider.beingDragged = false;
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
    vlc.seek(seekAmount, true);
    didSeek = true;
    timeoutId = setTimeout(handleTimeout, 500);
  }
  element.onmousedown = function() { 
    if(!buttonIsActive(buttonId)) return false;
    didSeek = false;
    timeoutId = setTimeout(handleTimeout, 500);
    return false;
  }
  element.onmouseup = function() { 
    if(!buttonIsActive(buttonId)) return false;
    if(timeoutId) {
        clearTimeout(timeoutId);
        timeoutId = null;
    }
    if(!didSeek) pybridge.skip(direction);
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
    var progress = document.getElementById("progress");
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
        if(buttonIsActive("bottom-buttons-fullscreen")) vlc.fullscreen();
    };
    setupSeekButton(-1, "bottom-buttons-previous");
    setupSeekButton(1, "bottom-buttons-next");
}

function onClose()
{
   vlc.stop();
   closeApp();
}

function onUnload() {
    jsdump("onUnload running.");
    vlc.stop();
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

function xulcontexthandler(browserID, event) {
  var itemsAdded = 0;
  var menu = getContextClickMenu(event.target);
  var popup = document.getElementById('contextPopup');
  if(menu == '') return false;
  while (popup.firstChild) {
    popup.removeChild(popup.firstChild);
  }
  menu = menu.split("\n");
  while (menu.length > 0) {
    var line = menu.shift().split('|');
    if (line.length > 1) {
      var newItem = document.createElement('menuitem');
      newItem.setAttribute("label", line[1]);
      newItem.setAttribute("oncommand", 
      "pybridge.loadURLInBrowser('" + browserID + "', '" + line[0] + "');");
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

function openFile() {
    var fp = Components.classes["@mozilla.org/filepicker;1"]
            .createInstance(Components.interfaces.nsIFilePicker);
    fp.init(window, "Open File",
            Components.interfaces.nsIFilePicker.modeGetFile);
    var res = fp.show();
    if (res == Components.interfaces.nsIFilePicker.returnOK){
        pybridge.openFile(fp.file.path);
    }
}

function handleExit() {
    vlc.stop();
    pybridge.quit();
}
