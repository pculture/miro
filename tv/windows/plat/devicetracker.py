import logging
import os

import ctypes

from miro.plat.frontends.widgets import timer
from miro.plat import usbutils
from miro import app
from miro import devices
from miro import messages

GWL_WNDPROC = -4
WndProcType = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, ctypes.c_uint,
                                 ctypes.c_int, ctypes.c_int)

class DeviceTracker(object):
    def __init__(self):
        self._connected = {}

    def start_tracking(self):
	self._wndprocWrapped = WndProcType(self._wndproc) # keep it around to
                                                          # avoid GC
        self._oldwndproc = ctypes.windll.user32.SetWindowLongW(
		app.widgetapp.window._window.window.handle,
		GWL_WNDPROC, self._wndprocWrapped)

        self._devicesChanged()

    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == 537 and wparam == 7:
            #previousChange, self._lastChange = self._lastChange, time.time()
            #if self._lastChange - previousChange > 0.25:
            self._devicesChanged()
        return ctypes.windll.user32.CallWindowProcW(self._oldwndproc, hwnd,
                                                    msg, wparam, lparam)

    def _devicesChanged(self):
        # re-poll the devices, and figure out what, if anything, is different
        volumes = set()
        for device in usbutils.connectedDevices():
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
	database = devices.load_database(mount)
        device_info = devices.device_manager.get_device_by_id(
	    device['vendor_id'], device['product_id'],
            database.get('device_name'))
        if not os.path.exists(mount):
            mount = size = remaining = None
	else:
            available = ctypes.wintypes.LARGE_INTEGER()
            total = ctypes.wintypes.LARGE_INTEGER()
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(unicode(mount),
                                                       ctypes.byref(available),
						       ctypes.byref(total),
                                                       None)
	    remaining = available.value
	    size = total.value
        return messages.DeviceInfo(device['volume'], device_info, mount,
				   database, size, remaining)

    def _check_device_mount(self, device):
        if device['volume'] not in self._connected:
            # device was removed
            return
        if os.path.exists(device['mount']):
            self._device_changed(device)
	    return
        timer.add(0.5, self._check_device_mount, device)

    def _device_connected(self, device):
        try:
           info = self._get_device_info(device)
	except KeyError:
            logging.debug('unknown device connected: %r' % (device,))
            return
        if not info.mount:
            # we don't get notified :( so poll instead
            timer.add(0.5, self._check_device_mount, device)
	devices.device_connected(info)

    def _device_changed(self, device):
        try:
            info = self._get_device_info(device)
        except KeyError:
            return
        devices.device_changed(info)

    def _device_disconnected(self, device):
        try:
            info = self._get_device_info(device)
        except KeyError:
            return
        devices.device_disconnected(info)

tracker = DeviceTracker()
