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

// idmap.cpp -- implementation of IpMap

#ifdef __GNUC__
#include <ext/hash_map>
namespace std {
        using namespace __gnu_cxx; // needed to use hash_map
}
#else
// WINDOWS
#include <hash_map>
namespace std {
        using namespace stdext; // needed to use hash_map
}
#endif
#include "infolist-idmap.h"
#include "Python.h"

typedef std::hash_map<int, InfoListNode*> HashMapType;

// Wrap hash_map in a struct so we can pass pointers to C
struct InfoListIDMapStruct {
        HashMapType map;
};

InfoListIDMap*
infolist_idmap_new()
{
        try {
                return new InfoListIDMapStruct();
        } catch(std::bad_alloc& e) {
                return (InfoListIDMap*)PyErr_NoMemory();
        }
}

void
infolist_idmap_free(InfoListIDMap* id_map)
{
        delete id_map;
}

void
infolist_idmap_set(InfoListIDMap* id_map,
           int id,
           InfoListNode* node)
{
        id_map->map[id] = node;
}

InfoListNode*
infolist_idmap_get(InfoListIDMap* id_map,
           int id)
{
        HashMapType::const_iterator iter = id_map->map.find(id);
        if(iter == id_map->map.end()) return NULL;
        else return iter->second;
}

void
infolist_idmap_remove(InfoListIDMap* id_map,
              int id)
{
        id_map->map.erase(id);
}
