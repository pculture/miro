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

#include <Python.h>

/*
 * fasttypes.c
 *
 * Datastructures written in C to be fast.  This used to be a big C++ file
 * that depended on boost.  Nowadays we only define LinkedList, which is easy
 * enough to implement in pure C.
 */

static int nodes_deleted = 0; // debugging only

/* forward define python type objects */

static PyTypeObject LinkedListType;
static PyTypeObject LinkedListIterType;

/* Structure definitions */

typedef struct LinkedListNode {
    PyObject *obj;
    struct LinkedListNode* next;
    struct LinkedListNode* prev;
    int deleted; // Has this node been removed?
    int iter_count; // How many LinkedListIters point to this node?
} LinkedListNode;

typedef struct {
    PyObject_HEAD
    int count;
    LinkedListNode* sentinal;
    // sentinal object to make list operations simpler/faster and equivalent
    // to the boost API.  It's prev node is the last element in the list and
    // it's next node is the first
} LinkedListObject;

typedef struct {
    PyObject_HEAD
    LinkedListNode* node;
    LinkedListObject* list;
} LinkedListIterObject;

/* LinkedListNode */

void check_node_deleted(LinkedListNode* node)
{
    if(node->iter_count <= 0 && node->deleted) {
        free(node);
        nodes_deleted += 1;
    }
}

static int remove_node(LinkedListObject* self, LinkedListNode* node)
{
    if(node->obj == NULL) {
        PyErr_SetString(PyExc_IndexError, "can't remove lastIter()");
        return 0;
    }
    node->next->prev = node->prev;
    node->prev->next = node->next;
    node->deleted = 1;
    self->count -= 1;
    Py_DECREF(node->obj);
    check_node_deleted(node);
    return 1;
}

/* LinkedListIter */

void switch_node(LinkedListIterObject* self, LinkedListNode* new_node)
{
    LinkedListNode* old_node;

    old_node = self->node;
    self->node = new_node;
    old_node->iter_count--;
    self->node->iter_count++;
    check_node_deleted(old_node);
}

// Note that we don't expose the new method to python.  We create
// LinkedListIters in the factory methods firstIter() and lastIter()
static LinkedListIterObject* LinkedListIterObject_new(LinkedListObject*list,
        LinkedListNode* node)
{
    LinkedListIterObject* self;

    self = (LinkedListIterObject*)PyType_GenericAlloc(&LinkedListIterType, 0);
    if(self != NULL) {
        self->node = node;
        self->list = list;
        node->iter_count++;
    }
    return self;
}

static void LinkedListIterObject_dealloc(LinkedListIterObject* self)
{
    self->node->iter_count--;
    check_node_deleted(self->node);
}

static PyObject *LinkedListIter_forward(LinkedListIterObject* self, PyObject *obj)
{
    switch_node(self, self->node->next);
    Py_RETURN_NONE;
}

static PyObject *LinkedListIter_back(LinkedListIterObject* self, PyObject *obj)
{
    switch_node(self, self->node->prev);
    Py_RETURN_NONE;
}

static PyObject *LinkedListIter_value(LinkedListIterObject* self, PyObject *obj)
{
    PyObject* retval;

    if(self->node->deleted) {
        PyErr_SetString(PyExc_ValueError, "Node deleted");
        return NULL;
    }
    retval = self->node->obj;
    if(retval == NULL) {
        PyErr_SetString(PyExc_IndexError, "can't get value of lastIter()");
        return NULL;
    }
    Py_INCREF(retval);
    return retval;
}

static PyObject *LinkedListIter_copy(LinkedListIterObject* self, PyObject *obj)
{
    return (PyObject*)LinkedListIterObject_new(self->list, self->node);
}

