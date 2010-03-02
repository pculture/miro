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
