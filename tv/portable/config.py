from threading import RLock
import os
import platformcfg

__data = None
__lock = RLock()
__callbacks = set()

if 'DTV_CHANNELGUIDE_URL' in os.environ:
    effectiveChannelGuide = os.environ['DTV_CHANNELGUIDE_URL']
else:
    effectiveChannelGuide = 'https://channelguide.participatoryculture.org/'

if 'DTV_VIDEOBOMB_URL' in os.environ:
    effectiveVideobomb = os.environ['DTV_VIDEOBOMB_URL']
else:
    effectiveVideobomb = 'http://www.videobomb.com/api/submit_or_bomb'

class Pref:
    def __init__(self, **kwds):
        self.__dict__.update(kwds)

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
CHANNEL_GUIDE_URL           = Pref( key='ChannelGuideURL',       default=effectiveChannelGuide, platformSpecific=False )
VIDEOBOMB_URL               = Pref( key='VideobombURL',          default=effectiveVideobomb,    platformSpecific=False )
VOLUME_LEVEL                = Pref( key='VolumeLevel',           default=1.0,   platformSpecific=False )

MOVIES_DIRECTORY            = Pref( key='MoviesDirectory',       default=None,  platformSpecific=True )
SUPPORT_DIRECTORY           = Pref( key='SupportDirectory',      default=None,  platformSpecific=True )
DB_PATHNAME                 = Pref( key='DBPathname',            default=None,  platformSpecific=True )

def addChangeCallback(callback):
    __callbacks.add(callback)

def removeChangeCallback(callback):
    __callbacks.discard(callback)

def load():
    global __data
    __lock.acquire()
    __data = platformcfg.load()
    if __data is None:
        __data = dict()
    __lock.release()

def save():
    __checkValidity()
    __lock.acquire()
    platformcfg.save( __data )
    __lock.release()

def get(descriptor):
    __checkValidity()
    __lock.acquire()
    if descriptor.platformSpecific:
        value = platformcfg.get(descriptor)
    else:
        value = __data.get(descriptor.key, descriptor.default)
    __lock.release()
    return value
    
def set(descriptor, value):
    __checkValidity()
    __lock.acquire()
    __data[ descriptor.key ] = value
    __notifyListeners(descriptor.key, value)
    __lock.release()

def __checkValidity():
    if __data == None:
        load()

def __notifyListeners(key, value):
    for callback in __callbacks:
        callback(key, value)


# Hack. Getting the support directory path here forces it to be created at
# import time (ie, before the application standard startup sequence is running)
# which solves bug #1260994: the bittorent-dtv folder won't end up at the
# root of the user's home folder. Warning, 'config' MUST be import BEFORE
# 'downloader' in app.py for this to work.
get(SUPPORT_DIRECTORY)
