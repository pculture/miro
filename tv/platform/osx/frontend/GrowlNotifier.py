import objc
import Foundation

import prefs
import config

from gtcache import gettext as _

###############################################################################

DOWNLOAD_COMPLETE = u'Download Complete'
DOWNLOAD_FAILED = u'Download Failed'

###############################################################################

bundlePath = '%s/Growl.framework' % Foundation.NSBundle.mainBundle().privateFrameworksPath()
objc.loadBundle('Growl', globals(), bundle_path=bundlePath)

###############################################################################

def register():
    notifier = GrowlNotifier.alloc().init()
    GrowlApplicationBridge.setGrowlDelegate_(notifier)

def notifyDownloadComplete(title):
    GrowlApplicationBridge.notifyWithTitle_description_notificationName_iconData_priority_isSticky_clickContext_(
        _(u'Download Completed'),
        _(u'Download of video \'%s\' is finished.') % title,
        DOWNLOAD_COMPLETE,
        objc.nil,
        0,
        objc.NO,
        objc.nil)

def notifyDownloadFailed(title):
    GrowlApplicationBridge.notifyWithTitle_description_notificationName_iconData_priority_isSticky_clickContext_(
        _(u'Download Failed'),
        _(u'Download of video \'%s\' has failed.') % title,
        DOWNLOAD_FAILED,
        objc.nil,
        0,
        objc.NO,
        objc.nil)

###############################################################################

class GrowlNotifier (NSObject):
    
    def registrationDictionaryForGrowl(self):
        notifications = [DOWNLOAD_COMPLETE]
        info = {u'ApplicationName': unicode(config.get(prefs.LONG_APP_NAME)),
                u'AllNotifications': notifications, 
                u'DefaultNotifications': notifications}
        return info
        
###############################################################################
