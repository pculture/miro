var pybridge = Components.classes["@participatoryculture.org/dtv/pybridge;1"].
                getService(Components.interfaces.pcfIDTVPyBridge);

var originalMoviesDir = null;

function onload() {
    updateUI()
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
    if (getWidget("radio-channel").selected) {
	style = 0;
	location = getWidget("menulist-searchengine").value;
    } else if (getWidget("radio-searchengine").selected) {
	style = 1;
	location = getWidget("menulist-searchengine").value;
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

