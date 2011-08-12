from miro import app
from miro import prefs
from miro.devices import DeviceInfo
from miro.gtcache import gettext as _

# USB IDs come from http://developer.android.com/guide/developing/device.html
devices = []

for data in (
    ('Acer', 0x0502),
    ('Dell', 0x413c),
    ('Foxconn', 0x0489),
    ('Garmin-Asus', 0x091E),
    ('HTC', 0x0bb4),
    ('Huawei', 0x12d1),
    ('Kyocera', 0x0482),
    ('LG', 0x1004),
    ('Motorola', 0x22b8),
    ('Nokia', 0x0421),
    ('Nvidia', 0x0955),
    ('Pantech', 0x10A9),
    ('Samsung', 0x04e8),
    ('Sharp', 0x04dd),
    ('Sony Ericsson', 0x0fce),
    ('SEMC', 0xfce, 'Sony Ericsson'), # also SE
    ('ZTE', 0x19D2)):
    if len(data) == 2:
        name, vendor_id = data
        visible_name = name
    else:
        name, vendor_id, visible_name = data
    info = DeviceInfo(_('Generic %(name)s Device', {'name': visible_name}),
                      device_name='%s*' % name,
                      vendor_id=vendor_id,
                      product_id=None,
                      video_conversion='hero',
                      audio_conversion='mp3',
                      container_types='mp3 asf isom wav mpeg avi'.split(),
                      audio_types='mp* wmav* aac pcm*'.split(),
                      video_types='h264 mpeg* wmv*'.split(),
                      mount_instructions=_(
            "Your device must be mounted in order for %(shortappname)s to "
            "sync files to it.", {'shortappname':
                                      app.config.get(prefs.SHORT_APP_NAME)}),
                      video_path=u'Miro',
                      audio_path=u'Miro')
    devices.append(info)

