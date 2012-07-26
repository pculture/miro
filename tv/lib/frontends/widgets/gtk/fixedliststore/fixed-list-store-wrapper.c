/* -- THIS FILE IS GENERATED - DO NOT EDIT *//* -*- Mode: C; c-basic-offset: 4 -*- */

#include <Python.h>



#line 3 "fixed-list-store.override"
#include <Python.h>
#include "pygobject.h"
#include "fixed-list-store.h"
#line 12 "fixed-list-store.c"


/* ---------- types from other modules ---------- */
static PyTypeObject *_PyGObject_Type;
#define PyGObject_Type (*_PyGObject_Type)
static PyTypeObject *_PyGtkTreeModel_Type;
#define PyGtkTreeModel_Type (*_PyGtkTreeModel_Type)


/* ---------- forward type declarations ---------- */
PyTypeObject G_GNUC_INTERNAL PyMiroFixedListStore_Type;

#line 25 "fixed-list-store.c"



/* ----------- MiroFixedListStore ----------- */

static int
_wrap_miro_fixed_list_store_new(PyGObject *self, PyObject *args, PyObject *kwargs)
{
    GType obj_type = pyg_type_from_object((PyObject *) self);
    GParameter params[1];
    PyObject *parsed_args[1] = {NULL, };
    char *arg_names[] = {"row_count", NULL };
    char *prop_names[] = {"row_count", NULL };
    guint nparams, i;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O:miro.fixedliststore.FixedListStore.__init__" , arg_names , &parsed_args[0]))
        return -1;

    memset(params, 0, sizeof(GParameter)*1);
    if (!pyg_parse_constructor_args(obj_type, arg_names,
                                    prop_names, params, 
                                    &nparams, parsed_args))
        return -1;
    pygobject_constructv(self, nparams, params);
    for (i = 0; i < nparams; ++i)
        g_value_unset(&params[i].value);
    if (!self->obj) {
        PyErr_SetString(
            PyExc_RuntimeError, 
            "could not create miro.fixedliststore.FixedListStore object");
        return -1;
    }
    return 0;
}

static PyObject *
_wrap_miro_fixed_list_store_row_of_iter(PyGObject *self, PyObject *args, PyObject *kwargs)
{
    static char *kwlist[] = { "iter", NULL };
    PyObject *py_iter;
    GtkTreeIter *iter = NULL;
    int ret;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs,"O:Miro.FixedListStore.row_of_iter", kwlist, &py_iter))
        return NULL;
    if (pyg_boxed_check(py_iter, GTK_TYPE_TREE_ITER))
        iter = pyg_boxed_get(py_iter, GtkTreeIter);
    else {
        PyErr_SetString(PyExc_TypeError, "iter should be a GtkTreeIter");
        return NULL;
    }
    
    ret = miro_fixed_list_store_row_of_iter(MIRO_FIXED_LIST_STORE(self->obj), iter);
    
    return PyInt_FromLong(ret);
}

static const PyMethodDef _PyMiroFixedListStore_methods[] = {
    { "row_of_iter", (PyCFunction)_wrap_miro_fixed_list_store_row_of_iter, METH_VARARGS|METH_KEYWORDS,
      NULL },
    { NULL, NULL, 0, NULL }
};

PyTypeObject G_GNUC_INTERNAL PyMiroFixedListStore_Type = {
    PyObject_HEAD_INIT(NULL)
    0,                                 /* ob_size */
    "miro.fixedliststore.FixedListStore",                   /* tp_name */
    sizeof(PyGObject),          /* tp_basicsize */
    0,                                 /* tp_itemsize */
    /* methods */
    (destructor)0,        /* tp_dealloc */
    (printfunc)0,                      /* tp_print */
    (getattrfunc)0,       /* tp_getattr */
    (setattrfunc)0,       /* tp_setattr */
    (cmpfunc)0,           /* tp_compare */
    (reprfunc)0,             /* tp_repr */
    (PyNumberMethods*)0,     /* tp_as_number */
    (PySequenceMethods*)0, /* tp_as_sequence */
    (PyMappingMethods*)0,   /* tp_as_mapping */
    (hashfunc)0,             /* tp_hash */
    (ternaryfunc)0,          /* tp_call */
    (reprfunc)0,              /* tp_str */
    (getattrofunc)0,     /* tp_getattro */
    (setattrofunc)0,     /* tp_setattro */
    (PyBufferProcs*)0,  /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,                      /* tp_flags */
    NULL,                        /* Documentation string */
    (traverseproc)0,     /* tp_traverse */
    (inquiry)0,             /* tp_clear */
    (richcmpfunc)0,   /* tp_richcompare */
    offsetof(PyGObject, weakreflist),             /* tp_weaklistoffset */
    (getiterfunc)0,          /* tp_iter */
    (iternextfunc)0,     /* tp_iternext */
    (struct PyMethodDef*)_PyMiroFixedListStore_methods, /* tp_methods */
    (struct PyMemberDef*)0,              /* tp_members */
    (struct PyGetSetDef*)0,  /* tp_getset */
    NULL,                              /* tp_base */
    NULL,                              /* tp_dict */
    (descrgetfunc)0,    /* tp_descr_get */
    (descrsetfunc)0,    /* tp_descr_set */
    offsetof(PyGObject, inst_dict),                 /* tp_dictoffset */
    (initproc)_wrap_miro_fixed_list_store_new,             /* tp_init */
    (allocfunc)0,           /* tp_alloc */
    (newfunc)0,               /* tp_new */
    (freefunc)0,             /* tp_free */
    (inquiry)0              /* tp_is_gc */
};



/* ----------- functions ----------- */

const PyMethodDef miro_fixed_list_store_functions[] = {
    { NULL, NULL, 0, NULL }
};

/* initialise stuff extension classes */
void
miro_fixed_list_store_register_classes(PyObject *d)
{
    PyObject *module;

    if ((module = PyImport_ImportModule("gobject")) != NULL) {
        _PyGObject_Type = (PyTypeObject *)PyObject_GetAttrString(module, "GObject");
        if (_PyGObject_Type == NULL) {
            PyErr_SetString(PyExc_ImportError,
                "cannot import name GObject from gobject");
            return ;
        }
    } else {
        PyErr_SetString(PyExc_ImportError,
            "could not import gobject");
        return ;
    }
    if ((module = PyImport_ImportModule("gtk")) != NULL) {
        _PyGtkTreeModel_Type = (PyTypeObject *)PyObject_GetAttrString(module, "TreeModel");
        if (_PyGtkTreeModel_Type == NULL) {
            PyErr_SetString(PyExc_ImportError,
                "cannot import name TreeModel from gtk");
            return ;
        }
    } else {
        PyErr_SetString(PyExc_ImportError,
            "could not import gtk");
        return ;
    }


#line 174 "fixed-list-store.c"
    pygobject_register_class(d, "MiroFixedListStore", MIRO_TYPE_FIXED_LIST_STORE, &PyMiroFixedListStore_Type, Py_BuildValue("(O)", &PyGObject_Type));
    pyg_set_object_has_new_constructor(MIRO_TYPE_FIXED_LIST_STORE);
}
