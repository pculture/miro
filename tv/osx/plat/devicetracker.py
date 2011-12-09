# Miro - an RSS based video player application
# Copyright (C) 2010, 2011
# Participatory Culture Foundation
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

from miro import app
from miro.plat.popen import Popen

kFSEventStreamCreateFlagIgnoreSelf = 0x08 # not defined for some reason

STREAM_INTERVAL = 0.5

def diskutil(cmd, path_or_disk, use_plist=True):
    args = ['/usr/sbin/diskutil', cmd]
    if use_plist:
        args.append('-plist')
    if path_or_disk:
        args.append(path_or_disk)
    proc = Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = proc.communicate()
    if not use_plist:
        return stdout
    try:
        return plistlib.readPlistFromString(stdout)
    except:
        logging.warn('error parsing plist for command: %s\n%s' % (
            ' '.join(args), stdout))

class DeviceTracker(object):

    def start_tracking(self):
        self._mounted_volumes = set()
        self.stream = FSEventStreamCreate(kCFAllocatorDefault,
                                          self.streamCallback,
                                          None,
                                          ['/Volumes/'],
                                          kFSEventStreamEventIdSinceNow,
                                          STREAM_INTERVAL,
                                          kFSEventStreamCreateFlagNoDefer |
                                          kFSEventStreamCreateFlagIgnoreSelf)
        FSEventStreamScheduleWithRunLoop(self.stream, CFRunLoopGetMain(),
                                         kCFRunLoopDefaultMode)
        FSEventStreamStart(self.stream)

        disk_list = diskutil('list', '')
        if disk_list:
            for volume in disk_list.VolumesFromDisks:
                self._disk_mounted('/Volumes/%s' % volume.encode('utf8'))
        elif app.controller:
            app.controller.failed_soft('initial device scan',
                                       'returned None')


    def streamCallback(self, stream, clientInfo, numEvents, eventPaths,
                        eventMasks, eventIDs):
        for path, mask in zip(eventPaths, eventMasks):
            if mask & kFSEventStreamEventFlagMount:
                self._disk_mounted(path)
            elif mask & kFSEventStreamEventFlagUnmount:
                self._disk_unmounted(path)

    def _disk_mounted(self, volume):
        volume_info = diskutil('info', volume)
        if not volume_info:
            logging.debug('unknown device connected @ %r' % volume)
            return
        if volume_info.BusProtocol != 'USB':
            return # don't care about non-USB devices
        real_volume = volume_info.MountPoint.encode('utf8')
        disk_info = diskutil('info', volume_info.ParentWholeDisk)
        if not disk_info:
            logging.debug('unknown device connected @ %r' % volume)
            return
        device_name = disk_info.MediaName[:-6] # strip off ' Media'
        logging.debug('seen device: %r' % device_name)
        self._mounted_volumes.add(volume)
        app.device_manager.device_connected(volume.decode('utf8'),
                                            name=device_name,
                                            mount=real_volume + '/',
                                            size=volume_info.TotalSize,
                                            remaining=volume_info.FreeSpace)

    def _disk_unmounted(self, volume):
        if volume in self._mounted_volumes:
            self._mounted_volumes.remove(volume)
            app.device_manager.device_disconnected(volume.decode('utf8'))

    def eject(self, device):
        diskutil('eject', device.mount, use_plist=False)

