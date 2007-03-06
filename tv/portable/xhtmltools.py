import xml.sax.saxutils
import xml.dom
import re
from urllib import quote, quote_plus, unquote
from HTMLParser import HTMLParser
import types
import random

##
# very simple parser to convert HTML to XHTML
class XHTMLifier(HTMLParser):
    def convert(self,data, addTopTags=False, filterFontTags=False):
        if addTopTags:
            self.output = u'<html><head></head><body>'
        else:
            self.output = ''
        self.stack = []
        self.filterFontTags = filterFontTags
        self.feed(data)
        try:
            self.close()
        except:
            print 'DTV: unexpected error while parsing html data.'
        while len(self.stack) > 0:
            temp = self.stack.pop()
            self.output += u'</'+temp+'>'
        if addTopTags:
            self.output += u'</body></html>'
        return self.output
    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'br':
            self.output += u'<br/>'
        else:
            if not (tag.lower() == 'font' and self.filterFontTags):
                self.output += u'<'+tag
                for attr in attrs:
                    if attr[1] == None:
                        self.output += u' '+attr[0]+u'='+xml.sax.saxutils.quoteattr(attr[0])
                    else:
                        self.output += u' '+attr[0]+u'='+xml.sax.saxutils.quoteattr(attr[1])
                self.output += u'>'
            self.stack.append(tag)
    def handle_endtag(self, tag):
        if tag.lower() != 'br' and len(self.stack) > 1:
            temp = self.stack.pop()
            if not (tag.lower() == 'font' and self.filterFontTags):
                self.output += u'</'+temp+u'>'
                while temp != tag and len(self.stack) > 1:
                    temp = self.stack.pop()
                    self.output += u'</'+temp+u'>'
    def handle_startendtag(self, tag, attrs):
        self.output += u'<'+tag+u'/>'
    def handle_data(self, data):
        data = data.replace(u'&',u'&amp;')
        data = data.replace(u'<',u'&lt;')
        self.output += data
    def handle_charref(self, name):
        self.output += u'&#'+name+';'
    def handle_entityref(self, name):
        self.output += u'&'+name+';'

##
# Parses HTML entities in data
def unescape(data):
    return xml.sax.saxutils.unescape(data)

#
# encodes string for use in a URL
def urlencode(data):
    data = unicode(data)
    return unicode(quote(data.encode('utf-8','replace')))

#
# gets a string from a URL
def urldecode(data):
    return unquote(data)

##
# Returns XHTMLified version of HTML document
def xhtmlify(data,addTopTags=False, filterFontTags=False):
    x = XHTMLifier()
    return x.convert(data, addTopTags, filterFontTags)

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


HTMLHeaderRE = re.compile(u"^(.*)\<\s*head\s*(.*?)\s*\>(.*?)\</\s*head\s*\>(.*)",re.I | re.S)

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
