<script type="text/javascript">
<!-- // Protect from our XML parser, which doesn't know to protect <script>

///////////////////////////////////////////////////////////////////////////////
//// For use on your page                                                  ////
///////////////////////////////////////////////////////////////////////////////

// For calling from page Javascript: Cause a URL to be loaded. The
// assumption is that the application will notice, abort the load, and
// take some action based on the URL.
function eventURL(url) {
    document.location.href = url;
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
// function returns false.
function setViewFilter(viewName, fieldKey, functionKey, parameter, invert) {
    url = 'action:setViewFilter?';
    url = url + 'viewName=' + URLencode(viewName);
    url = url + '&fieldKey=' + URLencode(fieldKey);
    url = url + '&functionKey=' + URLencode(functionKey);
    if (parameter)
	url = url + '&parameter=' + URLencode(parameter);
    if (invert)
	url = url + '&invert=true';
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
function playView(viewName, firstItemId) {
    url = 'action:playView?';
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
//            (functionKey), (invert)"
//   onblur="endEditFilter()"
// replacing the arguments in parentheses with the desired strings.

var editFilterTimers = new Array();
var editFilterField = null;
var editFilterOldValue = '';
var editFilterCount = 0;
var editFilterViews = new Array();
var editFilterFieldKeys = new Array();
var editFilterFunctionKeys = new Array();
var editFilterInverts = new Array();
var editCurView = 0;

function startEditFilter(obj, views, fieldKeys, functionKeys, inverts) {
  editFilterOldValue = obj.value;

  editFilterField = obj;
  editFilterViews = views;
  editFilterFieldKeys = fieldKeys;
  editFilterFunctionKeys = functionKeys;
  editFilterInverts = inverts;
  editCurView = 0;

  editFilterTimerTick(editCurView);
}

function editFilterUpdate(viewName,functionName,fieldName,invert) {
    value = editFilterField.value;
    if (editFilterOldValue != value ||
	editFilterCount < editFilterViews.length) {
	if (editFilterOldValue != value) 
	    editFilterCount = 0;
	else
	    editFilterCount++;
	setViewFilter(viewName, fieldName,
		      functionName, value,
		      invert);
	editFilterOldValue = value;
    }
}

function editFilterTimerTick(curView) {
    editFilterUpdate(editFilterViews[editCurView],editFilterFunctionKeys[editCurView],editFilterFieldKeys[editCurView],editFilterInverts[editCurView]);
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
     return "http://downhillbattle.org|Downhill Battle\n\nhttp://slashdot.org|Slashdot";
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
