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
