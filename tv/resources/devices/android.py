from miro import app
from miro import prefs
from miro.devices import DeviceInfo, MultipleDeviceInfo
from miro.gtcache import gettext as _

defaults = {
    'audio_conversion': 'mp3',
    'container_types': 'mp3 wav asf isom ogg mpeg avi'.split(),
    'audio_types': 'mp* wmav* aac pcm* vorbis'.split(),
    'video_types': 'theora h264 mpeg* wmv*'.split(),
    'mount_instructions': _("Your phone must be in 'USB storage mode' in "
                            "order for %(shortappname)s to sync files to it.\n"
                            "To mount your phone, select 'Turn on USB "
                            "storage' from the notifications.",
                            {'shortappname':
                                 app.config.get(prefs.SHORT_APP_NAME)}),
    'video_path': u'Miro',
    'audio_path': u'Miro'
    }

tablet_defaults = defaults.copy()
tablet_defaults['mount_instructions'] = _(
    "Your tablet must be in 'USB storage mode' in "
    "order for %(shortappname)s to sync files to it.\n"
    "To mount your phone, select 'Turn on USB "
    "storage' from the notifications.",
    {'shortappname':
         app.config.get(prefs.SHORT_APP_NAME)})

htc_hero = DeviceInfo(u'HTC Hero',
                      video_conversion='hero',
                      video_path=u'Video',
                      audio_path=u'Music')

htc_evo = DeviceInfo(u'HTC EVO',
                     video_conversion='epic',
                     video_path=u'Video',
                     audio_path=u'Music')

htc_evo_4g = DeviceInfo(u'HTC EVO 4G',
                        video_conversion='epic')

htc_evo_3d = DeviceInfo('HTC EVO 3D',
                        video_conversion='sensationevo3d')

htc_legend = DeviceInfo(u'HTC Legend',
                        video_conversion='dreamg1',
                        video_path=u'/media/video',
                        audio_path=u'/media/audio')

tmobile_g1 = DeviceInfo(u'T-Mobile G1',
                        video_conversion='dreamg1')

tmobile_g2 = DeviceInfo(u'T-Mobile G2',
                        video_conversion='g2')

htc_vision = DeviceInfo(u'HTC Vision',
                        video_conversion='g2')

htc_desire_z = DeviceInfo(u'HTC Desire Z',
                        video_conversion='g2')

htc_incredible = DeviceInfo(u'HTC Droid Incredible',
                            video_conversion='epic')

htc_incredible_2 = DeviceInfo(u'HTC Droid Incredible 2',
                              video_conversion='epic')

htc_sensation = DeviceInfo(u'HTC Sensation',
                           video_conversion='epic')

htc_aria = DeviceInfo(u'HTC Aria',
                      video_conversion='hero')

generic_htc = DeviceInfo(_('Generic %(name)s Device', {'name': 'HTC'}),
                         video_conversion='hero')

htc_android_device = MultipleDeviceInfo(
    'HTC Android Phone', [htc_hero, htc_evo, htc_evo_4g, htc_evo_3d,
                          htc_legend,
                          tmobile_g1, tmobile_g2, htc_vision, htc_desire_z,
                          htc_incredible, htc_incredible_2, htc_sensation,
                          htc_aria,
                          generic_htc],
    vendor_id=0x0bb4,
    product_id=0x0ff9,
    **defaults)

htc_desire = DeviceInfo(u'HTC Desire',
                        vendor_id=0x0bb4,
                        product_id=0x0c87,
                        device_name='HTC Android Phone',
                        video_conversion='epic',
                        **defaults)

htc_desire_hd = DeviceInfo(u'HTC Desire HD',
                           vendor_id=0xbb4,
                           product_id=0x0ca2,
                           device_name='HTC Android Phone',
                           video_conversion='epic',
                           **defaults)

