/*****************************************************************************
 Watching for 'load completed' events                           
 *****************************************************************************/

const NOTIFY_STATE_DOCUMENT =
    Components.interfaces.nsIWebProgress.NOTIFY_STATE_DOCUMENT;
const STATE_IS_DOCUMENT =
    Components.interfaces.nsIWebProgressListener.STATE_IS_DOCUMENT;
const STATE_STOP =
    Components.interfaces.nsIWebProgressListener.STATE_STOP;

function Listener(display) {
    this.display = display;
}

Listener.prototype = {
    QueryInterface: function(aIID) {
        if (aIID.equals(Components.interfaces.nsIWebProgressListener) ||
            aIID.equals(Components.interfaces.nsISupportsWeakReference) ||
            aIID.equals(Components.interfaces.nsISupports))
            return this;
        throw Components.results.NS_NOINTERFACE;
    },

    onStateChange: function(aProgress,aRequest,aFlag,aStatus) {
        if ((aFlag & STATE_STOP) && (aFlag && STATE_IS_DOCUMENT)) {
            aRequest.QueryInterface(Components.interfaces.nsIChannel);
            /*
            alert("Finished loading for " + this.display +
                  "!\n"+aRequest.URI.spec);
            */

            /* Commented out because nothing needs this anymore.

            Old notes on the effect:

            "Called when the main window display with the given name
            (the <browser /> with the given id) finishes loading a
            document. The URL of the document is supplied too, as a
            string. This would generally be called once per load,
            but if the load contains subdocuments such as <iframes>,
            it might get called for each of them too.
  
            NEEDS: Look into using the DOMWindow attribute on
            nsIWebProgress to ensure we receive only the load event
            from the top-level <browser />.  Failing that, security
            audit to make sure that malicious JS can't figure out the
            URL we're trying to load, generate a spurious
            load-finished message, and somehow do something nasty (the
            best I can do is that if we think the load has finished
            early, we might somehow start loading the next page
            without waiting for the old load to finish, possibly
            causing some of the mutators meant for the old page to
            land on the new page?  tenuous.)"

            // Chuck it up into Python.
            var py =
                Components.classes["@participatoryculture.org/dtv/pybridge;1"].
                getService();
            py.QueryInterface(Components.interfaces.pcfIDTVPyBridge);
            py.displayFinishedLoading(this.display, aRequest.URI.spec);
            */
        }
    },

    onLocationChange: function(a,b,c) {},
    onProgressChange: function(a,b,c,d,e,f) {},
    onStatusChange: function(a,b,c,d) {},
    onSecurityChange: function(a,b,c) {},
    onLinkIconAvailable: function(a) {}
}

var channelsListener = new Listener("channelsDisplay");
var mainListener = new Listener("mainDisplay");

/*****************************************************************************
 Watching for application exit
 *****************************************************************************/

function quitObserver()
{
  this.register();
}

