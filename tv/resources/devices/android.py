from miro import app
from miro import prefs
from miro.devices import DeviceInfo, MultipleDeviceInfo
from miro.gtcache import gettext as _

defaults = {
    'audio_conversion': 'mp3',
    'audio_types': '.mp3 .wma .m4a .aac .mid .wav .oga'.split(),
    'mount_instructions': _("Your phone must be in 'USB storage mode' in "
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

htc_evo = DeviceInfo(u'HTC EVO',
                     video_conversion='epic',
                     video_path=u'Video',
                     audio_path=u'Music')

htc_legend = DeviceInfo(u'HTC Legend',
                        video_conversion='dreamg1',
                        video_path=u'/media/video',
                        audio_path=u'/media/audio')

tmobile_g1 = DeviceInfo(u'T-Mobile G1',
                        video_conversion='dreamg1')

tmobile_g2 = DeviceInfo(u'T-Mobile G2',
                        video_conversion='g2')

generic_htc = DeviceInfo(_('Generic %(name)s Device', {'name': 'HTC'}),
                         video_conversion='hero')

htc_android_device = MultipleDeviceInfo(
    'HTC Android Phone', [htc_hero, htc_evo, htc_legend,
                          tmobile_g1, tmobile_g2, generic_htc],
    vendor_id=0x0bb4,
    product_id=0x0ff9,
    **defaults)

htc_desire = DeviceInfo(u'HTC Desire',
                        vendor_id=0x0bb4,
                        product_id=0x0c87,
                        device_name='HTC Android Phone',
                        video_conversion='epic',
                        **defaults)

nexus_one = DeviceInfo(u'Nexus One',
                       vendor_id=0x18d1,
                       product_id=0x4e11,
                       device_name='Google, Inc.Nexus One',
                       video_conversion='nexusone',
                       **defaults)

# the Droid apparently can have two different USB IDs
motorola_droid_one = DeviceInfo(u'Motorola Droid',
                            vendor_id=0x22b8,
                            product_id=0x41db,
                            device_name='Motorola A855',
                            video_conversion='droid',
                            **defaults)

motorola_droid_two = DeviceInfo(u'Motorola Droid',
                                vendor_id=0x22b,
                                product_id=0x41d9,
                                device_name='Motorola A855',
                                video_conversion='droid',
                                **defaults)

motorola_droid2 = DeviceInfo(u'Motorola Droid 2',
                             vendor_id=0x22b8,
                             product_id=0x42a3,
                             device_name='Motorola A955',
                             video_conversion='droid',
                             **defaults)

motorola_droidx = DeviceInfo(u'Motorola Droid X',
                             vendor_id=0x22b8,
                             product_id=0x4285,
                             device_name='Motorola MB810',
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

nookcolor = DeviceInfo(
    name=u'MyNOOKColor',
    device_name='B&N Ebook Disk',
    vendor_id=0x2080,
    product_id=0x0002,
    # FIXME - the Nook Color has no way to play videos, so this should
    # really be disabled.
    video_conversion='copy',
    video_path=u'My Files/Video',
    audio_conversion='mp3',
    audio_path=u'My Files/Music',
    audio_types=['.mp3'],
    mount_instructions=_('Your Nook Color must be connected to your computer '
                         'and in USB Mode to sync files to it.\n')
    )

devices = [htc_android_device, htc_desire, nexus_one,
           motorola_droid_one, motorola_droid_two, motorola_droid2,
           motorola_droidx,
           galaxy_tab, epic, nookcolor]

