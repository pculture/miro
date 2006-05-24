const JSBRIDGE_CONTRACTID = "@participatoryculture.org/dtv/jsbridge;1";
const JSBRIDGE_CLASSID    = Components.ID("{421AA951-F53D-4499-B362-E432CAE920F4}");

var pybridge = Components.classes["@participatoryculture.org/dtv/pybridge;1"].
        getService(Components.interfaces.pcfIDTVPyBridge);

function writelog(str) {
    Components.classes['@mozilla.org/consoleservice;1']
	.getService(Components.interfaces.nsIConsoleService)	
	.logStringMessage(str);
}

function jsBridge() {
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

jsBridge.prototype = {
    QueryInterface: function(iid) {
	if (iid.equals(Components.interfaces.pcfIDTVJSBridge) ||
	    iid.equals(Components.interfaces.nsISupports))
	    return this;
	throw Components.results.NS_ERROR_NO_INTERFACE;
    },

    init: function(mainWindowDocument) {
        this.mainWindowDocument = mainWindowDocument;
        this.initBrowser("mainDisplay");
        this.initBrowser("videoInfoDisplay");
        this.initBrowser("channelsDisplay");
    },

    closeWindow: function() {
        var wwatchContractID = "@mozilla.org/embedcomp/window-watcher;1";
        var wwatch = Components.classes[wwatchContractID]
                .getService(Components.interfaces.nsIWindowWatcher);
        var window = wwatch.getWindowByName("DemocracyPlayer", null);
        window.close();
    },

    initBrowser: function(area) {
        var browser = this.mainWindowDocument.getElementById(area);
        var listener = new LoadFinishedListener(area);
        browser.addProgressListener(listener);
        progressListeners[area] = listener;
    },

    xulNavigateDisplay: function(area, uri) {
        var browser = this.mainWindowDocument.getElementById(area);
        browser.contentDocument.location = uri;
    },

    copyTextToClipboard: function(text) {
        var gClipboardHelper = Components.classes["@mozilla.org/widget/clipboardhelper;1"].getService(Components.interfaces.nsIClipboardHelper);
          gClipboardHelper.copyString(text);
    },

    getDocument: function(area) {
        var browser = this.mainWindowDocument.getElementById(area);
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
