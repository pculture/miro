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

import objc
import Foundation

from miro import prefs
from miro import config
from miro.plat.frontends.widgets.threads import on_ui_thread

###############################################################################

bundlePath = '%s/Sparkle.framework' % Foundation.NSBundle.mainBundle().privateFrameworksPath()
objc.loadBundle('Sparkle', globals(), bundle_path=bundlePath)

###############################################################################

class MiroHost (SUHost):
    
    def setObject_forUserDefaultsKey_(self, obj, key):
        descriptor = prefs.Pref(key=key, default='', platformSpecific=False)
        config.set(descriptor, obj)
        
    def objectForUserDefaultsKey_(self, key):
        descriptor = prefs.Pref(key=key, default='', platformSpecific=False)
        return config.get(descriptor)

###############################################################################

class MiroUpdateDriver (SUUIBasedUpdateDriver):

    def downloadDidFinish_(self, download):
        # WARNING: this bypasses the superclass DSA signature based security measures!
        # We might want to think about implementing them.
        # See: <http://sparkle.andymatuschak.org/documentation/pmwiki.php/Documentation/BasicSetup>
        self.extractUpdate()

###############################################################################

def setup():
    """ Instantiate the unique global SUUpdater object."""
    global suUpdater
    suUpdater = SUUpdater.sharedUpdater()
    suUpdater.setUpdateCheckInterval_(0)


@on_ui_thread
def handleNewUpdate(latest):
    """ A new update has been found, the Sparkle framework will now take control
    and perform user interaction and automatic update on our behalf. Since the
    appcast has already been fetched and parsed by the crossplatform code, Sparkle 
    is actually not used in *full* automatic mode so we have to short-circuit 
    some of its code and manually call the parts we are interested in.
    
    This includes:
    - manually building a clean dictionary containing the RSS item corresponding 
      to the latest version of the software and then creating an SUAppcastItem 
      with this dictionary.
    - manually setting the global updater 'updateItem' ivar to the SUAppcastItem
      instance we just created. This is slightly hackish, but this is the *only* 
      way to make it work correctly in our case, otherwise Sparkle will fail to
      download the update and throw a 'bad URL' error.
    - manually creating and calling an SUUpdateAlert object (which we must retain
      to prevent it to be automatically released by the Python garbage collector
      and therefore cause bad crashes).
    """
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
    suHost = MiroHost.alloc().initWithBundle_(None)

    global suDriver
    suDriver = MiroUpdateDriver.alloc().initWithUpdater_(None)
    objc.setInstanceVariable(suDriver, 'host', suHost, True)
    objc.setInstanceVariable(suDriver, 'updateItem', suItem, True)
    if not suDriver.itemContainsSkippedVersion_(suItem):
        suDriver.didFindValidUpdate()


def _transfer(source, skey, dest, dkey=None):
    if dkey is None:
        dkey = skey
    if skey in source:
        dest[dkey] = source[skey]

###############################################################################