PyObject* LinkedListIter_richcmp(LinkedListIterObject *o1,
        LinkedListIterObject *o2, int opid)
{
    if(!PyObject_TypeCheck(o1, &LinkedListIterType) ||
        !PyObject_TypeCheck(o2, &LinkedListIterType)) {
        return Py_NotImplemented;
    }
    switch(opid) {
        case Py_EQ:
            if(o1->node == o2->node) Py_RETURN_TRUE;
            else Py_RETURN_FALSE;
        case Py_NE:
            if(o1->node != o2->node) Py_RETURN_TRUE;
            else Py_RETURN_FALSE;
        default:
            return Py_NotImplemented;
    }
}

static PyMethodDef LinkedListIter_methods[] = {
    {"forward", (PyCFunction)LinkedListIter_forward, METH_NOARGS,
             "Move to the next element",
    },
    {"back", (PyCFunction)LinkedListIter_back, METH_NOARGS,
             "Move to the previous element",
    },
    {"value", (PyCFunction)LinkedListIter_value, METH_NOARGS,
             "Return the current element",
    },
    {"copy", (PyCFunction)LinkedListIter_copy, METH_NOARGS,
             "Duplicate iter",
    },
    {NULL},
};

static PyTypeObject LinkedListIterType = {
    PyObject_HEAD_INIT(NULL)
    0,                                 /* ob_size */
    "fasttypes.LinkedListIter",            /* tp_name */
    sizeof(LinkedListIterObject),          /* tp_basicsize */
    0,                                 /* tp_itemsize */
    (destructor)LinkedListIterObject_dealloc,      /* tp_dealloc */
    0,                                 /* tp_print */
    0,                                 /* tp_getattr */
    0,                                 /* tp_setattr */
    0,                                 /* tp_compare */
    0,                                 /* tp_repr */
    0,                                 /* tp_as_number */
    0,                                 /* tp_as_sequence */
    0,                                 /* tp_as_mapping */
    0,                                 /* tp_hash  */
    0,                                 /* tp_call */
    0,                                 /* tp_str */
    0,                                 /* tp_getattro */
    0,                                 /* tp_setattro */
    0,                                 /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT|Py_TPFLAGS_HAVE_RICHCOMPARE, /* tp_flags */
    "fasttypes LinkedListIter",        /* tp_doc */
    0,                                 /* tp_traverse */
    0,                                 /* tp_clear */
    (richcmpfunc)LinkedListIter_richcmp,            /* tp_richcompare */
    0,                                 /* tp_weaklistoffset */
    0,                                 /* tp_iter */
    0,                                 /* tp_iternext */
    LinkedListIter_methods,           /* tp_methods */
    0,                                 /* tp_members */
    0,                                 /* tp_getset */
    0,                                 /* tp_base */
    0,                                 /* tp_dict */
    0,                                 /* tp_descr_get */
    0,                                 /* tp_descr_set */
    0,                                 /* tp_dictoffset */
    0,                                 /* tp_init */
    0,                                 /* tp_alloc */
    0,                                 /* tp_new */
};

/* LinkedList */

LinkedListNode* make_new_node(PyObject* obj, LinkedListNode* prev,
        LinkedListNode* next)
{
    LinkedListNode* retval;
    retval = malloc(sizeof(LinkedListNode));
    if(!retval) {
        PyErr_SetString(PyExc_MemoryError, "can't create new node");
        return NULL;
    }
    Py_XINCREF(obj);
    retval->obj = obj;
    retval->prev = prev;
    retval->next = next;
    retval->iter_count = retval->deleted = 0;
    return retval;
}

void set_iter_type_error(PyObject* obj)
{
    // Set an exception when we expected a LinkedListIter and got something
    // else
    PyObject* args;
    PyObject* fmt;
    PyObject* err_str;

    args = Py_BuildValue("(O)", obj);
    fmt = PyString_FromString("Expected LinkedListIter, got %r");
    err_str = PyString_Format(fmt, args);
    PyErr_SetObject(PyExc_TypeError, err_str);
    Py_DECREF(fmt);
    Py_DECREF(err_str);
    Py_DECREF(args);
}

