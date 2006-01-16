function onLoad() {
    jsdump("onLoad running.");
    var py = Components.classes["@participatoryculture.org/dtv/pybridge;1"].
    	getService();
    py.QueryInterface(Components.interfaces.pcfIDTVPyBridge); // necessary?
    py.onStartup(document);
}

/*
function testCreate() {
    elt = document.createElement("browser");
    elt.setAttribute("width", "100");
    elt.setAttribute("height", "100");
    elt.setAttribute("src", "http://web.mit.edu");
    main = document.getElementById("main");
    main.appendChild(elt);
}
*/

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
