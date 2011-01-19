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

// infolist-platform.h -- platform-specific functions
//
// This header defines functions that platforms use to integrate InfoList with
// the GUI framework.  Each platform should have a C file (or multiple files)
// that define functions for each of these hooks.
//
// All functions should return 0 on success and -1 on failure (and set the
// python exception)

int
infolistplat_init(void);

int
infolistplat_nodelist_created(InfoListNodeList* nodelist);

int
infolistplat_nodelist_will_destroy(InfoListNodeList* nodelist);


// Called before adding nodes to the list
void
infolistplat_will_add_nodes(InfoListNodeList* nodelist);

// Called for over node added to the list.  They will be added from back to
// front.
int
infolistplat_node_added(InfoListNodeList* nodelist,
                       InfoListNode* node);

// Called before making updates to the list
void
infolistplat_will_change_nodes(InfoListNodeList* nodelist);

// Called for each node changed
int
infolistplat_node_changed(InfoListNodeList* nodelist,
                         InfoListNode* node);

// Called before removing nodes from the list
void
infolistplat_will_remove_nodes(InfoListNodeList* nodelist);

// Called for each node removed from the list.  Rows will be removed back to
// front.
int
infolistplat_node_removed(InfoListNodeList* nodelist,
                         InfoListNode* node);

// Called before reordering nodes
void
infolistplat_will_reorder_nodes(InfoListNodeList* nodelist);

// Called after reordering nodes
int
infolistplat_nodes_reordered(InfoListNodeList* nodelist);

int
infolistplat_add_to_tableview(InfoListNodeList* nodelist,
                              PyObject* tableview);

InfoListNode*
infolistplat_node_for_pos(InfoListNodeList* nodelist,
                          PyObject* pos);
