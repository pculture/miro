<script type="text/javascript">
<!-- // Protect from our XML parser, which doesn't know to protect <script>

///////////////////////////////////////////////////////////////////////////////
//// Machinery related to dynamic updates in full XUL mode                 ////
///////////////////////////////////////////////////////////////////////////////

function handleUpdate(event) {
    r = event.target;
    eval(r.responseText);
}

function beginUpdates() {
    if (getDTVPlatform() == 'xul') {
        // Under XUL, open a 'push' HTTP connection to the controller to
        // receive updates. This avoids calling across the Python/XPCOM
        // boundary, which causes deadlocks sometimes for poorly understood
        // reasons.
        //        port = getServerPort();
        var cookie = getEventCookie();
        //        url = "http://127.0.0.1:" + port + "/dtv/mutators/" + cookie;
        var url = "/dtv/mutators/" + cookie;

        var xr = new XMLHttpRequest();
        /*
        netscape.security.PrivilegeManager.
            enablePrivilege("UniversalBrowserRead");
        */
        xr.multipart = true;
        xr.open("GET", url, true);
        xr.onload = handleUpdate;
        xr.send(null);
    }
}
     
///////////////////////////////////////////////////////////////////////////////
//// For use on your page                                                  ////
///////////////////////////////////////////////////////////////////////////////

function jsdump(str) {
    Components.classes['@mozilla.org/consoleservice;1']
	.getService(Components.interfaces.nsIConsoleService)	
	.logStringMessage(str);
}

function getEventCookie() {
    var elt = document.getElementsByTagName("html")[0];
    return elt.getAttribute('eventCookie');
}

function getDTVPlatform() {
    var elt = document.getElementsByTagName("html")[0];
    return elt.getAttribute('dtvPlatform');
}

/*
// NEEDS: eliminate! just use relative URLs
function getServerPort() {
    var elt = document.getElementsByTagName("html")[0];
    return elt.getAttribute('serverPort');
}
*/

// For calling from page Javascript: Cause a URL to be loaded. The
// assumption is that the application will notice, abort the load, and
// take some action based on the URL.
function eventURL(url) {
    if (getDTVPlatform() == 'xul') {
    	// XUL strategy: async HTTP request to our in-process HTTP
        // server.  Since it falls under the "same origin" security
        // model exemption, no need for complicated preferences
        // shenanigans -- what a nice day!
        //        url = "http://127.0.0.1:" + getServerPort() + "/dtv/action/" +
        //            getEventCookie() + "?" + url; NEEDS: remove
        url = "/dtv/action/" + getEventCookie() + "?" + url;
    	var req = new XMLHttpRequest();
        req.open("GET", url, true);
        req.send(null);
        // NEEDS: there is another copy of this in main.js.
    }
    else if (typeof(window.frontend) == 'undefined') {
	// Generic strategy: trigger a load, and hope the application
	// catches it and cancels it without creating a race
	// condition.
	document.location.href = url;
    } else {
	// OS X WebKit (KHTML) strategy: pass in an Objective C object
	// through the window object and call a method on it.
	window.frontend.eventURL(url);
    }

    return false;
}    

function recommendItem(title, url, feedURL) {
    body = "You should check out this video:\n";
    body = body + url + "\n\n";
    body = body + "I found it while using DTV, which you can download here:\n";
    body = body + "http://www.dtvmac.com\n\n";
    body = body + "The video was on this channel (click 'subscribe' in DTV and paste in this address):\n"
    body = body + feedURL + "\n\n"
    
    url = 'mailto:';
    url = url + "?subject=" + URLencode(title);
    url = url + "&body=" + URLencode(body);
    eventURL(url);
    
    return false;
}

// Change a view's filter. The filter controls which records are
// included and which are not. (You can only do this if, when the view
// was declared in the page header, it was given an initial filter
// with the t:filter tag.) viewName is the name of the view whose
// filter should be changed, as declared in the t:view tag. fieldKey
// is the property of the record that should be tested (eg, 'name'.)
// functionKey is the function that should be used to do the test (eg,
// 'global filter substring'.) parameter is an extra parameter to pass
// to the test function (such as a search string). If invert is true,
// the sense of the filter is reversed: only objects that don't match
// it will be included. For convenience in 'onclick' handlers, this
// function returns false. param is a hack to include a static
// parameter in addition to the dynamic one.
function setViewFilter(viewName, fieldKey, functionKey, parameter, invert, param) {
    url = 'action:setViewFilter?';
    url = url + 'viewName=' + URLencode(viewName);
    url = url + '&fieldKey=' + URLencode(fieldKey);
    url = url + '&functionKey=' + URLencode(functionKey);
    if (parameter)
	url = url + '&parameter=' + URLencode(param+'|'+parameter);
    else
	url = url + '&parameter='+ URLencode(param);
    if (invert)
	url = url + '&invert=true';
    else
	url = url + '&invert=false';
    eventURL(url);
    return false;
}

// Change a view's sort. The sort controls the order in which records
// are displayed. (You can only do this if, when the view was declared
// in the page header, it was given an initial sort with the t:sort
// tag.)  viewName is the name of the view whose sort should be
// changed, as declared in the t:view tag. fieldKey is the property of
// the record to sort on (eg, 'name'.) functionKey is the comparison
// function for the sort (eg, 'global sort text'.) If reverse is true,
// the records will be shown in the opposite of their normal order as
// defined by the other parameters. For convenience in 'onclick'
// handlers, this function returns false.
function setViewSort(viewName, fieldKey, functionKey, reverse) {
    url = 'action:setViewSort?';
    url = url + 'viewName=' + URLencode(viewName);
    url = url + '&fieldKey=' + URLencode(fieldKey);
    url = url + '&functionKey=' + URLencode(functionKey);
    if (reverse)
	url = url + '&reverse=true';
    eventURL(url);
    return false;
}

