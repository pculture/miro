import logging
import plistlib
import subprocess

from AppKit import *
from Foundation import *
from FSEvents import *

from miro.plat.frontends.widgets import threads

from miro import devices
from miro import messages

STREAM_INTERVAL = 0.5

def diskutil(cmd, pathOrDisk):
    args = ['diskutil', cmd, '-plist']
    if pathOrDisk:
        args.append(pathOrDisk)
    proc = subprocess.Popen(args, stdout=subprocess.PIPE)
    stdout, stderr = proc.communicate()
    try:
        return plistlib.readPlistFromString(stdout)
    except:
        logging.debug(
            'error parsing plist for command: diskutil %s -plist %s\n%s' % (
                cmd, pathOrDisk, stdout))

class DeviceTracker(object):
    def __init__(self):
        self._info_for_volume = {}

    @threads.on_ui_thread
    def start_tracking(self):
        stream = FSEventStreamCreate(kCFAllocatorDefault,
                                           self.streamCallback, None,
                                           ['/Volumes/'],
                                           kFSEventStreamEventIdSinceNow,
                                           STREAM_INTERVAL, 0)
        FSEventStreamScheduleWithRunLoop(stream, CFRunLoopGetCurrent(),
                                         kCFRunLoopDefaultMode)
        assert FSEventStreamStart(stream)

        for volume in diskutil(list, '').VolumesFromDisks:
            self._disk_mounted('/Volumes/%s' % volume)

    def streamCallback(self, stream, clientInfo, numEvents, eventPaths,
                        eventMasks, eventIDs):
        for path, mask in zip(eventPaths, eventMasks):
            if mask & kFSEventStreamEventFlagMount:
                self._disk_mounted(path)
            elif mask & kFSEventStreamEventFlagUnmount:
                self._disk_unmounted(path)

    def _disk_mounted(self, volume):
        volume_info = diskutil('info', volume)
        if volume_info.BusProtocol != 'USB':
            return # don't care about non-USB devices
        disk_info = diskutil('info', volume_info.ParentWholeDisk)
        device_name = disk_info.MediaName[:-6] # strip off ' Media'
        database = devices.load_database(volume)
        try:
            device_info = devices.device_manager.get_device(
                device_name, database.get('device_name'))
        except KeyError:
            logging.info('unknown device: %r' % device_name)
            return
        self._info_for_volume[volume] = device_info
        info = messages.DeviceInfo(volume, device_info, volume,
                                   database, volume_info.TotalSize,
                                   volume_info.FreeSpace)
        devices.device_connected(info)

    def _disk_unmounted(self, volume):
        if not volume in self._info_for_volume:
            return
        device_info = self._info_for_volume.pop(volume)
        info = messages.DeviceInfo(volume, device_info, volume, {}, None, None)
        devices.device_disconnected(info)

    def eject(self, device):
        diskutil('eject', device.mount)

tracker = DeviceTracker()
