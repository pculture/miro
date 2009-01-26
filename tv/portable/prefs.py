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

import os
from miro import util

class Pref:
    def __init__(self, **kwds):
        self.__dict__.update(kwds)

    def __eq__(self, other):
        return self.key == other.key
    def __ne__(self, other):
        return self.key != other.key

# These are normal user preferences.
MAIN_WINDOW_FRAME           = Pref( key='mainWindowFrame',       default=None,  platformSpecific=False )
LEFT_VIEW_SIZE              = Pref( key='leftViewSize',          default=None,  platformSpecific=False )
RIGHT_VIEW_SIZE             = Pref( key='rightViewSize',         default=None,  platformSpecific=False )
CHECK_CHANNELS_EVERY_X_MN   = Pref( key='checkChannelsEveryXMn', default=60,    platformSpecific=False )
LIMIT_UPSTREAM              = Pref( key='limitUpstream',         default=False, platformSpecific=False )
UPSTREAM_LIMIT_IN_KBS       = Pref( key='upstreamLimitInKBS',    default=12,    platformSpecific=False )
UPSTREAM_TORRENT_LIMIT      = Pref( key='upstreamTorrentLimit',  default=10,    platformSpecific=False )
LIMIT_DOWNSTREAM_BT         = Pref( key='limitDownstreamBT',     default=False, platformSpecific=False )
DOWNSTREAM_BT_LIMIT_IN_KBS  = Pref( key='downstreamBTLimitInKBS', default=200,   platformSpecific=False )
LIMIT_CONNECTIONS_BT = Pref( key='limitConnectionsBT',     default=False, platformSpecific=False )
CONNECTION_LIMIT_BT_NUM  = Pref( key='connectionLimitBTNum', default=100,   platformSpecific=False )
PRESERVE_DISK_SPACE         = Pref( key='preserveDiskSpace',     default=True,  platformSpecific=False )
PRESERVE_X_GB_FREE          = Pref( key='preserveXGBFree',       default=0.2,   platformSpecific=False )
EXPIRE_AFTER_X_DAYS         = Pref( key='expireAfterXDays',      default=6,     platformSpecific=False )
DOWNLOADS_TARGET            = Pref( key='DownloadsTarget',       default=8,     platformSpecific=False ) # max auto downloads
MAX_MANUAL_DOWNLOADS        = Pref( key='MaxManualDownloads',    default=10,    platformSpecific=False )
VOLUME_LEVEL                = Pref( key='VolumeLevel',           default=1.0,   platformSpecific=False )
BT_MIN_PORT                 = Pref( key='BitTorrentMinPort',     default=8500,  platformSpecific=False )
BT_MAX_PORT                 = Pref( key='BitTorrentMaxPort',     default=8600,  platformSpecific=False )
UPLOAD_RATIO                = Pref( key='uploadRatio',           default=2.0,   platformSpecific=False )
LIMIT_UPLOAD_RATIO          = Pref( key='limitUploadRatio',      default=False, platformSpecific=False )
STARTUP_TASKS_DONE          = Pref( key='startupTasksDone',      default=False, platformSpecific=False )
SINGLE_VIDEO_PLAYBACK_MODE  = Pref( key='singleVideoPlaybackMode', default=False, platformSpecific=False )
PLAY_DETACHED               = Pref( key='detachedPlaybackMode',  default=False, platformSpecific=False )
DETACHED_WINDOW_FRAME       = Pref( key='detachedWindowFrame',   default=None,  platformSpecific=False )
RESUME_VIDEOS_MODE          = Pref( key='resumeVideosMode',      default=True,  platformSpecific=False )
WARN_IF_DOWNLOADING_ON_QUIT = Pref( key='warnIfDownloadingOnQuit', default=True, platformSpecific=False )
TRUNCATE_CHANNEL_AFTER_X_ITEMS = Pref( key='TruncateChannelAFterXItems',  default=1000, platformSpecific=False)
MAX_OLD_ITEMS_DEFAULT       = Pref( key='maxOldItemsDefault',    default=20,    platformSpecific=False)
USE_UPNP                    = Pref( key='useUpnp',               default=True,  platformSpecific=False )
BT_ENC_REQ                  = Pref( key='BitTorrentEncReq',      default=False, platformSpecific=False )
CHANNEL_AUTO_DEFAULT        = Pref( key='ChannelAutoDefault',    default=u"new", platformSpecific=False )
FLASH_REQUEST_COUNT         = Pref( key='flashRequestCount',     default=0,     platformSpecific=False )

