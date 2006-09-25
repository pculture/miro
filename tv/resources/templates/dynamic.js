<script type="text/javascript">
<!-- // Protect from our XML parser, which doesn't know to protect <script>

///////////////////////////////////////////////////////////////////////////////
//// For use on your page                                                  ////
///////////////////////////////////////////////////////////////////////////////

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
    var mailURL = 'http://www.videobomb.com/index/democracyemail?url=' + 
                url + '&title=' + title;
    try {
        document.location.href = mailURL;
    } catch (e) {
        // The backend will handle the URL load and this sometimes leads to an
        // exception here.
    }
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
var editSearchCallback = null;

function startEditSearch(obj, callback) {
  editSearchOldValue = obj.value;

  editSearchField = obj;
  editSearchCallback = callback;
  editSearchTimerTick();
}

function editSearchUpdate() {
    value = editSearchField.value;
    if (editSearchOldValue != value) {
	url = 'action:setSearchString?searchString=' + URLencode(value);
	eventURL(url);
	editSearchOldValue = value;
	if(editSearchCallback) editSearchCallback();
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

function handleContextMenuSelect(event) {
  if(event.button == 2) {
    var area = event.currentTarget.getAttribute("selectArea");
    var id = event.currentTarget.getAttribute("selectID");
    var viewName = event.currentTarget.getAttribute("selectViewName");
    var url = 'action:handleContextMenuSelect?id=' + id + '&area=' + area +
              '&viewName=' + viewName;
    eventURL(url);
  }
  return true;
}

function handleSelect(event) {
    var id = event.currentTarget.getAttribute("selectID");
    var viewName = event.currentTarget.getAttribute("selectViewName");
    var area = event.currentTarget.getAttribute("selectArea");
    var shiftKey = '0';
    var ctrlKey = '0';
    if(event.shiftKey) shiftKey = '1';
    if(event.ctrlKey || event.metaKey) ctrlKey = '1';
    eventURL('action:handleSelect?area=' + area + '&viewName=' + viewName + 
	'&id=' + id + '&shiftDown=' + shiftKey + '&ctrlDown=' + ctrlKey);
    return true;
}

function handleDblClick(event, viewName, id) {
   if(event.target.tagName && event.target.tagName.toUpperCase() == 'A') {
       // Either a link in the descrption, or a bomb/mailto/trash click
       return true;
   } else {
       return eventURL('action:playViewNamed?viewName=' + viewName + 
           '&firstItemId=' + id);
   }
}

function sendKeyToSearchBox(event) {
  if(event.altKey || event.ctrlKey || event.metaKey ||
      (event.target.tagName && event.target.tagName.toUpperCase() == 'INPUT'))
      return true;
  var searchBox = document.getElementById("search-box");
  searchBox.focus();
  return true;
}

function playNewVideos(event, id) {
  eventURL('action:playNewVideos?id=' + id);
  event.stopPropagation(); // don't want handleSelect to deal with this event
  return false;
}

///////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////

-->
</script>
