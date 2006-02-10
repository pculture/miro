from xpcom import components, nsError, ServerException
import traceback
import sys
import os
import time

# Copied from resource.py; if you change this function here, change it
# there too.
def appRoot():
    klass = components.classes["@mozilla.org/file/directory_service;1"]
    service = klass.getService(components.interfaces.nsIProperties)
    file = service.get("XCurProcD", components.interfaces.nsIFile)
    return file.path

class PyBridge:
    _com_interfaces_ = [components.interfaces.pcfIDTVPyBridge]
    _reg_clsid_ = "{F87D30FF-C117-401e-9194-DF3877C926D4}"
    _reg_contractid_ = "@participatoryculture.org/dtv/pybridge;1"
    _reg_desc_ = "Bridge into DTV Python core"

    def __init__(self):
        pass

    def onStartup(self, mainWindowDocument):
        print "onStartup"
        self.mainWindowDocument = mainWindowDocument

        class AutoflushingStream:
            def __init__(self, stream):
                self.stream = stream
            def write(self, *args):
                self.stream.write(*args)
                self.stream.flush()

        try:
            if os.environ.has_key('TMP'):
                h = open("%s/dtv-log" % os.environ['TMP'], "wt")
                sys.stdout = sys.stderr = AutoflushingStream(h)
        except:
            pass
        try:
            print "got:: %s" % mainWindowDocument

#           klass = components.classes["@participatoryculture.org/dtv/jsbridge;1"]
#           jsb = klass.getService(components.interfaces.pcfIDTVJSBridge)
#           jsb.xulLoadURI(elt, "http://www.achewood.com")

        except:
            traceback.print_exc()

    def bootApp(self):
        import app
        app.start()

    def onShutdown(self):
        print "onShutdown in pybridge"
        import app
        app.Controller().onShutdown()

    def eventURL(self, cookie, url):
        import frontend
        frontend.HTMLDisplay.dispatchEventByCookie(cookie, url)

    def addChannel(self, url):
        print "Add Channel %s" % url
        import feed
        feed.Feed(url)

    def getServerPort(self):
        # Frontend has to go first, because it knows the right time to
        # import frontend for the first time (after the right set of classes
        # have been set up)
        import app
        import frontend
        return frontend.getServerPort()
