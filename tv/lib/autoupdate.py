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

"""Checks the AUTOUPDATE_URL to see if there's a more recent version
of the application.

Call ``check_for_updates``.
"""

import logging

from miro import prefs
from miro import config
from miro import eventloop
from miro import feedparser
from miro import signals

from miro.httpclient import grabURL

check_in_progress = False

def check_for_updates(up_to_date_callback=None):
    """Checks the AUTOUPDATE_URL for the recent version.

    The ``up_to_date_callback`` is a function that should take no
    arguments and return nothing.
    """
    import miro.plat
    if miro.plat.AUTOUPDATE == False:
        logging.info("this platform has autoupdate disabled.  skipping.")
        return

    global check_in_progress
    if not check_in_progress:
        check_in_progress = True
        logging.info("Checking for updates...")
        url = config.get(prefs.AUTOUPDATE_URL)
        update_handler = lambda data: _handle_app_cast(data,
                                                       up_to_date_callback)
        error_handler = _handle_error
        grabURL(url, update_handler, error_handler)

def _handle_error(error):
    """Error handler"""
    global check_in_progress
    check_in_progress = False
    logging.warn("HTTP error while checking for updates %s", error)
    eventloop.add_timeout(86400, check_for_updates, "Check for updates")

def _handle_app_cast(data, up_to_date_callback):
    """Handle appcast data when it's correctly fetched
    """
    # python 2.4 requires that except and finally clauses be in different
    # try blocks.
    try:
        try:
            appcast = feedparser.parse(data['body'])
            if appcast['bozo'] == '1':
                return

            up_to_date = True
            latest = _get_item_for_latest(appcast)
            if latest is None:
                logging.info('No updates for this platform.')
                # this will go through the finally clause below
                return

            serial = int(config.get(prefs.APP_SERIAL))
            up_to_date = (serial >= _get_item_serial(latest))

            if not up_to_date:
                logging.info('New update available.')
                signals.system.update_available(latest)
            elif up_to_date_callback:
                logging.info('Up to date.  Notifying callback.')
                up_to_date_callback()
            else:
                logging.info('Up to date.')

        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            logging.exception("Error while handling appcast data.")

    finally:
        global check_in_progress
        check_in_progress = False
        eventloop.add_timeout(86400, check_for_updates, "Check for updates")

def _get_item_for_latest(appcast):
    """Filter out non platform items, sort remaining from latest to
    oldest and return the item corresponding to the latest known
    version.

    If there are no entries for this platform (this happens with
    Linux), then this returns None.
    """
    platform = config.get(prefs.APP_PLATFORM)
    rejected_items = []

    for item in appcast['entries']:
        rejected_enclosures = []
        for enclosure in item['enclosures']:
            if enclosure['dtv:platform'] != platform:
                rejected_enclosures.append(enclosure)
            if enclosure['type'] != 'application/octet-stream':
                rejected_enclosures.append(enclosure)
        for enclosure in rejected_enclosures:
            item['enclosures'].remove(enclosure)
        if len(item['enclosures']) == 0:
            rejected_items.append(item)

    for item in rejected_items:
        appcast['entries'].remove(item)

    # we've removed all entries that aren't relevant to this platform.
    # if there aren't any left, we return None and the caller can deal
    # with things.
    if not appcast['entries']:
        return None

    appcast['entries'].sort(key=_get_item_serial, reverse=True)
    return appcast['entries'][0]

def _get_item_serial(item):
    """Returns the serial of the first enclosure of the passed item
    """
    return int(item['enclosures'][0]['dtv:serial'])
