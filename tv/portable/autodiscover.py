# Miro - an RSS based video player application
# Copyright (C) 2009 Participatory Culture Foundation
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

import re
import logging
import traceback
import xml.dom.minidom
import urllib2

from miro import opml
from miro import util
"""
This file contains the RSS/Atom/OPML autodiscovery path.  It used to live in
subscription.py
"""

reflexiveAutoDiscoveryOpener = urllib2.urlopen

def flatten(subscriptions):
    """
    Take a nested subscription list, and remove the folders, putting everything
    at the root level.
    """
    def _flat(subscriptions):
        for subscription in subscriptions:
            if subscription['type'] == 'folder':
                for child in _flat(subscription['children']):
                    yield child
            else:
                yield subscription
    return list(_flat(subscriptions))

def parse_file(path):
    try:
        subscriptionFile = open(path, "r")
        content = subscriptionFile.read()
        subscriptionFile.close()
        return parse_content(content)
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        pass

def parse_content(content):
    try:
        dom = xml.dom.minidom.parseString(content)
        try:
            root = dom.documentElement
            if root.nodeName == "rss":
                return _getSubscriptionsFromRSSChannel(root)
            elif root.nodeName == "feed":
                return _getSubscriptionsFromAtomFeed(root)
            elif root.nodeName == "opml":
                subscriptions = opml.Importer().import_content(content)
                return flatten(subscriptions)
            else:
                return None
        finally:
            dom.unlink()
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        if util.chatter:
            logging.warn("Error parsing XML content...\n%s",
                    traceback.format_exc())

# =========================================================================

def _getSubscriptionsFromRSSChannel(root):
    try:
        channel = root.getElementsByTagName("channel").pop()
        subscriptions = _getSubscriptionsFromAtomLinkConstruct(channel)
        if subscriptions is not None:
            return subscriptions
        else:
            link = channel.getElementsByTagName("link").pop()
            href = link.firstChild.data
            return _getSubscriptionsFromReflexiveAutoDiscovery(href, "application/rss+xml")
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        pass

def _getSubscriptionsFromAtomFeed(root):
    try:
        subscriptions = _getSubscriptionsFromAtomLinkConstruct(root)
        if subscriptions is not None:
            return subscriptions
        else:
            link = _getAtomLink(root)
            rel = link.getAttribute("rel")
            if rel == "alternate":
                href = link.getAttribute("href")
                return _getSubscriptionsFromReflexiveAutoDiscovery(href, "application/atom+xml")
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        pass

def _getSubscriptionsFromAtomLinkConstruct(node):
    try:
        link = _getAtomLink(node)
        if link.getAttribute("rel") in ("self", "start"):
            href = link.getAttribute("href")
            return [{'type': 'feed', 'url': href}]
    except (KeyboardInterrupt, SystemExit):
        raise
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
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        return []
    else:
        if len(urls) == 0:
            return []
    return [{'type': 'feed', 'url': url} for url in urls]

def _getAtomLink(node):
    return node.getElementsByTagNameNS("http://www.w3.org/2005/Atom", "link").pop()
# =========================================================================
