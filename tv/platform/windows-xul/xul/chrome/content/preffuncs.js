function openPrefServerCommunications() {
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
    req.open("GET", "http://127.0.0.1:" + serverPort + "/dtv/prefjs", true);
    req.onload = processPrefServerMessage;
    req.send(null);
    jsdump("started prefs pump");
}
function processPrefServerMessage(event) {
    eval(event.target.responseText);
}
function finalizeChanges() {
 var limit = (document.getElementById("limitupstream").checked);
 if (limit) {
     maxUpstreamChange();
 }
 var minspace = (document.getElementById("hasminspace").checked);
 if (minspace) {
     minSpaceChange();
 }
}
function setRunAtStartup(value) {
    document.getElementById("runonstartup").checked = value;
}
function runOnStartupChange() {
  if (document.getElementById("runonstartup").checked)
      eventURL(window.arguments[0],'action:setRunAtStartup?value=1');
  else
      eventURL(window.arguments[0],'action:setRunAtStartup?value=0');
}
function setCheckEvery(minutes) {
  var check = document.getElementById("checkevery");
  if (minutes == 30)
      check.value = "30";
  else 
      if (minutes == 60)
          check.value = "60";
      else
          check.value = "never";
}
function checkEveryChange(minutes) {
   eventURL(window.arguments[0],'action:setCheckEvery?value=' + minutes.toString());
}
function setMaxUpstream(max) {
    document.getElementById("maxupstream").value = max;
}
function setLimitUpstream(limit) {
    document.getElementById("limitupstream").checked = limit;
    if (!limit) {
        ele = document.getElementById("maxupstream");
        ele.value = '';
        ele.disabled = true;
    }
}
function limitUpstreamChange() {
  var ret = (document.getElementById("limitupstream").checked);
  var textbox = document.getElementById("maxupstream");
  textbox.disabled = !ret;
  if (ret) {
    textbox.value = "16";
    eventURL(window.arguments[0],'action:setLimitUpstream?value=1');
  } else {
    textbox.value = "";
    eventURL(window.arguments[0],'action:setLimitUpstream?value=0');
  }
}
function maxUpstreamChange() {
  var textbox = document.getElementById("maxupstream");
  var value = parseInt(textbox.value);
  if ((value == 0) || (isNaN(value))) {
    value = 1;
    textbox.value="1";
  } else {
    textbox.value=value;
  }
  jsdump("Setting max upstream to "+value);
  eventURL(window.arguments[0],'action:setMaxUpstream?value=' + value.toString());
}
function setMinDiskSpace(min) {
    document.getElementById("minspace").value = min;
}
function setHasMinDiskSpace(hasit) {
    document.getElementById("hasminspace").checked = hasit;
    if (!hasit) {
       ele = document.getElementById("minspace");
       ele.value = '';
       ele.disabled = true;
    }
}
function hasMinSpaceChange() {
  var ret = (document.getElementById("hasminspace").checked);
  var textbox = document.getElementById("minspace");
  textbox.disabled = !ret;
  if (ret) {
    textbox.value = "1";
    eventURL(window.arguments[0],'action:setPreserveDiskSpace?value=1');
  } else {
    textbox.value = "";
    eventURL(window.arguments[0],'action:setPreserveDiskSpace?value=0');
  }
}
function minSpaceChange() {
  var textbox = document.getElementById("minspace");
  var value = parseInt(textbox.value);
  if ((value == 0) || (isNaN(value))) {
    value = 1;
    textbox.value="1";
  } else {
    textbox.value=value;
  }
  eventURL(window.arguments[0],'action:setMinDiskSpace?value=' + value.toString());
}
function setExpire(days) {
  var check = document.getElementById("expiration");
      if (days == "1")
          check.value = "1";
      else
      if (days == "3")
          check.value = "3";
      else
      if (days == "6")
          check.value = "6";
      else
      if (days == "10")
          check.value = "10";
      else
      if (days == "30")
          check.value = "30";
      else

          check.value = "never";
}
function expirationChange(days) {
    eventURL(window.arguments[0],'action:setDefaultExpiration?value=' + days.toString());
}
