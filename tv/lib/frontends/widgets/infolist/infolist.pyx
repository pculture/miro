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

# infolistmodule.pyx -- Pyrex module definition

ctypedef unsigned char boolean

cdef extern from "stdlib.h":
    ctypedef unsigned long size_t
    void qsort(void *base, size_t nmemb, size_t size,
            int(*compar)(void *, void *))

cdef extern from "Python.h":
    ctypedef struct PyObject

    PyObject* PyExc_KeyError

    void* PyMem_Malloc(size_t n) except NULL
    void PyMem_Free(void *p)
    object PyCObject_FromVoidPtr(void* cobj, void (*destr)(void *))
    void* PyCObject_AsVoidPtr(object self)

cdef extern from "infolist-nodelist.h":
    ctypedef struct InfoListNode
    ctypedef struct InfoListNode:
            InfoListNode *next
            InfoListNode *prev
            # group_hash stores the hash of return value of the current
            # grouping function.
            # We use the hash the value for quick comparisons.  With at least
            # 32 bits of hash data and since we only compare adjacent items,
            # collisions shouldn't be an issue.
            # group_hash is computed lazily, it's -1 if the value hasn't been
            # computed
            long group_hash
            # would be nice to list the python objects here, but Pyrex doesn't
            # support it well.  Use the infolist_node_get_* methods for
            # access.

    InfoListNode* infolist_node_new(object id, object info, 
            object sort_key) except NULL
    int infolist_node_free(InfoListNode* node) except -1
    int infolist_node_is_sentinal(InfoListNode* node) except -1
    object infolist_node_get_id(InfoListNode* node)
    object infolist_node_get_info(InfoListNode* node)
    object infolist_node_get_sort_key(InfoListNode* node)
    void infolist_node_set_info(InfoListNode* node, object info)
    void infolist_node_set_sort_key(InfoListNode* node, object sort_key)
    int infolist_node_cmp(InfoListNode* node1, InfoListNode* node2)
    int infolist_node_sort(InfoListNode** node_array, int count) except -1
    int infolist_node_sort_reversed(InfoListNode** node_array,
            int count) except -1

    ctypedef struct InfoListNodeList:
        int node_count

    InfoListNodeList* infolist_nodelist_new() except NULL
    void infolist_nodelist_free(InfoListNodeList* nodelist)
    InfoListNode* infolist_nodelist_head(
            InfoListNodeList* nodelist) except NULL
    InfoListNode* infolist_nodelist_tail(
            InfoListNodeList* nodelist) except NULL
    int infolist_nodelist_insert_before(InfoListNodeList* nodelist,
            InfoListNode* node, InfoListNode* new_node) except -1
    int infolist_nodelist_insert_after(InfoListNodeList* nodelist,
            InfoListNode* node, InfoListNode* new_node) except -1
    int infolist_nodelist_remove(InfoListNodeList* nodelist,
            InfoListNode* node) except -1
    int infolist_nodelist_node_index(InfoListNodeList* nodelist,
            InfoListNode* node) except -1
    InfoListNode* infolist_nodelist_nth_node(InfoListNodeList* nodelist,
            int n) except NULL
    int infolist_nodelist_check_nodes(InfoListNodeList* nodelist) except -1

cdef extern from "infolist-platform.h":
    int infolistplat_init() except -1
    int infolistplat_nodelist_created(InfoListNodeList* nodelist) except -1
    int infolistplat_nodelist_will_destroy(
            InfoListNodeList* nodelist) except -1
    void infolistplat_will_add_nodes(InfoListNodeList* nodelist)
    int infolistplat_node_added(InfoListNodeList* nodelist,
            InfoListNode* node) except -1
    void infolistplat_will_change_nodes(InfoListNodeList* nodelist)
    int infolistplat_node_changed(InfoListNodeList* nodelist,
            InfoListNode* node) except -1
    void infolistplat_will_remove_nodes(InfoListNodeList* nodelist)
    int infolistplat_node_removed(InfoListNodeList* nodelist,
            InfoListNode* node) except -1
    void infolistplat_will_reorder_nodes(InfoListNodeList* nodelist)
    int infolistplat_nodes_reordered(InfoListNodeList* nodelist) except -1
    int infolistplat_add_to_tableview(InfoListNodeList* nodelist,
            object tableview) except -1
    InfoListNode* infolistplat_node_for_pos(InfoListNodeList* nodelist,
            object pos) except NULL
    object infolistplat_iter_for_node(InfoListNodeList* nodelist,
            InfoListNode* node)

