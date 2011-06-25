/*
 * Copyright 2004-2005 The Growl Project.
 * Created by Jeremy Rossi <jeremy@jeremyrossi.com>
 * Released under the BSD license.
 */

#include <Python.h>
#include <CoreFoundation/CoreFoundation.h>

static PyObject * growl_PostDictionary(CFStringRef name, PyObject *self, PyObject *args) {
	int i, j;

	PyObject *inputDict;
	PyObject *pKeys = NULL;
	PyObject *pKey, *pValue;

	CFMutableDictionaryRef note = CFDictionaryCreateMutable(kCFAllocatorDefault,
															/*capacity*/ 0,
															&kCFTypeDictionaryKeyCallBacks,
															&kCFTypeDictionaryValueCallBacks);

	if (!PyArg_ParseTuple(args, "O!", &PyDict_Type, &inputDict))
		goto error;

	pKeys = PyDict_Keys(inputDict);
	for (i = 0; i < PyList_Size(pKeys); ++i) {
		CFStringRef convertedKey;

		/* Converting the PyDict key to NSString and used for key in note */
		pKey = PyList_GetItem(pKeys, i);
		if (!pKey)
			// Exception already set
			goto error;
		pValue = PyDict_GetItem(inputDict, pKey);
		if (!pValue) {
			// XXX Neeed a real Error message here.
			PyErr_SetString(PyExc_TypeError," ");
			goto error;
		}
		if (PyUnicode_Check(pKey)) {
			convertedKey = CFStringCreateWithBytes(kCFAllocatorDefault,
												   (const UInt8 *)PyUnicode_AS_DATA(pKey),
												   PyUnicode_GET_DATA_SIZE(pKey),
												   kCFStringEncodingUnicode,
												   false);
		} else if (PyString_Check(pKey)) {
			convertedKey = CFStringCreateWithCString(kCFAllocatorDefault,
													 PyString_AsString(pKey),
													 kCFStringEncodingUTF8);
		} else {
			PyErr_SetString(PyExc_TypeError,"The Dict keys must be strings/unicode");
			goto error;
		}

		/* Converting the PyDict value to NSString or NSData based on class  */
		if (PyString_Check(pValue)) {
			CFStringRef convertedValue = CFStringCreateWithCString(kCFAllocatorDefault,
																   PyString_AS_STRING(pValue),
																   kCFStringEncodingUTF8);
			CFDictionarySetValue(note, convertedKey, convertedValue);
			CFRelease(convertedValue);
		} else if (PyUnicode_Check(pValue)) {
			CFStringRef convertedValue = CFStringCreateWithBytes(kCFAllocatorDefault,
																 (const UInt8 *)PyUnicode_AS_DATA(pValue),
																 PyUnicode_GET_DATA_SIZE(pValue),
																 kCFStringEncodingUnicode,
																 false);
			CFDictionarySetValue(note, convertedKey, convertedValue);
			CFRelease(convertedValue);
		} else if (PyInt_Check(pValue)) {
			long v = PyInt_AS_LONG(pValue);
			CFNumberRef convertedValue = CFNumberCreate(kCFAllocatorDefault,
														kCFNumberLongType,
														&v);
			CFDictionarySetValue(note, convertedKey, convertedValue);
			CFRelease(convertedValue);
		} else if (pValue == Py_None) {
			CFDataRef convertedValue = CFDataCreate(kCFAllocatorDefault, NULL, 0);
			CFDictionarySetValue(note, convertedKey, convertedValue);
			CFRelease(convertedValue);
		} else if (PyList_Check(pValue)) {
			int size = PyList_Size(pValue);
			CFMutableArrayRef listHolder = CFArrayCreateMutable(kCFAllocatorDefault,
																size,
																&kCFTypeArrayCallBacks);
			for (j = 0; j < size; ++j) {
				PyObject *lValue = PyList_GetItem(pValue, j);
				if (PyString_Check(lValue)) {
					CFStringRef convertedValue = CFStringCreateWithCString(kCFAllocatorDefault,
																		   PyString_AS_STRING(lValue),
																		   kCFStringEncodingUTF8);
					CFArrayAppendValue(listHolder, convertedValue);
					CFRelease(convertedValue);
				} else if (PyUnicode_Check(lValue)) {
					CFStringRef convertedValue = CFStringCreateWithBytes(kCFAllocatorDefault,
																		 (const UInt8 *)PyUnicode_AS_DATA(lValue),
																		 PyUnicode_GET_DATA_SIZE(lValue),
																		 kCFStringEncodingUnicode,
																		 false);
					CFArrayAppendValue(listHolder, convertedValue);
					CFRelease(convertedValue);
				} else {
					CFRelease(convertedKey);
					PyErr_SetString(PyExc_TypeError,"The lists must only contain strings");
					goto error;
				}
			}
			CFDictionarySetValue(note, convertedKey, listHolder);
			CFRelease(listHolder);
		} else if (PyObject_HasAttrString(pValue, "rawImageData")) {
			PyObject *lValue = PyObject_GetAttrString(pValue, "rawImageData");
			if (!lValue) {
				goto error;
			} else if (PyString_Check(lValue)) {
				CFDataRef convertedValue = CFDataCreate(kCFAllocatorDefault,
														(const UInt8 *)PyString_AsString(lValue),
														PyString_Size(lValue));
				Py_DECREF(lValue);
				CFDictionarySetValue(note, convertedKey, convertedValue);
				CFRelease(convertedValue);
			} else {
				Py_DECREF(lValue);
				CFRelease(convertedKey);
				PyErr_SetString(PyExc_TypeError, "Icon with rawImageData attribute present must ensure it is a string.");
				goto error;
			}
		} else {
			CFRelease(convertedKey);
			PyErr_SetString(PyExc_TypeError, "Value is not of Str/List");
			goto error;
		}
		CFRelease(convertedKey);
	}

	Py_BEGIN_ALLOW_THREADS
	CFNotificationCenterPostNotification(CFNotificationCenterGetDistributedCenter(),
										 /*name*/ name,
										 /*object*/ NULL,
										 /*userInfo*/ note,
										 /*deliverImmediately*/ false);
	CFRelease(note);
	Py_END_ALLOW_THREADS

	Py_DECREF(pKeys);

	Py_INCREF(Py_None);
	return Py_None;

error:
	CFRelease(note);

	Py_XDECREF(pKeys);

	return NULL;
}

static PyObject * growl_PostRegistration(PyObject *self, PyObject *args) {
	return growl_PostDictionary(CFSTR("GrowlApplicationRegistrationNotification"), self, args);
}

static PyObject * growl_PostNotification(PyObject *self, PyObject *args) {
	return growl_PostDictionary(CFSTR("GrowlNotification"), self, args);
}

static PyMethodDef GrowlMethods[] = {
	{"PostNotification", growl_PostNotification, METH_VARARGS, "Send a notification to GrowlHelperApp"},
	{"PostRegistration", growl_PostRegistration, METH_VARARGS, "Send a registration to GrowlHelperApp"},
	{NULL, NULL, 0, NULL}		/* Sentinel */
};


PyMODINIT_FUNC init_growl(void) {
	Py_InitModule("_growl", GrowlMethods);
}
