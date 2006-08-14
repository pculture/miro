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
    this.highlightCSSClass = " drag-highlight " + type;
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
  var elt = searchUpForElementWithAttribute(event.target, "dragdesttype");
  if(elt) {
    var dragDestType = canElementSupportDrag(elt, event.dataTransfer);
    if(dragDestType) {
      event.dataTransfer.dropEffect = elt.getAttribute('drageffect' + dragDestType);
      event.preventDefault();
      dragHighlight.setHightlight(elt, dragDestType);
    } 
  } 
}

function handleDragLeave(event) {
  dragHighlight.removeHighlight();
}

function handleDrop(event) {
  dragHighlight.removeHighlight();
  var elt = searchUpForElementWithAttribute(event.target, "dragdesttype");
  if(elt) {
    var dragDestType = canElementSupportDrag(elt, event.dataTransfer);
    var dragDestMimeType = "application/x-democracy-" + dragDestType + "-drag";
    var sourceData = event.dataTransfer.getData(dragDestMimeType);
    if(dragDestType) {
      var dragDestData = elt.getAttribute("dragdestdata");
      eventURL('action:handleDrop?data=' + dragDestData + "&type=" +
	      dragDestType + "&sourcedata=" + sourceData);
    }
  }
}
