from xpcom import components
import traceback
import sys
import config
import prefs
import webbrowser

from frontend_implementation import urlcallbacks

nsIContentPolicy = components.interfaces.nsIContentPolicy

class MyContentPolicy:
    _com_interfaces_ = [nsIContentPolicy]
    _reg_clsid_ = "{CFECB6A2-24AE-48f4-9A7A-87E62B972795}"
    _reg_contractid_ = "@participatoryculture.org/dtv/mycontentpolicy;1"
    _reg_desc_ = "Democracy content policy"

    def __init__(self):
        pass

    def shouldLoad(self, contentType, contentLocation, requestOrigin, context, mimeTypeGuess,  extra):
        rv = nsIContentPolicy.ACCEPT
        if (requestOrigin is not None and 
                contentType == nsIContentPolicy.TYPE_DOCUMENT):
            url = contentLocation.spec
            referrer = requestOrigin.spec
            if not urlcallbacks.runCallback(referrer, url):
                rv = nsIContentPolicy.REJECT_REQUEST
        return rv

    def shouldProcess(self, contentType, contentLocation, requestOrigin, context, mimeType,  extra):
        return nsIContentPolicy.ACCEPT

catman = components.classes["@mozilla.org/categorymanager;1"].getService()
catman.queryInterface(components.interfaces.nsICategoryManager)
catman.addCategoryEntry("content-policy", "@participatoryculture.org/dtv/mycontentpolicy;1", "@participatoryculture.org/dtv/mycontentpolicy;1", True, True)
