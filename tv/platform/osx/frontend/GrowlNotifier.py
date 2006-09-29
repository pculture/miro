import objc
import Foundation

import prefs
import config

###############################################################################

DOWNLOAD_COMPLETE = 'Download Complete'
DOWNLOAD_FAILED = 'Download Failed'

###############################################################################

bundlePath = '%s/Growl.framework' % Foundation.NSBundle.mainBundle().privateFrameworksPath()
objc.loadBundle('Growl', globals(), bundle_path=bundlePath)

###############################################################################

def register():
    notifier = GrowlNotifier.alloc().init()
    GrowlApplicationBridge.setGrowlDelegate_(notifier)

def notifyDownloadComplete(title):
    GrowlApplicationBridge.notifyWithTitle_description_notificationName_iconData_priority_isSticky_clickContext_(
        'Download Completed',
        'Download of video \'%s\' is finished.' % title,
        DOWNLOAD_COMPLETE,
        objc.nil,
        0,
        objc.YES,
        objc.nil)

def notifyDownloadFailed(title):
    GrowlApplicationBridge.notifyWithTitle_description_notificationName_iconData_priority_isSticky_clickContext_(
        'Download Failed',
        'Download of video \'%s\' has failed.' % title,
        DOWNLOAD_FAILED,
        objc.nil,
        0,
        objc.YES,
        objc.nil)

###############################################################################

class GrowlNotifier (NSObject):
    
    def registrationDictionaryForGrowl(self):
        notifications = [DOWNLOAD_COMPLETE, DOWNLOAD_FAILED]
        info = {'ApplicationName': config.get(prefs.LONG_APP_NAME),
                'AllNotifications': notifications, 
                'DefaultNotifications': notifications}
        return info
        
###############################################################################