// Start the video player. The playlist will be the items in the view
// named by viewName. If firstItemId is the id of an item in the view,
// playback will start on that item; otherwise playback will start on
// the first item.
function playViewNamed(viewName, firstItemId) {
    url = 'action:playViewNamed?';
    url = url + 'viewName=' + URLencode(viewName);
    url = url + '&firstItemId=' + URLencode(firstItemId);
    eventURL(url);
    return false;
}

// You can make 'incremental search' text boxes on your page that
// effectively tie the text box to the 'parameter' argument of setViewFilter,
// with the other argumens fixed. To do this, add these two attributes to
// the text box:
//   onfocus="startEditFilter(this, (viewName), (fieldKey),
//            (functionKey), (invert), (param)"
//   onblur="endEditFilter()"
// replacing the arguments in parentheses with the desired strings.
//
// Note that params is a big hack to pass a static parameter in
// addition to the dynamic one

var editFilterTimers = new Array();
var editFilterField = null;
var editFilterOldValue = '';
var editFilterCount = 0;
var editFilterViews = new Array();
var editFilterFieldKeys = new Array();
var editFilterFunctionKeys = new Array();
var editFilterInverts = new Array();
var editFilterParams = new Array();
var editCurView = 0;

function startEditFilter(obj, views, fieldKeys, functionKeys, inverts, params) {
  editFilterOldValue = obj.value;

  editFilterField = obj;
  editFilterViews = views;
  editFilterFieldKeys = fieldKeys;
  editFilterFunctionKeys = functionKeys;
  editFilterInverts = inverts;
  editFilterParams = params;
  editCurView = 0;

  editFilterTimerTick(editCurView);
}

function editFilterUpdate(viewName,functionName,fieldName,invert, param) {
    value = editFilterField.value;
    if (editFilterOldValue != value ||
	editFilterCount < editFilterViews.length) {
	if (editFilterOldValue != value) 
	    editFilterCount = 0;
	else
	    editFilterCount++;
	setViewFilter(viewName, fieldName,
		      functionName, value,
		      invert, param);
	editFilterOldValue = value;
    }
}

function editFilterTimerTick(curView) {
    editFilterUpdate(editFilterViews[editCurView],editFilterFunctionKeys[editCurView],editFilterFieldKeys[editCurView],editFilterInverts[editCurView], editFilterParams[editCurView]);
    editCurView++;
    if (editCurView >= editFilterViews.length) {
	editCurView = 0;
    }
  editFilterTimer = setTimeout(editFilterTimerTick, 50);
}

function endEditFilter() {
  clearTimeout(editFilterTimer);
  editFilterCount = 0;
  editFilterUpdate();
}

// Internal use: 'URL encode' the given string.
function URLencode(str) {
    return escape(str).replace(/\+/g, '%2C').replace(/\"/g,'%22').
	replace(/\'/g, '%27');
}

///////////////////////////////////////////////////////////////////////////////
//// For calling by host templating code                                   ////
///////////////////////////////////////////////////////////////////////////////

// For calling by host templating code: Returns items that should
// appear in the context click menu in the format url|description with
// one item on each line. Blank lines are separators
function getContextClickMenu(element) {
    while (1) {
	if (element.nodeType == 1 && element.getAttribute('t:contextMenu')) {
	    ret = element.getAttribute('t:contextMenu');
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

// For calling by host templating code: Set CSS styles on the item
// with the given ID to make it disappear.
function hideItem(id) {
    elt = document.getElementById(id);
    elt.style.display = 'none';
    forceRedisplay(elt);
}

// For calling by host templating code: Set CSS styles on the item
// with the given ID to make it visible if it was previously hidden.
function showItem(id) {
    elt = document.getElementById(id);
    elt.style.display = '';
    forceRedisplay(elt);
}

// For calling by host templating code: Replace the item with the
// given id with the element described by the proided XML.
function changeItem(id, newXML) {
    elt = document.getElementById(id);
    r = document.createRange();
    r.selectNode(elt);
    frag = r.createContextualFragment(newXML);
    elt.parentNode.replaceChild(frag, elt);
}

// For calling by host templating code: Parse the XML in newXML into a
// new element, and insert the new element immediately before the item
// with the given id, such that the newly inserted item has the same
// parent.
function addItemBefore(newXML, id) {
    elt = document.getElementById(id);
    r = document.createRange();
    r.selectNode(elt);
    frag = r.createContextualFragment(newXML);
    elt.parentNode.insertBefore(frag, elt);
}    

// For calling by host templating code: Parse the XML in newXML into a
// new element, and insert the new element as the final child of the
// item with the given id.
function addItemAtEnd(newXML, id) {
    elt = document.getElementById(id);
    r = document.createRange();
    r.selectNode(elt);
    frag = r.createContextualFragment(newXML);
    elt.insertBefore(frag, null);
}    

// For calling by host templating code: Remove the item with the given
// id.
function removeItem(id) {
    elt = document.getElementById(id);
    elt.parentNode.removeChild(elt);
}    

// Internal use: Sometime if all you do is change the style on a node,
// Safari doesn't update the view until your mouse is next over the
// window. Force the issue by making a drastic change in the vicinity
// of the given element and then reversing it.
function forceRedisplay(elt) {
    r = document.createRange();
    r.selectNode(elt);
    frag = r.extractContents();
    r.insertNode(frag);
}

///////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////

-->
</script>
