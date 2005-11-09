function onIncrement() {
  var textbox = document.getElementById("textbox");

  contractid = "@test.mozilla.org/simple-test;1?impl=js";
  // dump("Trying contract: " + contractid + "\n");

  var test = Components.classes[contractid].
      createInstance(Components.interfaces.nsISimpleTest);

  textbox.value = test.add(textbox.value, 1);
}

function onDecrement() {
  var textbox = document.getElementById("textbox");

  contractid = "@test.mozilla.org/simple-test-2;1?impl=js";
  var test = Components.classes[contractid].
      createInstance(Components.interfaces.nsISubtract);

  textbox.value = test.subtract(textbox.value, 1);
}

doubleImpl = "js";
function setDoubleImpl(impl) {
    doubleImpl = impl;
}

function onDouble() {
  var textbox = document.getElementById("textbox");

  contractid = "@test.mozilla.org/simple-test-3;1?impl=" + doubleImpl;

  var test = Components.classes[contractid].
      createInstance(Components.interfaces.nsIMultiply);

  textbox.value = test.multiply(textbox.value, 2);
}

function onNewWindow() {
    window.open("chrome://dtv/content/main.xul", "copy", "titlebar=no,chrome");
}

function onLoad() {
    var py = Components.classes["@participatoryculture.org/dtv/pybridge;1"].
    	getService();
    py.QueryInterface(Components.interfaces.pcfIDTVPyBridge); // optional?
    //document.getElementById("channelsDisplay_html").loadURI("http://www.penny-arcade.com");
    //    py.onStartup(document, document.getElementById("channelsDisplay_html"));
    document.myProp = "myVal";
    py.onStartup(document);
}

function testCreate() {
    elt = document.createElement("browser");
    elt.setAttribute("width", "100");
    elt.setAttribute("height", "100");
    elt.setAttribute("src", "http://web.mit.edu");
    main = document.getElementById("main");
    main.appendChild(elt);
}