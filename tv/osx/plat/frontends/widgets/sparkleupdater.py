# Miro - an RSS based video player application
# Copyright (C) 2005, 2006, 2007, 2008, 2009, 2010, 2011
# Participatory Culture Foundation
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

import os
import objc
import logging
from Foundation import *

from miro import app
from miro import prefs
from miro.plat.frontends.widgets.threads import on_ui_thread

###############################################################################

bundlePath = '%s/Sparkle.framework' % Foundation.NSBundle.mainBundle().privateFrameworksPath()
objc.loadBundle('Sparkle', globals(), bundle_path=bundlePath)

###############################################################################

SUSkippedVersionPref = prefs.Pref(key="SUSkippedVersion", default='', platformSpecific=False)

updater = None
alerter = None

(
    SUInstallUpdateChoice,
    SURemindMeLaterChoice,
    SUSkipThisVersionChoice
) = range(3)

# Dummy NSURLDownload override so we can avoid checking the DSA key by
# pretending we got the download from a SSL-enabled source.
class DummyURLDownload(NSObject):
    @objc.signature("@@:")
    def request(self):
        return self.theRequest

    def initWithRequest_(self, request):
        self = self.init()
        self.theRequest = request
        return self

class MiroUpdateDriver(SUUIBasedUpdateDriver):
    @objc.signature("v@:@i")
    def updateAlert_finishedWithChoice_(self, alert, choice):
        if choice == SUInstallUpdateChoice:
            app.config.set(SUSkippedVersionPref, '')
        elif choice == SURemindMeLaterChoice:
            app.config.set(SUSkippedVersionPref, '')
        elif choice == SUSkipThisVersionChoice:
            suItem = objc.getInstanceVariable(self, 'updateItem')
            app.config.set(SUSkippedVersionPref, suItem.versionString())
        # Do whatever it is the superclass has to do.
        SUUIBasedUpdateDriver.updateAlert_finishedWithChoice_(self, alert,
                                                              choice)

    # NB: we override this because Sparkle 1.5 or above will require DSA
    # checking on all non-secure download.  (Secure = appcast + download
    # both transmitted via SSL).  We currently don't do this so need to trick
    # Sparkle into thinking we got it over SSL.
    @objc.signature("v@:@")
    def downloadDidFinish_(self, d):
        url = d.request().URL()
        temp_url = NSURL.alloc().initWithScheme_host_path_('https', url.host(),
                                                           url.path())
        appcast_url = objc.getInstanceVariable(self, 'appcastURL')
        temp_appcast_url = NSURL.alloc().initWithScheme_host_path_('https',
                                                           appcast_url.host(),
                                                           appcast_url.path())
        request = NSURLRequest.requestWithURL_(temp_url)
        fake_d = DummyURLDownload.alloc().initWithRequest_(request)

        objc.setInstanceVariable(self, 'appcastURL', temp_appcast_url, objc.YES)

        # Back to your regular scheduled programming ..
        SUUIBasedUpdateDriver.downloadDidFinish_(self, fake_d)

        # Restoring values to what they were previously.
        objc.setInstanceVariable(self, 'appcastURL', appcast_url, objc.YES)

###############################################################################

def setup():
    """ Instantiate the unique global MiroUpdater object."""
    global updater
    updater = SUUpdater.sharedUpdater()

