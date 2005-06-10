import xml.sax.saxutils
import xml.dom
import re
from HTMLParser import HTMLParser

##
# very simple parser to convert HTML to XHTML
class XHTMLifier(HTMLParser):
    def convert(self,data, addTopTags=False):
        if addTopTags:
            self.output = '<html><head></head><body>'
        else:
            self.output = ''
	self.stack = []
	self.feed(data)
	self.close()
	while len(self.stack) > 0:
	    temp = self.stack.pop()
	    self.output += '</'+temp+'>'
        if addTopTags:
            self.output += '</body></html>'
	return self.output
    def handle_starttag(self, tag, attrs):
	if tag.lower() == 'br':
	    self.output += '<br/>'
	else:
	    self.output += '<'+tag
	    for attr in attrs:
		if attr[1] == None:
		    self.output += ' '+attr[0]+'='+xml.sax.saxutils.quoteattr(attr[0])
		else:
		    self.output += ' '+attr[0]+'='+xml.sax.saxutils.quoteattr(attr[1])
	    self.output += '>'
	    self.stack.append(tag)
    def handle_endtag(self, tag):
	if tag.lower() != 'br' and len(self.stack) > 1:
	    temp = self.stack.pop()
	    self.output += '</'+temp+'>'
	    while temp != tag and len(self.stack) > 1:
		temp = self.stack.pop()
		self.output += '</'+temp+'>'	    
    def handle_startendtag(self, tag, attrs):
	self.output += '<'+tag+'/>'
    def handle_data(self, data):
	data = data.replace('&','&amp;')
	data = data.replace('<','&lt;')
	self.output += data
    def handle_charref(self, name):
	self.output += '&#'+name+';'
    def handle_entityref(self, name):
	self.output += '&'+name+';'

##
# Parses HTML entities in data
def unescape(data):
    return xml.sax.saxutils.unescape(data)

##
# Returns XHTMLified version of HTML document
def xhtmlify(data,addTopTags = False):
    x = XHTMLifier()
    return x.convert(data, addTopTags)

xmlheaderRE = re.compile("^\<\?xml\s*(.*?)\s*\?\>(.*)", re.S)
##
# Adds a <?xml ?> header to the given xml data or replaces an
# existing one without a charset with one that has a charset
def fixXMLHeader(data,charset):
    header = xmlheaderRE.match(data)
    if header is None:
        print "Adding header %s" % charset
        return '<?xml version="1.0" encoding="%s"?>%s' % (charset,data)
    else:
        xmlDecl = header.expand('\\1')
        theRest = header.expand('\\2')
        if xmlDecl.find('encoding'):
            return data
        else:
            print "Changing header to include charset"
            return '<?xml %s encoding="%s"?>%s' % (xmlDecl,charset,theRest)


HTMLHeaderRE = re.compile("^(.*)\<\s*head\s*(.*?)\s*\>(.*?)\</\s*head\s*\>(.*)",re.I | re.S)

##
# Adds a <meta http-equiv="Content-Type" content="text/html;
# charset=blah"> tag to an HTML document
#
# Since we're only feeding this to our own HTML Parser anyway, we
# don't care that it might bung up XHTML
def fixHTMLHeader(data,charset):
    header = HTMLHeaderRE.match(data)
    if header is None:
        #Something is very wrong with this HTML
        return data
    else:
        headTags = header.expand('\\3')
        #This isn't exactly robust, but neither is scraping HTML
        if headTags.lower().find('content-type') != -1:
            return data
        else:
            print " adding %s Content-Type to HTML" % charset
            return header.expand('\\1<head \\2><meta http-equiv="Content-Type" content="text/html; charset=')+charset+header.expand('">\\3</head>\\4')
