//
//  callbacks.m
//  BitTorrent
//
//  Created by Dr. Burris T. Ewell on Tue Apr 30 2002.
//  Copyright (c) 2001 __MyCompanyName__. All rights reserved.
//

#import <Cocoa/Cocoa.h>

#import <python2.3/Python.h>
#import "BTCallbacks.h"
#import "pystructs.h"

static PyObject *chooseFile(bt_ProxyObject *self, PyObject *args)
{
    NSAutoreleasePool *pool =[[NSAutoreleasePool alloc] init];
    char *def = "";
    PyObject *obj, *mm;
    PyObject *megabyte;
    char *saveas = NULL;
    int dir, len;
    PyObject *res;
    NSString *str;

    if (!PyArg_ParseTuple(args, "s#Osi", &def, &len, &obj, &saveas, &dir))
        return NULL;

    megabyte  = Py_BuildValue("f", 1048576.0);
    obj = PyNumber_Divide(obj, megabyte);
    
    mm = PyImport_ImportModule("__main__");

    str = [NSString stringWithUTF8String:def];
    if (!str) {
        str = [NSString stringWithCString:def length:len];
        if (!str) { return NULL;}
    }
    
    Py_BEGIN_ALLOW_THREADS
        [self->dlController chooseFile:str size:PyFloat_AsDouble(obj) isDirectory:dir];
    Py_END_ALLOW_THREADS
  
    PyObject_CallMethod(self->chooseFlag, "wait", NULL);  
    
    Py_BEGIN_ALLOW_THREADS
    str = [self->dlController savePath];
    Py_END_ALLOW_THREADS

    if(str) {
        res = PyString_FromString([str UTF8String]);
    }
    else {
        Py_INCREF(Py_None);
        res = Py_None;
    }
    
    Py_DECREF(obj);
    Py_DECREF(megabyte);
    
    [pool release];
    return res;
}