@on_ui_thread
def handleNewUpdate(latest):
    """A new update has been found, the Sparkle framework will now take control
    and perform user interaction and automatic update on our behalf. Since the
    appcast has already been fetched and parsed by the crossplatform code,
    Sparkle is actually not used in *full* automatic mode so we have to
    short-circuit some of its code and manually call the parts we are
    interested in.
    
    This includes:
    - manually building a clean dictionary containing the RSS item
      corresponding to the latest version of the software and then
      creating an SUAppcastItem with this dictionary.

    - manually allocating and initializing a driver for the updater.  The
      driver determines the policy for doing updates (e.g. auto updates,
      UI, etc).  We use our own driver based on the SUUIBasedUpdateDriver,
      which has overrides for a couple of functions to bypass functionality
      which we don't implement yet, or if we have extra work that needs to be
      done (possibly by calling portable code).

    - manually setting ivar updateItem, host, appcastURL into the driver, which
      would normally be done by Sparkle internally.  Set the driver to be an
      ivar of the updater object, which was created at startup.  We ask the
      bridge to retain these for us, as they would be if they were done by
      Sparkle internally.  A bit hackish but it is the only way to make the
      Sparkle guts happy since we are creating things manually.

    - manually creating and calling an SUUpdateAlert object (which we must
      retain to prevent it to be automatically released by the Python
      garbage collector and therefore cause bad crashes).

    - Set the delegate of the alerter to be the driver - which will handle
      callbacks in response to state changes in the alerter.
    """
    if not _host_supported(latest):
        logging.warn("Update available but host system not supported.")
        return

    # If already running don't bother.
    global updater
    if updater.updateInProgress():
        # Update currently in progress.
        return

    dictionary = dict()
    _transfer(latest, 'title',            dictionary)
    _transfer(latest, 'pubdate',          dictionary, 'pubDate')
    _transfer(latest, 'description',      dictionary)
    _transfer(latest, 'releasenoteslink', dictionary, 'sparkle:releaseNotesLink')

    enclosure = latest['enclosures'][0]
    suEnclosure = dict()
    _transfer(enclosure, 'sparkle:dsaSignature',       suEnclosure)
    _transfer(enclosure, 'sparkle:md5Sum',             suEnclosure)
    _transfer(enclosure, 'sparkle:version',            suEnclosure)
    _transfer(enclosure, 'sparkle:shortVersionString', suEnclosure)
    _transfer(enclosure, 'url',                        suEnclosure)
    dictionary['enclosure'] = suEnclosure

    suItem = SUAppcastItem.alloc().initWithDictionary_(dictionary)
    skipped_version = app.config.get(SUSkippedVersionPref)
    
    if suItem.versionString() == skipped_version:
        logging.debug("Skipping update by user request")
    else:
        host = objc.getInstanceVariable(updater, 'host')

        global alerter # keep a reference around

        final = app.config.get(prefs.APP_FINAL_RELEASE)
        pref = prefs.AUTOUPDATE_URL if final else prefs.AUTOUPDATE_BETA_URL
        appcast_url = NSURL.alloc().initWithString_(app.config.get(pref))
        
        alerter = SUUpdateAlert.alloc().initWithAppcastItem_host_(suItem, host)
        driver = MiroUpdateDriver.alloc().initWithUpdater_(updater)
        objc.setInstanceVariable(driver, 'updateItem', suItem, True)
        objc.setInstanceVariable(driver, 'host', host, True)
        objc.setInstanceVariable(driver, 'appcastURL', appcast_url, True)
        objc.setInstanceVariable(updater, 'driver', driver, True)

        alerter.setDelegate_(driver)
        alerter.showWindow_(updater)


def _get_minimum_system_version(info):
    try:
        minimum = [int(i) for i in info['minimumsystemversion'].split('.')]
        if len(minimum) == 2:
            minimum.append(0)
        return minimum
    except KeyError:
        return [0, 0, 0]

def _get_host_version():
    version = [int(i) for i in os.uname()[2].split('.')]
    version[0] = version[0] - 4
    version.insert(0, 10)
    return version

def _test_host_version(host_version, minimum_version):
    return host_version >= minimum_version

def _host_supported(info):
    host_version = _get_host_version()
    minimum_version = _get_minimum_system_version(info)
    return _test_host_version(host_version, minimum_version)


def _transfer(source, skey, dest, dkey=None):
    if dkey is None:
        dkey = skey
    if skey in source:
        dest[dkey] = source[skey]

###############################################################################

