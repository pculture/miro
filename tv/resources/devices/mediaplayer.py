from miro.devices import DeviceInfo
from miro.gtcache import gettext as _

sony_walkman = DeviceInfo(u'Sony Walkman',
                          vendor_id=0x054c,
                          product_id=0x0327,
                          device_name='WALKMAN',
                          video_conversion='playstationportablepsp',
                          video_path=u'VIDEO',
                          audio_conversion='mp3',
                          audio_path=u'MUSIC',
                          audio_types='.mp3 .wma .mp4 .m4a'.split(),
                          mount_instructions=_(
        "Your Walkman must be in USB Storage mode to sync files to it.\n"))

iriver_t10 = DeviceInfo(u'iRiver T10',
                        vendor_id=0x4102,
                        product_id=0x1013,
                        device_name='iriver T10',
                        video_conversion='copy',
                        video_path=u'Playlists',
                        audio_conversion='mp3',
                        audio_path=u'Playlists',
                        audio_types='.mp3 .wma .ogg .asf'.split(),
                        mount_instructions=_(
        "Your device must be in USB Storage mode to sync files to it.\n"))

psp = DeviceInfo(u'Playstation Portable',
                 vendor_id=0x054c,
                 product_id=0x02d2,
                 device_name='Sony PSP',
                 video_conversion='playstationportablepsp',
                 video_path=u'Video',
                 audio_conversion='mp3',
                 audio_path=u'Music',
                 audio_types='.mp3 .mp4 .wav .wma'.split(),
                 mount_instructions=_(
        "Your PSP must be in USB Storage mode to sync files to it.\n"))

devices = [sony_walkman, iriver_t10, psp]
