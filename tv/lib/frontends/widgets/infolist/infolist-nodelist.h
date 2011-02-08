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

// infolist-nodelist.h -- Basic data structures for InfoList
//
// InfoListNode stores the data for 1 row our table.  This includes ItemInfo
// objects, as well as a sort key, and a dict to store attributes.
//
// InfoListNodeList is basically a simple linked list of InfoListNodes.
// However, InfoListNodeList has some features to be able to lookup rows by
// their index, and calculate the index of each row.  These operations are
// O(N), but then O(1) until a node is inserted/removed.  Since we don't do
// that all that often, this works well in practice.
//
// Error handling:
//
// The general convention is to return NULL or -1 and set a python error
// on failure for any of these methods.

#ifndef __INFOLIST_DATA_H__
#define __INFOLIST_DATA_H__

#ifdef __cplusplus
extern "C" {
#endif

#include <Python.h>

struct InfoListNodeStruct
{
        PyObject* id;
        PyObject* info;
        PyObject* sort_key;
        struct InfoListNodeStruct *next;
        struct InfoListNodeStruct *prev;
        // Call infolist_nodelist_calc_positions before using position
        unsigned int position;
};
typedef struct InfoListNodeStruct InfoListNode;

// Create a new InfoListNode, we ADDREF all the python objects
InfoListNode*
infolist_node_new(PyObject* id,
                  PyObject* info,
                  PyObject* sort_key);

// Free a InfoListNode and DECREF the python objects
int
infolist_node_free(InfoListNode* node);

// Check for a sentinal node.  sentinals are before/after the last node with
// valid data.
int
infolist_node_is_sentinal(InfoListNode* node);

// get/set python objects for a node.  Reference counting is as usual for
// python (nodes hold a reference to the objects inside them, return values
// get ADDREFed)
PyObject*
infolist_node_get_id(InfoListNode* node);

PyObject*
infolist_node_get_info(InfoListNode* node);

PyObject*
infolist_node_get_sort_key(InfoListNode* node);

void
infolist_node_set_info(InfoListNode* node,
                       PyObject* info);

void
infolist_node_set_sort_key(InfoListNode* node,
                           PyObject* sort_key);

// Sort an array of nodes by their sort key
int
infolist_node_cmp(const InfoListNode* node1,
                  const InfoListNode* node2);
int
infolist_node_sort(InfoListNode** node_array,
                   int count);
int
infolist_node_sort_reversed(InfoListNode** node_array,
                            int count);

struct InfoListNodeListStruct
{
        // Basic list functionality
        int node_count;
        InfoListNode sentinal_start, sentinal_end;
        // Handle index lookup
        InfoListNode** index_lookup;
        int index_lookup_capacity;
        int index_lookup_dirty;
        // Handle node positions
        int node_positions_dirty;
        // Place to store Platform-specific stuff
        void* plat_data;
        void* plat_data2;
        void* plat_data3;
};
typedef struct InfoListNodeListStruct InfoListNodeList;

// Make a new list
InfoListNodeList*
infolist_nodelist_new(void);

// Delete a list and free all of it's resources
void
infolist_nodelist_free(InfoListNodeList* nodelist);

// Insert a new node before pos
int
infolist_nodelist_insert_before(InfoListNodeList* nodelist,
                                InfoListNode* pos,
                                InfoListNode* new_node);

// Insert a new node after pos
int
infolist_nodelist_insert_after(InfoListNodeList* nodelist,
                               InfoListNode* pos,
                               InfoListNode* new_node);

// Remove a node from the list.  WARNING: Does not free it!
int
infolist_nodelist_remove(InfoListNodeList* nodelist,
                         InfoListNode* node);

// Get the first node in the list, return a sentinal if the list is empty
InfoListNode*
infolist_nodelist_head(InfoListNodeList* nodelist);

// Get the last node in the list, return a sentinal if the list is empty
InfoListNode*
infolist_nodelist_tail(InfoListNodeList* nodelist);

// Get the nth node in the list
InfoListNode*
infolist_nodelist_nth_node(InfoListNodeList* nodelist,
                           int n);

// Find the index of a node
int
infolist_nodelist_node_index(InfoListNodeList* nodelist,
                             InfoListNode* node);

// Calculate node positions
// Set the position attribute for each node with it's current index
int
infolist_nodelist_calc_positions(InfoListNodeList* nodelist);

// Debugging function, check that the linked list makes sense
int
infolist_nodelist_check_nodes(InfoListNodeList* nodelist);

#ifdef __cplusplus
} // extern "C"
#endif

#endif // __INFOLIST_DATA_H__
