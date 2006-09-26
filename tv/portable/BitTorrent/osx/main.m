//
//  main.m
//  BitTorrent OSX
//
//  Created by Andrew Loewenstern on Mon Apr 29 2002.
//  Copyright (c) 2001 __MyCompanyName__. All rights reserved.
//

#import <Cocoa/Cocoa.h>
#import <python2.3/Python.h>
#import <sys/resource.h>

// external function, registers Python module containing BT callbacks
void init_callbacks();

int main(int argc, const char *argv[])
{
    
    NSAutoreleasePool *pool =[[NSAutoreleasePool alloc] init];
    PyObject *mm, *md, *path;    
    struct rlimit lim;
    
    // set the open file limit to 11
    if(!getrlimit(RLIMIT_NOFILE, &lim)) {
        lim.rlim_cur = lim.rlim_max;
        if(setrlimit(RLIMIT_NOFILE, &lim)) {
            NSLog(@"Failed to increase open file limit.");
        }
    }
    else {
        // try something reasonable
        lim.rlim_cur = 1024;
        if(setrlimit(RLIMIT_NOFILE, &lim)) {
            NSLog(@"Failed to increase open file limit.");
        }
    }
    
    // set up python
    Py_SetPythonHome((char*)[[[NSBundle mainBundle] resourcePath] cString]);
    Py_Initialize();
    PySys_SetArgv(argc, (char **)argv);
    PyEval_InitThreads();

    // add our resource path to sys.path so we can find the BT modules
    mm = PyImport_ImportModule("sys");
    md = PyModule_GetDict(mm);
    path = PyDict_GetItemString(md, "path");
    PyList_Append(path, PyString_FromString([[[NSBundle mainBundle] resourcePath] cString]));
    
    [pool release];
    return NSApplicationMain(argc, argv);
}
