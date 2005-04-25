import xml.sax.saxutils
from HTMLParser import HTMLParser

##
# very simple parser to convert HTML to XHTML
class XHTMLifier(HTMLParser):
    def convert(self,data):
	self.output = ''
	self.stack = []
	self.feed(data)
	self.close()
	while len(self.stack) > 0:
	    temp = self.stack.pop()
	    self.output += '</'+temp+'>'

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
def xhtmlify(data):
    x = XHTMLifier()
    return x.convert(data)
