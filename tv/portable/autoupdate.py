import prefs
import config
import dialogs
import logging
import eventloop
import feedparser

from httpclient import grabURL
from gtcache import gettext as _

delegate = None
checkInProgress = False

# Pass in a connection to the frontend
def setDelegate(newDelegate):
    global delegate
    delegate = newDelegate

# Trigger the version checking process
def checkForUpdates(notifyIfUpToDate=False):
    global checkInProgress
    if not checkInProgress:
        checkInProgress = True
        logging.info("Checking for updates...")
        url = config.get(prefs.AUTOUPDATE_URL)
        updateHandler = lambda data: _handleAppCast(data, notifyIfUpToDate)
        errorHandler = _handleError
        grabURL(url, updateHandler, errorHandler)

# Error handler
def _handleError(error):
    global checkInProgress
    checkInProgress = False
    logging.warn("HTTP error while checking for updates: %s" % error)
    eventloop.addTimeout (86400, checkForUpdates, "Check for updates")

# Handle appcast data when it's correctly fetched
def _handleAppCast(data, notifyIfUpToDate):
    try:
        try:
            appcast = feedparser.parse(data['body'])
            if appcast['bozo'] == '1':
                return

            upToDate = True
            latest = _getItemForLatest(appcast)
            if latest is not None:
                serial = int(config.get(prefs.APP_SERIAL))
                upToDate = (serial > _getItemSerial(latest))
        
            if not upToDate:
                logging.info('New update available.')
                if hasattr(delegate, 'handleNewUpdate'):
                    delegate.handleNewUpdate(latest)
                else:
                    _handleNewUpdate(latest)
            elif notifyIfUpToDate:
                logging.info('Up to date. Notifying')
                _handleUpToDate()
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

# A new update is available, deal with it.
def _handleNewUpdate(item):
    url = item['enclosures'][0]['href']
    def callback(dialog):
        global delegate
        if dialog.choice == dialogs.BUTTON_DOWNLOAD:
            delegate.openExternalURL(url)
    summary = _("%s Version Alert") % (config.get(prefs.SHORT_APP_NAME), )
    message = _("A new version of %s is available. Would you like to download it now?") % (config.get(prefs.LONG_APP_NAME), )
    dlog = dialogs.ChoiceDialog(summary, message, dialogs.BUTTON_DOWNLOAD, dialogs.BUTTON_CANCEL)
    dlog.run(callback)

# We are up to date, notify user.
def _handleUpToDate():
    title = _('%s Version Check') % (config.get(prefs.SHORT_APP_NAME), )
    message = _('%s is up to date.') % (config.get(prefs.LONG_APP_NAME), )
    dialogs.MessageBoxDialog(title, message).run()
