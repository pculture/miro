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
import ctypes, ctypes.wintypes
import tempfile
import _winreg

import os

LOTS_OF_DEBUGGING = False

if LOTS_OF_DEBUGGING:
    logging.getLogger().setLevel(logging.DEBUG)

def warn(what, code, message):
    logging.warn('error doing %s (%d): %s', what, code, message)

INVALID_HANDLE_VALUE = -1
DIGCF_PRESENT = 0x00000002
DIGCF_DEVICEINTERFACE = 0x00000010
ERROR_INSUFFICIENT_BUFFER = 122
ERROR_NO_MORE_ITEMS = 259
MAXIMUM_USB_STRING_LENGTH = 255
FILE_READ_ONLY_VOLUME = 0x00080000
MAX_PATH = 260

GENERIC_READ = 0x80000000L
GENERIC_WRITE = 0x40000000L
FILE_SHARE_READ = 0x1
FILE_SHARE_WRITE = 0x2
OPEN_EXISTING = 0x3

FSCTL_LOCK_VOLUME = 0x90018 # XXX use these to do eject another way?
FSCTL_DISMOUNT_VOLUME = 0x90020
IOCTL_STORAGE_MEDIA_REMOVAL = 0x2D4804
IOCTL_STORAGE_EJECT_MEDIA = 0x2D4808
IOCTL_STORAGE_GET_DEVICE_NUMBER = 0x2D1080

kernel32 = ctypes.windll.kernel32

setupapi = ctypes.windll.setupapi
SetupDiGetClassDevs = setupapi.SetupDiGetClassDevsW
SetupDiEnumDeviceInterfaces = setupapi.SetupDiEnumDeviceInterfaces
SetupDiGetDeviceInterfaceDetail = setupapi.SetupDiGetDeviceInterfaceDetailW
GetVolumeInformation = kernel32.GetVolumeInformationW

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

class PREVENT_MEDIA_REMOVAL(ctypes.Structure):
    _fields_ = [('PreventMediaRemoval', ctypes.wintypes.BOOLEAN)]

class STORAGE_DEVICE_NUMBER(ctypes.Structure):
    _fields_ = [('DeviceType', ctypes.wintypes.DWORD),
                ('DeviceNumber', ctypes.wintypes.ULONG),
                ('PartitionNumber', ctypes.wintypes.ULONG)]

GUID_DEVINTERFACE_VOLUME = GUID(0x53F5630D, 0xB6BF, 0x11D0,
        (ctypes.c_ubyte*8)(0x94, 0xF2, 0x00, 0xA0, 0xC9, 0x1E, 0xFB, 0x8B))
GUID_DEVINTERFACE_DISK = GUID(0x53F56307, 0xB6BF, 0x11D0,
        (ctypes.c_ubyte*8)(0x94, 0xF2, 0x00, 0xA0, 0xC9, 0x1E, 0xFB, 0x8B))

hDevInfo = None
current_guid = None

def get_class_devs(guid=None):
    global hDevInfo, current_guid
    if guid is None:
        guid = GUID_DEVINTERFACE_VOLUME
    current_guid = guid
    hDevInfo = SetupDiGetClassDevs(ctypes.byref(current_guid),
                                   0,
                                   0,
                                   DIGCF_PRESENT | DIGCF_DEVICEINTERFACE)
    if hDevInfo == INVALID_HANDLE_VALUE:
        warn('get_class_devs', ctypes.GetLastError(),
             ctypes.FormatError())

def get_device_interface(i, device=None):
    interfaceData = SP_DEVICE_INTERFACE_DATA()
    interfaceData.cbSize = ctypes.sizeof(SP_DEVICE_INTERFACE_DATA)
    if SetupDiEnumDeviceInterfaces(
        hDevInfo,
        device and ctypes.byref(device) or None,
        ctypes.byref(current_guid),
        i,
        ctypes.byref(interfaceData)):
        return interfaceData
    elif ctypes.GetLastError() == ERROR_NO_MORE_ITEMS:
        return
    else:
        warn('get_device_interface', ctypes.GetLastError(),
             ctypes.FormatError())

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
            warn('get_device_interface_detail', ctypes.GetLastError(),
                 ctypes.FormatError())
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

