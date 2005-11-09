from xpcom import components, nsError, ServerException
import traceback
import sys
import time

class PyBridge:
    _com_interfaces_ = [components.interfaces.pcfIDTVPyBridge]
    _reg_clsid_ = "{F87D30FF-C117-401e-9194-DF3877C926D4}"
    _reg_contractid_ = "@participatoryculture.org/dtv/pybridge;1"
    _reg_desc_ = "Bridge into DTV Python core"

    def __init__(self):
	pass

    def onStartup(self, mainWindowDocument):
	self.mainWindowDocument = mainWindowDocument

	class AutoflushingStream:
	    def __init__(self, stream):
		self.stream = stream
	    def write(self, *args):
		self.stream.write(*args)
		self.stream.flush()

	h = open("/tmp/dtv-log", "wt")
	sys.stdout = sys.stderr = AutoflushingStream(h)
	try:
	    print "got:: %s" % mainWindowDocument

#	    klass = components.classes["@participatoryculture.org/dtv/jsbridge;1"]
#	    jsb = klass.getService(components.interfaces.pcfIDTVJSBridge)
#	    jsb.xulLoadURI(elt, "http://www.achewood.com")

	    import app
	    app.start()
	except:
	    traceback.print_exc()