# This doesn't need to be defined on the platform, but it can be overridden there if the platform wants to.
SHOW_ERROR_DIALOG           = Pref( key='showErrorDialog',       default=True,  platformSpecific=True )

# this is the name of the last search engine used
LAST_SEARCH_ENGINE = \
    Pref(key='LastSearchEngine', default=u"all", platformSpecific=False)
# comma-separated list of search engine names; see searchengines.py for more information
SEARCH_ORDERING = \
    Pref(key='SearchOrdering', default=None, platformSpecific=False)

# These have a hardcoded default which can be overridden by setting an
# environment variable.

if 'DTV_CHANNELGUIDE_URL' in os.environ:
    effectiveChannelGuide = util.unicodify(os.environ['DTV_CHANNELGUIDE_URL'])
else:
    effectiveChannelGuide = u'https://www.miroguide.com/'

if 'DTV_CHANNELGUIDE_FIRST_TIME_URL' in os.environ:
    effectiveChannelGuideFirstTime = util.unicodify(os.environ['DTV_CHANNELGUIDE_FIRST_TIME_URL'])
else:
    effectiveChannelGuideFirstTime = u'https://www.miroguide.com/firsttime'

if 'DTV_SHARE_URL' in os.environ:
    effectiveShare = util.unicodify(os.environ['DTV_SHARE_URL'])
else:
    effectiveShare = u'https://www.miroguide.com/share'

if 'DTV_AUTOUPDATE_URL' in os.environ:
    effectiveAutoupdate = util.unicodify(os.environ['DTV_AUTOUPDATE_URL'])
else:
    effectiveAutoupdate = u'http://www.participatoryculture.org/democracy-appcast.xml'

CHANNEL_GUIDE_URL = Pref(key='ChannelGuideURL', default=effectiveChannelGuide,
                         platformSpecific=False)
CHANNEL_GUIDE_FIRST_TIME_URL = Pref(key='ChannelGuideFirstTimeURL', default=effectiveChannelGuideFirstTime,
                         platformSpecific=False)
CHANNEL_GUIDE_ALLOWED_URLS = Pref(key='ChannelGuideAllowedURLs',
                              default='http://pagead2.googlesyndication.com/ '
                              'http://www.google.com/ '
                              'http://www.googleadservices.com',
                              platformSpecific=False)
ADDITIONAL_CHANNEL_GUIDES = Pref(key='additionalChannelGuides', default='',
                                  platformSpecific=False)
SHARE_URL         = Pref(key='ShareURL',        default=effectiveShare,
                         platformSpecific=False)
AUTOUPDATE_URL    = Pref(key='AutoupdateURL',   default=effectiveAutoupdate,
                         platformSpecific=False)
DONATE_URL        = Pref(key='DonateURL', default=u"http://www.getmiro.com/donate/",
                         platformSpecific=False)
HELP_URL          = Pref(key='HelpURL', default=u"http://www.getmiro.com/help/",
                         platformSpecific=False)
BUG_REPORT_URL    = Pref(key='ReportURL', default=u"http://www.getmiro.com/bug.html",
                         platformSpecific=False)
TRANSLATE_URL     = Pref(key='TranslateURL', default=u"https://translations.launchpad.net/democracy/trunk/+pots/democracyplayer",
                         platformSpecific=False)
PLANET_URL        = Pref(key='PlanetURL', default=u"http://planet.getmiro.com/",
                         platformSpecific=False)

# These can be safely ignored on platforms without minimize to tray
MINIMIZE_TO_TRAY = \
    Pref(key='MinimizeToTray',   default=True, platformSpecific=False)
MINIMIZE_TO_TRAY_ASK_ON_CLOSE = \
    Pref(key='MinimizeToTrayAskOnClose', default=True, platformSpecific=False)

# These are computed by special platform code.
RUN_AT_STARTUP     = Pref( key='RunAtStartup',  default=False,  platformSpecific=True )
MOVIES_DIRECTORY = \
    Pref(key='MoviesDirectory',  default=None, platformSpecific=True)
NON_VIDEO_DIRECTORY = \
    Pref(key='NonVideoDirectory',  default=None, platformSpecific=True)
