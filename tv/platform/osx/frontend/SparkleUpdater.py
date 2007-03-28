import objc
import Foundation

import platformutils

###############################################################################

bundlePath = '%s/Sparkle.framework' % Foundation.NSBundle.mainBundle().privateFrameworksPath()
objc.loadBundle('Sparkle', globals(), bundle_path=bundlePath)

###############################################################################

def setup():
    """ Instantiate the unique global SUUpdater object."""
    global updater
    updater = SUUpdater.alloc().init()
    updater.scheduleCheckWithInterval_(0)


@platformutils.onMainThread
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

    global updater
    objc.setInstanceVariable(updater, 'updateItem', suItem, True)

    alerter = SUUpdateAlert.alloc().initWithAppcastItem_(suItem)
    alerter.setDelegate_(updater)
    alerter.showWindow_(updater)
    alerter.retain()


def _transfer(source, skey, dest, dkey=None):
    if dkey is None:
        dkey = skey
    if skey in source:
        dest[dkey] = source[skey]

###############################################################################

