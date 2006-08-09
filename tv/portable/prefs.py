import os

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
LIMIT_UPSTREAM              = Pref( key='limitUpstream',         default=True,  platformSpecific=False )
UPSTREAM_LIMIT_IN_KBS       = Pref( key='upstreamLimitInKBS',    default=4,     platformSpecific=False )
PRESERVE_DISK_SPACE         = Pref( key='preserveDiskSpace',     default=False, platformSpecific=False )
PRESERVE_X_GB_FREE          = Pref( key='preserveXGBFree',       default=1,     platformSpecific=False )
EXPIRE_AFTER_X_DAYS         = Pref( key='expireAfterXDays',      default=6,     platformSpecific=False )
DOWNLOADS_TARGET            = Pref( key='DownloadsTarget',       default=4,     platformSpecific=False )
TORRENT_DOWNLOADS_TARGET    = Pref( key='TorrentDownloadsTarget',default=3,     platformSpecific=False )
MAX_MANUAL_DOWNLOADS        = Pref( key='MaxManualDownloads',    default=10,    platformSpecific=False )
VOLUME_LEVEL                = Pref( key='VolumeLevel',           default=1.0,   platformSpecific=False )
BT_MIN_PORT                 = Pref( key='BitTorrentMinPort',     default=6980,  platformSpecific=False )
BT_MAX_PORT                 = Pref( key='BitTorrentMaxPort',     default=6999,  platformSpecific=False )
UPLOAD_RATIO                = Pref( key='uploadRatio',           default=2.0,   platformSpecific=False )
STARTUP_TASKS_DONE          = Pref( key='startupTasksDone',      default=False, platformSpecific=False )

# These have a hardcoded default which can be overridden by setting an
# environment variable.

if 'DTV_CHANNELGUIDE_URL' in os.environ:
    effectiveChannelGuide = os.environ['DTV_CHANNELGUIDE_URL']
else:
    effectiveChannelGuide = 'https://channelguide.participatoryculture.org/'

if 'DTV_VIDEOBOMB_URL' in os.environ:
    effectiveVideobomb = os.environ['DTV_VIDEOBOMB_URL']
else:
    effectiveVideobomb = 'http://www.videobomb.com/api/submit_or_bomb'

if 'DTV_AUTOUPDATE_URL' in os.environ:
    effectiveAutoupdate = os.environ['DTV_AUTOUPDATE_URL']
else:
    effectiveAutoupdate = 'http://www.participatoryculture.org/democracy-version.xml'

CHANNEL_GUIDE_URL = Pref(key='ChannelGuideURL', default=effectiveChannelGuide,
                         platformSpecific=False)
VIDEOBOMB_URL     = Pref(key='VideobombURL',    default=effectiveVideobomb,
                         platformSpecific=False)
AUTOUPDATE_URL    = Pref(key='AutoupdateURL',   default=effectiveAutoupdate,
                         platformSpecific=False)

# These are computed by special platform code.
RUN_AT_STARTUP     = Pref( key='RunAtStartup',  default=False,  platformSpecific=True )
MOVIES_DIRECTORY = \
    Pref(key='MoviesDirectory',  default=None, platformSpecific=True)
SUPPORT_DIRECTORY = \
    Pref(key='SupportDirectory', default=None, platformSpecific=True)
ICON_CACHE_DIRECTORY = \
    Pref(key='IconCacheDirectory', default=None, platformSpecific=True)
DB_PATHNAME = \
    Pref(key='DBPathname',       default=None, platformSpecific=True)
BSDDB_PATHNAME = \
    Pref(key='BSDDBPathname',    default=None, platformSpecific=True)
LOG_PATHNAME = \
    Pref(key='LogPathname',      default=None, platformSpecific=True)
DOWNLOADER_LOG_PATHNAME = \
    Pref(key='DownloaderLogPathname', default=None, platformSpecific=True)

# These are normally read from resources/app.config.
SHORT_APP_NAME = \
    Pref(key='shortAppName', default=None, platformSpecific=False)
LONG_APP_NAME = \
    Pref(key='longAppName',  default=None, platformSpecific=False)
PROJECT_URL = \
    Pref(key='projectURL',   default=None, platformSpecific=False)
PUBLISHER = \
    Pref(key='publisher',    default=None, platformSpecific=False)
APP_VERSION = \
    Pref(key='appVersion',   default=None, platformSpecific=False)
APP_REVISION = \
    Pref(key='appRevision',  default=None, platformSpecific=False)
APP_PLATFORM = \
    Pref(key='appPlatform',  default=None, platformSpecific=False)
APP_SERIAL = \
    Pref(key='appSerial-unknown',    default="0", platformSpecific=False)
