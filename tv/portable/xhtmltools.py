import xml.sax.saxutils
import xml.dom
import re
from urllib import quote, quote_plus
from HTMLParser import HTMLParser
import types
import random

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

#
# encodes string for use in a URL
def urlencode(data):
    return quote(data.encode('utf-8'), '')

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
        #print "Adding header %s" % charset
        return '<?xml version="1.0" encoding="%s"?>%s' % (charset,data)
    else:
        xmlDecl = header.expand('\\1')
        theRest = header.expand('\\2')
        if xmlDecl.find('encoding'):
            return data
        else:
            #print "Changing header to include charset"
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
            #print " adding %s Content-Type to HTML" % charset
            return header.expand('\\1<head \\2><meta http-equiv="Content-Type" content="text/html; charset=')+charset+header.expand('">\\3</head>\\4')

# Takes a string and do whatever needs to be done to make it into a
# UTF-8 string. If a Unicode string is given, it is just encoded in
# UTF-8. Otherwise, if an encoding hint is given, first try to decode
# the string as if it were in that encoding; if that fails (or the
# hint isn't given), liberally (if necessary lossily) interpret it as
# defaultEncoding, as declared on the next line:
defaultEncoding = "iso-8859-1" # aka Latin-1
_utf8cache = {}

def toUTF8Bytes(string, encoding=None):
    global _utf8cache
    try:
        return _utf8cache[(string, encoding)]
    except:
        # If we got a Unicode string, half of our work is already done.
        if type(string) == unicode:
            _utf8cache[(string, encoding)] = string.encode('utf-8')

        # If we knew the encoding of the string, try that.
        try:
            if encoding is not None:
                _utf8cache[(string, encoding)] = string.decode(encoding).encode('utf-8')
        except UnicodeDecodeError:
            # string is not really encoded in 'encoding'.
            pass

        # Encoding wasn't provided, or it was wrong. Interpret provided string
        # liberally as a fixed defaultEncoding (see above.)
        _utf8cache[(string, encoding)] = string.decode(defaultEncoding, 'replace').encode('utf-8')
        return _utf8cache[(string, encoding)]

# Converts a Python dictionary to data suitable for a POST or GET submission
def URLEncodeDict(orig):
    output = []
    for key in orig.keys():
        if type(orig[key]) is types.ListType:
            for value in orig[key]:
                output.append('%s=%s' % (quote_plus(key), quote_plus(value)))
        else:
            output.append('%s=%s' % (quote_plus(key), quote_plus(orig[key])))
    return '&'.join(output)

def multipartEncode(postVars, files):
    # Generate a random 64bit number for our boundaries
    boundary = 'dp%s'% (hex(random.getrandbits(64))[2:-1])
    output = []
    if postVars is not None:
        for key in postVars.keys():
            output.append('--%s\r\n' % boundary)
            output.append('Content-Disposition: form-data; name="%s"\r\n\r\n' %
                          quote_plus(key))
            output.append(postVars[key])
            output.append('\r\n')
    if files is not None:
        for key in files.keys():
            output.append('--%s\r\n' % boundary)
            output.append('Content-Disposition: form-data; name="%s"; filename="%s"\r\n' %
                          (quote_plus(key),
                           quote_plus(files[key]['filename'])))
            output.append('Content-Type: %s\r\n\r\n' % files[key]['mimetype'])
            
            output.append(files[key]['handle'].read())
            output.append('\r\n')
    output.append('--%s--' % boundary)
    return (''.join(output), boundary)
