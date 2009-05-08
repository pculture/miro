# Miro - an RSS based video player application
# Copyright (C) 2005-2009 Participatory Culture Foundation
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

from miro.xhtmltools import urlencode
from miro import httpclient
from miro import singleclick
from miro import feed
from miro import folder
from miro import guide

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
                    'feed', 'link', 'trackback', 'section')
# =========================================================================

def get_subscriptions_from_query(subscription_type, query):
    subscriptions = []
    # the query string shouldn't be a unicode.  if we pass it in as a unicode
    # then parse_qs returns unicode values which aren't properly converted
    # and then we end up with boxes instead of ' and " characters.
    query = str(query)
    parsedQuery = cgi.parse_qs(query)
    for key, value in parsedQuery.items():
        match = re.match(r'^url(\d+)$', key)
        if match:
            subscription = {'type': subscription_type, 'url': unicode(value[0], 'utf8')}
            subscriptions.append(subscription)
            urlId = match.group(1)
            for key2 in ADDITIONAL_KEYS:
                if '%s%s' % (key2, urlId) in parsedQuery:
                    value = unicode(parsedQuery['%s%s' % (key2, urlId)][0], "utf-8")
                    if key2 == 'type':
                        subscription['mime_type'] = value
                    else:
                        subscription[key2] = value
    return subscriptions

def is_subscribe_link(url):
    """Returns whether this is a subscribe url or not.

    It's pretty hearty and shouldn't throw exceptions.
    """
    if not isinstance(url, basestring):
        return False
    try:
        scheme, host, path, params, query, frag = urlparse.urlparse(url)
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        logging.warn("is_subscribe_link: Error parsing '%s'\n%s", url,
                traceback.format_exc())
        return False
    return host in SUBSCRIBE_HOSTS

def find_subscribe_links(url):
    """Given a URL, test if it's trying to subscribe the user using
    subscribe.getdemocracy.com.  Returns the list of parsed URLs.
    """
    try:
        scheme, host, path, params, query, frag = urlparse.urlparse(url)
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        logging.warn("find_subscribe_links: Error parsing '%s'\n%s", url,
                traceback.format_exc())
        return []

    if host not in SUBSCRIBE_HOSTS:
        return []
    if path in ('/', '/opml.php'):
        return get_subscriptions_from_query('feed', query)
    elif path in ('/download.php','/download','/download/'):
        return get_subscriptions_from_query('download', query)
    elif path in ('/site.php', '/site', '/site/'):
        return get_subscriptions_from_query('site', query)
    else:
        return [{'type': 'feed', 'url': urllib2.unquote(path[1:])}]


