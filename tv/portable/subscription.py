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

import cgi
import re
import traceback
import logging
import urllib2
import urlparse
import xml.dom.minidom

from miro import util

"""
This file handles checking URLs that the user clicks on to see if they are
subscribe links.  Subscribe links are specially formatted URLs that signal
that we should subscribe the user to a feed, add a new channel guide, start a
new video download, or something similar.

Our basic strategy is to have have links with the host subscribe.getmiro.com.
That way we can parse them in miro and have an actual page on
subscribe.getmiro.com that the user will see if they click it in an actual web
browser.
"""

SUBSCRIBE_HOSTS = ('subscribe.getdemocracy.com', 'subscribe.getmiro.com')

# if you update this list, also update the list on
# subscribe.getmiro.com/geturls.php
ADDITIONAL_KEYS =  ('title', 'description', 'length', 'type', 'thumbnail',
                    'feed', 'link', 'trackback')
# =========================================================================

reflexiveAutoDiscoveryOpener = urllib2.urlopen

def parseFile(path):
    try:
        subscriptionFile = open(path, "r")
        content = subscriptionFile.read()
        subscriptionFile.close()
        return parseContent(content)
    except:
        pass

def parseContent(content):
    try:
        dom = xml.dom.minidom.parseString(content)
        try:
            root = dom.documentElement
            urlsType = 'rss'
            if root.nodeName == "rss":
                urls = _getSubscriptionsFromRSSChannel(root)
            elif root.nodeName == "feed":
                urls = _getSubscriptionsFromAtomFeed(root)
            elif root.nodeName == "opml":
                urlsType, urls = _getSubscriptionsFromOPMLOutline(root)
            else:
                return None
            return urlsType, urls
        finally:
            dom.unlink()
    except:
        if util.chatter:
            logging.warn("Error parsing OPML content...\n%s",
                    traceback.format_exc())

def get_urls_from_query(query):
    urls = []
    # the query string shouldn't be a unicode.  if we pass it in as a unicode
    # then parse_qs returns unicode values which aren't properly converted
    # and then we end up with boxes instead of ' and " characters.
    query = str(query)
    parsedQuery = cgi.parse_qs(query)
    for key, value in parsedQuery.items():
        match = re.match(r'^url(\d+)$', key)
        if match:
            urlId = match.group(1)
            additional = {}
            for key2 in ADDITIONAL_KEYS:
                if '%s%s' % (key2, urlId) in parsedQuery:
                    additional[key2] = unicode(parsedQuery['%s%s' % (key2, urlId)][0])
            urls.append((unicode(value[0]), additional))
    return urls

def isSubscribeLink(url):
    try:
        scheme, host, path, params, query, frag = urlparse.urlparse(url)
    except:
        return False
    return host in SUBSCRIBE_HOSTS

def findSubscribeLinks(url):
    """Given a URL, test if it's trying to subscribe the user using
    subscribe.getdemocracy.com.  Returns the list of parsed URLs.
    """
    try:
        scheme, host, path, params, query, frag = urlparse.urlparse(url)
    except:
        logging.warn("Error parsing %s in findSubscribeLinks()\n%s", url,
                traceback.format_exc())
        return 'none', []
    if host not in SUBSCRIBE_HOSTS:
        return 'none', []
    if path in ('/', '/opml.php'):
        return 'feed', get_urls_from_query(query)
    elif path in ('/download.php','/download','/download/'):
        return 'download', get_urls_from_query(query)
    elif path in ('/channelguide.php', '/channelguide', '/channelguide/'):
        return 'guide', get_urls_from_query(query)
    else:
        return 'feed', [(urllib2.unquote(path[1:]), {})]

# =========================================================================

def _getSubscriptionsFromRSSChannel(root):
    try:
        channel = root.getElementsByTagName("channel").pop()
        urls = _getSubscriptionsFromAtomLinkConstruct(channel)
        if urls is not None:
            return urls
        else:
            link = channel.getElementsByTagName("link").pop()
            href = link.firstChild.data
            return _getSubscriptionsFromReflexiveAutoDiscovery(href, "application/rss+xml")
    except:
        pass

def _getSubscriptionsFromAtomFeed(root):
    try:
        urls = _getSubscriptionsFromAtomLinkConstruct(root)
        if urls is not None:
            return urls
        else:
            link = _getAtomLink(root)
            rel = link.getAttribute("rel")
            if rel == "alternate":
                href = link.getAttribute("href")
                return _getSubscriptionsFromReflexiveAutoDiscovery(href, "application/atom+xml")
    except:
        pass

def _getSubscriptionsFromAtomLinkConstruct(node):
    try:
        link = _getAtomLink(node)
        if link.getAttribute("rel") in ("self", "start"):
            href = link.getAttribute("href")
            return [href]
    except:
        pass

def _getSubscriptionsFromReflexiveAutoDiscovery(url, ltype):
    try:
        urls = list()
        html = reflexiveAutoDiscoveryOpener(url).read()
        for match in re.findall("<link[^>]+>", html):
            altMatch = re.search("rel=\"alternate\"", match)
            typeMatch = re.search("type=\"%s\"" % re.escape(ltype), match)
            hrefMatch = re.search("href=\"([^\"]*)\"", match)
            if None not in (altMatch, typeMatch, hrefMatch):
                href = hrefMatch.group(1)
                urls.append(href)
    except:
        urls = None
    else:
        if len(urls) == 0:
            urls = None
    return urls

def _getAtomLink(node):
    return node.getElementsByTagNameNS("http://www.w3.org/2005/Atom", "link").pop()

# =========================================================================

def _getSubscriptionsFromOPMLOutline(root):
    try:
        urls = list()
        body = root.getElementsByTagName("body").pop()
        urlsType = _searchOPMLNodeRecursively(body, urls)
    except:
        urls = None
    else:
        if len(urls) == 0:
            urls = None
    return urlsType, urls

def _searchOPMLNodeRecursively(node, urls, urlsType=None):
    try:
        children = node.childNodes
        for child in children:
            if hasattr(child, 'getAttribute'):
                if child.hasAttribute("xmlUrl"):
                     newType, newURL = _handleOPMLChild(child)
                     if urlsType is None:
                         urlsType = newType
                         urls.append(newURL)
                     elif urlsType == newType:
                         urls.append(newURL)
                     else:
                         logging.debug('%s != %s, ignoring' % (urlsType, newType))
                else:
                    urlsType = _searchOPMLNodeRecursively(child, urls, urlsType)
    except Exception, e:
        logging.exception('error searching OPML')
    return urlsType

def _handleOPMLChild(node):
    type = node.getAttribute('type')
    url = node.getAttribute('xmlUrl')
    if type == 'download':
        additional = {}
        for key in ADDITIONAL_KEYS:
            attribute = 'additional%s' % key.capitalize()
            if node.hasAttribute(attribute):
                additional[key] = node.getAttribute(attribute)
        return type, (url, additional)
    else:
        return type, url
# =========================================================================