def read_write_drive(mount):
    """
    Checks if the given mount path is read write.
    """
    try:
        # create buffers for output params.  We don't actually use volume_name
        # or fs_name at the moment, but the API requires us to pass them in.
        volume_name = ctypes.create_string_buffer(MAX_PATH+1)
        fs_name = ctypes.create_string_buffer(MAX_PATH+1)
        volume_flags = ctypes.wintypes.DWORD(0)

        rv = GetVolumeInformation(mount, volume_name, MAX_PATH+1,
                None, None, ctypes.byref(volume_flags), fs_name, MAX_PATH+1)
        if rv == 0: # mount path is invalid
            return False

        if volume_flags.value & FILE_READ_ONLY_VOLUME:
            return False

        return True
    except EnvironmentError:
        if LOTS_OF_DEBUGGING:
            logging.exception('error in read_write_drive(%r)', mount)
        return False

def get_device_number(handle_or_path):
    opened_handle = False
    if isinstance(handle_or_path, basestring):
        opened_handle = True
        handle = kernel32.CreateFileA(
            unicode(handle_or_path).encode('utf8'),
            GENERIC_READ | GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            0, None)
        if handle == INVALID_HANDLE_VALUE:
            return handle
    else:
        handle = handle_or_path
    length = ctypes.wintypes.DWORD(0)
    sdn = STORAGE_DEVICE_NUMBER()
    try:
        if not kernel32.DeviceIoControl(
            handle, IOCTL_STORAGE_GET_DEVICE_NUMBER, None, 0,
            ctypes.byref(sdn), ctypes.sizeof(sdn),
            ctypes.byref(length), None):
            warn('get_device_number',
                 ctypes.GetLastError(),
                 ctypes.FormatError())
            return INVALID_HANDLE_VALUE
        else:
            return sdn.DeviceNumber
    finally:
        if opened_handle:
            kernel32.CloseHandle(handle)

def eject_mount(mount_point):
    """
    Given a mount point ('G:\\'), ejects the drive.
    """
    get_class_devs(guid=GUID_DEVINTERFACE_DISK)
    if mount_point.endswith('\\'):
        # strip trailing slash
        mount_point = mount_point[:-1]
    device_number = get_device_number('\\\\.\\%s' % mount_point)
    if device_number == INVALID_HANDLE_VALUE:
        return False
    index = 0
    while True:
        interface = get_device_interface(index)
        if interface is None:
            return False
        index += 1
        path, device = get_device_interface_detail(interface)
        if get_device_number(path) == device_number:
            device_eject(get_parent(device.DevInst))
            return True

def iter_reg_keys(key_or_handle, root=_winreg.HKEY_LOCAL_MACHINE):
    if isinstance(key_or_handle, basestring):
        handle = _winreg.OpenKey(root, key_or_handle)
    else:
        handle = key_or_handle
    index = 0
    while True:
        try:
            yield _winreg.EnumKey(handle, index)
        except EnvironmentError:
            break
        index += 1

def iter_reg_values(key_or_handle, root=_winreg.HKEY_LOCAL_MACHINE):
    if isinstance(key_or_handle, basestring):
        handle = _winreg.OpenKey(root, key_or_handle)
    else:
        handle = key_or_handle
    index = 0
    while True:
        try:
            name, value, type_ = _winreg.EnumValue(handle, index)
            yield name, value
        except EnvironmentError:
            break
        index += 1

