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

/*
 * osxdnd.js
 * DND support for OS X.
 * NOTE: This file gets included for all the platforms, but it's only used in OSX.  OSX hooks up these functions to the various 
 * drag and drop events using HTMLArea.getBodyTagExtra()
 */

var dragHighlight = {
  highlightedElement: null,
  highlightCSSClass: null,

  removeHighlight: function() {
    if(this.highlightedElement) {
      this.highlightedElement.className = 
        this.highlightedElement.className.replace(this.highlightCSSClass, "");
      this.highlightedElement = null;
    }
  },

  setHightlight: function(element, type) {
    this.removeHighlight();
    if(element.className) {
      this.highlightCSSClass = " drag-highlight " + type;
    } else {
      this.highlightCSSClass = "drag-highlight " + type;
    }
    element.className += this.highlightCSSClass;
    this.highlightedElement = element;
  }
};

function canElementSupportDrag(element, dataTransfer) {
  var dragDestTypes = element.getAttribute("dragdesttype").split(":");
  for(var i = 0; i < dragDestTypes.length; i++) {
    var dragDestType = dragDestTypes[i];
    var mimeType = "application/x-democracy-" + dragDestType + "-drag";
    for(var j = 0; j < dataTransfer.types.length; j++) {
      if(dataTransfer.types[j] == mimeType) return dragDestType;
    }
  }
  return false;
}

function searchUpForElementWithAttribute(element, attributeName) {
    while (1) {
	if (element.nodeType == 1 && element.getAttribute(attributeName)) {
            return element;
	}
	if (element.parentNode) {
	    element = element.parentNode;
        } else {
            return null;
        }
    }

    return null;
}

function findDropInfo(startElement) {
  var elt = searchUpForElementWithAttribute(event.target, "dragdesttype");
  while(elt) {
    var dragDestType = canElementSupportDrag(elt, event.dataTransfer);
    if(dragDestType) {
        return {'dragDestType': dragDestType, 'element': elt};
    } 
    elt = searchUpForElementWithAttribute(elt.parentNode, "dragdesttype");
  }
  return null;
}


function handleDragStart(event) {
   var elt = searchUpForElementWithAttribute(event.target, "dragsourcetype");
   if(elt) {
      var dragSourceType = elt.getAttribute("dragsourcetype") 
      var mimeType = "application/x-democracy-" + dragSourceType + "-drag";
      event.dataTransfer.setData(mimeType, elt.getAttribute("dragsourcedata"));
      event.dataTransfer.effectAllowed = "all";
      var dragImage = document.getElementById(elt.getAttribute('dragicon'));
      event.dataTransfer.setDragImage(dragImage, 5, 5);
      return false;
   }
}

function handleDragOver(event) {
  var dropInfo = findDropInfo(event.target);
  if(dropInfo) {
    var dragDestType = dropInfo['dragDestType'];
    var elt = dropInfo['element'];
    event.dataTransfer.dropEffect = elt.getAttribute('drageffect' + dragDestType);
    event.preventDefault();
    dragHighlight.setHightlight(elt, dragDestType);
  } 
}

function handleDragLeave(event) {
  dragHighlight.removeHighlight();
}

function handleDrop(event) {
  dragHighlight.removeHighlight();
  var dropInfo = findDropInfo(event.target);
  if(dropInfo) {
    var dragDestType = dropInfo['dragDestType'];
    var elt = dropInfo['element'];
    var dragDestMimeType = "application/x-democracy-" + dragDestType + "-drag";
    var sourceData = event.dataTransfer.getData(dragDestMimeType);
      var dragDestData = elt.getAttribute("dragdestdata");
      eventURL('action:handleDrop?data=' + dragDestData + "&type=" +
	      dragDestType + "&sourcedata=" + sourceData);
  }
}
