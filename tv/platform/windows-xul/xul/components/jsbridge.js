const JSBRIDGE_CONTRACTID = "@participatoryculture.org/dtv/jsbridge;1";
const JSBRIDGE_CLASSID    = Components.ID("{421AA951-F53D-4499-B362-E432CAE920F4}");

function writelog(str) {
    Components.classes['@mozilla.org/consoleservice;1']
	.getService(Components.interfaces.nsIConsoleService)	
	.logStringMessage(str);
}

function jsBridge() {
}

jsBridge.prototype = {
    QueryInterface: function(iid) {
	if (iid.equals(Components.interfaces.pcfIDTVJSBridge) ||
	    iid.equals(Components.interfaces.nsISupports))
	    return this;
	throw Components.results.NS_ERROR_NO_INTERFACE;
    },

    xulLoadURI: function(xulElt, uri) {
	xulElt.loadURI(uri);
    },

    xulAddProgressListener: function(xulElt, listener) {
	xulElt.addProgressListener(listener);
    },
    xulRemoveProgressListener: function(xulElt, listener) {
	xulElt.removeProgressListener(listener);
    },

    xulGetContentListener: function(xulElt) {
	return xulElt.docShell.parentURIContentListener;
    },
    xulSetContentListener: function(xulElt, listener) {
	//	xulElt.docShell.parentURIContentListener = listener;
	ds = xulElt.docShell;
	ds = ds.QueryInterface(Components.interfaces.nsIDocShell);
	ds.parentURIContentListener = listener;
    },

    xulGetContentWindow: function(xulElt) {
	return xulElt.contentWindow;
    },

    xulRemoveAllChildren: function(xulElt) {
        writelog("xulRemoveAllChildren");
        while (xulElt.hasChildNodes()) {
            writelog("removing a child");
            xulElt.removeChild(xulElt.firstChild);
            writelog("child removed");
        }
        writelog("xulRemoveAllChildren done");
    },

    xulAddElementAtEnd: function(xulElt, xml, id) {
	elt = xulElt.contentDocument.getElementById(id);
	r = xulElt.contentDocument.createRange();
	r.selectNode(elt);
	frag = r.createContextualFragment(xml);
	elt.insertBefore(frag, null);
    },
    xulAddElementBefore: function(xulElt, xml, id) {
	elt = xulElt.contentDocument.getElementById(id);
	r = xulElt.contentDocument.createRange();
	r.selectNode(elt);
	frag = r.createContextualFragment(xml);
	elt.parentNode.insertBefore(frag, elt);
    },
    xulRemoveElement: function(xulElt, id) {
	elt = xulElt.contentDocument.getElementById(id);
	elt.parentNode.removeChild(elt);
    },
    xulChangeElement: function(xulElt, id, xml) {
	elt = xulElt.contentDocument.getElementById(id);
	r = xulElt.contentDocument.createRange();
	r.selectNode(elt);
	frag = r.createContextualFragment(xml);
	elt.parentNode.replaceChild(frag, elt);
    },
    xulHideElement: function(xulElt, id) {
	elt = xulElt.contentDocument.getElementById(id);
	elt.style.display = 'none';
    },
    xulShowElement: function(xulElt, id) {
	elt = xulElt.contentDocument.getElementById(id);
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
