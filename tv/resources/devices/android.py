from miro import app
from miro import prefs
from miro.devices import DeviceInfo, MultipleDeviceInfo
from miro.gtcache import gettext as _

defaults = {
    'audio_conversion': 'mp3',
    'audio_types': '.mp3 .wma .m4a .aac .mid .wav .oga'.split(),
    'mount_instructions': _(u"Your phone must be in 'USB storage mode' in "
                            "order for %(shortappname)s to sync files to it.\n"
                            "To mount your phone, select 'Turn on USB "
                            "storage' from the notifications.",
                            {'shortappname':
                                 app.config.get(prefs.SHORT_APP_NAME)}),
    'video_path': u'Miro',
    'audio_path': u'Miro'
    }

htc_hero = DeviceInfo(u'HTC Hero',
                      video_conversion='hero',
                      video_path=u'Video',
                      audio_path=u'Music')

tmobile_g1 = DeviceInfo(u'T-Mobile G1',
                        video_conversion='dreamg1')

tmobile_g2 = DeviceInfo(u'T-Mobile G2',
                        video_conversion='g2')

htc_android_device = MultipleDeviceInfo(
    'HTC Android Phone', [htc_hero, tmobile_g1, tmobile_g2],
    vendor_id=0x0bb4,
    product_id=0x0ff9,
    **defaults)

nexus_one = DeviceInfo(u'Nexus One',
                       vendor_id=0x18d1,
                       product_id=0x4e11,
                       device_name='Google_ Inc.Nexus_One',
                       video_conversion='nexusone',
                       **defaults)

motorola_droid = DeviceInfo(u'Motorola Droid',
                            vendor_id=0x22b8,
                            product_id=0x41db,
                            device_name='Motorola A855',
                            video_conversion='droid',
                            **defaults)

motorola_droid2 = DeviceInfo(u'Motorola Droid 2',
                             vendor_id=0x22b8,
                             product_id=0x42a3,
                             device_name='Motorola A955',
                             video_conversion='droid',
                             **defaults)

galaxy_tab = DeviceInfo(u'Galaxy Tab',
                        vendor_id=0x04e8,
                        product_id=0x681d,
                        device_name='SAMSUNG SGH-T849',
                        video_conversion='galaxytab',
                        **defaults)

epic = DeviceInfo(u'Epic',
                  vendor_id=0x04e8,
                  product_id=0x6601,
                  device_name="SAMSUNG SPH-D700 Card",
                  video_conversion='epic',
                  **defaults)

devices = [htc_android_device, nexus_one, motorola_droid, motorola_droid2,
           galaxy_tab, epic]

