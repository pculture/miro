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

"""``miro.prefs`` -- Defines :class:`Pref` and lists global preferences.
"""

import os
from miro import util

class Pref:
    """Class for defining preferences.  Preferences are defined using
    keywords:

    * **key** -- the name of the key--must be unique among all preferences
    * **default** -- the default value to use
    * **platformSpecific** -- whether or not this is platform specific;
      this should usually be False
    * **possible_values** -- a list of possible values for this preference;
      if the saved value gets corrupted for some reason and therefore does not
      correspond to any of the possible values, the failsafe is picked instead.
    * **failsafe_value** -- value to be used in case of corruption (see above).

    Pref example::

        FOO = Pref(key="foo", default=None, platformSpecific=False)
    """
    def __init__(self, key, default, platformSpecific, possible_values=None, failsafe_value=None):
        self.key = key
        self.default = default
        self.platformSpecific = platformSpecific
        self.possible_values = possible_values
        self.failsafe_value = failsafe_value
    def __eq__(self, other):
        return self.key == other.key
    def __ne__(self, other):
        return self.key != other.key

# These are normal user preferences.
MAIN_WINDOW_FRAME           = Pref(key='mainWindowFrame',       default=None,  platformSpecific=False)
LEFT_VIEW_SIZE              = Pref(key='leftViewSize',          default=None,  platformSpecific=False)
RIGHT_VIEW_SIZE             = Pref(key='rightViewSize',         default=None,  platformSpecific=False)
CHECK_CHANNELS_EVERY_X_MN   = Pref(key='checkChannelsEveryXMn', default=60,    platformSpecific=False)
LIMIT_UPSTREAM              = Pref(key='limitUpstream',         default=False, platformSpecific=False)
UPSTREAM_LIMIT_IN_KBS       = Pref(key='upstreamLimitInKBS',    default=12,    platformSpecific=False)
UPSTREAM_TORRENT_LIMIT      = Pref(key='upstreamTorrentLimit',  default=10,    platformSpecific=False)
LIMIT_DOWNSTREAM_BT         = Pref(key='limitDownstreamBT',     default=False, platformSpecific=False)
DOWNSTREAM_BT_LIMIT_IN_KBS  = Pref(key='downstreamBTLimitInKBS', default=200,   platformSpecific=False)
LIMIT_CONNECTIONS_BT        = Pref(key='limitConnectionsBT',     default=False, platformSpecific=False)
CONNECTION_LIMIT_BT_NUM     = Pref(key='connectionLimitBTNum', default=100,   platformSpecific=False)
PRESERVE_DISK_SPACE         = Pref(key='preserveDiskSpace',     default=True,  platformSpecific=False)
PRESERVE_X_GB_FREE          = Pref(key='preserveXGBFree',       default=0.2,   platformSpecific=False)
EXPIRE_AFTER_X_DAYS         = Pref(key='expireAfterXDays',      default=6,     platformSpecific=False,
                                   possible_values=[1,3,6,10,30,-1], failsafe_value=-1)
DOWNLOADS_TARGET            = Pref(key='DownloadsTarget',       default=4,     platformSpecific=False) # max auto downloads
MAX_MANUAL_DOWNLOADS        = Pref(key='MaxManualDownloads',    default=5,    platformSpecific=False)
VOLUME_LEVEL                = Pref(key='VolumeLevel',           default=1.0,   platformSpecific=False)
BT_MIN_PORT                 = Pref(key='BitTorrentMinPort',     default=8500,  platformSpecific=False)
BT_MAX_PORT                 = Pref(key='BitTorrentMaxPort',     default=8600,  platformSpecific=False)
UPLOAD_RATIO                = Pref(key='uploadRatio',           default=2.0,   platformSpecific=False)
LIMIT_UPLOAD_RATIO          = Pref(key='limitUploadRatio',      default=False, platformSpecific=False)
STARTUP_TASKS_DONE          = Pref(key='startupTasksDone',      default=False, platformSpecific=False)
SINGLE_VIDEO_PLAYBACK_MODE  = Pref(key='singleVideoPlaybackMode', default=False, platformSpecific=False)
PLAY_DETACHED               = Pref(key='detachedPlaybackMode',  default=False, platformSpecific=False)
DETACHED_WINDOW_FRAME       = Pref(key='detachedWindowFrame',   default=None,  platformSpecific=False)
RESUME_VIDEOS_MODE          = Pref(key='resumeVideosMode',      default=True,  platformSpecific=False)
PLAY_IN_MIRO                = Pref(key='playInMiro',            default=True,  platformSpecific=False)
WARN_IF_DOWNLOADING_ON_QUIT = Pref(key='warnIfDownloadingOnQuit', default=True, platformSpecific=False)
WARN_IF_CONVERTING_ON_QUIT  = Pref(key='warnIfConvertingOnQuit', default=True, platformSpecific=False)
TRUNCATE_CHANNEL_AFTER_X_ITEMS = Pref(key='TruncateChannelAFterXItems',  default=1000, platformSpecific=False)
MAX_OLD_ITEMS_DEFAULT       = Pref(key='maxOldItemsDefault',    default=20,    platformSpecific=False)
USE_UPNP                    = Pref(key='useUpnp',               default=True,  platformSpecific=False)
BT_ENC_REQ                  = Pref(key='BitTorrentEncReq',      default=False, platformSpecific=False)
CHANNEL_AUTO_DEFAULT        = Pref(key='ChannelAutoDefault',    default=u"new", platformSpecific=False)
FLASH_REQUEST_COUNT         = Pref(key='flashRequestCount',     default=0,     platformSpecific=False)
ENABLE_SUBTITLES            = Pref(key='enableSubtitles',       default=False, platformSpecific=False)
SUBTITLE_ENCODING           = Pref(key='subtitleEncoding',      default=None,  platformSpecific=False)
SUBTITLE_FONT               = Pref(key='subtitleFont',          default=None,  platformSpecific=False)
# language setting: "system" uses system default; all other languages are overrides
LANGUAGE                    = Pref(key='language',              default="system", platformSpecific=False)
MAX_CONCURRENT_CONVERSIONS  = Pref(key='maxConcurrentConversions', default=1, platformSpecific=False)

