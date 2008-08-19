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

from miro import prefs
from miro import config
import logging
from miro import eventloop
from miro import feedparser
from miro import signals

from miro.httpclient import grabURL

checkInProgress = False

def checkForUpdates(upToDateCallback=None):
    """Trigger the version checking process
    """
    global checkInProgress
    if not checkInProgress:
        checkInProgress = True
        logging.info("Checking for updates...")
        url = config.get(prefs.AUTOUPDATE_URL)
        updateHandler = lambda data: _handleAppCast(data, upToDateCallback)
        errorHandler = _handleError
        grabURL(url, updateHandler, errorHandler)

def _handleError(error):
    """Error handler
    """
    global checkInProgress
    checkInProgress = False
    logging.warn("HTTP error while checking for updates")
    eventloop.addTimeout (86400, checkForUpdates, "Check for updates")

def _handleAppCast(data, upToDateCallback):
    """Handle appcast data when it's correctly fetched
    """
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
                signals.system.updateAvailable(latest)
            elif upToDateCallback:
                logging.info('Up to date. Notifying')
                upToDateCallback()
            else:
                logging.info('Up to date.')
        except:
            logging.warn("Error while handling appcast data.")
            import traceback
            traceback.print_exc()
    finally:
        global checkInProgress
        checkInProgress = False
        eventloop.addTimeout(86400, checkForUpdates, "Check for updates")

def _getItemForLatest(appcast):
    """Filter out non platform items, sort remaining from latest to oldest
    and return the item corresponding to the latest known version.
    """
    platform = config.get(prefs.APP_PLATFORM)
    rejectedItems = list()
    for item in appcast['entries']:
        rejectedEnclosures = list()
        for enclosure in item['enclosures']:
            if enclosure['dtv:platform'] != platform:
                rejectedEnclosures.append(enclosure)
            if enclosure['type'] != 'application/octet-stream':
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

def _getItemSerial(item):
    """Returns the serial of the first enclosure of the passed item
    """
    return int(item['enclosures'][0]['dtv:serial'])
