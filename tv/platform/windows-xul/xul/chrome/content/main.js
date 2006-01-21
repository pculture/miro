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

function onLoad() {
    jsdump("onLoad running.");
    var qo = new quitObserver();
    var py = Components.classes["@participatoryculture.org/dtv/pybridge;1"].
    	getService();
    py.QueryInterface(Components.interfaces.pcfIDTVPyBridge); // necessary?
    py.onStartup(document);
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

//FIXME: Duplicated from dynamic.js
function eventURL(cookie, url) {
  var py = Components.classes["@participatoryculture.org/dtv/pybridge;1"].
        getService();
  py.QueryInterface(Components.interfaces.pcfIDTVPyBridge); // necessary?
  py.eventURL(cookie, url);
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
