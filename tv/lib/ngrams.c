/*
# Miro - an RSS based video player application
# Copyright (C) 2005, 2006, 2007, 2008, 2009, 2010, 2011
# Participatory Culture Foundation
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

/*
 * ngrams.c
 *
 * Calculate N-grams for a string quickly.
 */

#include <Python.h>

static int one_pass(PyObject* ngram_list, PyObject* string, int n)
{
    PyObject *ngram;
    Py_ssize_t len, i;

    if((len = PySequence_Length(string)) == -1) {
        return -1;
    }
    for(i=0; i + n <= len; i++) {
        ngram = PySequence_GetSlice(string, i, i+n);
        if(!ngram) {
            return -1;
        }
        if(PyList_Append(ngram_list, ngram) == -1) {
            return -1;
        }
        Py_DECREF(ngram);
    }
    return 0;
}

static PyObject *breakup_word(PyObject *self, PyObject *args)
{
    PyObject* source_string;
    PyObject* ngram_list;
    long min, max;
    Py_ssize_t n;

    if (!PyArg_ParseTuple(args, "Oll:breakup_list", &source_string, &min,
                &max)) {
        return NULL;
    }

    ngram_list = PyList_New(0);
    if(!ngram_list) return NULL;

    for(n=min; n <= max; n++) {
        if(one_pass(ngram_list, source_string, n) < 0) {
            Py_DECREF(ngram_list);
            return NULL;
        }
    }

    return ngram_list;
}

static PyObject *breakup_list(PyObject *self, PyObject *args)
{
    PyObject* source_list;
    PyObject* iter;
    PyObject* item;
    PyObject* ngram_list;
    long min, max;
    Py_ssize_t n;

    if (!PyArg_ParseTuple(args, "Oll:breakup_list", &source_list, &min,
                &max)) {
        return NULL;
    }

    iter = PyObject_GetIter(source_list);
    if(!iter) return NULL;

    ngram_list = PyList_New(0);
    if(!ngram_list) return NULL;


    while ((item = PyIter_Next(iter))) {
        for(n=min; n <= max; n++) {
            if(one_pass(ngram_list, item, n) < 0) {
                Py_DECREF(item);
                Py_DECREF(iter);
                Py_DECREF(ngram_list);
                return NULL;
            }
        }
        Py_DECREF(item);
    }


    Py_DECREF(iter);

    return ngram_list;
}

static PyMethodDef NgramsMethods[] =
{
    {"breakup_word", (PyCFunction)breakup_word, METH_VARARGS,
        "split a words into a list of ngrams"
    },
    {"breakup_list", (PyCFunction)breakup_list, METH_VARARGS,
        "split a sequence of words into a list of ngrams"
    },
    { NULL, NULL, 0, NULL }
};

PyMODINIT_FUNC initngrams(void)
{
    PyObject *m;

    m = Py_InitModule("ngrams", NgramsMethods);
}