cdef class InfoListAttributeStore:
    """Stores the attributes for an InfoList

    For most rows, the attributes will be empty.  As an optimization, we share
    a single dictionary between all of those.
    """
    cdef dict attr_dict_map # maps id -> attr_dicts
    cdef dict empty_dict # shared empty dict

    def __init__(self, *args, **kwargs):
        self.attr_dict_map = {}
        self.empty_dict = {}

    def get_attr(self, id_, name):
        if id_ not in self.attr_dict_map:
            raise KeyError(name)
        else:
            return self.attr_dict_map[id_][name]

    def set_attr(self, id_, name, value):
        if id_ not in self.attr_dict_map:
            self.attr_dict_map[id_] = {name: value}
        else:
            self.attr_dict_map[id_][name] = value

    def unset_attr(self, id_, name):
        if (id_ in self.attr_dict_map
                and name in self.attr_dict_map[id_]):
            del self.attr_dict_map[id_][name]

    def get_attr_dict(self, id_):
        if id_ not in self.attr_dict_map:
            return self.empty_dict
        else:
            return self.attr_dict_map[id_]

    def del_attr_dict(self, id_):
        if id_ in self.attr_dict_map:
            del self.attr_dict_map[id_]

cdef InfoListNode* insert_node_before(InfoListNodeList* nodelist,
        InfoListNode* node, InfoListNode* pos, int reverse) except NULL:
    cdef int cmp_result
    # Insert a node in the correct position in nodelist by searching backwards
    # from pos.  Returns the position just before node gets inserted, which is
    # can be used for future calls
    while not infolist_node_is_sentinal(pos):
        cmp_result = infolist_node_cmp(node, pos)
        if reverse:
            cmp_result *= -1
        if cmp_result < 0:
            pos = pos.prev
        else:
            break
    infolist_nodelist_insert_after(nodelist, pos, node)
    return pos

cdef int update_sort_key(InfoListNode* node, object new_sort_key, int reverse):
    # Update node's sort key, then return TRUE if the node is now out of place
    # in the list.
    cdef int cmp_result
    cdef object old_sort_key

    old_sort_key = infolist_node_get_sort_key(node)
    infolist_node_set_sort_key(node, new_sort_key)
    if old_sort_key == new_sort_key: # sort key didn't change
        return 0
    if not infolist_node_is_sentinal(node.next):
        cmp_result = infolist_node_cmp(node, node.next)
        if (not reverse and cmp_result > 0) or (reverse and cmp_result < 0):
            return 1
    if not infolist_node_is_sentinal(node.prev):
        cmp_result = infolist_node_cmp(node, node.prev)
        if (not reverse and cmp_result < 0) or (reverse and cmp_result > 0):
            return 1
    return 0

cdef enum SortMode:
    INFOLIST_SORT_NORMAL = 0
    INFOLIST_SORT_REVERSED = 1