class Subscriber(object):
    """
    This class represents the common functionality of the subscription handlers
    (OPML import, one-click links in the Guide, and command-line additions).
    """

    def _get_section(self, subscription):
        section = subscription.get('section', None)
        if section not in (u'audio', u'video'):
            section = u'video'
        return section

    def add_subscriptions(self, subscriptions_list, parent_folder=None):
        """
        We loop through the list of subscriptions, creating things as we go (if
        needed).  We also keep track of what we've added.

        Each type (folder, feed, site, download) gets dispatched to one of our
        methods.  Each dispatcher returns True if it's added the subscription,
        anything else if it's been ignored for some reason (generally because
        it's already present in the DB).

        The only exception to this is the 'folder' type, which has the same
        return signature as this method.

        Returns a tuple of dictionaries (added, ignored).  Each dictionary maps
        a subscription type (feed, site, download) to the number of
        added/ignored items in this subscription.
        """
        added = {}
        ignored = {}
        for subscription in subscriptions_list:
            subscription_type = subscription['type']
            handler = getattr(self, 'handle_%s' % subscription_type, None)
            if handler:
                trackback = subscription.get('trackback')
                if trackback:
                    httpclient.grabURL(trackback, lambda x: None, lambda x: None)
                ret = handler(subscription, parent_folder)
                if ret:
                    if subscription_type == 'folder':
                        for key, value in ret[0].items():
                            added.setdefault(key, [])
                            added[key].extend(value)
                        for key, value in ret[1].items():
                            ignored.setdefault(key, [])
                            ignored[key].extend(value)
                    else:
                        added.setdefault(subscription_type, [])
                        added[subscription_type].append(subscription)
                else:
                    ignored.setdefault(subscription_type, [])
                    ignored[subscription_type].append(subscription)
            else:
                raise ValueError('unknown subscription type: %s' % subscription_type)
        return added, ignored

    def handle_folder(self, folder_dict, parent_folder):
        """
        Folder subscriptions look like:

        {
            'type': 'folder',
            'title': name of the folder,
            'section': one of ['audio', 'video'],
            'children': a list of sub-feeds
        }
        """
        assert parent_folder is None, "no nested folders"
        title = folder_dict['title']
        section = self._get_section(folder_dict)
        obj = folder.ChannelFolder(title, section)
        return self.add_subscriptions(folder_dict['children'], obj)

    def handle_feed(self, feed_dict, parent_folder):
        """
        Feed subscriptions look like:

        {
            'type': 'feed',
            'url': URL of the RSS/Atom feed
            'title': name of the feed (optional),
            'section': one of ['audio', 'video'] (ignored if it's in a folder),
            'search_term': terms for which this feed is a search (optional),
            'auto_download': one of 'all', 'new', 'off' (optional),
            'expiry_time': one of 'system', 'never', an integer of hours (optional),
        }
        """
        url = feed_dict['url']

        search_term = feed_dict.get('search_term')
        if search_term:
            url = u"dtv:searchTerm:%s?%s" % (urlencode(url), urlencode(search_term))

        f = feed.get_feed_by_url(url)
        if f is None:
            if parent_folder:
                section = parent_folder.section
            else:
                section = self._get_section(feed_dict)

            f = feed.Feed(url, section=section)
            title = feed_dict.get('title')
            if title is not None and title != '':
                f.set_title(title)
            auto_download_mode = feed_dict.get('auto_download')
            if auto_download_mode is not None and auto_download_mode in ['all',
                    'new', 'off']:
                f.set_auto_download_mode(auto_download_mode)
            expiry_time = feed_dict.get('expiry_time')
            if expiry_time is not None and expiry_time != '':
                if expiry_time == 'system':
                    f.setExpiration(u'system', 0)
                elif expiry_time == 'never':
                    f.setExpiration(u'never', 0)
                else:
                    f.setExpiration(u'feed', expiry_time)
            if parent_folder is not None:
                f.set_folder(parent_folder)
            return True
        else:
            return False

    def handle_site(self, site_dict, parent_folder):
        """
        Site subscriptions look like:

        {
            'type': 'site',
            'url': URL of the site
            'title': name of the site (optional),
        }
        """
        assert parent_folder is None, "no folders in site section"
        url = site_dict['url']
        if guide.get_guide_by_url(url) is None:
            new_guide = guide.ChannelGuide(url, [u'*'])
            title = site_dict.get('title')
            if title is not None and title != url:
                new_guide.set_title(title)
            return True
        else:
            return False

    def handle_download(self, download_dict, parent_folder):
        """
        Download subscriptions look like:

        {
            'type': 'download',
            'url': URL of the file to download
            'title': name of the download (optional),
            'link': page representing this download (optional),
            'feed': RSS feed containing this item (optional),
            'mime_type': the MIME type of the item (optional),
            'description': a description of the item (optional),
            'thumbnail': a thumbnail image for the item (optional),
            'length': the length in seconds of the item (optional)
        }
        """
        assert parent_folder is None, "no folders in downloads"
        url = download_dict['url']
        mime_type = download_dict.get('mime_type', 'video/x-unknown')
        entry = singleclick._build_entry(url, mime_type, download_dict)
        singleclick.download_video(entry)
        return False # it's all async, so we don't know right away
