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

// infolist-nodelist.c -- implementation for InfoListNodeList

#include "infolist-nodelist.h"
#include "Python.h"
#include "stdlib.h"

#define CHECK_NOT_IN_LIST(node, error_rv) if(node->next || node->prev) { \
        PyErr_SetString(PyExc_ValueError, "node in list"); \
        return error_rv; }

#define CHECK_IN_LIST(node, error_rv) if(!node->next || !node->prev) { \
        PyErr_SetString(PyExc_ValueError, "node not in list"); \
        return error_rv; }

InfoListNode*
infolist_node_new(PyObject* id,
                  PyObject* info,
                  PyObject* sort_key)
{
        InfoListNode* node;

        node = PyMem_New(InfoListNode, 1);
        if(!node) {
                return (InfoListNode*)PyErr_NoMemory();
        }
        Py_INCREF(id);
        Py_INCREF(info);
        Py_INCREF(sort_key);
        node->id = id;
        node->info = info;
        node->sort_key = sort_key;
        node->prev = node->next = NULL;
        node->group_hash = -1;
        return node;
}

int
infolist_node_free(InfoListNode* node)
{
        CHECK_NOT_IN_LIST(node, -1);
        Py_DECREF(node->id);
        Py_DECREF(node->info);
        Py_DECREF(node->sort_key);
        PyMem_Free(node);
        return 0;
}

static void
infolist_node_make_sentinals(InfoListNode* start, InfoListNode* end)
{
        start->id = end->id = NULL;
        start->info = end->info = NULL;
        start->sort_key = end->sort_key = NULL;
        start->next = end->next = end;
        end->prev = start->prev = start;
}

int
infolist_node_is_sentinal(InfoListNode* node)
{
        return node->info == NULL;
}

PyObject*
infolist_node_get_id(InfoListNode* node)
{
        Py_INCREF(node->id);
        return node->id;
}

PyObject*
infolist_node_get_info(InfoListNode* node)
{
        Py_INCREF(node->info);
        return node->info;
}

PyObject*
infolist_node_get_sort_key(InfoListNode* node)
{
        Py_INCREF(node->sort_key);
        return node->sort_key;
}

void
infolist_node_set_info(InfoListNode* node, PyObject* info)
{

        Py_DECREF(node->info);
        Py_INCREF(info);
        node->info = info;
}

void
infolist_node_set_sort_key(InfoListNode* node, PyObject* sort_key)
{
        Py_DECREF(node->sort_key);
        Py_INCREF(sort_key);
        node->sort_key = sort_key;
}

static int cmp_failed;

int
infolist_node_cmp(const InfoListNode* node1,
                  const InfoListNode* node2)
{
        int cmp_result;

        if(PyObject_Cmp(node1->sort_key, node2->sort_key, &cmp_result) == -1) {
                cmp_failed = 1;
                cmp_result = 0;
        }
        if(cmp_result == 0) {
                // for a tiebreak, just compare the node pointers.  This
                // ensures that the order is completely defined and avoids
                // issues like #16113
                return (node1 < node2) ? -1 : 1;
        }
        return cmp_result;
}

static int
qsort_compare(const void* arg1,
              const void* arg2)
{
        return infolist_node_cmp(*((InfoListNode**)arg1),
                                 *((InfoListNode**)arg2));
}

static int
qsort_compare_reverse(const void* arg1,
                      const void* arg2)
{
        return infolist_node_cmp(*((InfoListNode**)arg2),
                                 *((InfoListNode**)arg1));
}

int
infolist_node_sort(InfoListNode** node_array, int count)
{
        cmp_failed = 0;
        qsort(node_array, count, sizeof(InfoListNode*), qsort_compare);
        if(cmp_failed) {
                // The exception should have been set when the comparison failed.
                // return -1 should propagate it.
                return -1;
        }
        return 0;
}

int
infolist_node_sort_reversed(InfoListNode** node_array, int count)
{
        cmp_failed = 0;
        qsort(node_array, count, sizeof(InfoListNode*), qsort_compare_reverse);
        if(cmp_failed) {
                // The exception should have been set when the comparison failed.
                // return -1 should propagate it.
                printf("CMP FAILED\n");
                return -1;
        }
        return 0;
}

InfoListNodeList*
infolist_nodelist_new(void)
{
        InfoListNodeList* nodelist;

        nodelist = PyMem_New(InfoListNodeList, 1);
        if(!nodelist) {
                return (InfoListNodeList*)PyErr_NoMemory();
        }
        nodelist->node_count = 0;
        infolist_node_make_sentinals(&nodelist->sentinal_start,
                                     &nodelist->sentinal_end);
        nodelist->index_lookup = NULL;
        nodelist->index_lookup_capacity = 0;
        nodelist->index_lookup_dirty = 0;
        nodelist->node_positions_dirty = 0;
        nodelist->plat_data = nodelist->plat_data2 = nodelist->plat_data3 = NULL;
        return nodelist;
}


void
infolist_nodelist_free(InfoListNodeList* nodelist)
{
        InfoListNode* node;
        InfoListNode* next;

        node = infolist_nodelist_head(nodelist);
        while(!infolist_node_is_sentinal(node)) {
                next = node->next;
                // we don't need all the bookkeeping in
                // infolist_nodelist_remove(), just do enough so that
                // infolist_node_free doesn't complain.
                node->prev = node->next = NULL;
                infolist_node_free(node);
                node = next;
        }
        PyMem_Free(nodelist->index_lookup);
        PyMem_Free(nodelist);
}

