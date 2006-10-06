var pybridge = Components.classes["@participatoryculture.org/dtv/pybridge;1"].
                getService(Components.interfaces.pcfIDTVPyBridge);

function writelog(str) {
    Components.classes['@mozilla.org/consoleservice;1']
	.getService(Components.interfaces.nsIConsoleService)	
	.logStringMessage(str);
}

var initialButton;
var inSearch = false;
var searchSuccess = false;
var cancelled = false;
var wizard;
var homedir;
function onload() {
    wizard = getWidget("democracy-startup");
    initialButton = wizard.getButton("next").label;
    setSearchDir(pybridge.getSpecialFolder("My Documents"));
    
    wizard.getButton("cancel").disabled = true;
    wizard.getButton("cancel").style.display = "none";
    updateUI();
}

function onwizardfinish() {
    pybridge.setStartupTasksDone(true);
    var wwatch = Components.classes["@mozilla.org/embedcomp/window-watcher;1"]
            .getService(Components.interfaces.nsIWindowWatcher);
    var startupTasksURL = "chrome://dtv/content/startup.xul";
    this.startup = wwatch.openWindow(null, "chrome://dtv/content/main.xul",
            "DemocracyPlayer", "chrome,dialog=yes,all", null);
}

function searchPossible() {
    if (! getWidget("radio-search-yes").selected)
	return false;
    return !searchSuccess;
}

function updateUI ()
{
    if(!wizard) return; // onload hasn't been called yet
    if (inSearch) {
	wizard.canAdvance = false;
	wizard.canRewind = false;
    } else {
	wizard.canAdvance = true;
	wizard.canRewind = true;
    }
    wizard.getButton("next").label = initialButton;
    if (wizard.currentPage.id == "page-search") {
	var meter = getWidget("progressmeter-search-progress");
	if (searchSuccess) {
	    meter.mode = "determined";
	    meter.value = 100;
	} else if (inSearch) {
	    meter.mode = "undetermined";
	} else {
	    meter.mode = "determined";
	    meter.value = 0;
	}
	if (inSearch || searchSuccess) {
	    getWidget("radio-search-yes").disabled = true;
	    getWidget("radio-search-no").disabled = true;
	    getWidget("radio-search-location-restrict").disabled = true;
	    getWidget("radio-search-location-custom").disabled = true;
	    getWidget("textbox-search-directory").disabled = true;
	    getWidget("button-search-directory").disabled = true;
	    toggledEnable("radio-search-yes", "radio-search-location-custom");
	    doubleToggledEnable("radio-search-yes", "radio-search-location-custom", "textbox-search-directory");
	    doubleToggledEnable("radio-search-yes", "radio-search-location-custom", "button-search-directory");
	    getWidget("description-search-progress").disabled = false;
	    getWidget("progressmeter-search-progress").disabled = false;
	    getWidget("button-search-cancel").disabled = false;
	} else {
	    getWidget("radio-search-yes").disabled = false;
	    getWidget("radio-search-no").disabled = false;
	    toggledEnable("radio-search-yes", "radio-search-location-restrict");
	    toggledEnable("radio-search-yes", "radio-search-location-custom");
	    doubleToggledEnable("radio-search-yes", "radio-search-location-custom", "textbox-search-directory");
	    doubleToggledEnable("radio-search-yes", "radio-search-location-custom", "button-search-directory");
	    getWidget("description-search-progress").disabled = true;
	    getWidget("progressmeter-search-progress").disabled = true;
	    getWidget("button-search-cancel").disabled = true;
	}
	if (searchPossible()) {
	    wizard.getButton("next").label = "Search";
	}
    }
}

function onsearchcancel ()
{
    pybridge.startupCancelSearch()
}

function onsearch ()
{
    if (searchPossible()) {
	var path;
	if (getWidget("radio-search-location-custom").selected)
	    path = getWidget("textbox-search-directory").abspath;
	else
	    path = homedir;
	getWidget("vbox-startup-search").style.display="block";
	inSearch = true;
	updateUI();
	pybridge.startupDoSearch(path);
	return (false);
    } else {
	return (true);
    }
}

function updateSearchProgress (message)
{
    getWidget('description-search-progress').value = message;
}

function searchFinished (message)
{
    inSearch = false;
    searchSuccess = true;
    getWidget('description-search-progress').value = message;
    updateUI();
}

function searchCancelled (message)
{
    inSearch = false;
    searchSuccess = false;
    getWidget('description-search-progress').value = message;
    updateUI();
}


function toggledEnable (toggle, widget)
{
    toggle = getWidget (toggle);
    widget = getWidget (widget);
    if (toggle.selected) {
        widget.disabled = false;
    } else {
	widget.disabled = true;
    }
}

function doubleToggledEnable (toggle1, toggle2, widget)
{
    toggle1 = getWidget (toggle1);
    toggle2 = getWidget (toggle2);
    widget = getWidget (widget);
    if (toggle1.selected && toggle2.selected) {
        widget.disabled = false;
    } else {
	widget.disabled = true;
    }
}

function setSearchDir(directory) {
    var searchDirBox = document.getElementById('textbox-search-directory');
    searchDirBox.abspath = directory;
    searchDirBox.value = pybridge.shortenDirectoryName(directory);
}

function selectSearchDirectory() {
    var fp = Components.classes["@mozilla.org/filepicker;1"]
	.createInstance(Components.interfaces.nsIFilePicker);

    fp.init(window, "Select custom search directory",
            Components.interfaces.nsIFilePicker.modeGetFolder);
    var res = fp.show();
    if (res == Components.interfaces.nsIFilePicker.returnOK){
        setSearchDir(fp.file.path);
    }

}

function getWidget(widgetID)
{
    return document.getElementById(widgetID);
}
