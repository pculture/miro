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

function openBugReportWindow() {
  var py = makeService("@participatoryculture.org/dtv/pybridge;1",Components.interfaces.pcfIDTVPyBridge);

  py.openBugTracker();
}

function updateLabel() {
  var elt = document.getElementById("log");
  var textIn = window.arguments[0]["report"];
  elt.setAttribute("value", textIn);
}

function updateLabelStartupError() {
  var py = makeService("@participatoryculture.org/dtv/pybridge;1",Components.interfaces.pcfIDTVPyBridge);
  var elt = document.getElementById("log");
  elt.setAttribute("value", py.getStartupError());
}

function copyLogToClipboard() {
  var log = document.getElementById("log");
  var clipboard = Components.classes["@mozilla.org/widget/clipboardhelper;1"]
      .getService(Components.interfaces.nsIClipboardHelper);
  clipboard.copyString(log.value);
}
