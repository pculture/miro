from threading import RLock
import os
import platformcfg
import util
import resource

__appConfig = None
__data = None
__lock = RLock()
__callbacks = set()

class Pref:
    def __init__(self, **kwds):
        self.__dict__.update(kwds)

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
DOWNLOADS_TARGET            = Pref( key='DownloadsTarget',       default=3,     platformSpecific=False )
MAX_MANUAL_DOWNLOADS        = Pref( key='MaxManualDownloads',    default=10,    platformSpecific=False )
VOLUME_LEVEL                = Pref( key='VolumeLevel',           default=1.0,   platformSpecific=False )

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
DB_PATHNAME = \
    Pref(key='DBPathname',       default=None, platformSpecific=True)
LOG_PATHNAME = \
    Pref(key='LogPathname',      default=None, platformSpecific=True)

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

def addChangeCallback(callback):
    __callbacks.add(callback)

def removeChangeCallback(callback):
    __callbacks.discard(callback)

def load():
    global __data
    __lock.acquire()
    try:
        # There's some sleight-of-hand here. The Windows port needs to
        # look up config.LONG_APP_NAME and config.PUBLISHER to compute
        # the path to the data file that is read when load() is
        # called. Setting __appConfig to a true value (and populating
        # it with those keys) before calling load() ensures that (a)
        # the values will be available and (b) we won't get caught in
        # an infinite loop of load()s. But in general, you shouldn't
        # call config.get() or config.set() from platformcfg.load()
        # unless you know exactly what you are doing, and maybe not
        # even then.
        global __appConfig
        __appConfig = util.readSimpleConfigFile(resource.path('app.config'))

        __data = platformcfg.load()
        if __data is None:
            __data = dict()

        # This is a bit of a hack to automagically get the serial
        # number for this platform
        APP_SERIAL.key = ('appSerial-%s' % get(APP_PLATFORM))

    finally:
        __lock.release()

def save():
    __lock.acquire()
    try:
        __checkValidity()
        platformcfg.save( __data )
    finally:
        __lock.release()

def get(descriptor):
    __lock.acquire()
    try:
        __checkValidity()

        if descriptor.platformSpecific:
            return platformcfg.get(descriptor)
        elif descriptor.key in __appConfig:
            return __appConfig[descriptor.key]
        else:
            return __data.get(descriptor.key, descriptor.default)
    finally:
        __lock.release()

def getAppConfig():
    __lock.acquire()
    try:
        __checkValidity()
        return __appConfig.copy()
    finally:
        __lock.release()
    
def set(descriptor, value):
    __lock.acquire()
    try:
        __checkValidity()
        __data[ descriptor.key ] = value
        __notifyListeners(descriptor.key, value)
    finally:
        __lock.release()

def __checkValidity():
    if __appConfig == None:
        load()

def __notifyListeners(key, value):
    for callback in __callbacks:
        callback(key, value)


def ensureMigratedMoviePath(pathname):
    if hasattr(platformcfg, 'ensureMigratedMoviePath'):
        pathname = platformcfg.ensureMigratedMoviePath(pathname)
    return pathname

# Hack. Getting the support directory path here forces it to be created at
# import time (ie, before the application standard startup sequence is running)
# which solves bug #1260994: the bittorent-dtv folder won't end up at the
# root of the user's home folder. Warning, 'config' MUST be import BEFORE
# 'downloader' in app.py for this to work.
get(SUPPORT_DIRECTORY)
