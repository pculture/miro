function openBugReportWindow() {
  var py = Components.classes["@participatoryculture.org/dtv/pybridge;1"].
        getService(Components.interfaces.pcfIDTVPyBridge);
  py.openURL("https://develop.participatoryculture.org/projects/democracy/newticket");
}

function updateLabel() {
  var elt = document.getElementById("log");
  var textIn = window.arguments[0]["report"];
  elt.setAttribute("value", textIn);
}

function updateLabelStartupError() {
  var py = Components.classes["@participatoryculture.org/dtv/pybridge;1"].
        getService(Components.interfaces.pcfIDTVPyBridge);
  var elt = document.getElementById("log");
  elt.setAttribute("value", py.getStartupError());
}

function copyLogToClipboard() {
  var log = document.getElementById("log");
  var clipboard = Components.classes["@mozilla.org/widget/clipboardhelper;1"]
      .getService(Components.interfaces.nsIClipboardHelper);
  clipboard.copyString(log.value);
}
