from xpcom import components, nsError, ServerException
import traceback
import sys
import time
import re

class DispatchHandler:
    _com_interfaces_ = [components.interfaces.nsIProtocolHandler]
    _reg_clsid_ = "{E48AA35F-7E2D-4a2b-8971-FD2EE0E5A231}"
    _reg_contractid_ = "@mozilla.org/network/protocol;1?name=dispatch"
    _reg_desc_ = "Handles DTV 'dispatch:' URLs"

    def __init__(self):
 	print "******** DispatchHandler init"
 	self.scheme = "dispatch"
 	self.defaultPort = -1
 	iph = components.interfaces.nsIProtocolHandler
 	self.protocolFlags = iph.URI_NORELATIVE | iph.URI_NOAUTH
 	print "DispatchHandler init done"

    def allowPort(self, port, scheme):
 	print "allowPort"
 	return False

    def newURI(self, spec, charset, baseURI):
 	# I doubt that ignoring 'charset' is completely correct
 	ret = components.classes["@mozilla.org/network/simple-uri;1"] \
 	    .createInstance(components.interfaces.nsIURI)
 	ret.spec = spec
 	return ret

    def newChannel(self, inputURI):
	match = re.compile(r"dispatch:([^?]+)\?(.*)").match(inputURI.spec)
	if match:
	    cookie = match.group(1)
	    url = match.group(2)
	    import frontend
	    frontend.HTMLDisplay.dispatchEventByCookie(cookie, url)
	else:
	    print "Warning: badly formed dispatch url '%s'" % inputURI.spec
	    raise ValueError
	
	# Return a channel that returns the empty string
	ioS = components.classes["@mozilla.org/network/io-service;1"] \
	    .getService(components.interfaces.nsIIOService)

	# NEEDS: return a channel returning valid XML, to avoid noise
	# in JS logs. While we're at it, it'd be clever to load
	# template-generated HTML from a channel, rather than a file:
	# URL, and use that as the basis for the permission grant.
	out = ioS.newChannel("about:blank", None, None)
	return out

class ActionHandler:
    _com_interfaces_ = [components.interfaces.nsIProtocolHandler]
    _reg_clsid_ = "{C6C5665E-ECD6-4770-9B3B-1C78C71AEEC0}"
    _reg_contractid_ = "@mozilla.org/network/protocol;1?name=action"
    _reg_desc_ = "Handles DTV 'action:' URLs"

    def __init__(self):
 	self.scheme = "action"
 	self.defaultPort = -1
 	iph = components.interfaces.nsIProtocolHandler
 	self.protocolFlags = iph.URI_NORELATIVE | iph.URI_NOAUTH

    def allowPort(self, port, scheme):
 	return False

    def newURI(self, spec, charset, baseURI):
 	# I doubt that ignoring 'charset' is completely correct
 	ret = components.classes["@mozilla.org/network/simple-uri;1"] \
 	    .createInstance(components.interfaces.nsIURI)
 	ret.spec = spec
 	return ret

    def newChannel(self, inputURI):
	print "NEEDS: global dispatch of URI: %s" % inputURI.spec
	ioS = components.classes["@mozilla.org/network/io-service;1"] \
	    .getService(components.interfaces.nsIIOService)
	out = ioS.newChannel("about:blank", None, None)
	return out

class TemplateHandler:
    _com_interfaces_ = [components.interfaces.nsIProtocolHandler]
    _reg_clsid_ = "{8D189EBA-6BEF-4119-9047-9B3CCADAD0A8}"
    _reg_contractid_ = "@mozilla.org/network/protocol;1?name=template"
    _reg_desc_ = "Handles DTV 'template:' URLs"

    def __init__(self):
 	self.scheme = "template"
 	self.defaultPort = -1
 	iph = components.interfaces.nsIProtocolHandler
 	self.protocolFlags = iph.URI_NORELATIVE | iph.URI_NOAUTH

    def allowPort(self, port, scheme):
 	return False

    def newURI(self, spec, charset, baseURI):
 	# I doubt that ignoring 'charset' is completely correct
 	ret = components.classes["@mozilla.org/network/simple-uri;1"] \
 	    .createInstance(components.interfaces.nsIURI)
 	ret.spec = spec
 	return ret

    def newChannel(self, inputURI):
	print "NEEDS: global dispatch of URI: %s" % inputURI.spec
	ioS = components.classes["@mozilla.org/network/io-service;1"] \
	    .getService(components.interfaces.nsIIOService)
	out = ioS.newChannel("about:blank", None, None)
	return out
