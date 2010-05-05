# Miro - an RSS based video player application
# Copyright (C) 2005-2010 Participatory Culture Foundation
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
#
# In addition, as a special exception, the copyright holders give
# permission to link the code of portions of this program with the OpenSSL
# library.
#
# You must obey the GNU General Public License in all respects for all of
# the code used other than OpenSSL. If you modify file(s) with this
# exception, you may extend this exception to your version of the file(s),
# but you are not obligated to do so. If you do not wish to do so, delete
# this exception statement from your version. If you delete this exception
# statement from all source files in the program, then also delete it here.

"""``miro.xhtmltools`` -- XML related utility functions.
"""

import xml.sax.saxutils
import xml.dom
import re
from urllib import quote, quote_plus, unquote
from HTMLParser import HTMLParser, HTMLParseError
import random
import logging

class XHTMLifier(HTMLParser):
    """Very simple parser to convert HTML to XHTML

    """
    # FIXME - this should probably be rewritten to use StringIO.
    def convert(self, data, add_top_tags=False, filter_font_tags=False):
        """Converts an HTML data unicode string to an XHTML data
        unicode string.
        """
        try:
            if add_top_tags:
                self.output = u'<html><head></head><body>'
            else:
                self.output = ''
            self.stack = []
            self.filter_font_tags = filter_font_tags
            self.feed(data)
            self.close()
            while len(self.stack) > 0:
                temp = self.stack.pop()
                self.output += u'</'+temp+'>'
            if add_top_tags:
                self.output += u'</body></html>'
            return self.output

        except HTMLParseError:
            logging.warn("xhtmlifier: parse exception")
            logging.debug("data: '%s'", data)

    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'br':
            self.output += u'<br/>'
            return


        if not (tag.lower() == 'font' and self.filter_font_tags):
            self.output += u'<' + tag
            for attr in attrs:
                if attr[1] == None:
                    self.output += (u' ' +
                                    attr[0] +
                                    u'=' +
                                    xml.sax.saxutils.quoteattr(attr[0]))
                else:
                    self.output += (u' ' +
                                    attr[0] +
                                    u'=' +
                                    xml.sax.saxutils.quoteattr(attr[1]))
            self.output += u'>'
        self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag.lower() != 'br' and len(self.stack) > 1:
            temp = self.stack.pop()
            if not (tag.lower() == 'font' and self.filter_font_tags):
                self.output += u'</'+temp+u'>'
                while temp != tag and len(self.stack) > 1:
                    temp = self.stack.pop()
                    self.output += u'</' + temp + u'>'

    def handle_startendtag(self, tag, attrs):
        self.output += u'<' + tag + u'/>'

    def handle_data(self, data):
        data = data.replace(u'&', u'&amp;')
        data = data.replace(u'<', u'&lt;')
        self.output += data

    def handle_charref(self, name):
        self.output += u'&#' + name + ';'

    def handle_entityref(self, name):
        self.output += u'&' + name + ';'

def unescape(data):
    """Parses HTML entities in data"""
    return xml.sax.saxutils.unescape(data)

def urlencode(data):
    """Encodes string for use in a URL"""
    if isinstance(data, unicode):
        data = data.encode('utf-8', 'replace')
    else:
        data = str(data)
    return unicode(quote(data))

def urldecode(data):
    """Gets a string from a URL"""
    return unquote(data)

def xhtmlify(data, add_top_tags=False, filter_font_tags=False):
    """Returns XHTMLified version of HTML document"""
    x = XHTMLifier()
    ret = x.convert(data, add_top_tags, filter_font_tags)

    # if we got a bad return, try it again without filtering font
    # tags
    if ret is None and filter_font_tags:
        x = XHTMLifier()
        ret = x.convert(data, add_top_tags, filter_font_tags=False)

    # if that's still bad, try converting &quot; to ".
    # this fixes bug #10095 where Google Video items are sometimes
    # half quoted.
    if ret is None:
        x = XHTMLifier()
        ret = x.convert(data.replace("&quot;", '"'), add_top_tags,
                        filter_font_tags=False)

    if ret is None:
        ret = u""

    return ret

XML_HEADER_RE = re.compile("^\<\?xml\s*(.*?)\s*\?\>(.*)", re.S)

def fix_xml_header(data, charset):
    """Adds a <?xml ?> header to the given xml data or replaces an
    existing one without a charset with one that has a charset
    """
    header = XML_HEADER_RE.match(data)
    if header is None:
        # print "Adding header %s" % charset
        return '<?xml version="1.0" encoding="%s"?>%s' % (charset, data)

    xml_decl = header.expand('\\1')
    the_rest = header.expand('\\2')
    if xml_decl.find('encoding') != -1:
        return data

    # print "Changing header to include charset"
    return '<?xml %s encoding="%s"?>%s' % (xml_decl, charset, the_rest)


HTML_HEADER_RE = re.compile(
    u"^(.*)\<\s*head\s*(.*?)\s*\>(.*?)\</\s*head\s*\>(.*)", re.I | re.S)

def fix_html_header(data, charset):
    """Adds a <meta http-equiv="Content-Type" content="text/html;
    charset=blah"> tag to an HTML document

    Since we're only feeding this to our own HTML Parser anyway, we
    don't care that it might bung up XHTML.
    """
    header = HTML_HEADER_RE.match(data)
    if header is None:
        # something is very wrong with this HTML
        return data

    head_tags = header.expand('\\3')
    # this isn't exactly robust, but neither is scraping HTML
    if head_tags.lower().find('content-type') != -1:
        return data

    return header.expand('\\1<head\\2><meta http-equiv="Content-Type" content="text/html; charset=') + charset + header.expand('">\\3</head>\\4')

def url_encode_dict(orig):
    """Converts a Python dictionary to data suitable for a POST or GET
    submission
    """
    output = []
    for key, val in orig.items():
        if isinstance(val, list) or isinstance(val, tuple):
            for v in val:
                output.append('%s=%s' % (quote_plus(key), quote_plus(v)))
        elif isinstance(val, basestring):
            output.append('%s=%s' % (quote_plus(key), quote_plus(orig[key])))
        else:
            logging.warning("url_encode_dict: trying to encode non-string: '%s'", repr(val))
    return '&'.join(output)

def multipart_encode(post_vars, files):
    # Generate a random 64bit number for our boundaries
    boundary = 'dp%s' % hex(random.getrandbits(64))[2:-1]
    output = []
    if post_vars is not None:
        for key, value in post_vars.items():
            output.append('--%s\r\n' % boundary)
            output.append('Content-Disposition: form-data; name="%s"\r\n\r\n' %
                          quote_plus(key))
            if isinstance(value, unicode):
                value = value.encode('utf8', 'xmlcharrefreplace')
            output.append(value)
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
            files[key]['handle'].close()
    output.append('--%s--\n' % boundary)
    return (''.join(output), boundary)
