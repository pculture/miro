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
    float       seconds = 0;
    
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

        seconds = handle / 1000000000;
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