def get_real_reg_handle(reg_key, parent_handle=None):
    # key parts is now something like: ['SYSTEM',
    # 'CurrentControllerSet', 'Enum', USBSTOR',
    # 'DISK&VEN_SAMSUNG&PROD_SGH_T849_CARD&REV_0000',
    # '1000AD3789CA&1'], but that name has had '-' converted to '_',
    # so if it doesn't work we'll need to massage it a bit
    try:
        return _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE,
                                 reg_key)
    except OSError:
        pass

    key_parts = reg_key.upper().split('\\')
    good_key = []
    handle = None
    while key_parts:
        try:
            handle = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE,
                                   '\\'.join(good_key + key_parts[:1]))
        except OSError:
            for key in iter_reg_keys('\\'.join(good_key)):
                if key.replace('-', '_').upper() == key_parts[0]:
                    good_key.append(key)
                    break
            else:
                raise OSError('could not find %s underneath %s' % (
                                   key_parts[0], '\\'.join(good_key)))
        else:
            if len(key_parts) != 1: # not the last round
                handle.Close()
            good_key.append(key_parts[0])
        key_parts = key_parts[1:]
    return handle

def get_friendy_name(key):
    for name, value in iter_reg_values(get_real_reg_handle(key)):
        if name.lower() == 'friendlyname':
            return value

def connected_devices():
    """
    Returns a generator which returns small dictionaries of data
    representing the connected USB storage devices.
    """
    drive_names = set()
    get_class_devs() # reset the device class to pick up all devices
    interface_index = 0
    while True:
        interface = get_device_interface(interface_index)
        if interface is None:
            break
        interface_index += 1 # loop through the interfaces
        path, device = get_device_interface_detail(interface)
        device_id = get_device_id(device.DevInst)
        if LOTS_OF_DEBUGGING:
            logging.debug('connected_devices(): %i %r %r',
                          interface_index, path, device_id)
        if '_??_USBSTOR' in device_id:
            """Looks like:
STORAGE\VOLUME\_??_USBSTOR#DISK&VEN_KINGSTON&PROD_DATATRAVELER_G3&REV_PMAP#\
001372982D6AEAC18576014E&0#{53F56307-B6BF-11D0-94F2-00A0C91EFB8B}"""
            reg_key = '\\'.join(device_id.split('_??_')[1].split('#')[:3])
            logging.debug('reg key from device_id: %r', reg_key)
        else:
            deviceParent = get_parent(device.DevInst)
            reg_key = get_device_id(deviceParent)
            if LOTS_OF_DEBUGGING:
                logging.debug('parent id: %r', reg_key)
            if not reg_key.startswith('USBSTOR'):
                # not a USB storage device
                continue
        reg_key = reg_key.replace('-', '_')
        volume_name = get_volume_name(path + '\\')
        if LOTS_OF_DEBUGGING:
            logging.debug('volume name: %r', volume_name)
        drive_name = get_path_name(volume_name)
        if LOTS_OF_DEBUGGING:
            logging.debug('drive name: %r (%s)', drive_name,
                          read_write_drive(drive_name))
        full_key = 'SYSTEM\\CurrentControlSet\\Enum\\%s' % reg_key
        try:
            friendly_name = get_friendy_name(full_key)
        except WindowsError:
            friendly_name = None
            logging.debug('could not open registry key %r (from %r/%r)',
                          full_key, path, device_id,
                          exc_info=True)
        if not friendly_name:
            continue
        yield {
            'volume': volume_name,
            'mount': drive_name,
            'name': friendly_name,
            }
        if drive_name:
            drive_names.add(drive_name[0])
    for letter in sorted(set('DEFGHIJKLMNOPQRSTUVWXYZ') - drive_names):
        mount = u'%s:\\' % letter
        if read_write_drive(mount):
            if LOTS_OF_DEBUGGING:
                logging.debug('drive %s is mounted', letter)
            yield {
                'volume': u'fake-volume-%s' % letter,
                'mount': mount,
                'name': 'Drive %s:' % letter
                }
        elif LOTS_OF_DEBUGGING:
                logging.debug('drive %s is missing', letter)

if __name__ == '__main__':
    for d in connected_devices():
        print d
