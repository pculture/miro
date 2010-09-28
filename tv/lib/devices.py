from glob import glob
from ConfigParser import SafeConfigParser

from miro import messages

from miro.plat import resources

class DeviceInfo(object):
    def __init__(self, name, parser):
        self.io_name = name
        self.name = parser.get(name, 'name')
        self.video_conversion = parser.get(name, 'video_conversion')
        self.video_path = parser.get(name, 'video_path')
        self.audio_conversion = parser.get(name, 'audio_conversion')
        self.audio_path = parser.get(name, 'audio_path')
        self.audio_types = parser.get(name, 'audio_types').split()
        self.mount_instructions = parser.get(
            name, 'mount_instructions').replace('\\n', '\n')

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
                self.device_map[section] = info

    def get_device(self, name):
        return self.device_map[name]

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
