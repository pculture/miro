#!/usr/bin/env python

# Miro - an RSS based video player application
# Copyright (C) 2005-2008 Participatory Culture Foundation
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA

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
        self.transStack = []

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
            self.transStack[-1] += '${'+attrs['i18n:name']+'}'
        if 'i18n:translate' in attrs.keys():
            self.transStack.append("")
        self.tagStack.append(name)
        self.attrStack.append(attrs)

    def endElement(self,name):
        if self.inTranslate():
            self.output += "msgid \""
            self.output += self.transStack[-1].strip().replace("\r\n"," ").replace("\r"," ").replace("\n"," ")
            self.output += "\"\nmsgstr \"\"\n\n"
            self.transStack.pop()
        self.tagStack.pop()
        self.attrStack.pop()

    def characters(self, data):
        if self.inTranslate():
            self.transStack[-1] += data.replace('"','\\"')

if __name__ == "__main__":
    parser = make_parser()
    parser.setContentHandler(GettextParser())
    parser.setFeature(feature_external_ges,0)
    parser.parse(stdin)
