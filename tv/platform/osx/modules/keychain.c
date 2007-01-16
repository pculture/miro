#include <Security/Security.h>
#include <Python.h>

#define RETURN_NONE_IF(e) if ((e)) return Py_None

static PyObject* keychain_getAuthInfo(PyObject* self, PyObject* args)
{
    char*   serviceName = NULL;
    int     serviceNameLength = 0;
    int     ok = PyArg_ParseTuple(args, "s#", &serviceName, &serviceNameLength);

    RETURN_NONE_IF(!ok);
    
    OSStatus                    err = noErr;
    SecKeychainSearchRef        search = NULL;
    SecKeychainAttribute        searchAttr[] =  { { kSecServerItemAttr, serviceNameLength, serviceName } };
    SecKeychainAttributeList    searchAttrList = { 1, searchAttr };
    
    err = SecKeychainSearchCreateFromAttributes( NULL, kSecInternetPasswordItemClass, &searchAttrList, &search);
    RETURN_NONE_IF(err != noErr);

    SecKeychainItemRef  item;
    err = SecKeychainSearchCopyNext(search, &item);
    RETURN_NONE_IF(err != noErr);

    SecKeychainAttributeList*   attrList = NULL;
    void*                       passwordData = NULL;
    UInt32                      passwordLength = 0U;
    UInt32                      tags[] = { kSecAccountItemAttr };
    UInt32                      formats[] = { CSSM_DB_ATTRIBUTE_FORMAT_STRING };
    SecKeychainAttributeInfo    info = { 1, tags, formats };
    
    err = SecKeychainItemCopyAttributesAndData( item, &info, NULL, &attrList, &passwordLength, &passwordData);
    RETURN_NONE_IF(err != noErr);

    PyObject*   username = PyString_FromStringAndSize(attrList->attr[0].data, attrList->attr[0].length);
    PyObject*   password = PyString_FromStringAndSize(passwordData, passwordLength);
    PyObject*   authInfo = PyDict_New();

    PyDict_SetItemString(authInfo, "username", username);
    PyDict_SetItemString(authInfo, "password", password);

    SecKeychainItemFreeAttributesAndData(attrList, passwordData);
    CFRelease(item);
    CFRelease(search);

    return authInfo;
}


static PyMethodDef KeychainMethods[] = 
{
    { "getAuthInfo", keychain_getAuthInfo, METH_VARARGS, "Returns authentication info for the passed domain." },
    { NULL, NULL, 0, NULL }
};

PyMODINIT_FUNC initkeychain(void)
{
    Py_InitModule("keychain", KeychainMethods);
}
