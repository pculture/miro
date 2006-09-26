#import <python2.3/Python.h>

// this is the proxy object that has the callbacks for each DL
// encapsulates a connection to the it's DL Window controller
typedef struct {
    PyObject_HEAD
    id dlController;  // NSProxy connection
    PyObject *chooseFlag;  // chooseFileFlag
} bt_ProxyObject;
