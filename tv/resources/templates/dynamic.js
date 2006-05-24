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
}
     
///////////////////////////////////////////////////////////////////////////////
//// For use on your page                                                  ////
///////////////////////////////////////////////////////////////////////////////

function jsdump(str) {
    Components.classes['@mozilla.org/consoleservice;1']
	.getService(Components.interfaces.nsIConsoleService)	
	.logStringMessage(str);
}

function getDTVPlatform() {
    var elt = document.getElementsByTagName("html")[0];
    return elt.getAttribute('dtvPlatform');
}

// For calling from page Javascript: Cause a URL to be loaded. The
// assumption is that the application will notice, abort the load, and
// take some action based on the URL.
function eventURL(url) {
    if (typeof(window.frontend) == 'undefined') {
	// Generic strategy: trigger a load, and hope the application
	// catches it and cancels it without creating a race
	// condition.
        try {
            document.location.href = url;
        } catch (e) {
            // This may happen if the backend decides to handle the url load
            // itself.
        }
    } else {
	// OS X WebKit (KHTML) strategy: pass in an Objective C object
	// through the window object and call a method on it.
	window.frontend.eventURL(url);
    }

    return false;
}    

// Open email client with email about selected video
// All parameters come in URL encoded
function recommendItem(title, url, feedURL) {
    url = URLdecode(url);
    feedURL = URLdecode(feedURL);
    body = "You should check out this video:\n";
    body = body + url + "\n\n";
    body = body + "I found it while using the Democracy Player, which you can download here:\n";
    body = body + "http://www.getdemocracy.com\n\n";
    body = body + "The video was on this channel (click 'subscribe' in Democracy and paste in this address):\n"
    body = body + feedURL + "\n\n"
    
    url = 'mailto:';
    url = url + "?subject=" + title;
    url = url + "&body=" + URLencode(body);
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
//   onfocus="startEditSearch(this)"
//   onblur="endEditFilter()"
// replacing the arguments in parentheses with the desired strings.
//
// You'll also need to provide a updateSearchString function at the
// top of your template to perform the actual update

var editSearchField = null;
var editSearchOldValue = '';
var editSearchTimer = null;

function startEditSearch(obj) {
  editSearchOldValue = obj.value;

  editSearchField = obj;
  editSearchTimerTick();
}

function editSearchUpdate() {
    value = editSearchField.value;
    if (editSearchOldValue != value) {
	url = 'action:setSearchString?searchString=' + URLencode(value);
	eventURL(url);
	editSearchOldValue = value;
    }
}

function editSearchTimerTick() {
    editSearchUpdate();
    editSearchTimer = setTimeout(editSearchTimerTick, 50);
}

function endEditSearch() {
  clearTimeout(editSearchTimer);
  editSearchUpdate();
}

// Internal use: 'URL encode' the given string.
function URLencode(str) {
    return encodeURIComponent(str)
}

function URLdecode(str) {
  return decodeURIComponent(str)
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
