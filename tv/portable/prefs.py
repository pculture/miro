import os
import util

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
RUN_DTV_AT_STARTUP          = Pref( key='runAtStartup',          default=False, platformSpecific=False )
CHECK_CHANNELS_EVERY_X_MN   = Pref( key='checkChannelsEveryXMn', default=60,    platformSpecific=False )
LIMIT_UPSTREAM              = Pref( key='limitUpstream',         default=False, platformSpecific=False )
UPSTREAM_LIMIT_IN_KBS       = Pref( key='upstreamLimitInKBS',    default=12,    platformSpecific=False )
UPSTREAM_TORRENT_LIMIT      = Pref( key='upstreamTorrentLimit',  default=10,    platformSpecific=False )
PRESERVE_DISK_SPACE         = Pref( key='preserveDiskSpace',     default=False, platformSpecific=False )
PRESERVE_X_GB_FREE          = Pref( key='preserveXGBFree',       default=1,     platformSpecific=False )
EXPIRE_AFTER_X_DAYS         = Pref( key='expireAfterXDays',      default=6,     platformSpecific=False )
DOWNLOADS_TARGET            = Pref( key='DownloadsTarget',       default=8,     platformSpecific=False )
TORRENT_DOWNLOADS_TARGET    = Pref( key='TorrentDownloadsTarget',default=3,     platformSpecific=False )
MAX_MANUAL_DOWNLOADS        = Pref( key='MaxManualDownloads',    default=10,    platformSpecific=False )
VOLUME_LEVEL                = Pref( key='VolumeLevel',           default=1.0,   platformSpecific=False )
BT_MIN_PORT                 = Pref( key='BitTorrentMinPort',     default=8500,  platformSpecific=False )
BT_MAX_PORT                 = Pref( key='BitTorrentMaxPort',     default=8600,  platformSpecific=False )
UPLOAD_RATIO                = Pref( key='uploadRatio',           default=2.0,   platformSpecific=False )
STARTUP_TASKS_DONE          = Pref( key='startupTasksDone',      default=False, platformSpecific=False )
SINGLE_VIDEO_PLAYBACK_MODE  = Pref( key='singleVideoPlaybackMode',default=False,platformSpecific=False )
RESUME_VIDEOS_MODE          = Pref( key='resumeVideosMode',      default=True,  platformSpecific=False )

# Only used on particular platforms.
XINE_VIZ                    = Pref( key="xineViz",               default=u"goom",platformSpecific=False )

# These have a hardcoded default which can be overridden by setting an
# environment variable.

if 'DTV_CHANNELGUIDE_URL' in os.environ:
    effectiveChannelGuide = util.unicodify(os.environ['DTV_CHANNELGUIDE_URL'])
else:
    effectiveChannelGuide = u'https://channelguide.participatoryculture.org/'

if 'DTV_VIDEOBOMB_URL' in os.environ:
    effectiveVideobomb = util.unicodify(os.environ['DTV_VIDEOBOMB_URL'])
else:
    effectiveVideobomb = u'http://www.videobomb.com/api/submit_or_bomb'

if 'DTV_AUTOUPDATE_URL' in os.environ:
    effectiveAutoupdate = util.unicodify(os.environ['DTV_AUTOUPDATE_URL'])
else:
    effectiveAutoupdate = u'http://www.participatoryculture.org/democracy-appcast.xml'

CHANNEL_GUIDE_URL = Pref(key='ChannelGuideURL', default=effectiveChannelGuide,
                         platformSpecific=False)
VIDEOBOMB_URL     = Pref(key='VideobombURL',    default=effectiveVideobomb,
                         platformSpecific=False)
AUTOUPDATE_URL    = Pref(key='AutoupdateURL',   default=effectiveAutoupdate,
                         platformSpecific=False)
DONATE_URL        = Pref(key='DonateURL', default=u"http://www.getdemocracy.com/donate/",
                         platformSpecific=False)
HELP_URL          = Pref(key='HelpURL', default=u"http://www.getdemocracy.com/help/",
                         platformSpecific=False)
BUG_REPORT_URL    = Pref(key='ReportURL', default=u"https://develop.participatoryculture.org/trac/democracy/newticket",
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
    Pref(key='bugTrackerURL',      default=None, platformSpecific=False)
PUBLISHER = \
    Pref(key='publisher',         default=None, platformSpecific=False)
APP_VERSION = \
    Pref(key='appVersion',        default=None, platformSpecific=False)
APP_REVISION = \
    Pref(key='appRevision',       default=None, platformSpecific=False)
APP_PLATFORM = \
    Pref(key='appPlatform',       default=None, platformSpecific=False)
APP_SERIAL = \
    Pref(key='appSerial-unknown', default=u"0",  platformSpecific=False)
MOZILLA_LIB_PATH = \
    Pref(key='mozillaLibPath',    default=None, platformSpecific=False)
