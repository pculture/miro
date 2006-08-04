var nsIDragService = Components.interfaces.nsIDragService;
var nsIDragSession = Components.interfaces.nsIDragSession;
var nsITransferable = Components.interfaces.nsITransferable;
var nsISupportsArray = Components.interfaces.nsISupportsArray;
var nsISupportsString = Components.interfaces.nsISupportsString;

function writelog(str) {
    Components.classes['@mozilla.org/consoleservice;1']
	.getService(Components.interfaces.nsIConsoleService)	
	.logStringMessage(str);
}


function getDragData(element) {
  var dragSourceType = element.getAttribute("dragsourcetype") 
  var mimeType = "application/x-democracy-" + dragSourceType + "-drag";
  var transferable = Components.classes[
      "@mozilla.org/widget/transferable;1"].createInstance(nsITransferable)
  transferable.addDataFlavor(mimeType);
  var supportsString = Components.classes[
      "@mozilla.org/supports-string;1"].createInstance(nsISupportsString);
  supportsString.data = "BOGUS DATA";
  transferable.setTransferData(mimeType, supportsString, 
          supportsString.data.length * 2);
  var dragArray = Components.classes[
      "@mozilla.org/supports-array;1"].createInstance(nsISupportsArray);
  dragArray.AppendElement(transferable);
  return dragArray;
}

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

function onDragGesture(event, browser) {
  var element = searchUpForElementWithAttribute(event.target,
    "dragsourcetype");
  if(element) {
    var dragService = Components.classes["@mozilla.org/widget/dragservice;1"].getService(nsIDragService);
    if(!dragService.getCurrentSession()) {
      event.stopPropagation();
      var dragArray = getDragData(element);
      dragService.invokeDragSession(null, dragArray, null,
          nsIDragService.DRAGDROP_ACTION_COPY);
    } 
  } 
}

function canElementSupportDrag(element, dragSession) {
  var dragDestTypes = element.getAttribute("dragdesttype").split(":");
  for(var i = 0; i < dragDestTypes.length; i++) {
    var dragDestType = dragDestTypes[i];
    var mimeType = "application/x-democracy-" + dragDestType + "-drag";
    if(dragSession.isDataFlavorSupported(mimeType)) return dragDestType;
  }
  return false;
}

function onDragOver(event, browser) {
  var dragService = Components.classes["@mozilla.org/widget/dragservice;1"].getService(nsIDragService);
  var dragSession = dragService.getCurrentSession();
  if(!dragSession) return;

  var canDrop = false;

  var elt = searchUpForElementWithAttribute(event.target, "dragdesttype");
  if(elt) {
    var dragDestType = canElementSupportDrag(elt, dragSession);
    if(dragDestType) {
      dragHighlight.setHightlight(elt, dragDestType);
      canDrop = true;
    } 
  } 
  dragSession.canDrop = canDrop;
  event.stopPropagation();
}

function onDragExit(event, browser) {
  dragHighlight.removeHighlight();
}

function onDragDrop(event, browser) {
  dragHighlight.removeHighlight();
  var elt = searchUpForElementWithAttribute(event.target, "dragdesttype");
  if(elt) {
    var dragDestMimeType = "application/x-democracy-" +
        elt.getAttribute("dragdesttype") + "-drag";
    var dragService = Components.classes[
        "@mozilla.org/widget/dragservice;1"].getService(nsIDragService);
    var dragSession = dragService.getCurrentSession();
    if(dragSession && canElementSupportDrag(elt, dragSession)) {
      var dragDestData = elt.getAttribute("dragdestdata");
      var browserDoc = document.getElementById(browser).contentWindow.document;
      pybridge.handleDrop(dragDestData);
    }
  }
}
