#!/usr/bin/env python
# xgettext-xml.py (c) 2005 Nicholas Nassar
#
# This file is part of DTV
#
# It is a simple utility to extract translatable gettext strings from
# HTML template documents. It takes in an XML document on stdin and
# returns POT file entries on stdout.
#
# The format is roughly based on
# http://www.zope.org/DevHome/Wikis/DevSite/Projects/ComponentArchitecture/ZPTInternationalizationSupport

from xml.sax.handler import ContentHandler,feature_external_ges
from xml.sax import make_parser, parse
from sys import stdin

##
# Parser that reads in an XML template file in this format and output
# a POT file
class GettextParser(ContentHandler):
    def startDocument(self):
	self.output = ''
	self.tagStack = []
	self.attrStack = []

    def inTranslate(self):
	ret = False
	try:
	    ret = 'i18n:translate' in self.attrStack[-1].keys()
	except:
	    pass
	return ret

    def endDocument(self):
	print self.output

    def startElement(self,name,attrs):
	if self.inTranslate():
	    self.output += '${'+attrs['i18n:name']+'}'
	elif 'i18n:translate' in attrs.keys():
	    self.output += "msgid \""
	self.tagStack.append(name)
	self.attrStack.append(attrs)

    def endElement(self,name):
	if self.inTranslate():
	    self.output += "\"\nmsgstr \"\"\n\n"
	self.tagStack.pop()
	self.attrStack.pop()

    def characters(self, data):
	if self.inTranslate():
	    self.output += data.replace('"','\\"')

if __name__ == "__main__":
    parser = make_parser()
    parser.setContentHandler(GettextParser())
    parser.setFeature(feature_external_ges,0)
    parser.parse(stdin)
