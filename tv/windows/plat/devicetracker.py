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

import ctypes

from miro.plat.frontends.widgets import timer
from miro.plat import usbutils
from miro import app

GWL_WNDPROC = -4
WndProcType = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, ctypes.c_uint,
                                 ctypes.c_int, ctypes.c_int)

class DeviceTracker(object):
    def __init__(self):
        self._connected = {}

    def start_tracking(self):
        self._wndproc_wrapped = WndProcType(self._wndproc) # keep it around to
                                                           # avoid GC
        self._oldwndproc = ctypes.windll.user32.GetWindowLongW(
            app.widgetapp.window._window.window.handle,
            GWL_WNDPROC) # set it up before we set up our callback
        self._oldwndproc = ctypes.windll.user32.SetWindowLongW(
                app.widgetapp.window._window.window.handle,
                GWL_WNDPROC, self._wndproc_wrapped)

        self._devices_changed()

    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == 537 and wparam == 7:
            #previousChange, self._lastChange = self._lastChange, time.time()
            #if self._lastChange - previousChange > 0.25:
            self._devices_changed()
        if not self._oldwndproc:
            # we can get here if GetWindowLongW returned 0.  Call the
            # default window proc.
            return ctypes.windll.user32.DefWindowProcW(hwnd, msg, wparam, lparam)
        else:
            return ctypes.windll.user32.CallWindowProcW(self._oldwndproc, hwnd,
                                                    msg, wparam, lparam)

    def _devices_changed(self):
        # re-poll the devices, and figure out what, if anything, is
        # different
        volumes = set()
        for device in usbutils.connected_devices():
            logging.debug('%s', str(device))
            volume = device['volume']
            volumes.add(volume)
            if volume not in self._connected:
                self._connected[volume] = device
                self._device_connected(device)

        for vol in self._connected.keys():
            if vol not in volumes:
                device = self._connected.pop(vol)
                self._device_disconnected(device)

    def _get_device_info(self, device):
        mount = device['mount']
        if mount and usbutils.read_write_drive(mount):
            available = ctypes.wintypes.LARGE_INTEGER()
            total = ctypes.wintypes.LARGE_INTEGER()
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                unicode(mount),
                ctypes.byref(available),
                ctypes.byref(total),
                None)
            device['size'] = total.value
            device['remaining'] = available.value
        elif mount:
            device['future_mount'] = device['mount']
            device['mount'] = None

        return device['volume'], device

    def _check_device_mount(self, device):
        if device['volume'] not in self._connected:
            # device was removed
            return
        if 'future_mount' in device and os.path.exists(device['future_mount']):
            device['mount'] = device['future_mount']
            del device['future_mount']
            self._device_changed(device)
            return
        timer.add(0.5, self._check_device_mount, device)

    def _device_connected(self, device):
        id_, info = self._get_device_info(device)
        logging.debug('seen device: %r' % (device,))
        if not info['mount']:
            # we don't get notified :( so poll instead
            timer.add(0.5, self._check_device_mount, device)
        app.device_manager.device_connected(id_, **info)

    def _device_changed(self, device):
        id_, info = self._get_device_info(device)
        app.device_manager.device_changed(id_, **info)

    def _device_disconnected(self, device):
        id_, info = self._get_device_info(device)
        app.device_manager.device_disconnected(id_)

    def eject(self, info):
        if info.id not in self._connected:
            return
        usb_info = self._connected[info.id]
        usbutils.eject_mount(usb_info['mount'])
