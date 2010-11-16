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

import ctypes, ctypes.wintypes

INVALID_HANDLE_VALUE = -1
DIGCF_PRESENT = 0x00000002
DIGCF_DEVICEINTERFACE = 0x00000010
ERROR_INSUFFICIENT_BUFFER = 122
ERROR_NO_MORE_ITEMS = 259
MAXIMUM_USB_STRING_LENGTH = 255

kernel32 = ctypes.windll.kernel32

setupapi = ctypes.windll.setupapi
SetupDiGetClassDevs = setupapi.SetupDiGetClassDevsW
SetupDiEnumDeviceInterfaces = setupapi.SetupDiEnumDeviceInterfaces
SetupDiGetDeviceInterfaceDetail = setupapi.SetupDiGetDeviceInterfaceDetailW

CM_Get_Parent = setupapi.CM_Get_Parent
CM_Get_Device_ID = setupapi.CM_Get_Device_IDW
CM_Request_Device_Eject = setupapi.CM_Request_Device_EjectW

class GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_ulong),
                ("Data2", ctypes.c_ushort),
                ("Data3", ctypes.c_ushort),
                ("Data4", ctypes.c_ubyte * 8)]

    def __str__(self):
        return '{%08X-%04X-%04X-%04X-%012X}' % (
            self.Data1, self.Data2, self.Data3,
            self.Data4[0] * 256 + self.Data4[1],
            self.Data4[2] * (256 ** 5) +
            self.Data4[3] * (256 ** 4) +
            self.Data4[4] * (256 ** 3) +
            self.Data4[5] * (256 ** 2) +
            self.Data4[6] * 256 +
            self.Data4[7])

class SP_DEVINFO_DATA(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.wintypes.DWORD),
            ("ClassGuid", GUID),
            ("DevInst", ctypes.wintypes.DWORD),
            ("Reserved", ctypes.c_void_p)
            ]

class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.wintypes.DWORD),
            ("InterfaceClassGuid", GUID),
            ("Flags", ctypes.wintypes.DWORD),
            ("Reserved", ctypes.c_void_p)
            ]

class SP_DEVICE_INTERFACE_DETAIL_DATA(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.wintypes.DWORD),
            ("DevicePath", ctypes.c_wchar*255)]

GUID_DEVINTERFACE_VOLUME = GUID(0x53F5630D, 0xB6BF, 0x11D0,
        (ctypes.c_ubyte*8)(0x94, 0xF2, 0x00, 0xA0, 0xC9, 0x1E, 0xFB, 0x8B))

hDevInfo = SetupDiGetClassDevs(ctypes.byref(GUID_DEVINTERFACE_VOLUME),
                               0,
                               0,
                               DIGCF_PRESENT | DIGCF_DEVICEINTERFACE)
if hDevInfo == INVALID_HANDLE_VALUE:
    print ctypes.windll.GetLastError(), ctypes.windll.FormatError()

def get_device_interface(i, device=None):
    interfaceData = SP_DEVICE_INTERFACE_DATA()
    interfaceData.cbSize = ctypes.sizeof(SP_DEVICE_INTERFACE_DATA)
    if SetupDiEnumDeviceInterfaces(
        hDevInfo,
        device and ctypes.byref(device) or None,
        ctypes.byref(GUID_DEVINTERFACE_VOLUME),
        i,
        ctypes.byref(interfaceData)):
        return interfaceData
    elif ctypes.GetLastError() == ERROR_NO_MORE_ITEMS:
        return
    else:
        print ctypes.GetLastError(), ctypes.windll.FormatError()

def get_device_interface_detail(interface):
    detail = None
    size = 0
    length = ctypes.wintypes.DWORD(0)
    device = SP_DEVINFO_DATA(cbSize=ctypes.sizeof(SP_DEVINFO_DATA))
    while not SetupDiGetDeviceInterfaceDetail(
        hDevInfo,
        ctypes.byref(interface),
        detail and ctypes.byref(detail) or None,
        size,
        ctypes.byref(length),
        ctypes.byref(device)
        ):
        if ctypes.GetLastError() == ERROR_INSUFFICIENT_BUFFER:
            size = length.value
            detail = SP_DEVICE_INTERFACE_DETAIL_DATA(
                cbSize=6)
        else:
            print ctypes.windll.GetLastError(), ctypes.windll.FormatError()
            return
    return detail.DevicePath, device

def device_eject(devInst):
    CM_Request_Device_Eject(devInst, None, None, 0, 0)


def get_parent(devInst):
    parent = ctypes.wintypes.DWORD(0)
    CM_Get_Parent(ctypes.byref(parent), devInst, 0)
    return parent.value

def get_device_id(devInst):
    buffer = ctypes.create_unicode_buffer(255)
    CM_Get_Device_ID(devInst, ctypes.byref(buffer), 255, 0)
    return buffer.value

def get_volume_name(mount_point):
    buffer = ctypes.create_unicode_buffer(50)
    kernel32.GetVolumeNameForVolumeMountPointW(mount_point,
                                               ctypes.byref(buffer), 50)
    return buffer.value

def get_path_name(volume):
    buffer = ctypes.create_unicode_buffer(255)
    length = ctypes.wintypes.DWORD(0)
    kernel32.GetVolumePathNamesForVolumeNameW(volume, ctypes.byref(buffer),
                                              255, ctypes.byref(length))
    return buffer.value

def connected_devices():
    """
    Returns a generator which returns small dictionaries of data representing
    the connected USB storage devices.
    """
    interface_index = 0
    while True:
        interface = get_device_interface(interface_index)
        if interface is None:
            break
        interface_index += 1 # loop through the interfaces
        path, device = get_device_interface_detail(interface)
        deviceParent = get_parent(device.DevInst)
        if not get_device_id(deviceParent).startswith('USBSTOR'):
            # not a USB storage device
            continue
        volume_name = get_volume_name(path + '\\')
        drive_name = get_path_name(volume_name)
        # parent's parent device ID looks like
        # USB\VID_0BB4&PID_0FF9\HT09NR210732
        _, ids, serial = get_device_id(
            get_parent(deviceParent)).split('\\', 2)
        vendor_id, product_id = [int(id[-4:], 16) for id in ids.split('&')]
        yield {
                'volume': volume_name,
                'mount': drive_name,
                'vendor_id': vendor_id,
                'product_id': product_id,
                'serial': serial,
                'devInst': get_parent(deviceParent)
                }

