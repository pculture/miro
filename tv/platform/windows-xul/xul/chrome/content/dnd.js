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


function getDragAction(effect) {
  if(effect == "copy") return nsIDragService.DRAGDROP_ACTION_COPY;
  if(effect == "move") return nsIDragService.DRAGDROP_ACTION_MOVE;
  if(effect == "link") return nsIDragService.DRAGDROP_ACTION_LINK;
  return nsIDragService.DRAGDROP_ACTION_NONE;
}

function getDragData(element) {
  var dragSourceType = element.getAttribute("dragsourcetype") 
  var mimeType = "application/x-democracy-" + dragSourceType + "-drag";
  var transferable = Components.classes[
      "@mozilla.org/widget/transferable;1"].createInstance(nsITransferable)
  transferable.addDataFlavor(mimeType);
  var supportsString = Components.classes[
      "@mozilla.org/supports-string;1"].createInstance(nsISupportsString);
  supportsString.data = element.getAttribute("dragsourcedata");
  transferable.setTransferData(mimeType, supportsString, 
          supportsString.data.length * 2);
  var dragArray = Components.classes[
      "@mozilla.org/supports-array;1"].createInstance(nsISupportsArray);
  dragArray.AppendElement(transferable);
  return dragArray;
}

function findDragInfo(startElement) {
  var dragService = Components.classes[
      "@mozilla.org/widget/dragservice;1"].getService(nsIDragService);
  var dragSession = dragService.getCurrentSession();
  if(!dragSession) return null;

  var elt = searchUpForElementWithAttribute(startElement, "dragdesttype");
  while(elt) {
    var dragDestType = canElementSupportDrag(elt, dragSession);
    if(dragDestType) {
      return {'dragDestType': dragDestType, 'element': elt};
    } 
    elt = searchUpForElementWithAttribute(elt.parentNode, 'dragdesttype');
  } 
  return null;
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
  
  var dragInfo = findDragInfo(event.target);
  if(dragInfo) {
    var elt = dragInfo['element'];
    var dragDestType = dragInfo['dragDestType'];
    var dragEffect = elt.getAttribute('drageffect' + dragDestType);
    dragSession.dragAction = getDragAction(dragEffect);
    dragHighlight.setHightlight(elt, dragDestType);
    canDrop = true;
  } 
  dragSession.canDrop = canDrop;
  if(!canDrop) dragSession.dragAction = nsIDragService.DRAGDROP_ACTION_NONE;

  event.stopPropagation();
}

function onDragExit(event, browser) {
   if(event.screenX == 0 && event.screenY == 0) {
     dragHighlight.removeHighlight();
   }
}

function onDragDrop(event, browser) {
  dragHighlight.removeHighlight();
  var dragInfo = findDragInfo(event.target);
  if(dragInfo) {
    var elt = dragInfo['element'];
    var dragType = dragInfo['dragDestType'];
    var dragService = Components.classes[
        "@mozilla.org/widget/dragservice;1"].getService(nsIDragService);
    var dragSession = dragService.getCurrentSession();
    if(dragSession) {
      var dragDestData = elt.getAttribute("dragdestdata");
      var trans = Components.classes[
        "@mozilla.org/widget/transferable;1"].createInstance(nsITransferable)
      var mimeType = "application/x-democracy-" + dragType + "-drag";
      trans.addDataFlavor(mimeType);
      dragSession.getData(trans, 0);
      var rawData = new Object();
      var length = new Object();
      trans.getTransferData(mimeType, rawData, length);
      var sourceData = rawData.value.QueryInterface(nsISupportsString);
      pybridge.handleDrop(dragDestData, dragType, sourceData.data);
    }
  }
}
