# Miro - an RSS based video player application
# Copyright (C) 2009-2010 Participatory Culture Foundation
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

"""
This file contains the RSS/Atom/OPML autodiscovery path.  It used to
live in subscription.py
"""

import re
import logging
import traceback
import xml.dom.minidom
from xml.parsers.expat import ExpatError
import urllib2

from miro import opml
from miro import util

REFLEXIVE_AUTO_DISCOVERY_OPENER = urllib2.urlopen

def flatten(subscriptions):
    """
    Take a nested subscription list, and remove the folders, putting
    everything at the root level.
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
        subscription_file = open(path, "r")
        content = subscription_file.read()
        subscription_file.close()
        return parse_content(content)
    except (IOError, ExpatError):
        pass

def parse_content(content):
    try:
        dom = xml.dom.minidom.parseString(content)
    except (ExpatError, TypeError):
        if util.chatter:
            logging.warn("Error parsing XML content...\n%s",
                    traceback.format_exc())
        return

    try:
        root = dom.documentElement
        if root.nodeName == "rss":
            return _get_subs_from_rss_channel(root)
        elif root.nodeName == "feed":
            return _get_subs_from_atom_feed(root)
        elif root.nodeName == "opml":
            subscriptions = opml.Importer().import_content(content)
            return flatten(subscriptions)
        else:
            return None
    finally:
        dom.unlink()

def _get_subs_from_rss_channel(root):
    try:
        channel = root.getElementsByTagName("channel").pop()
        subscriptions = _get_subs_from_atom_link_construct(channel)
        if subscriptions is not None:
            return subscriptions
        else:
            link = channel.getElementsByTagName("link").pop()
            href = link.firstChild.data
            return _get_subs_from_reflexive_auto_discovery(
                href, "application/rss+xml")
    except (IndexError, AttributeError):
        pass

def _get_subs_from_atom_feed(root):
    try:
        subscriptions = _get_subs_from_atom_link_construct(root)
        if subscriptions is not None:
            return subscriptions
        else:
            link = _get_atom_link(root)
            rel = link.getAttribute("rel")
            if rel == "alternate":
                href = link.getAttribute("href")
                return _get_subs_from_reflexive_auto_discovery(
                    href, "application/atom+xml")
    except (IndexError, AttributeError):
        pass

def _get_subs_from_atom_link_construct(node):
    try:
        link = _get_atom_link(node)
        if link.getAttribute("rel") in ("self", "start"):
            href = link.getAttribute("href")
            return [{'type': 'feed', 'url': href}]
    except (IndexError, AttributeError):
        pass

ALT_RE = re.compile("rel=\"alternate\"")
HREF_RE = re.compile("href=\"([^\"]*)\"")

def _get_subs_from_reflexive_auto_discovery(url, ltype):
    try:
        urls = list()
        html = REFLEXIVE_AUTO_DISCOVERY_OPENER(url).read()
        for match in re.findall("<link[^>]+>", html):
            alt_match = ALT_RE.search(match)
            type_match = re.search("type=\"%s\"" % re.escape(ltype), match)
            href_match = HREF_RE.search(match)
            if None not in (alt_match, type_match, href_match):
                href = href_match.group(1)
                urls.append(href)
    except IOError:
        return []

    return [{'type': 'feed', 'url': url} for url in urls]

ATOM_SPEC = "http://www.w3.org/2005/Atom"

def _get_atom_link(node):
    return node.getElementsByTagNameNS(ATOM_SPEC, "link").pop()