int
infolist_nodelist_insert_before(InfoListNodeList* nodelist,
                                InfoListNode* pos,
                                InfoListNode* new_node)
{
        InfoListNode* old_prev;

        CHECK_IN_LIST(pos, -1);
        CHECK_NOT_IN_LIST(new_node, -1);
        if(pos->prev == pos) {
                PyErr_SetString(PyExc_ValueError,
                                "can't insert before start sentinal");
                return -1;
        }

        old_prev = pos->prev;
        new_node->prev = old_prev;
        new_node->next = pos;
        pos->prev = new_node;
        old_prev->next = new_node;

        nodelist->node_count++;
        nodelist->index_lookup_dirty = 1;
        nodelist->node_positions_dirty = 1;
        return 0;
}

int
infolist_nodelist_insert_after(InfoListNodeList* nodelist,
                               InfoListNode* pos,
                               InfoListNode* new_node)
{
        InfoListNode* old_next;

        CHECK_IN_LIST(pos, -1);
        CHECK_NOT_IN_LIST(new_node, -1);
        if(pos->next == pos) {
                PyErr_SetString(PyExc_ValueError,
                                "can't insert after end sentinal");
                return -1;
        }
        old_next = pos->next;
        new_node->prev = pos;
        new_node->next = old_next;
        pos->next = new_node;
        old_next->prev = new_node;

        nodelist->node_count++;
        nodelist->index_lookup_dirty = 1;
        nodelist->node_positions_dirty = 1;
        return 0;
}

int
infolist_nodelist_remove(InfoListNodeList* nodelist,
                         InfoListNode* node)
{
        CHECK_IN_LIST(node, -1);
        if(infolist_node_is_sentinal(node)) {
                PyErr_SetString(PyExc_ValueError, "can't remove sentinal");
                return -1;
        }
        node->prev->next = node->next;
        node->next->prev = node->prev;
        node->prev = node->next = NULL;

        nodelist->node_count--;
        nodelist->index_lookup_dirty = 1;
        nodelist->node_positions_dirty = 1;
        return 0;
}

static int
infolist_nodelist_ensure_index_lookup_capacity(InfoListNodeList* nodelist)
{
        InfoListNode** new_index_lookup;
        int new_capacity;
        if(nodelist->index_lookup_capacity >= nodelist->node_count) return 0;

        new_capacity = nodelist->node_count * 2;
        new_index_lookup = PyMem_Resize(nodelist->index_lookup,
                                        InfoListNode*,
                                        new_capacity);
        if(!new_index_lookup) {
                PyErr_SetNone(PyExc_MemoryError);
                return -1;
        }
        nodelist->index_lookup = new_index_lookup;
        nodelist->index_lookup_capacity = new_capacity;
        return 0;
}

static int
infolist_nodelist_ensure_index_lookup(InfoListNodeList* nodelist)
{
        int i;
        InfoListNode* node;

        if(!nodelist->index_lookup_dirty) return 0;
        if(infolist_nodelist_ensure_index_lookup_capacity(nodelist) == -1)
                return -1;
        node = infolist_nodelist_head(nodelist);
        for(i = 0; i < nodelist->node_count; i++) {
                nodelist->index_lookup[i] = node;
                node = node->next;
        }
        return 0;
}

InfoListNode*
infolist_nodelist_head(InfoListNodeList* nodelist)
{
        return nodelist->sentinal_start.next;
}

InfoListNode*
infolist_nodelist_tail(InfoListNodeList* nodelist)
{
        return nodelist->sentinal_end.prev;
}

InfoListNode*
infolist_nodelist_nth_node(InfoListNodeList* nodelist,
                           int n)
{
        if(n < 0 || n >= nodelist->node_count) {
                PyErr_SetString(PyExc_ValueError, "index out of range");
                return NULL;
        }
        // special-case this one
        if(n == 0) return infolist_nodelist_head(nodelist);
        if(infolist_nodelist_ensure_index_lookup(nodelist) == -1) return NULL;
        return nodelist->index_lookup[n];
}

int
infolist_nodelist_node_index(InfoListNodeList* nodelist,
                             InfoListNode* node)
{
        CHECK_IN_LIST(node, -1);

        infolist_nodelist_calc_positions(nodelist);
        return node->position;
}

int
infolist_nodelist_calc_positions(InfoListNodeList* nodelist)
{
        InfoListNode* node;
        int i;

        if(!nodelist->node_positions_dirty) return 0;
        node = infolist_nodelist_head(nodelist);
        for(i = 0; i < nodelist->node_count; i++) {
                node->position = i;
                node = node->next;
        }
        nodelist->node_positions_dirty = 0;
        return 0;
}

int
infolist_nodelist_check_nodes(InfoListNodeList* nodelist)
{
        int i, count;
        InfoListNode* node;

        count = 0;

        node = &nodelist->sentinal_start;
        if(node->prev != node) {
                PyErr_SetString(PyExc_AssertionError,
                                "start sentinal prev wrong");
                return -1;
        }
        while(node != &nodelist->sentinal_end) {
                if(node->next->prev != node) {
                        PyErr_SetString(PyExc_AssertionError,
                                        "node->next->prev != node");
                        return -1;
                }
                node = node->next;
                count++;
        }
        if(node->next != node) {
                PyErr_SetString(PyExc_AssertionError,
                                "end sentinal next wrong");
                return -1;
        }

        // count includes the start sentinal, so subtract 1
        if(count -1 != nodelist->node_count) {
                PyErr_SetString(PyExc_AssertionError, "node_count wrong");
                return -1;
        }

        infolist_nodelist_ensure_index_lookup(nodelist);
        node = infolist_nodelist_head(nodelist);
        for(i = 0; i < nodelist->node_count; i++) {
                if(nodelist->index_lookup[i] != node) {
                        PyErr_SetString(PyExc_AssertionError,
                                        "index_lookup wrong");
                        return -1;
                }
                node = node->next;
        }
        return 0;
}