htc_thunderbolt = DeviceInfo(u'HTC Thunderbolt',
                             vendor_id=0x0bb4,
                             product_id=0x0ca4,
                             device_name='HTC Android Phone',
                             video_conversion='epic',
                             **defaults)

htc_sensation = DeviceInfo(u'HTC Sensation',
                           vendor_id=0x0bb4,
                           product_id=0x0c86,
                           device_name='HTC Android Phone',
                           video_conversion='sensationevo3d',
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

motorola_xoom = DeviceInfo(u'Motorola Xoom',
                           vendor_id=0x18d1,
                           product_id=0x70a8,
                           device_name='Motorola MZ604',
                           video_conversion='xoom',
                           **tablet_defaults)

galaxy_s2 = DeviceInfo(u'Galaxy S2',
                       vendor_id=0x04e8,
                       product_id=0x685e,
                       device_name='Android UMS Composite',
                       video_conversion='epic',
                       **defaults)

galaxy_tab = DeviceInfo(u'Galaxy Tab',
                        vendor_id=0x04e8,
                        product_id=0x681d,
                        device_name='SAMSUNG SGH-T849',
                        video_conversion='galaxytab',
                        **tablet_defaults)

epic = DeviceInfo(u'Epic',
                  vendor_id=0x04e8,
                  product_id=0x6601,
                  device_name="SAMSUNG SPH-D700 Card",
                  video_conversion='epic',
                  **defaults)

lg_optimus_2x = DeviceInfo(u'Optimus 2x',
                           vendor_id=0x1004,
                           product_id=0x618e,
                           device_name='LGE P990',
                           video_conversion='epic',
                           **defaults)

lg_optimus_s = DeviceInfo(
    u'Optimus S',
    vendor_id=0x1004,
    product_id=0x618E,
    device_name='GOOGLE Mass storage',
    video_conversion='hero',
    audio_conversion='mp3',
    container_types='mp3 wav asf isom ogg mpeg avi'.split(),
    audio_types='mp* wmav* aac pcm* vorbis'.split(),
    video_types='theora h264 mpeg* wmv*'.split(),
    mount_instructions=_("Your phone must be in 'USB storage mode' in "
                            "order for %(shortappname)s to sync files to it.\n"
                            "To mount your phone, select 'Turn on USB "
                            "storage' from the notifications.",
                            {'shortappname':
                                 app.config.get(prefs.SHORT_APP_NAME)}),
    video_path=u'Media/Video',
    audio_path=u'Media/Audio')

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
    container_types=['mp3', 'isom'],
    audio_types=['mp*', 'aac'],
    video_types=[],
    mount_instructions=_('Your Nook Color must be connected to your computer '
                         'and in USB Mode to sync files to it.\n')
    )

toshiba_thrive = DeviceInfo(
    u'Toshiba Thrive',
    vendor_id=0x18d1,
    product_id=0x7102,
    device_name='AT100',
    video_conversion='xoom',
    audio_conversion='mp3',
    container_types='mp3 wav asf isom ogg mpeg avi'.split(),
    audio_types='mp* wmav* aac pcm* vorbis'.split(),
    video_types='theora h264 mpeg* wmv*'.split(),
    mount_instructions=_("Your tablet must be in 'USB storage mode' in "
                            "order for %(shortappname)s to sync files to it.\n"
                            "To mount your phone, select 'Turn on USB "
                            "storage' from the notifications.",
                            {'shortappname':
                                 app.config.get(prefs.SHORT_APP_NAME)}),
    video_path=u'Movies',
    audio_path=u'Music')

devices = [htc_android_device, htc_desire, htc_desire_hd, htc_thunderbolt,
           htc_sensation, nexus_one,
           motorola_droid_one, motorola_droid_two, motorola_droid2,
           motorola_droidx, motorola_xoom, lg_optimus_2x, lg_optimus_s,
           galaxy_s2, galaxy_tab, epic, nookcolor, toshiba_thrive]

