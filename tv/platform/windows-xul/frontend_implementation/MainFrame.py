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

	# Find our global XPCOM controller object
	print "MainFrame about to try"
	klass = components.classes["@participatoryculture.org/dtv/pybridge;1"]
	self.pybridge = klass.getService(components.interfaces.pcfIDTVPyBridge)
	klass = components.classes["@participatoryculture.org/dtv/jsbridge;1"]
	self.jsbridge = klass.getService(components.interfaces.pcfIDTVJSBridge)
	print "MainFrame init got bridges: %s %s" % (self.pybridge, self.jsbridge)

    def selectDisplay(self, newDisplay, area):
        """Install the provided 'newDisplay' in the requested area"""

	print "selectDisplay called"
        oldDisplay = None # protect from GC at least until new window's in
        if self.selectedDisplays.has_key(area):
            oldDisplay = self.selectedDisplays[area]
            if oldDisplay:
                oldDisplay.onDeselected_private(self)
                oldDisplay.onDeselected(self)

	# On this platform, we leave the dirty work entirely up to the
	# displays!
	if oldDisplay:
	    oldDisplay.doDeselect(self, area)
	if newDisplay:
	    newDisplay.doSelect(self, area)

        self.selectedDisplays[area] = newDisplay
        newDisplay.onSelected_private(self)
        newDisplay.onSelected(self)

    # Internal use: return the DOM element corresponding to a given
    # display area, assuming that we want to use the area to display
    # content of the given "mode" (currently 'video' or 'html'.)
    def getAreaElement(self, area, mode):
	theId = "%s_%s" % (area, mode)
	print "getAreaElement %s" % theId
	return self.pybridge.mainWindowDocument.getElementById(theId)

    # Internal use: if the given display area isn't "prepared" to
    # display content "in the given mode," do whatever is necessary
    # XUL-side to prepare it. In practice, the only use for this is
    # switching between "video" and "html" modes for mainDisplay.
    def ensureAreaMode(self, area, mode):
	print "EnsureAreaMode"
	if area == self.mainDisplay:
	    htmlElt = self.getAreaElement(area, "html")
	    videoElt = self.getAreaElement(area, "video")
	    if mode == "video":
		htmlElt.setAttribute("collapsed", "true")
		videoElt.setAttribute("collapsed", "false")
	    else:
		htmlElt.setAttribute("collapsed", "false")
		videoElt.setAttribute("collapsed", "true")

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

    def doDeselect(self, frame, area):
	pass

    def doSelect(self, frame, area):
	pass

    def unlink(self):
	pass

    def __del__(self):
        self.unlink()

###############################################################################
###############################################################################