static PyObject* insert_before(LinkedListObject* self, LinkedListNode* node,
        PyObject* obj)
{
    LinkedListNode* new_node;
    PyObject* retval;

    new_node = make_new_node(obj, node->prev, node);
    if(!new_node) return NULL;
    node->prev->next = new_node;
    node->prev = new_node;
    self->count += 1;
    retval = (PyObject*)LinkedListIterObject_new(self, new_node);
    return retval;
}

static PyObject* LinkedList_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    LinkedListObject *self;
    LinkedListNode *sentinal;

    self = (LinkedListObject *)type->tp_alloc(type, 0);
    if (self == NULL) return NULL;

    sentinal = make_new_node(NULL, NULL, NULL);
    if(!sentinal) {
        Py_DECREF(self);
        return NULL;
    }
    self->sentinal = sentinal->next = sentinal->prev = sentinal;
    sentinal->iter_count = 1; // prevent the sentinal from being deleted
    self->count = 0;

    return (PyObject *)self;
}

static void LinkedList_dealloc(LinkedListObject* self)
{
    LinkedListNode* node;

    node = self->sentinal->next;
    while(node != self->sentinal) {
        node->deleted = 1;
        check_node_deleted(node);
        node = node->next;
    }

    self->sentinal->iter_count -= 1;
    check_node_deleted(self->sentinal);
    return;
}

static int LinkedList_init(LinkedListObject *self)
{
    self->count = 0;
    return 0;
}

static Py_ssize_t LinkedList_len(LinkedListObject *self)
{
    return self->count;
}

static PyObject* LinkedList_get(LinkedListObject *self,
        LinkedListIterObject *iter)
{
    if(!PyObject_TypeCheck(iter, &LinkedListIterType)) {
        set_iter_type_error((PyObject*)iter);
        return NULL;
    }
    return PyObject_CallMethod((PyObject*)iter, "value", "()");
}
int LinkedList_set(LinkedListObject *self, LinkedListIterObject *iter,
        PyObject *value)
{
    if(!PyObject_TypeCheck(iter, &LinkedListIterType)) {
        set_iter_type_error((PyObject*)iter);
        return -1;
    }
    if(iter->node->deleted) {
        PyErr_SetString(PyExc_ValueError, "Node deleted");
        return -1;
    }
    if(iter->node->obj == NULL) {
        PyErr_SetString(PyExc_IndexError, "can't set value of lastIter()");
        return -1;
    }
    if(value == NULL) {
        if(!remove_node(self, iter->node)) return -1;
        return 0;
    }
    Py_INCREF(value);
    Py_DECREF(iter->node->obj);
    iter->node->obj = value;
    return 0;
}

static PyObject *LinkedList_insertBefore(LinkedListObject* self, PyObject *args)
{
    LinkedListIterObject *iter;
    PyObject *obj;

    if(!PyArg_ParseTuple(args, "OO", &iter, &obj)) return NULL;
    if(!PyObject_TypeCheck(iter, &LinkedListIterType)) {
        set_iter_type_error(obj);
        return NULL;
    }

    return insert_before(self, iter->node, obj);
}

static PyObject *LinkedList_append(LinkedListObject* self, PyObject *obj)
{
    return insert_before(self, self->sentinal, obj);
}

static PyObject *LinkedList_remove(LinkedListObject* self,
        LinkedListIterObject *iter)
{
    LinkedListNode* next_node;
    if(!PyObject_TypeCheck(iter, &LinkedListIterType)) {
        set_iter_type_error((PyObject*)iter);
        return NULL;
    }

    next_node = iter->node->next;
    if(!remove_node(self, iter->node)) return NULL;
    return (PyObject*)LinkedListIterObject_new(self, next_node);
}

static PyObject *LinkedList_firstIter(LinkedListObject* self, PyObject *obj)
{
    PyObject* retval;
    retval = (PyObject*)LinkedListIterObject_new(self, self->sentinal->next);
    return retval;
}

static PyObject *LinkedList_lastIter(LinkedListObject* self, PyObject *obj)
{
    PyObject* retval;
    retval = (PyObject*)LinkedListIterObject_new(self, self->sentinal);
    return retval;
}