SUPPORT_DIRECTORY = \
    Pref(key='SupportDirectory', default=None, platformSpecific=True)
ICON_CACHE_DIRECTORY = \
    Pref(key='IconCacheDirectory', default=None, platformSpecific=True)
DB_PATHNAME = \
    Pref(key='DBPathname',       default=None, platformSpecific=True)
BSDDB_PATHNAME = \
    Pref(key='BSDDBPathname',    default=None, platformSpecific=True)
SQLITE_PATHNAME = \
    Pref(key='SQLLitePathname',    default=None, platformSpecific=True)
LOG_PATHNAME = \
    Pref(key='LogPathname',      default=None, platformSpecific=True)
DOWNLOADER_LOG_PATHNAME = \
    Pref(key='DownloaderLogPathname', default=None, platformSpecific=True)
GETTEXT_PATHNAME = \
    Pref(key='GetTextPathname', default=None, platformSpecific=True)
HTTP_PROXY_SCHEME = \
    Pref(key='HttpProxyScheme', default='http', platformSpecific=True)
HTTP_PROXY_ACTIVE = \
    Pref(key='HttpProxyActive', default=False, platformSpecific=True)
HTTP_PROXY_HOST = \
    Pref(key='HttpProxyHost',   default=u"", platformSpecific=True)
HTTP_PROXY_PORT = \
    Pref(key='HttpProxyPort',   default=80, platformSpecific=True)
HTTP_PROXY_IGNORE_HOSTS = \
    Pref(key='HttpProxyIgnoreHosts', default=[], platformSpecific=True)
HTTP_PROXY_AUTHORIZATION_ACTIVE = \
    Pref(key='HttpProxyAuthorizationActive', default=False, platformSpecific=True)
HTTP_PROXY_AUTHORIZATION_USERNAME = \
    Pref(key='HttpProxyAuthorizationUsername',   default=u"", platformSpecific=True)
HTTP_PROXY_AUTHORIZATION_PASSWORD = \
    Pref(key='HttpProxyAuthorizationPassword',   default=u"", platformSpecific=True)

# These are normally read from resources/app.config.
SHORT_APP_NAME = \
    Pref(key='shortAppName',      default=None, platformSpecific=False)
LONG_APP_NAME = \
    Pref(key='longAppName',       default=None, platformSpecific=False)
PROJECT_URL = \
    Pref(key='projectURL',        default=None, platformSpecific=False)
HELP_URL = \
    Pref(key='helpURL',           default=None, platformSpecific=False)
RECOMMEND_URL = \
    Pref(key='recommendURL',      default=None, platformSpecific=False)
BUG_TRACKER_URL = \
    Pref(key='bugTrackerURL',     default=None, platformSpecific=False)
PUBLISHER = \
    Pref(key='publisher',         default=None, platformSpecific=False)
COPYRIGHT = \
    Pref(key='copyright',         default=None, platformSpecific=False)
APP_VERSION = \
    Pref(key='appVersion',        default=None, platformSpecific=False)
APP_REVISION = \
    Pref(key='appRevision',       default=None, platformSpecific=False)
APP_REVISION_NUM = \
    Pref(key='appRevisionNum',    default=None, platformSpecific=False)
APP_PLATFORM = \
    Pref(key='appPlatform',       default=None, platformSpecific=False)
APP_SERIAL = \
    Pref(key='appSerial-unknown', default=u"0",  platformSpecific=False)
MOZILLA_LIB_PATH = \
    Pref(key='mozillaLibPath',    default=None, platformSpecific=False)
BUILD_MACHINE = \
    Pref(key='buildMachine',      default=None, platformSpecific=False)
BUILD_TIME = \
    Pref(key='buildTime',         default=None, platformSpecific=False)
MAXIMIZE_ON_FIRST_RUN = \
    Pref(key='maximizeOnFirstRun',default=None, platformSpecific=False)
DEFAULT_CHANNELS_FILE = \
    Pref(key='defaultChannelsFile',default=None, platformSpecific=False)
THEME_NAME = \
    Pref(key='themeName',default=None, platformSpecific=False)
OPEN_FOLDER_ON_STARTUP = \
    Pref(key='openFolderOnStartup',default=None, platformSpecific=False)
OPEN_CHANNEL_ON_STARTUP = \
    Pref(key='openChannelOnStartup',default=None, platformSpecific=False)
