from glob import glob
from ConfigParser import SafeConfigParser

from miro import messages

from miro.plat import resources

class DeviceInfo(object):
    has_multiple_devices = False

    def __init__(self, section, parser):
        self.name = section
        self.device_name = self._get(section, parser, 'name')
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

class MultipleDeviceInfo(object):
    has_multiple_devices = True

    def __init__(self, *args):
        self.device_name = self.name = args[0].device_name
        self.devices = {}
        for info in args:
            self.add_device(info)

    def add_device(self, info):
        self.devices[info.name] = info

    def get_device(self, name):
        return self.devices[name]

class DeviceManager(object):
    def __init__(self):
        self.device_map = {}
        self.known_devices = {}

    def _add_device(self, info):
        device_name = info.device_name
        if device_name in self.device_map:
            existing = self.device_map[device_name]
            if isinstance(existing, MultipleDeviceInfo):
                existing.add_device(info)
                return
            else:
                info = MultipleDeviceInfo(existing, info)
        self.device_map[device_name] = info

    def startup(self):
        # load devices
        devices = glob(resources.path('devices/*.dev'))
        for device_desc in devices:
            parser = SafeConfigParser()
            parser.readfp(open(device_desc))
            for section in parser.sections():
                info = DeviceInfo(section, parser)
                self._add_device(info)

    def get_device(self, device_name, device_type=None):
        info = self.device_map[device_name]
        if not info.has_multiple_devices:
            return info
        if device_type is not None and device_type in info.devices:
            return info.devices[device_type]
        return info

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
