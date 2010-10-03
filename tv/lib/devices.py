from glob import glob
from ConfigParser import SafeConfigParser

from miro import messages

from miro.plat import resources

class DeviceInfo(object):
    def __init__(self, section, parser):
        self.name = section
        self.vendor_id = int(self._get(section, parser, 'vendor_id'), 16)
        self.product_id = [int(id, 16) for id in
                           self._get(section, parser, 'product_id').split()]
        self.video_conversion = self._get(section, parser, 'video_conversion')
        self.video_path = self._get(section, parser, 'video_path')
        self.audio_conversion = self._get(section, parser, 'audio_conversion')
        self.audio_path = self._get(section, parser, 'audio_path')
        self.audio_types = self._get(section, parser, 'audio_types').split()
        self.mount_instructions = self._get(
            section, parser, 'mount_instructions').replace('\\n', '\n')

    def _get(self, section, parser, name):
        try:
            return parser.get(section, name)
        except KeyError:
            pass
        try:
            return parser.get('DEFAULT', name)
        except KeyError:
            return None
class DeviceManager(object):
    def __init__(self):
        self.device_map = {}

    def startup(self):
        # load devices
        devices = glob(resources.path('devices/*.dev'))
        for device_desc in devices:
            parser = SafeConfigParser()
            parser.readfp(open(device_desc))
            for section in parser.sections():
                info = DeviceInfo(section, parser)
                for product_id in info.product_id:
                    self.device_map[(info.vendor_id, product_id)] = info

    def get_device(self, vendor_id, product_id):
        return self.device_map[(vendor_id, product_id)]

device_manager = DeviceManager()

def device_connected(info):
    message = messages.TabsChanged('devices',
                                   [info],
                                   [],
                                   [])
    message.send_to_frontend()

def device_changed(info):
    message = messages.TabsChanged('devices',
                                   [],
                                   [info],
                                   [])
    message.send_to_frontend()
    messages.DeviceChanged(info).send_to_frontend()


def device_disconnected(info):
    message = messages.TabsChanged('devices',
                                  [],
                                  [],
                                  [info.id])
    message.send_to_frontend()
