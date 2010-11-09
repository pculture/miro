from glob import glob
import json
import os, os.path
import shutil
import time
from ConfigParser import SafeConfigParser

from miro import item
from miro import fileutil
from miro import filetypes
from miro import messages
from miro import videoconversion

from miro.plat import resources
from miro.plat.utils import filename_to_unicode

class DeviceInfo(object):
    has_multiple_devices = False

    def __init__(self, section, parser):
        self.name = section.decode('utf8')
        self.device_name = self._get(section, parser, 'name')
        self.vendor_id = int(self._get(section, parser, 'vendor_id'), 16)
        self.product_id = int(self._get(section, parser, 'product_id'), 16)
        self.video_conversion = self._get(section, parser, 'video_conversion')
        self.video_path = self._get(section, parser, 'video_path')
        self.audio_conversion = self._get(section, parser, 'audio_conversion')
        self.audio_path = self._get(section, parser, 'audio_path')
        self.audio_types = self._get(section, parser, 'audio_types').split()
        self.mount_instructions = self._get(
            section, parser, 'mount_instructions').decode('utf8').replace(
            '\\n', '\n')

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

class DeviceSyncManager(object):
    """
    Represents a list of ItemInfos to sync to a device.
    """
    def __init__(self, device, item_infos):
        self.device = device
        self.was_updating = False
        self.item_infos = item_infos
        self.signal_handles = []
        self.waiting = set()

    def start(self):
        """
        Start syncing to the device.
        """
        self.was_updating = getattr(self.device, 'is_updating', False)
        self.device.is_updating = True # start the spinner
        messages.TabsChanged('devices', [], [self.device],
                             []).send_to_frontend()

        audio_target_folder = os.path.join(self.device.mount,
                                           self.device.info.audio_path)
        try:
            os.makedirs(audio_target_folder)
        except OSError:
            pass

        video_target_folder = os.path.join(self.device.mount,
                                           self.device.info.video_path)
        try:
            os.makedirs(audio_target_folder)
        except OSError:
            pass

        for info in self.item_infos:
            if self._exists(info):
                continue # don't recopy stuff
            if info.file_type == 'audio':
                if info.mime_type in self.device.info.audio_types:
                    final_path = os.path.join(audio_target_folder,
                                              os.path.basename(
                            info.video_path))
                    try:
                        shutil.copy(info.video_path, final_path)
                    except IOError:
                        # FIXME - we should pass the error back to the frontend
                        pass
                    else:
                        self._add_item(final_path, info)
                else:
                    self.start_conversion(self.device.info.audio_conversion,
                                          info,
                                          audio_target_folder)
            elif info.file_type == 'video':
                self.start_conversion(self.device.info.video_conversion,
                                      info,
                                      video_target_folder)

        self._check_finished()

    def start_conversion(self, conversion, info, target):
        conversion_manager = videoconversion.conversion_manager
        start_conversion = conversion_manager.start_conversion

        if not self.waiting:
            for signal, callback in (
                ('task-done', self._conversion_done_callback),
                ('task-removed', self._conversion_removed_callback),
                ('all-tasks-removed', self._conversion_removed_callback)):
                self.signal_handles.append(conversion_manager.connect(
                        signal, callback))

        self.waiting.add(info)
        start_conversion(conversion, info, target)

    def _exists(self, item_info):
        if item_info.file_type not in self.device.database:
            return False
        for existing in self.device.database[item_info.file_type].values():
            if item_info.file_url and \
                    existing.get('url') == item_info.file_url:
                return True
            elif (item_info.name, item_info.description, item_info.size,
                  item_info.duration) == \
                  (existing.get('name'), existing.get('description'),
                   existing.get('size'), existing.get('duration')):
                  # if a bunch of qualities are the same, we'll call it close
                  # enough
                  return True
        return False

    def _conversion_removed_callback(self, conversion_manager, task=None):
        if task is not None:
            try:
                self.waiting.remove(task)
            except KeyError:
                pass
        else: # remove all tasks
            self.waiting = set()
        self._check_finished()

    def _conversion_done_callback(self, conversion_manager, task):
        try:
            self.waiting.remove(task.item_info)
        except KeyError:
            pass # missing for some reason
        else:
            if task.is_finished(): # successful!
                self._add_item(task.final_output_path, task.item_info)
        self._check_finished()

    def _add_item(self, final_path, item_info):
        device_item = item.DeviceItem(
            device=self.device,
            file_type=item_info.file_type,
            video_path=final_path[len(self.device.mount):],
            name=item_info.name,
            feed_name=item_info.feed_name,
            feed_url=item_info.feed_url,
            description=item_info.description,
            release_date=time.mktime(item_info.release_date.timetuple()),
            size=item_info.size,
            duration=item_info.duration * 1000,
            permalink=item_info.permalink,
            commentslink=item_info.commentslink,
            payment_link=item_info.payment_link,
            screenshot=item_info.thumbnail,
            thumbnail_url=item_info.thumbnail_url,
            file_format=item_info.file_format,
            license=item_info.license,
            url=item_info.file_url,
            media_type_checked=item_info.media_type_checked,
            mime_type=item_info.mime_type)
        device_item._migrate_thumbnail()
        database = self.device.database
        database.setdefault(device_item.file_type, [])
        database[device_item.file_type][device_item.video_path] = \
            device_item.to_dict()
        messages.ItemsChanged('device', '%s-%s' % (self.device.id,
                                                   device_item.file_type),
                              [messages.ItemInfo(device_item)], # added
                              [], []).send_to_frontend() # changed, removed

    def _check_finished(self):
        if not self.waiting:
            # finished!
            write_database(self.device.mount, self.device.database)
            for handle in self.signal_handles:
                videoconversion.conversion_manager.disconnect(handle)
            self.signal_handles = None
            if not self.was_updating:
                self.device.is_updating = False # stop the spinner
                messages.TabsChanged('devices', [], [self.device],
                                     []).send_to_frontend()


def load_database(mount):
    file_name = os.path.join(mount, '.miro', 'json')
    if not os.path.exists(file_name):
        return {}
    return json.load(file(file_name))

def write_database(mount, database):
    try:
        os.makedirs(os.path.join(mount, '.miro'))
    except OSError:
        pass
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
    known_files = set()
    to_remove = []
    def _exists(item_path):
        return os.path.exists(os.path.join(device.mount,
                                           item_path))
    for item_type in ('video', 'audio'):
        device.database.setdefault(item_type, {})
        for item_path in device.database[item_type]:
            if _exists(item_path):
                known_files.add(os.path.normcase(item_path))
            else:
                to_remove.append((item_type, item_path))

    for filename in fileutil.miro_allfiles(device.mount):
        short_filename = filename[len(device.mount):]
        ufilename = filename_to_unicode(short_filename)
        if os.path.normcase(ufilename) in known_files: continue
        if filetypes.is_video_filename(ufilename):
            item_type = 'video'
        elif filetypes.is_audio_filename(ufilename):
            item_type = 'audio'
        else:
            continue
        device.database[item_type][ufilename] = {}

    for item_type, item_path in to_remove:
        del device.database[item_type][item_path]

    write_database(device.mount, device.database)