static PyMappingMethods LinkedListMappingMethods = {
    (lenfunc)LinkedList_len,
    (binaryfunc)LinkedList_get,
    (objobjargproc)LinkedList_set,
};

static PyMethodDef LinkedList_methods[] = {
    {"insertBefore", (PyCFunction)LinkedList_insertBefore, METH_VARARGS,
        "insert an element before iter",
    },
    {"append", (PyCFunction)LinkedList_append, METH_O,
        "append an element to the list",
    },
    {"remove", (PyCFunction)LinkedList_remove, METH_O,
        "remove an element to the list",
    },
    {"firstIter", (PyCFunction)LinkedList_firstIter, METH_NOARGS,
        "get an iter pointing to the first element in the list",
    },
    {"lastIter", (PyCFunction)LinkedList_lastIter, METH_NOARGS,
        "get an iter pointing to the last element in the list",
    },
    {NULL},
};

static PyTypeObject LinkedListType = {
        PyObject_HEAD_INIT(NULL)
            0,                                 /* ob_size */
        "fasttypes.LinkedList",            /* tp_name */
        sizeof(LinkedListObject),          /* tp_basicsize */
        0,                                 /* tp_itemsize */
        (destructor)LinkedList_dealloc,    /* tp_dealloc */
        0,                                 /* tp_print */
        0,                                 /* tp_getattr */
        0,                                 /* tp_setattr */
        0,                                 /* tp_compare */
        0,                                 /* tp_repr */
        0,                                 /* tp_as_number */
        0,                                 /* tp_as_sequence */
        &LinkedListMappingMethods,          /* tp_as_mapping */
        0,                                 /* tp_hash  */
        0,                                 /* tp_call */
        0,                                 /* tp_str */
        0,                                 /* tp_getattro */
        0,                                 /* tp_setattro */
        0,                                 /* tp_as_buffer */
        Py_TPFLAGS_DEFAULT,                /* tp_flags */
        "fasttypes LinkedList",            /* tp_doc */
        0,                                 /* tp_traverse */
        0,                                 /* tp_clear */
        0,                                 /* tp_richcompare */
        0,                                 /* tp_weaklistoffset */
        0,                                 /* tp_iter */
        0,                                 /* tp_iternext */
        LinkedList_methods,               /* tp_methods */
        0,                                 /* tp_members */
        0,                                 /* tp_getset */
        0,                                 /* tp_base */
        0,                                 /* tp_dict */
        0,                                 /* tp_descr_get */
        0,                                 /* tp_descr_set */
        0,                                 /* tp_dictoffset */
        (initproc)LinkedList_init,         /* tp_init */
        0,                                 /* tp_alloc */
        LinkedList_new,           /* tp_new */
};

/* Module-level stuff */

static PyObject *count_nodes_deleted(PyObject *obj)
{
    return PyInt_FromLong(nodes_deleted);
}

static PyObject *reset_nodes_deleted(PyObject *obj)
{
    nodes_deleted = 0;
    Py_RETURN_NONE;
}


static PyMethodDef FasttypesMethods[] =
{
    {"_count_nodes_deleted", (PyCFunction)count_nodes_deleted, METH_NOARGS,
        "get a count of how many nodes have been deleted (DEBUGGING ONLY)",
    },
    {"_reset_nodes_deleted", (PyCFunction)reset_nodes_deleted, METH_NOARGS,
        "reset the count of how many nodes have been deleted (DEBUGGING ONLY)",
    },
    { NULL, NULL, 0, NULL }
};

PyMODINIT_FUNC initfasttypes(void)
{
    PyObject *m;

    if (PyType_Ready(&LinkedListType) < 0)
        return;

    if (PyType_Ready(&LinkedListIterType) < 0)
        return;

    m = Py_InitModule("fasttypes", FasttypesMethods);

    Py_INCREF(&LinkedListType);
    Py_INCREF(&LinkedListIterType);
    PyModule_AddObject(m, "LinkedList", (PyObject *)&LinkedListType);
}