cdef class InfoList:
    """InfoList -- TableModel for ItemInfo and similar objects

    InfoList is a highly optimized TableModel for item lists.  It also has
    some nice features for handling item lists.
      - can quickly lookup an info by it's id attribute.
      - automatically keeps the list in sorted order
      - can store arbitrary attributes for each item.  This can help to
        implement animations and other UI goodies.

    There's nothing in the code that ties InfoList to ItemInfo objects, it
    supports any python object that has an id attribute.
    """

    cdef InfoListNodeList* nodelist
    cdef dict id_map # maps ids -> CObjects that point to nodes
    cdef object sort_key_func
    cdef object grouping_func
    cdef int sort_mode
    cdef InfoListAttributeStore attributes

    def __cinit__(self, *args, **kwargs):
        # __cinit__ should allocate any C resources
        self.nodelist = infolist_nodelist_new()
        infolistplat_nodelist_created(self.nodelist)
        self.id_map = {}

    def __dealloc__(self):
        # __dealloc__ should free any C resources
        infolistplat_nodelist_will_destroy(self.nodelist)
        infolist_nodelist_free(self.nodelist)

    def __init__(self, sort_key_func, reverse=False):
        """Create an InfoList.

        :param sort_key_func: function that inputs an info and outputs a key
                              to sort with
        :param reverse: Should we sort in reverse order?
        """
        self._set_sort(sort_key_func, reverse)
        self.attributes = InfoListAttributeStore()

    cdef int _set_sort(self, object sort_key_func, object reverse) except -1:
        if sort_key_func is None:
            raise ValueError("sort_key_func can't be None")
        self.sort_key_func = sort_key_func
        if reverse:
            self.sort_mode = INFOLIST_SORT_REVERSED
        else:
            self.sort_mode = INFOLIST_SORT_NORMAL
        return 0

    cdef int sort_nodes(self, InfoListNode** nodes, int count) except -1:
        if self.sort_mode == INFOLIST_SORT_NORMAL:
            infolist_node_sort(nodes, count)
        elif self.sort_mode == INFOLIST_SORT_REVERSED:
            infolist_node_sort_reversed(nodes, count)

    cdef int sort_nodes_reversed(self, InfoListNode** nodes,
            int count) except -1:
        if self.sort_mode == INFOLIST_SORT_NORMAL:
            infolist_node_sort_reversed(nodes, count)
        elif self.sort_mode == INFOLIST_SORT_REVERSED:
            infolist_node_sort(nodes, count)

    cdef InfoListNode* _fetch_node(self, object id) except NULL:
        cdef object cobject

        cobject = self.id_map[id]
        return <InfoListNode*>PyCObject_AsVoidPtr(cobject)

    def add_infos(self, new_infos):
        """Add a list of objects into the list.

        If we have a sort, they will be inserted in sorted order.  If not,
        they will be inserted at the end of the list.

        If any info is already in the list, then a ValueError will be thrown
        and no changes will be made.

        :param new_infos: an iterable with the infos
        """
        cdef InfoListNode* pos
        cdef InfoListNode* new_node
        cdef InfoListNode** node_array
        cdef int i
        cdef int count
        cdef int reverse_sort
        cdef int infos_created
        cdef int infos_added
        cdef object info, sort_key

        infos_created = infos_added = 0
        count = len(new_infos)
        node_array = <InfoListNode**>PyMem_Malloc(
                sizeof(InfoListNode*) * count)
        try:
            # prepare the insert
            for 0 <= i < count:
                info = new_infos[i]
                if info.id in self.id_map:
                    raise ValueError("Info with id %s already in list" %
                            info.id)
                sort_key = self.sort_key_func(info)
                node_array[i] = infolist_node_new(info.id, info, sort_key)
                infos_created += 1
            # insert nodes in reversed order, this makes calculating rows
            # simpler in the GTK code
            infolistplat_will_add_nodes(self.nodelist)
            pos = infolist_nodelist_tail(self.nodelist)
            self.sort_nodes_reversed(node_array, count)
            reverse_sort = (self.sort_mode == INFOLIST_SORT_REVERSED)
            for 0 <= i < count:
                new_node = node_array[i]
                pos = insert_node_before(self.nodelist, new_node, pos,
                        reverse_sort)
                infos_added += 1
                cobj = PyCObject_FromVoidPtr(new_node, NULL)
                self.id_map[infolist_node_get_id(new_node)] = cobj
                infolistplat_node_added(self.nodelist, new_node)
        finally:
            if infos_added < infos_created:
                for infos_added <= i < infos_created:
                    infolist_node_free(node_array[i])
            PyMem_Free(node_array)

    def update_infos(self, infos, resort):
        """Update a list of objects

        if any of the infos are not already in the list, a KeyError will be
        thown and no changes will be made.

        :param infos: list of infos to update
        :param resort: should the list be resorted?
        """

        cdef InfoListNode** node_array # stores the nodes we will update
        cdef InfoListNode* pos
        cdef InfoListNode* node
        cdef int count, move_count, reverse
        cdef object sort_key

        node_array = NULL
        count = len(infos)
        node_array = <InfoListNode**>PyMem_Malloc(
                sizeof(InfoListNode*) * count)
        try:
            # fetch first, in case of key error
            for 0 <= i < count:
                node_array[i] = self._fetch_node(infos[i].id)
            infolistplat_will_change_nodes(self.nodelist)
            for 0 <= i < count:
                node = node_array[i]
                infolist_node_set_info(node, infos[i])
                infolistplat_node_changed(self.nodelist, node)
            if not resort:
                return
            if self.sort_mode == INFOLIST_SORT_NORMAL:
                reverse = 0
            elif self.sort_mode == INFOLIST_SORT_REVERSED:
                reverse = 1

            # update sort keys and figure out which nodes actually need to
            # move.
            move_count = 0
            for 0 <= i < count:
                node = node_array[i]
                sort_key = self.sort_key_func(infolist_node_get_info(node))
                if update_sort_key(node, sort_key, reverse):
                    node_array[move_count] = node
                    move_count += 1
            if move_count == 0:
                return
            # remove infos, sort them, then re-enter them
            infolistplat_will_reorder_nodes(self.nodelist)
            for 0 <= i < move_count:
                infolist_nodelist_remove(self.nodelist, node_array[i])
            self.sort_nodes_reversed(node_array, move_count)
            pos = infolist_nodelist_tail(self.nodelist)
            for 0 <= i < move_count:
                pos = insert_node_before(self.nodelist, node_array[i], pos,
                        reverse)
            infolistplat_nodes_reordered(self.nodelist)
        finally:
            PyMem_Free(node_array)

    def remove_ids(self, id_list):
        """Remove objects from the list.

        If any id is not in the list, then a KeyError will be thrown and no
        changes will be made.

        :param id_list: list of ids to remove
        """

        cdef InfoListNode** to_remove
        cdef InfoListNode* node
        cdef int i, count

        count = len(id_list)
        to_remove = <InfoListNode**>PyMem_Malloc(sizeof(InfoListNode*) * count)
        try:
            # fetch all nodes first in case of KeyError
            for 0 <= i < count:
                to_remove[i] = self._fetch_node(id_list[i])
            infolistplat_will_remove_nodes(self.nodelist)
            # order nodes last-to-first so that we call
            # infolistplat_node_removed in that order
            self.sort_nodes_reversed(to_remove, count)
            for 0 <= i < count:
                node = to_remove[i]
                infolist_nodelist_remove(self.nodelist, node)
                del self.id_map[infolist_node_get_id(node)]
                self.attributes.del_attr_dict(infolist_node_get_info(node).id)
                infolistplat_node_removed(self.nodelist, node)
                infolist_node_free(node)
        finally:
            PyMem_Free(to_remove)

    def remove_all(self):
        """Remove all data from the InfoList."""
        cdef InfoListNode* node
        cdef InfoListNode* prev_node
        infolistplat_will_remove_nodes(self.nodelist)
        # remove last-to-first so that we call
        # infolistplat_node_removed in that order
        node = infolist_nodelist_tail(self.nodelist)
        while not infolist_node_is_sentinal(node):
            prev_node = node.prev
            infolist_nodelist_remove(self.nodelist, node)
            infolistplat_node_removed(self.nodelist, node)
            infolist_node_free(node)
            node = prev_node
        self.attributes = InfoListAttributeStore()
        self.id_map = {}

    def set_attr(self, id_, name, value):
        self.attributes.set_attr(id_, name, value)
        self._send_node_changed(id_)

    def unset_attr(self, id_, name):
        self.attributes.unset_attr(id_, name)
        self._send_node_changed(id_)

    def _send_node_changed(self, id_):
        cdef InfoListNode* node

        infolistplat_will_change_nodes(self.nodelist)
        infolistplat_node_changed(self.nodelist, self._fetch_node(id_))

    def get_attr(self, id_, name):
        return self.attributes.get_attr(id_, name)

    def get_info(self, id_):
        return infolist_node_get_info(self._fetch_node(id_))

    def get_first_info(self):
        cdef InfoListNode* node

        node = infolist_nodelist_head(self.nodelist)
        if infolist_node_is_sentinal(node):
            return None
        else:
            return infolist_node_get_info(node)

    def get_last_info(self):
        cdef InfoListNode* node

        node = infolist_nodelist_tail(self.nodelist)
        if infolist_node_is_sentinal(node):
            return None
        else:
            return infolist_node_get_info(node)

    def index_of_id(self, id_):
        return infolist_nodelist_node_index(self.nodelist,
                self._fetch_node(id_))

    def get_next_info(self, id_):
        cdef InfoListNode* node
        
        node = self._fetch_node(id_).next
        if infolist_node_is_sentinal(node):
            return None
        else:
            return infolist_node_get_info(node)

    def get_prev_info(self, id_):
        cdef InfoListNode* node
        
        node = self._fetch_node(id_).prev
        if infolist_node_is_sentinal(node):
            return None
        else:
            return infolist_node_get_info(node)

    def get_sort_key(self, id_):
        return infolist_node_get_sort_key(self._fetch_node(id_))

    def change_sort(self, sort_key_func, reverse=False):
        cdef InfoListNode** nodes
        cdef InfoListNode* node
        cdef InfoListNode* next_node
        cdef int i
        cdef int node_count
        cdef object info

        
        self._set_sort(sort_key_func, reverse)
        node_count = self.nodelist.node_count
        nodes = <InfoListNode**>PyMem_Malloc(
                sizeof(InfoListNode*) * node_count)
        try:
            # remove infos, sort them, then re-enter them
            infolistplat_will_reorder_nodes(self.nodelist)
            node = infolist_nodelist_head(self.nodelist)
            for 0 <= i < node_count:
                nodes[i] = node
                next_node = node.next
                info = infolist_node_get_info(node)
                infolist_node_set_sort_key(node, sort_key_func(info))
                infolist_nodelist_remove(self.nodelist, node)
                node = next_node
            self.sort_nodes_reversed(nodes, node_count)
            node = infolist_nodelist_tail(self.nodelist)
            for 0 <= i < node_count:
                infolist_nodelist_insert_after(self.nodelist, node, nodes[i])
            infolistplat_nodes_reordered(self.nodelist)
        finally:
            PyMem_Free(nodes)

    cdef long _get_group_hash(self, InfoListNode* node):
        """Get the group hash value for a node.

        grouping_func must be not None for this to work!

        _get_group_hash() handles caching group_hash values for nodes so we
        only have to calculate them once.
        """
        if node.group_hash == -1:
            node.group_hash = hash(self.grouping_func(
                infolist_node_get_info(node)))
        return node.group_hash

    def set_grouping(self, grouping_func):
        """Set a grouping function for this info list.

        Grouping functions input info objects and return values that will be
        used to segment the list into groups.  Adjacent infos with the same
        grouping value are part of the same group.

        get_group_info() can be used to find the position of an info inside
        its group.  row_for_iter() also returns this info.
        """
        cdef InfoListNode* node

        self.grouping_func = grouping_func
        # reset group_hash values
        node = infolist_nodelist_head(self.nodelist)
        while not infolist_node_is_sentinal(node):
            node.group_hash = -1
            node = node.next

    def get_group_info(self, id_):
        """Get the info about the group an info is inside.

        This method fetches the index of the info inside the group and the
        total size of the group.

        :returns: an (index, count) tuple
        :raises ValueError: if no groupping is set
        """
        if self.grouping_func is None:
            raise ValueError("no grouping set")

        return self._get_group_info(self._fetch_node(id_))

    cdef object _get_group_info(self, InfoListNode* node):
        """low-level function that the work for get_group_info().
        """
        cdef InfoListNode* other_node
        cdef long group_hash
        cdef int nodes_before
        cdef int nodes_after

        group_hash = self._get_group_hash(node)
        # count nodes in the same group before node
        nodes_before = 0
        other_node = node.prev
        while (not infolist_node_is_sentinal(other_node)
                and self._get_group_hash(other_node) == group_hash):
            nodes_before += 1
            other_node = other_node.prev
        # count nodes in the same group after node
        nodes_after = 0
        other_node = node.next
        while (not infolist_node_is_sentinal(other_node)
                and self._get_group_hash(other_node) == group_hash):
            nodes_after += 1
            other_node = other_node.next
        # now we can calculate the index of node and the size of the group
        return (nodes_before, nodes_before + nodes_after + 1)

    def get_group_top(self, id_):
        """Get the first info for an item's group

        :returns: an info object
        :raises ValueError: if no groupping is set
        """
        if self.grouping_func is None:
            raise ValueError("no grouping set")

        return self._get_group_top(self._fetch_node(id_))

    cdef object _get_group_top(self, InfoListNode* node):
        """low-level function that the work for get_group_top().
        """
        cdef InfoListNode* other_node
        cdef long group_hash

        group_hash = self._get_group_hash(node)
        # move up as long as we are still in the group
        other_node = node
        while (not infolist_node_is_sentinal(other_node)
                and self._get_group_hash(other_node.prev) == group_hash):
            other_node = other_node.prev
        return infolist_node_get_info(other_node)

    def __len__(self):
        return self.nodelist.node_count

    def info_list(self):
        """Get all objects, in order, in a python list """
        cdef list rv
        cdef InfoListNode* current_node

        current_node = infolist_nodelist_head(self.nodelist)
        rv = []
        while not infolist_node_is_sentinal(current_node):
            rv.append(infolist_node_get_info(current_node))
            current_node = current_node.next
        return rv

    def add_to_tableview(self, tableview):
        """Add this infolist to a TableView object."""
        infolistplat_add_to_tableview(self.nodelist, tableview)

    def row_for_iter(self, pos):
        """Get a (info, attr_dict, group_info) tuple for a row in this list.

        pos is platform-specific, on gtk it's a gtk.TreeIter object.

        :param pos: position in the list
        """
        cdef InfoListNode* node
        cdef object info

        node = infolistplat_node_for_pos(self.nodelist, pos)
        info = infolist_node_get_info(node)
        if self.grouping_func is None:
            group_info = None
        else:
            group_info = self._get_group_info(node)
        return (info, self.attributes.get_attr_dict(info.id), group_info)

    def iter_for_id(self, id_):
        """Get an TableModel iterator for an info in the list

        Iterators are a platform-specific object that refers to a position in
        the table.  "Iterator" is a bit of a misnomer, since they are only
        used for positions, not actually iterating through the list.

        :param id_: id of the info that we care about
        :returns: Platform-specific TableModel iterator

        """

        cdef InfoListNode* node

        node = self._fetch_node(id_)
        return infolistplat_iter_for_node(self.nodelist, node)

    def nth_row(self, index):
        cdef InfoListNode* node
        cdef object info

        node = infolist_nodelist_nth_node(self.nodelist, index)
        info = infolist_node_get_info(node)
        return (info, self.attributes.get_attr_dict(info.id))

    def __getitem__(self, pos):
        return self.row_for_iter(pos)

    def _sanity_check(self):
        """Debugging function that tests if the list structure is sane."""
        infolist_nodelist_check_nodes(self.nodelist)
        info_list = self.info_list()
        for info in info_list:
            if info is not self.get_info(info.id):
                raise AssertionError("id_map for %s is wrong" % info.id)

        for i in xrange(len(info_list) - 1):
            if (self.sort_mode == INFOLIST_SORT_NORMAL and 
                (self.get_sort_key(info_list[i].id) >
                    self.get_sort_key(info_list[i+1].id))):
                    raise AssertionError("infos out of order")
            elif (self.sort_mode == INFOLIST_SORT_REVERSED and 
                (self.get_sort_key(info_list[i].id) <
                    self.get_sort_key(info_list[i+1].id))):
                    raise AssertionError("infos out of order")

# module-level initialization
infolistplat_init()
