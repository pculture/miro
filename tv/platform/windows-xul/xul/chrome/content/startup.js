/*
# Miro - an RSS based video player application
# Copyright (C) 2005-2008 Participatory Culture Foundation
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
#
# In addition, as a special exception, the copyright holders give
# permission to link the code of portions of this program with the OpenSSL
# library.
#
# You must obey the GNU General Public License in all respects for all of
# the code used other than OpenSSL. If you modify file(s) with this
# exception, you may extend this exception to your version of the file(s),
# but you are not obligated to do so. If you do not wish to do so, delete
# this exception statement from your version. If you delete this exception
# statement from all source files in the program, then also delete it here.
*/

var pybridge = makeService("@participatoryculture.org/dtv/pybridge;1",Components.interfaces.pcfIDTVPyBridge);

function writelog(str) {
    Components.classes['@mozilla.org/consoleservice;1']
	.getService(Components.interfaces.nsIConsoleService)	
	.logStringMessage(str);
}

var initialButton;
var inSearch = false;
var searchSuccess = false;
var cancelled = false;
var finished = false;
var wizard;
var homedir;
function onload() {
    wizard = getWidget("democracy-startup");
    initialButton = wizard.getButton("finish").label;
    homedir = pybridge.getSpecialFolder("My Documents");
    setSearchDir(homedir);
    
    wizard.getButton("cancel").disabled = true;
    wizard.getButton("cancel").style.display = "none";
    updateUI();
}

function onwizardfinish() {
    if(finished) {
      return; 
      // User hit the Finish button quickly and we got this callback twice
    } else {
      finished = true;
    }
    var autoStartYes = getWidget("radiogroup-autostart-yes");
    pybridge.setRunAtStartup(autoStartYes.selected);
    //pybridge.setStartupTasksDone(true);
    var wwatch = Components.classes["@mozilla.org/embedcomp/window-watcher;1"]
            .getService(Components.interfaces.nsIWindowWatcher);
    var startupTasksURL = "chrome://dtv/content/startup.xul";
    wwatch.openWindow(null, "chrome://dtv/content/main.xul",
            "DemocracyPlayer", "chrome,resizable,dialog=no,all", null);
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
    wizard.getButton("finish").label = initialButton;
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
	    getWidget("description-search-progress").disabled = false;
	    getWidget("progressmeter-search-progress").disabled = false;
            var searchCancel = getWidget("button-search-cancel");
            searchCancel.disabled = false;
            if(inSearch) {
               searchCancel.label = searchCancel.getAttribute("cancel-label");
            } else {
               searchCancel.label = searchCancel.getAttribute("undo-label");
            }
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
	    wizard.getButton("finish").label = "Search";
	}
    }
}

function onsearchcancel ()
{
    pybridge.startupCancelSearch()
    getWidget("vbox-startup-search").setAttribute('collapsed', 'true');
}

function onsearch ()
{
    if (searchPossible()) {
	var path;
	if (getWidget("radio-search-location-custom").selected) {
	    path = getWidget("textbox-search-directory").abspath;
	} else {
	    path = homedir;
        }
	getWidget("vbox-startup-search").removeAttribute('collapsed');
	inSearch = true;
	updateUI();
	pybridge.startupDoSearch(path);
	return (false);
    } else {
	return (true);
    }
}

function setSearchProgressMessage(message) {
    var searchProgress = getWidget('description-search-progress');
    while(searchProgress.firstChild) {
        searchProgress.removeChild(searchProgress.firstChild);
    }
    searchProgress.appendChild(document.createTextNode(message));
}

function updateSearchProgress (message)
{
    setSearchProgressMessage(message);
}

function searchFinished (message)
{
    inSearch = false;
    searchSuccess = true;
    setSearchProgressMessage(message);
    updateUI();
}

function searchCancelled ()
{
    inSearch = false;
    searchSuccess = false;
    setSearchProgressMessage('');
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
