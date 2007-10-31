# Miro - an RSS based video player application
# Copyright (C) 2005-2007 Participatory Culture Foundation
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

import prefs
import config
import dialogs
import logging
import eventloop
import feedparser
import signals

from httpclient import grabURL
from gtcache import gettext as _

checkInProgress = False

# Trigger the version checking process
def checkForUpdates(upToDateCallback=None):
    global checkInProgress
    if not checkInProgress:
        checkInProgress = True
        logging.info("Checking for updates...")
        url = config.get(prefs.AUTOUPDATE_URL)
        updateHandler = lambda data: _handleAppCast(data, upToDateCallback)
        errorHandler = _handleError
        grabURL(url, updateHandler, errorHandler)

# Error handler
def _handleError(error):
    global checkInProgress
    checkInProgress = False
    logging.warn("HTTP error while checking for updates")
    eventloop.addTimeout (86400, checkForUpdates, "Check for updates")

# Handle appcast data when it's correctly fetched
def _handleAppCast(data, upToDateCallback):
    try:
        try:
            appcast = feedparser.parse(data['body'])
            if appcast['bozo'] == '1':
                return

            upToDate = True
            latest = _getItemForLatest(appcast)
            if latest is not None:
                serial = int(config.get(prefs.APP_SERIAL))
                upToDate = (serial >= _getItemSerial(latest))
        
            if not upToDate:
                logging.info('New update available.')
                signals.system.update_available(latest)
            elif upToDateCallback:
                logging.info('Up to date. Notifying')
                upToDateCallback()
            else:
                logging.info('Up to date.')
        except:
            logging.warn("Error while handling appcast data.")
            import traceback; traceback.print_exc()
    finally:
        global checkInProgress
        checkInProgress = False
        eventloop.addTimeout (86400, checkForUpdates, "Check for updates")

# Filter out non platform items, sort remaining from latest to oldest and return
# the item corresponding to the latest known version.
def _getItemForLatest(appcast):
    platform = config.get(prefs.APP_PLATFORM)
    rejectedItems = list()
    for item in appcast['entries']:
        rejectedEnclosures = list()
        for enclosure in item['enclosures']:
            if enclosure['dtv:platform'] != platform:
                rejectedEnclosures.append(enclosure)
        for enclosure in rejectedEnclosures:
            item['enclosures'].remove(enclosure)
        if len(item['enclosures']) == 0:
            rejectedItems.append(item)
    for item in rejectedItems:
        appcast['entries'].remove(item)

    try:
        appcast['entries'].sort(key=_getItemSerial, reverse=True)
        return appcast['entries'][0]
    except:
        return None

# Returns the serial of the first enclosure of the passed item
def _getItemSerial(item):
    return int(item['enclosures'][0]['dtv:serial'])

