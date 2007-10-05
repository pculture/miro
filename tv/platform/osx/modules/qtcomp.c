/*
 * Miro - an RSS based video player application
 * Copyright (C) 2005-2007 Participatory Culture Foundation
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
*/

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
