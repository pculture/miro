/*
# Miro - an RSS based video player application
# Copyright (C) 2005-2007 Participatory Culture Foundation
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
*/

var pybridge = makeService("@participatoryculture.org/dtv/pybridge;1",Components.interfaces.pcfIDTVPyBridge);

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

