/*
# Miro - an RSS based video player application
# Copyright (C) 2005-2010 Participatory Culture Foundation
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
*/

#include <CoreFoundation/CoreFoundation.h>
#include <IOKit/IOKitLib.h>
#include <Python.h>

#define RETURN_ZERO_IF(e) if ((e)) return Py_BuildValue("f", 0.0f)


static PyObject* idletime_get(PyObject* self, PyObject* args)
{
    kern_return_t   result;
    mach_port_t     masterPort;
    
    result = IOMasterPort(kIOMasterPortDefault, &masterPort);
    RETURN_ZERO_IF(result != KERN_SUCCESS);
    
    CFMutableDictionaryRef  matchingDict = IOServiceMatching("IOHIDSystem");
    io_iterator_t           hidIterator;
    
    result = IOServiceGetMatchingServices(masterPort, matchingDict, &hidIterator);
    RETURN_ZERO_IF(hidIterator == 0);
    
    io_registry_entry_t hidEntry = IOIteratorNext(hidIterator);
    RETURN_ZERO_IF(hidEntry == 0);
    
    CFMutableDictionaryRef  hidProperties = NULL;
    result = IORegistryEntryCreateCFProperties(hidEntry, &hidProperties, kCFAllocatorDefault, 0);
    RETURN_ZERO_IF(result != KERN_SUCCESS || hidProperties == NULL);
    
    CFTypeRef   hidIdleTime = CFDictionaryGetValue(hidProperties, CFSTR("HIDIdleTime"));
    float       seconds = 0.0f;
    
    if (hidIdleTime != NULL)
    {
        CFTypeID    type = CFGetTypeID(hidIdleTime);
        uint64_t    handle = 0;

        if (type == CFDataGetTypeID())
        {
            CFRange range = CFRangeMake(0, sizeof(handle));
            CFDataGetBytes((CFDataRef)hidIdleTime, range, (UInt8*)&handle);
        } 
        else if (type == CFNumberGetTypeID()) 
        {
            CFNumberGetValue((CFNumberRef)hidIdleTime, kCFNumberSInt64Type, &handle);
        }

        seconds = handle / 1000000000.0;
    }

    IOObjectRelease(hidEntry);
    IOObjectRelease(hidIterator);
    CFRelease(hidProperties);

    return Py_BuildValue("f", seconds);
}

static PyMethodDef IdleTimeMethods[] = 
{
    { "get", idletime_get, METH_VARARGS, "Returns the system idle time in seconds" },
    { NULL, NULL, 0, NULL }
};

PyMODINIT_FUNC initidletime(void)
{
    Py_InitModule("idletime", IdleTimeMethods);
}