quitObserver.prototype = {
  observe: function(subject, topic, data) {
    
    var py = Components.classes["@participatoryculture.org/dtv/pybridge;1"].
    	getService();
    py.QueryInterface(Components.interfaces.pcfIDTVPyBridge); // necessary?
    py.onShutdown();
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

/*****************************************************************************
 Communication with the server
 *****************************************************************************/

var serverPort = null;

function openServerCommunications() {
    // Figure out what port the server's on. We need that for the hook
    // we use to execute JS, and for the implementation of actionURL
    // for context menus, below.
    var py = Components.classes["@participatoryculture.org/dtv/pybridge;1"].
    	getService();
    py.QueryInterface(Components.interfaces.pcfIDTVPyBridge); // necessary?
    jsdump("getting server port");
    serverPort = py.getServerPort();
    jsdump("got server port");
 
    // Start listening for mesages from the server telling us to do
    // Javascript work. (Usually this would be location switching in a
    // display.)
    var req = new XMLHttpRequest();
    req.multipart = true;
    req.open("GET", "http://127.0.0.1:" + serverPort + "/dtv/xuljs", true);
    req.onload = processServerMessage;
    req.send(null);
    jsdump("started xuljs pump");
}

// Whatever the server gives us, we put in our mouth.
// NEEDS: maybe a security cookie, obtained though the pybridge
function processServerMessage(event) {
    eval(event.target.responseText);
}

// This is usually the only function the server calls
function navigateDisplay(displayName, url) {
  try {
    disp = document.getElementById(displayName);
    disp.contentDocument.location = url;
  } catch (e) {
    jsdump("Could not access display "+displayName);
  }
}

// If you have a cookie, you can simulate an event from here.
function eventURL(cookie, url) {
    url = "http://127.0.0.1:" + serverPort + "/dtv/action/" +
        cookie + "?" + url;
    var req = new XMLHttpRequest();
    req.open("GET", url, true);
    req.send(null);
}


// Used to send return values back to UIBackendDelegate
function delegateReturnURL(cookie, data) {
    url = "http://127.0.0.1:" + serverPort + "/dtv/delegateresult/" +
        cookie + "?" + data;
    var req = new XMLHttpRequest();
    req.open("GET", url, true);
    req.send(null);
}

/*****************************************************************************
 Volume Knob 
 *****************************************************************************/

var knobDragStart = 0;
var knobPos = 105;

function setVolume(percent) {
    /*  jsdump("Volume now at "+percent); */
  eventURL(getCookieFromBrowserId('mainDisplay'),'action:setVolume?level='+percent);
}

function volumeKnobMove(event) {
  if (knobDragStart > 0) {
    var left = 15;
    var right= 105;
    var knob = document.getElementById("knob");
    knobPos += event.clientX - knobDragStart;
    if (knobPos < left) knobPos = left;
    if (knobPos > right) knobPos = right;
    knobDragStart = event.clientX;
    knob.style.left = knobPos +"px";
    setVolume((knobPos - left)/(right-left));
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
 Main functions
 *****************************************************************************/

function onLoad() {
    jsdump("onLoad running.");

    // Start watching for application exit.
    // NEEDS: should this move out of onLoad() and be global?
    var qo = new quitObserver();

    // Find Python.
    var py = Components.classes["@participatoryculture.org/dtv/pybridge;1"].
    	getService();
    py.QueryInterface(Components.interfaces.pcfIDTVPyBridge); // necessary?

    // Bring up Python environment.
    py.onStartup(document);

    // Register the listeners that let us track the status of the
    // browser areas.
    jsdump("registering listeners.");
    var channelsDisplay = document.getElementById("channelsDisplay");
    channelsDisplay.webProgress.
        addProgressListener(channelsListener, NOTIFY_STATE_DOCUMENT);
    var mainDisplay = document.getElementById("mainDisplay");
    mainDisplay.webProgress.
        addProgressListener(mainListener, NOTIFY_STATE_DOCUMENT);
    jsdump("OK so far.");
        
    // Start the app.
    jsdump("booting app.");
    py.bootApp(document);

    // Start the server. For some reason it cause hangs if it's started
    // before the app.
    openServerCommunications();

    // Set up listeners for the volume knobby
    var knob = document.getElementById("volume");
    knob.onmousemove = volumeKnobMove;
    knob.onmousedown = volumeKnobDown;
    window.onmouseup = volumeKnobUp;
    knob.onmouseout = volumeKnobOut;
}

function onUnload() {
    jsdump("onUnload running.");

    // Unregister browser status listeners to avoid leaks.
    var channelsDisplay = document.getElementById("channelsDisplay");
    channelsDisplay.webProgress.
        removeProgressListener(channelsListener);
    var mainDisplay = document.getElementById("mainDisplay");
    mainDisplay.webProgress.
        removeProgressListener(mainListener);

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
    var py = Components.classes["@participatoryculture.org/dtv/pybridge;1"].
    	getService();
    py.QueryInterface(Components.interfaces.pcfIDTVPyBridge);
    py.addChannel(url);
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
       getService();
  startup.QueryInterface(Components.interfaces.nsIAppStartup); // necessary?
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
 if (window.outerHeight < 200) {
    window.outerHeight=200;
  }
  return true;  
}

function showIsScrapeAllowedDialog(cookie,text) {
  var params = {"in" : text, "out" : null};
  window.openDialog('chrome://dtv/content/canscrape.xul','canscrape','chrome,dependent,centerscreen,modal',params);
  delegateReturnURL(cookie, params.out);
}