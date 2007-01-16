#include <CoreFoundation/CoreFoundation.h>
#include <Carbon/Carbon.h>
#include <Python.h>

static PyObject* qtcomp_register(PyObject* self, PyObject* args)
{
    PyObject*   result = Py_False;
    const char* path = NULL;
    int         ok = PyArg_ParseTuple(args, "s", &path);
    
    if (ok)
    {
        CFStringRef componentPath = CFStringCreateWithCString(kCFAllocatorDefault, path, kCFStringEncodingUTF8);
        CFURLRef    componentURL = CFURLCreateWithFileSystemPath(kCFAllocatorDefault, componentPath, kCFURLPOSIXPathStyle, false);
        FSRef       fsref;
        
        if (CFURLGetFSRef(componentURL, &fsref) == true)
        {
            OSStatus    err = RegisterComponentFileRef(&fsref, false);
            if (err == noErr)
            {
                result = Py_True;
            }
        }
    
        CFRelease(componentURL);
        CFRelease(componentPath);        
    }
    
    return result;
}

static PyMethodDef QTCompMethods[] = 
{
    { "register", qtcomp_register, METH_VARARGS, "Dynamically register the Quicktime component at the passed path." },
    { NULL, NULL, 0, NULL }
};

PyMODINIT_FUNC initqtcomp(void)
{
    Py_InitModule("qtcomp", QTCompMethods);
}