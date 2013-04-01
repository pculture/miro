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
import os

import gio
from glib import GError

from miro import app
from miro.gtcache import gettext as _
from miro import messages

def log_drive(drive, when):
    logging.debug('drive %s: %s (%s)' % (when, drive,
                                         drive.get_identifier('unix-device')))

def log_volume(volume, when):
    logging.debug('volume %s: %s (unix: %s, drive: %s, mount: %s)' % (
            when, volume, volume.get_identifier('unix-device'),
            volume.get_drive(), volume.get_mount()))

def log_mount(mount, when):
    logging.debug('mount %s: %s (root: %s, volume: %s, drive: %s)' % (
            when, mount, mount.get_root().get_path(), mount.get_volume(),
            mount.get_drive()))

class DeviceTracker(object):
    def __init__(self):
        self._unix_device_to_drive = {}
        self._drive_has_volumes = {}

    def start_tracking(self):
        volume_monitor = gio.volume_monitor_get()
        volume_monitor.connect('drive-connected', self._drive_connected)
        volume_monitor.connect('drive-changed',
                               lambda x, y: log_drive(y, 'changed'))
        volume_monitor.connect('volume-added', self._volume_added)
        volume_monitor.connect('volume-changed', self._volume_changed)
        volume_monitor.connect('mount-added', self._mount_added)
        volume_monitor.connect('mount-removed',
                               lambda x, y: log_mount(y, 'removed'))
        volume_monitor.connect('volume-removed', self._volume_removed)
        volume_monitor.connect('drive-disconnected', self._drive_disconnected)

        for drive in volume_monitor.get_connected_drives():
            self._drive_connected(volume_monitor, drive)
            volumes = drive.get_volumes()
            if volumes:
                for volume in volumes:
                    self._volume_added(volume_monitor, volume)

    @staticmethod
    def _should_ignore_drive(drive):
        """
        Returns True if we should ignore everything about the given drive.
        """
        return drive is None or drive.get_name() == 'CD/DVD Drive'

    def _get_volume_info(self, volume):
        id_ = volume.get_identifier('unix-device')
        mount = size = remaining = None
        mount = volume.get_mount()
        if mount:
            mount = mount.get_root().get_path()
            if mount and os.path.exists(mount):
                if mount[-1] != os.path.sep:
                    mount = mount + os.path.sep  # make sure it ends with a /
                statinfo = os.statvfs(mount)
                size = statinfo.f_frsize * statinfo.f_blocks
                remaining = statinfo.f_frsize * statinfo.f_bavail
        # bz19369: we have to handle get_drive() returnning None
        if volume.get_drive():
            name = volume.get_drive().get_name()
        else:
            logging.warn("get_drive() returned %s for %s",
                         volume.get_drive(), mount)
            name = None
        return id_, {
            'name': name,
            'visible_name': volume.get_name(),
            'mount': mount,
            'size': size,
            'remaining': remaining
            }

    def _drive_connected(self, volume_monitor, drive):
        log_drive(drive, 'connected')
        if self._should_ignore_drive(drive):
            return
        logging.debug('seen device: %r', drive.get_name())
        id_ = drive.get_identifier('unix-device')
        volumes = drive.get_volumes()
        if volumes:
            # so we ignore the disconnected event, instead deferring to the
            # volume events
            self._drive_has_volumes.setdefault(id_, 0)
        else:
            self._unix_device_to_drive[id_] = drive
            app.device_manager.device_connected(id_, name=drive.get_name())

    def _drive_disconnected(self, volume_monitor, drive):
        log_drive(drive, 'disconnected')
        if self._should_ignore_drive(drive):
            return
        id_ = drive.get_identifier('unix-device')
        if self._drive_has_volumes.get(id_):
            # don't send an event; the volumes will do that
            del self._drive_has_volumes[id_]
        else:
            del self._unix_device_to_drive[id_]
            app.device_manager.device_disconnected(id_)

    def _volume_added(self, volume_monitor, volume):
        log_volume(volume, 'added')
        id_, info = self._get_volume_info(volume)
        # have to set this so that we can access it when the volume is removed
        self._unix_device_to_drive[id_] = volume.get_drive()
        if volume is None or self._should_ignore_drive(volume.get_drive()):
            return
        drive_id = volume.get_drive().get_identifier('unix-device')
        if drive_id != id_ and drive_id in self._unix_device_to_drive:
            # we sent a "connect message" for the drive; disconnect the extra
            # device before we connect the volume (#17891)
            del self._unix_device_to_drive[drive_id]
            app.device_manager.device_disconnected(drive_id)
        app.device_manager.device_connected(id_, **info)
        self._drive_has_volumes.setdefault(drive_id, 0)
        self._drive_has_volumes[drive_id] += 1

    def _volume_changed(self, volume_monitor, volume):
        log_volume(volume, 'changed')
        if volume is None or self._should_ignore_drive(volume.get_drive()):
            return
        try:
            id_, info = self._get_volume_info(volume)
        except AttributeError:
            # comes up when the device is rudely removed
            return
        else:
            app.device_manager.device_changed(id_, **info)

    def _mount_added(self, volume_monitor, mount):
        log_mount(mount, 'added')
        if mount.get_volume():
            self._volume_changed(volume_monitor, mount.get_volume())

    def _volume_removed(self, volume_monitor, volume):
        log_volume(volume, 'removed')
        if volume is None:
            return
        drive = volume.get_drive()
        if drive and self._should_ignore_drive(drive):
            return
        id_ = volume.get_identifier('unix-device')
        del self._unix_device_to_drive[id_]
        app.device_manager.device_disconnected(id_)
        if drive is None:  # can be None on force-disconnect
            return
        drive_id = drive .get_identifier('unix-device')
        try:
            self._drive_has_volumes[drive_id] -= 1
        except KeyError:
            logging.warn("KeyError in _volume_removed", exc_info=True)
            return
        if self._drive_has_volumes[drive_id] == 0:
            # re-add the bare device
            del self._drive_has_volumes[drive_id]
            self._drive_connected(volume_monitor, volume.get_drive())

    def eject(self, device):
        if device.id not in self._unix_device_to_drive:
            return
        drive = self._unix_device_to_drive[device.id]
        drive.eject(self._eject_callback,
                    gio.MOUNT_UNMOUNT_NONE, None, device)

    def _eject_callback(self, drive, result, device):
        try:
            result = drive.eject_finish(result)
        except (gio.Error, GError), e:
            # double check that the eject really failed.  I (BDK) have seen
            # the very strange error: Drive is activatable and not running.
            if any(v.get_mount() is not None for v in drive.get_volumes()):
                logging.exception('eject failed for %r' % drive)
                result = False
            else:
                logging.warning('eject succeeded, but returned error '
                                '%s for %r' % (e, drive))
                result = True
        if not result:
            messages.ShowWarning(
                _('Eject failed'),
                _("Ejecting device '%(name)s' failed.\n\n"
                        "The device is in use.", {'name': device.name})
                ).send_to_frontend()
