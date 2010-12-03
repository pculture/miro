# Miro - an RSS based video player application
# Copyright (C) 2010 Participatory Culture Foundation
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
#
# In addition, as a special exception, the copyright holders give
# permission to link the code of portions of this program with the OpenSSL
# library.
#
# You must obey the GNU General Public License in all respects for all of
# the code used other than OpenSSL. If you modify file(s) with this
# exception, you may extend this exception to your version of the file(s),
# but you are not obligated to do so. If you do not wish to do so, delete
# this exception statement from your version. If you delete this exception
# statement from all source files in the program, then also delete it here.

import logging
import plistlib
import subprocess

from AppKit import *
from Foundation import *
from FSEvents import *

from miro.plat.frontends.widgets import threads

from miro import app
from miro import devices
from miro import messages

kFSEventStreamCreateFlagIgnoreSelf = 0x08 # not defined for some reason

STREAM_INTERVAL = 0.5

def diskutil(cmd, path_or_disk, use_plist=True):
    args = ['diskutil', cmd]
    if use_plist:
        args.append('-plist')
    if path_or_disk:
        args.append(path_or_disk)
    proc = subprocess.Popen(args, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    stdout, stderr = proc.communicate()
    if not use_plist:
        return stdout
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
        self.stream = FSEventStreamCreate(kCFAllocatorDefault,
                                          self.streamCallback,
                                          None,
                                          ['/Volumes/'],
                                          kFSEventStreamEventIdSinceNow,
                                          STREAM_INTERVAL,
                                          kFSEventStreamCreateFlagNoDefer |
                                          kFSEventStreamCreateFlagIgnoreSelf)
        FSEventStreamScheduleWithRunLoop(self.stream, CFRunLoopGetCurrent(),
                                         kCFRunLoopDefaultMode)
        assert FSEventStreamStart(self.stream)

        for volume in diskutil('list', '').VolumesFromDisks:
            self._disk_mounted('/Volumes/%s' % volume)

    def streamCallback(self, stream, clientInfo, numEvents, eventPaths,
                        eventMasks, eventIDs):
        for path, mask in zip(eventPaths, eventMasks):
            if mask & kFSEventStreamEventFlagMount:
                self._disk_mounted(path)
            elif mask & kFSEventStreamEventFlagUnmount:
                self._disk_unmounted(path)
            else:
                logging.debug('unknown mask %i: %s' % (mask, path))

    def _disk_mounted(self, volume):
        volume_info = diskutil('info', volume)
        if not volume_info:
            logging.debug('unknown device connected @ %r' % volume)
            return
        if volume_info.BusProtocol != 'USB':
            return # don't care about non-USB devices
        disk_info = diskutil('info', volume_info.ParentWholeDisk)
        if not disk_info:
            logging.debug('unknown device connected @ %r' % volume)
            return
        device_name = disk_info.MediaName[:-6] # strip off ' Media'
        database = devices.load_database(volume)
        try:
            device_info = app.device_manager.get_device(
                device_name, database.get('device_name'))
        except KeyError:
            logging.debug('unknown device connected: %r' % device_name)
            return
        logging.debug('seen device: %r' % device_name)
        self._info_for_volume[volume] = device_info
        info = messages.DeviceInfo(volume, device_info, volume + '/',
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
        diskutil('eject', device.mount, use_plist=False)

