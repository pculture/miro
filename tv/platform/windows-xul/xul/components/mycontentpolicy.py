from xpcom import components
import traceback
import sys
import config
import webbrowser

class MyContentPolicy:
    _com_interfaces_ = [components.interfaces.nsIContentPolicy]
    _reg_clsid_ = "{CFECB6A2-24AE-48f4-9A7A-87E62B972795}"
    _reg_contractid_ = "@participatoryculture.org/dtv/mycontentpolicy;1"
    _reg_desc_ = "Democracy content policy"

    def __init__(self):
        pass

    def shouldLoad(self, contentType, contentLocation, requestOrigin, context, mimeTypeGuess,  extra):
        url = contentLocation.spec
        if ((contentType != components.interfaces.nsIContentPolicy.TYPE_DOCUMENT) or
            (url.startswith('chrome:') or
            url.startswith('http://127.0.0.1:') or  # FIXME get server port
            url.startswith('resource:') or
            url.startswith('about:') or
            url.startswith('javascript:') or
            url.startswith(config.get(config.CHANNEL_GUIDE_URL)))):
            return components.interfaces.nsIContentPolicy.ACCEPT
        else:
            print "DTV: openning %s in new window" % url
            # FIXME: Should this use the same code as UIBackendDelegate?
            webbrowser.open(contentLocation.spec)
            return components.interfaces.nsIContentPolicy.REJECT_SERVER

    def shouldProcess(self, contentType, contentLocation, requestOrigin, context, mimeType,  extra):
        return components.interfaces.nsIContentPolicy.ACCEPT

catman = components.classes["@mozilla.org/categorymanager;1"].getService()
catman.queryInterface(components.interfaces.nsICategoryManager)
catman.addCategoryEntry("content-policy", "@participatoryculture.org/dtv/mycontentpolicy;1", "@participatoryculture.org/dtv/mycontentpolicy;1", True, True)

