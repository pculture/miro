var pybridge = Components.classes["@participatoryculture.org/dtv/pybridge;1"].
                getService(Components.interfaces.pcfIDTVPyBridge);

function onload() {
    var channels = window.arguments[0]['channels'].QueryInterface(Components.interfaces.nsICollection);
    var count = channels.Count();
    var widget = getWidget ("menulist-channel");
    var i;
    for (i = 0; i < count; i++) {
        widget.appendItem (channels.GetElementAt (i).QueryInterface(Components.interfaces.nsISupportsString).data);
    }
    var engines = window.arguments[0]['engines'].QueryInterface(Components.interfaces.nsICollection);
    count = engines.Count();
    widget = getWidget ("menulist-searchengine");
    for (i = 0; i < count; i++) {
        widget.appendItem (engines.GetElementAt (i).QueryInterface(Components.interfaces.nsISupportsString).data);
    }
    getWidget("textbox-term").value = window.arguments[0]['defaultTerm'];
    getWidget("menulist-channel").selectedIndex = window.arguments[0]['defaultChannel'];
    getWidget("menulist-searchengine").selectedIndex = window.arguments[0]['defaultEngine'];
    getWidget("textbox-url").value = window.arguments[0]['defaultURL'];
    getWidget("radio-style").selectedIndex = window.arguments[0]['defaultStyle'];
    updateUI();
}

function updateUI ()
{
    toggledEnable("radio-channel", "menulist-channel")
    toggledEnable("radio-searchengine", "menulist-searchengine")
    toggledEnable("radio-url", "textbox-url")
}

function toggledEnable (toggle, widget)
{
    toggle = getWidget (toggle);
    widget = getWidget (widget);
    if (toggle.selected) {
        widget.disabled = "";
    } else {
	widget.disabled = "true";
    }
}

function onaccept ()
{
    term = getWidget ("textbox-term").value;
    var loc;
    var style;
    if (getWidget("radio-channel").selected) {
	style = 0;
	loc = getWidget("menulist-channel").selectedIndex;
    } else if (getWidget("radio-searchengine").selected) {
	style = 1;
	loc = getWidget("menulist-searchengine").selectedIndex;
    } else if (getWidget("radio-url").selected) {
	style = 2;
	loc = getWidget("textbox-url").value;
    }
    pybridge.handleSearchChannelDialog(window.arguments[0]['id'], 0, term, style, loc)
}

function oncancel ()
{
    pybridge.handleSearchChannelDialog(window.arguments[0]['id'], 1, "", 0, "")
}

function getWidget(widgetID)
{
    return document.getElementById(widgetID);
}

