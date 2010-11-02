from glob import glob
import json
import os, os.path
from ConfigParser import SafeConfigParser

from miro import fileutil
from miro import filetypes
from miro import messages

from miro.plat import resources
from miro.plat.utils import filename_to_unicode

class DeviceInfo(object):
    has_multiple_devices = False

    def __init__(self, section, parser):
        self.name = section
        self.device_name = self._get(section, parser, 'name')
        self.vendor_id = int(self._get(section, parser, 'vendor_id'), 16)
        self.product_id = int(self._get(section, parser, 'product_id'), 16)
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
        self.vendor_id = args[0].vendor_id
        self.product_id = args[0].product_id
        self.mount_instructions = args[0].mount_instructions
        self.devices = {}
        for info in args:
            self.add_device(info)

    def add_device(self, info):
        self.devices[info.name] = info

    def get_device(self, name):
        return self.devices[name]

class DeviceManager(object):
    def __init__(self):
        self.device_by_name = {}
        self.device_by_id = {}

    def _add_device(self, info):
        device_name = info.device_name
        if device_name in self.device_by_name:
            existing = self.device_by_name[device_name]
            if isinstance(existing, MultipleDeviceInfo):
                existing.add_device(info)
                return
            else:
                info = MultipleDeviceInfo(existing, info)
        self.device_by_name[device_name] = info
        self.device_by_id[(info.vendor_id, info.product_id)] = info

    def startup(self):
        # load devices
        devices = glob(resources.path('devices/*.dev'))
        for device_desc in devices:
            parser = SafeConfigParser()
            parser.readfp(open(device_desc))
            for section in parser.sections():
                info = DeviceInfo(section, parser)
                self._add_device(info)

    @staticmethod
    def _get_device_from_info(info, device_type):
        if not info.has_multiple_devices:
            return info
        if device_type is not None and device_type in info.devices:
            return info.devices[device_type]
        return info

    def get_device(self, device_name, device_type=None):
        info = self.device_by_name[device_name]
        return self._get_device_from_info(info, device_type)

    def get_device_by_id(self, vendor_id, product_id, device_type=None):
        info = self.device_by_id[(vendor_id, product_id)]
        return self._get_device_from_info(info, device_type)


device_manager = DeviceManager()

def load_database(mount):
    file_name = os.path.join(mount, '.miro', 'json')
    if not os.path.exists(file_name):
        return {}
    return json.load(file(file_name))

def write_database(mount, database):
    json.dump(database, file(os.path.join(mount, '.miro', 'json'), 'w'))

def device_connected(info):
    if info.mount:
        scan_device_for_files(info)
    message = messages.TabsChanged('devices',
                                   [info],
                                   [],
                                   [])
    message.send_to_frontend()

def device_changed(info):
    if info.mount:
        scan_device_for_files(info)
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

def scan_device_for_files(device):
    new_items = {'video': [], 'audio': []}
    known_files = set()
    def _exists(item):
        return os.path.exists(os.path.join(device.mount,
                                           item['video_path']))
    for item_type in ('video', 'audio'):
        for device_item in device.database.get(item_type, []):
            if _exists(device_item):
                new_items[item_type].append(device_item)
                known_files.add(os.path.normcase(device_item['video_path']))

    for filename in fileutil.miro_allfiles(device.mount):
        filename = os.path.normcase(filename)
        if filename in known_files: continue
        ufilename = filename_to_unicode(filename)
        if filetypes.is_video_filename(ufilename):
            item_type = 'video'
        elif filetypes.is_audio_filename(ufilename):
            item_type = 'audio'
        else:
            continue
        new_items[item_type].append({
                'video_path': filename[len(device.mount)+1:]
                })

    for item_type in ('video', 'audio'):
        device.database[item_type] = new_items[item_type]

    write_database(device.mount, device.database)