static PyObject *display(bt_ProxyObject *self, PyObject *args, PyObject *keywds)
{
    PyObject *d;
    NSData *data;
    NSAutoreleasePool *pool =[[NSAutoreleasePool alloc] init];

    if (!PyArg_ParseTuple(args, "O", &d))
        return NULL;

    Py_INCREF(d);
    data = [NSData dataWithBytes:&d length:sizeof(PyObject *)];
    
    Py_BEGIN_ALLOW_THREADS
        [self->dlController display:data];
    Py_END_ALLOW_THREADS
    
    [pool release];    

        
    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject *metaprogress(bt_ProxyObject *self, PyObject *args)
{
    NSAutoreleasePool *pool =[[NSAutoreleasePool alloc] init];
    float prog;
    if (!PyArg_ParseTuple(args, "f", &prog))
        return NULL;
    Py_BEGIN_ALLOW_THREADS
        [self->dlController progress:prog];
        [pool release];
    Py_END_ALLOW_THREADS
        
    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject *fnameprogress(bt_ProxyObject *self, PyObject *args)
{
    NSAutoreleasePool *pool =[[NSAutoreleasePool alloc] init];
    char *fname;
    if (!PyArg_ParseTuple(args, "s", &fname))
        return NULL;
    Py_BEGIN_ALLOW_THREADS
        [self->dlController progressFname:[NSString stringWithUTF8String:fname]];
    [pool release];
    Py_END_ALLOW_THREADS

        Py_INCREF(Py_None);
    return Py_None;

}

static PyObject *pathUpdated(bt_ProxyObject *self, PyObject *args)
{
    NSAutoreleasePool *pool =[[NSAutoreleasePool alloc] init];
    char *fname;
    if (!PyArg_ParseTuple(args, "s", &fname))
        return NULL;
    Py_BEGIN_ALLOW_THREADS
        [self->dlController pathUpdated:[NSString stringWithCString:fname]];
    [pool release];
    Py_END_ALLOW_THREADS

        Py_INCREF(Py_None);
    return Py_None;

}
static PyObject *finished(bt_ProxyObject *self, PyObject *args)
{
    NSAutoreleasePool *pool =[[NSAutoreleasePool alloc] init];

    Py_BEGIN_ALLOW_THREADS
        [self->dlController finished];
    Py_END_ALLOW_THREADS
    [pool release];
        Py_INCREF(Py_None);
    return Py_None;
}

static PyObject *nerror(bt_ProxyObject *self, PyObject *args)
{
    char *errmsg = NULL;
    char *BTerr = NULL;
    NSString *str;
    NSAutoreleasePool *pool =[[NSAutoreleasePool alloc] init];

    if(!PyArg_ParseTuple(args, "s", &BTerr, &errmsg))
        return NULL;
    if(errmsg)
        str = [NSString stringWithCString:errmsg];
    else
        str = [NSString stringWithCString:BTerr];

    Py_BEGIN_ALLOW_THREADS
        [self->dlController error:str];
    Py_END_ALLOW_THREADS
    [pool release];
    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject *paramfunc(bt_ProxyObject *self, PyObject *args)
{
    PyObject *d;
    NSData *data;
    NSAutoreleasePool *pool =[[NSAutoreleasePool alloc] init];

    if(!PyArg_ParseTuple(args, "O", &d))
        return NULL;
    
    Py_INCREF(d);
    data = [NSData dataWithBytes:&d length:sizeof(PyObject *)];
    
    Py_BEGIN_ALLOW_THREADS
        [self->dlController paramFunc:data];
    Py_END_ALLOW_THREADS
    
    [pool release];    
    Py_INCREF(Py_None);
    return Py_None;
}


// first up is a PythonType to hold the proxy to the DL window

staticforward PyTypeObject bt_ProxyType;

static void bt_proxy_dealloc(bt_ProxyObject* self)
{
    [self->dlController release];
    Py_DECREF(self->chooseFlag);
    PyObject_Del(self);
}

static struct PyMethodDef reg_methods[] = {
	{"display",	(PyCFunction)display, METH_VARARGS|METH_KEYWORDS},
    {"chooseFile",	(PyCFunction)chooseFile, METH_VARARGS},
    {"pathUpdated",	(PyCFunction)pathUpdated, METH_VARARGS},
	{"finished",	(PyCFunction)finished, METH_VARARGS},
	{"nerror",	(PyCFunction)nerror, METH_VARARGS},
    {"metaprogress", (PyCFunction)metaprogress, METH_VARARGS},
    {"fnameprogress", (PyCFunction)fnameprogress, METH_VARARGS},
	{"paramfunc",	(PyCFunction)paramfunc, METH_VARARGS},
	{NULL,		NULL}		/* sentinel */
};

static PyObject *proxy_getattr(PyObject *prox, char *name)
{
	return Py_FindMethod(reg_methods, prox, name);
}

static PyTypeObject bt_ProxyType = {
    PyObject_HEAD_INIT(NULL)
    0,
    "BT Proxy",
    sizeof(bt_ProxyObject),
    0,
    (destructor)bt_proxy_dealloc, /*tp_dealloc*/
    0,          /*tp_print*/
    proxy_getattr,          /*tp_getattr*/
    0,          /*tp_setattr*/
    0,          /*tp_compare*/
    0,          /*tp_repr*/
    0,          /*tp_as_number*/
    0,          /*tp_as_sequence*/
    0,          /*tp_as_mapping*/
    0,          /*tp_hash */
};

// given two ports, create a new proxy object
bt_ProxyObject *bt_getProxy(NSPort *receivePort, NSPort *sendPort, PyObject *chooseFileFlag)
{
    bt_ProxyObject *proxy;
    id foo;
    
    proxy = PyObject_New(bt_ProxyObject, &bt_ProxyType);
    foo = (id)[[NSConnection connectionWithReceivePort:receivePort
					sendPort:sendPort]
			    rootProxy];
    [foo setProtocolForProxy:@protocol(BTCallbacks)];
    [foo retain];
    proxy->dlController = foo;
    proxy->chooseFlag = chooseFileFlag;
    Py_INCREF(proxy->chooseFlag);
    return (bt_ProxyObject *)proxy;
}

// given two ports, create a new proxy object
bt_ProxyObject *bt_getMetaProxy(NSPort *receivePort, NSPort *sendPort)
{
    bt_ProxyObject *proxy;
    id foo;

    proxy = PyObject_New(bt_ProxyObject, &bt_ProxyType);
    foo = (id)[[NSConnection connectionWithReceivePort:receivePort
                                                             sendPort:sendPort]
        rootProxy];
    [foo setProtocolForProxy:@protocol(MetaGenerateCallbacks)];
    [foo retain];
    proxy->dlController = foo;
    return (bt_ProxyObject *)proxy;
}
