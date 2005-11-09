import app
from frontend import *
from xpcom import components

###############################################################################
#### Main window                                                           ####
###############################################################################

# NEEDS: save/restore window position and size
class MainFrame:
    def __init__(self, appl):
        """The initially active display will be an instance of NullDisplay."""
	print "MainFrame init"

        # Symbols by other parts of the program as as arguments
        # to selectDisplay
        self.mainDisplay = "mainDisplay"
        self.channelsDisplay = "channelsDisplay"
        self.collectionDisplay = "collectionDisplay"
        #(videoInfoDisplay?)

        # Child display state
        self.selectedDisplays = {}

	# Find the XUL document corresponding to the window
	klass = components.classes["@participatoryculture.org/dtv/pybridge;1"]
	pybridge = klass.getService(components.interfaces.pcfIDTVPyBridge)
	self.document = pybridge.mainWindowDocument

    def selectDisplay(self, newDisplay, area):
        """Install the provided 'newDisplay' in the requested area"""

	# Generate a deselection message for the previously selected
	# display in this area, if any
	print "selectDisplay called"
        oldDisplay = None # protect from GC at least until new window's in
        if self.selectedDisplays.has_key(area):
            oldDisplay = self.selectedDisplays[area]
            if oldDisplay:
                oldDisplay.onDeselected_private(self)
                oldDisplay.onDeselected(self)

	# Find the <box /> into which the display is to be inserted
	box = self.document.getElementById(area)

	# Remove the deselected display
	if oldDisplay:
	    box.removeChild(oldDisplay.getXULElement(self))

	# Insert the newly selected display
	if newDisplay:
	    box.appendChild(newDisplay.getXULElement(self))

	# Generate a selection message for the new display, if any
        self.selectedDisplays[area] = newDisplay
	if newDisplay:
	    newDisplay.onSelected_private(self)
	    newDisplay.onSelected(self)

    # Internal use: get the XUL document corresponding to the window.
    def getXULDocument(self):
	return self.document

    # Internal use: return an estimate of the size of a given display area
    # as a (width, height) pair, or None if no information's available.
    def getDisplaySizeHint(self, area):
	return None

    def unlink(self):
	pass

    def __del__(self):
        self.unlink()

###############################################################################
#### The no-op display (here's as good a place as any)                     ####
###############################################################################

class NullDisplay (app.Display):
    "A blank placeholder Display."

    def __init__(self):
        app.Display.__init__(self)
	self.elt = None
	self.frame = None

    def getXULElement(self, frame):
	if self.frame is None:
	    self.frame = frame
	    self.elt = self.frame.getXULDocument().createElement("spacer")
	    self.elt.setAttribute("width", "0")
	    self.elt.setAttribute("height", "0")
	    self.elt.setAttribute("collapsed", "true")
	else:
	    assert self.frame == frame, "XUL displays cannot be reused"
	return self.elt

    def unlink(self):
	pass

    def __del__(self):
        self.unlink()

###############################################################################
###############################################################################
