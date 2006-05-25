const JSBRIDGE_CONTRACTID = "@participatoryculture.org/dtv/jsbridge;1";
const JSBRIDGE_CLASSID    = Components.ID("{421AA951-F53D-4499-B362-E432CAE920F4}");

var pybridge = Components.classes["@participatoryculture.org/dtv/pybridge;1"].
        getService(Components.interfaces.pcfIDTVPyBridge);

function writelog(str) {
    Components.classes['@mozilla.org/consoleservice;1']
	.getService(Components.interfaces.nsIConsoleService)	
	.logStringMessage(str);
}

function LoadFinishedListener(area)
{
    this.area = area;
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
      pybridge.pageLoadFinished(this.area);
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

function WindowObserver() { }

WindowObserver.prototype = {
  observe: function(window, topic, data) {
    if(topic == 'domwindowclosed') {
        var id = window.arguments[0]['id'];
        var out = window.arguments[0]['out'];
        writelog(id + ":" + out);
    }
  }
}

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
    this.windowWatcher = 
        Components.classes["@mozilla.org/embedcomp/window-watcher;1"]
        .getService(Components.interfaces.nsIWindowWatcher);
   /*
    this.windowObserver = new WindowObserver();
    this.windowWatcher.registerNotification(this.windowObserver);
    */
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

  showChoiceDialog: function(id, title, description, defaultLabel, otherLabel) {
    var params = { "id": id, "title": title, "description" : description, 
        "defaultLabel": defaultLabel, "otherLabel": otherLabel, "out" : -1};
    this.window.openDialog("chrome://dtv/content/choice_dialog.xul",
            "choice", "chrome,dependent,centerscreen,modal", params);
  },

  showHTTPAuthDialog: function(id, description, prefillUser, prefillPassword) {
    var params = {"id": id, "text" : description, "prefillUser": prefillUser,
        "prefillPassword": prefillPassword, "out" : null};
    this.window.openDialog("chrome://dtv/content/password.xul",
            "choice", "chrome,dependent,centerscreen,modal", params);
  },

  showBugReportDialog: function(when, report) {
    var params = {"when" : when, "report": report};
    this.window.openDialog("chrome://dtv/content/bugreport.xul",
            "choice", "chrome,dependent,centerscreen,modal", params);
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
    var parent = elt.parentNode;
    parent.removeChild(elt);
    parent.insertBefore(this.createNode(document, xml), next);
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
  }
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
