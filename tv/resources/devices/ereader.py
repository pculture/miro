from miro.devices import DeviceInfo
from miro.gtcache import gettext as _

kindle = DeviceInfo(u'Kindle',
                    vendor_id=0x1949,
                    product_id=0x0004,
                    device_name='Kindle Internal Storage',
                    video_conversion='copy',
                    video_path=u'music',
                    audio_conversion='mp3',
                    audio_path=u'music',
                    container_types=['mp3'],
                    audio_types=['.mp3'],
                    video_types=[],
                    mount_instructions=_(
        "Your Kindle must be mounted to sync files to it.\n"))

kindle_fire = DeviceInfo(u'Kindle Fire',
                         vendor_id=0x1949,
                         product_id=0x0006,
                         device_name='Amazon Kindle',
                         video_conversion='kindlefire',
                         video_path=u'Video',
                         audio_conversion='mp3',
                         audio_path='Music',
                         container_types='mp3 isom asf'.split(),
                         audio_types='mp* aac'.split(),
                         video_types=['h264'],
                         mount_instructions=_(
        'Your Kindle must be in USB Storage mode to sync files to it.\n'))

devices = [kindle, kindle_fire]