# This doesn't need to be defined on the platform, but it can be overridden there if the platform wants to.
SHOW_ERROR_DIALOG           = Pref(key='showErrorDialog',       default=True,  platformSpecific=True)

# this is the name of the last search engine used
LAST_SEARCH_ENGINE = \
    Pref(key='LastSearchEngine', default=u"all", platformSpecific=False)
# comma-separated list of search engine names; see searchengines.py for more information
SEARCH_ORDERING = \
    Pref(key='SearchOrdering', default=None, platformSpecific=False)


# These have a hardcoded default which can be overridden by setting an
# environment variable.

def get_from_environ(key, default):
    if key in os.environ:
        return util.unicodify(os.environ[key])

    return default

default_guide = get_from_environ('DTV_CHANNELGUIDE_URL',
                                 u'https://www.miroguide.com/')
default_guide_first_time = get_from_environ('DTV_CHANNELGUIDE_FIRST_TIME_URL',
                                            u'https://www.miroguide.com/firsttime')
default_share = get_from_environ('DTV_SHARE_URL',
                                 u'https://www.miroguide.com/share')
default_autoupdate = get_from_environ('DTV_AUTOUPDATE_URL',
                                      u'http://www.participatoryculture.org/democracy-appcast.xml')

CHANNEL_GUIDE_URL = Pref(key='ChannelGuideURL', default=default_guide,
                         platformSpecific=False)
CHANNEL_GUIDE_FIRST_TIME_URL = Pref(key='ChannelGuideFirstTimeURL', default=default_guide_first_time,
                         platformSpecific=False)
CHANNEL_GUIDE_ALLOWED_URLS = Pref(key='ChannelGuideAllowedURLs',
                              default='http://pagead2.googlesyndication.com/ '
                              'http://www.google.com/ '
                              'http://www.googleadservices.com',
                              platformSpecific=False)
ADDITIONAL_CHANNEL_GUIDES = Pref(key='additionalChannelGuides', default='',
                                  platformSpecific=False)
SHARE_URL         = Pref(key='ShareURL',        default=default_share,
                         platformSpecific=False)
AUTOUPDATE_URL    = Pref(key='AutoupdateURL',   default=default_autoupdate,
                         platformSpecific=False)
DONATE_URL        = Pref(key='DonateURL', default=u"http://www.getmiro.com/donate/",
                         platformSpecific=False)
TROUBLESHOOT_URL  = Pref(key='TroubleshootURL', default=u"http://manual.getmiro.com/troubleshooting.html",
                         platformSpecific=False)
HELP_URL          = Pref(key='HelpURL', default=u"http://www.getmiro.com/help/",
                         platformSpecific=False)
BUG_REPORT_URL    = Pref(key='ReportURL', default=u"http://www.getmiro.com/bug.html",
                         platformSpecific=False)
TRANSLATE_URL     = Pref(key='TranslateURL', default=u"http://develop.participatoryculture.org/index.php/TranslationGuide",
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
SQLITE_PATHNAME = \
    Pref(key='SQLLitePathname',    default=None, platformSpecific=True)
LOG_PATHNAME = \
    Pref(key='LogPathname',      default=None, platformSpecific=True)
DOWNLOADER_LOG_PATHNAME = \
    Pref(key='DownloaderLogPathname', default=None, platformSpecific=True)
GETTEXT_PATHNAME = \
    Pref(key='GetTextPathname', default=None, platformSpecific=True)
ENABLED_EXTENSIONS = \
    Pref(key='EnabledExtensions', default=[], platformSpecific=False)
DISABLED_EXTENSIONS = \
    Pref(key='DisabledExtensions', default=[], platformSpecific=False)
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
TRADEMARK = \
    Pref(key='trademark',         default=None, platformSpecific=False)
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
