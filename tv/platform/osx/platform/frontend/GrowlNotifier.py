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

import objc
import Foundation

from miro import prefs
from miro import config

from miro.gtcache import gettext as _

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
