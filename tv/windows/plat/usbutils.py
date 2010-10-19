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

def getDeviceInterface(i, device=None):
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
        

def getDeviceInterfaceDetail(interface):
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

def getParent(devInst):
    parent = ctypes.wintypes.DWORD(0)
    CM_Get_Parent(ctypes.byref(parent), devInst, 0)
    return parent.value

def getDeviceID(devInst):
    buffer = ctypes.create_unicode_buffer(255)
    CM_Get_Device_ID(devInst, ctypes.byref(buffer), 255, 0)
    return buffer.value

def getVolumeName(mount_point):
    buffer = ctypes.create_unicode_buffer(50)
    kernel32.GetVolumeNameForVolumeMountPointW(mount_point, ctypes.byref(buffer), 50)
    return buffer.value

def getPathName(volume):
    buffer = ctypes.create_unicode_buffer(255)
    length = ctypes.wintypes.DWORD(0)
    kernel32.GetVolumePathNamesForVolumeNameW(volume, ctypes.byref(buffer), 255, ctypes.byref(length))
    return buffer.value

def connectedDevices():
    interfaceIndex = 0
    while True:
        interface = getDeviceInterface(interfaceIndex)
        if interface is None:
            break
        interfaceIndex += 1 # loop through the interfaces
        path, device = getDeviceInterfaceDetail(interface)
        deviceParent = getParent(device.DevInst)
        if not getDeviceID(deviceParent).startswith('USBSTOR'):
            # not a USB storage device
            continue
        volumeName = getVolumeName(path + '\\')
        driveName = getPathName(volumeName)
        # parent's parent device ID looks like USB\VID_0BB4&PID_0FF9\HT09NR210732
        _, ids, serial = getDeviceID(getParent(deviceParent)).split('\\', 2)
        vendor_id, product_id = [int(id[-4:], 16) for id in ids.split('&')]
        yield {
                'volume': volumeName,
                'mount': driveName,
                'vendor_id': vendor_id,
                'product_id': product_id,
                'serial': serial
                }

