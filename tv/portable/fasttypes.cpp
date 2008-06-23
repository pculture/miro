/*
# Miro - an RSS based video player application
# Copyright (C) 2005-2008 Participatory Culture Foundation
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

// fasttypes.cpp implements linked list and sorted list types for
// Python using the STL class libraries.

// TODO: Finalize and document the Python classes

// I duplicate a lot of code in LinkedList and SortedList. I probably
// could get around this by creating a template class containing the
// identical functions, then extending that to make LinkedList and
// SortedList.

#include <boost/python.hpp>
#include <boost/python/module.hpp>
#include <boost/python/def.hpp>
#include <boost/python/call.hpp>
#include <boost/python/exception_translator.hpp>
#include <list>
#include <set>
#include <iterator>
#include <exception>
using namespace boost::python;
using namespace std;

// Python None
object none = object();

// Code to pass index exceptions through to Python
struct indexException : std::exception
{
  char const* what() throw() { return "list index out of range"; }
};
void indexExceptionTranslator(exception const& x) {
  PyErr_SetString(PyExc_IndexError, "list index out of range");
}

struct indexPopException : std::exception
{
  char const* what() throw() { return "pop from empty list"; }
};
void indexPopExceptionTranslator(exception const& x) {
  PyErr_SetString(PyExc_IndexError, "pop from empty list");

}

typedef std::list<object>::iterator LinkedListIterator;
typedef std::multiset<object,object>::iterator SortedListIterator;

//Create a linked list type with Pythonish semantics, but backed by STL
class LinkedList:protected std::list<object> {
private:
  size_t length ;
public:
  LinkedList() {
    length = 0;
  }

  object pop() {
    if (length == 0)
      throw indexPopException();
    else {
      length--;
      object temp = back();
      pop_back();
      return temp;
    }
  }

  LinkedListIterator append(const object &obj) {
    length++;
    return insert(end(),obj);
  }

  LinkedListIterator prepend(const object &obj) {
    length++;
    return insert(begin(),obj);
  }

  object getItem(LinkedListIterator &it) {
    if (it == end())
      throw indexException();
    else
      return *it;
  }

  object getItem(size_t n) {
    if (n >= length)
      throw indexException();
    else {
      LinkedListIterator it = begin();
      advance(it,n);
      return *it;
    }
  }

  void setItem(LinkedListIterator &it, object &obj) {
    //Raise an exception if iterator is pointing into space
    if (it == end())
      throw indexException();
    else
      *it = obj;
  }

  void setItem(size_t n, object &obj) {
    if (n < length) {
      LinkedListIterator it = begin();
      advance(it,n);
      *it = obj;
    } else {
      throw indexException();
    }
  }
  
  LinkedListIterator insertBefore(LinkedListIterator &it, object &obj) {
    length++;
    return insert(it, obj);
  }

  LinkedListIterator delItem(LinkedListIterator &it) {
    if (it == end())
      throw indexException();
    else {
      length--;
      return erase(it);
    }
  }

  LinkedListIterator delItem(size_t n) {
    if (n < length) {
      length--;
      LinkedListIterator it = begin();
      advance(it,n);
      return erase(it);
    } else {
      throw indexException();
    }
  }

  LinkedListIterator first() {
    return begin();
  }

  LinkedListIterator last() {
    return end();
  }

  size_t len() {
    return length;
  }

};

//Create a sorted list type with Pythonish semantics, but backed by STL
class SortedList:public std::multiset<object,object> {
private:
  size_t length ;
public:
  SortedList(const key_compare& comp): std::multiset<object,object>(comp),
                                       length(0) {}

  object pop() {
    if (length == 0)
      throw indexPopException();
    else {
      length--;
      SortedListIterator it = end();
      advance(it, -1);
      object temp = *it;
      erase(it);
      return temp;
    }
  }

  SortedListIterator append(const object &obj) {
    length++;
    return insert(end(),obj);
  }

  SortedListIterator prepend(const object &obj) {
    length++;
    return insert(begin(),obj);
  }

  object getItem(SortedListIterator &it) {
    if (it == end())
      throw indexException();
    else
      return *it;
  }

  object getItem(size_t n) {
    if (n >= length)
      throw indexException();
    else {
      SortedListIterator it = begin();
      advance(it,n);
      return *it;
    }
  }

  void setItem(SortedListIterator &it, object &obj) {
    //Raise an exception if iterator is pointing into space
    if (it == end())
      throw indexException();
    else {
      insert(it, obj);
      erase(it);
    }
  }

  void setItem(size_t n, object &obj) {
    if (n < length) {
      SortedListIterator it = begin();
      advance(it,n);
      insert(it, obj);
      erase(it);
    } else {
      throw indexException();
    }
  }
  
  SortedListIterator insertBefore(SortedListIterator &it, object &obj) {
    length++;
    return insert(it, obj);
  }

  void delItem(SortedListIterator &it) {
    if (it == end())
      throw indexException();
    else {
      length--;
      erase(it);
    }
  }

  void delItem(size_t n) {
    if (n < length) {
      length--;
      SortedListIterator it = begin();
      advance(it,n);
      erase(it);
    } else {
      throw indexException();
    }
  }

  SortedListIterator first() {
    return begin();
  }

  SortedListIterator last() {
    return end();
  }

  size_t len() {
    return length;
  }

};


// Create some function pointers so we can pass the overloaded
// functions to Python
object (LinkedList::*LLgetItem1)(size_t) = &LinkedList::getItem;
object (LinkedList::*LLgetItem2)(LinkedListIterator&) = &LinkedList::getItem;
void (LinkedList::*LLsetItem1)(size_t, object&) = &LinkedList::setItem;
void (LinkedList::*LLsetItem2)(LinkedListIterator&, object&) = &LinkedList::setItem;
LinkedListIterator (LinkedList::*LLdelItem1)(size_t) = &LinkedList::delItem;
LinkedListIterator (LinkedList::*LLdelItem2)(LinkedListIterator&) = &LinkedList::delItem;

object (SortedList::*SLgetItem1)(size_t) = &SortedList::getItem;
object (SortedList::*SLgetItem2)(SortedListIterator&) = &SortedList::getItem;
void (SortedList::*SLsetItem1)(size_t, object&) = &SortedList::setItem;
void (SortedList::*SLsetItem2)(SortedListIterator&, object&) = &SortedList::setItem;
void (SortedList::*SLdelItem1)(size_t) = &SortedList::delItem;
void (SortedList::*SLdelItem2)(SortedListIterator&) = &SortedList::delItem;

// As far as I can tell, there's no easy way to test that this
// iterator isn't past-the-end, so calling either of these on a
// past-the-end iterator is undefined and may segfault some STL
// implementations
LinkedListIterator *copyLLIter(LinkedListIterator& it) {
  return new LinkedListIterator(it);
}
void incLLIter(LinkedListIterator& it) {
  advance(it,1);
}
void decLLIter(LinkedListIterator& it) {
  advance(it,-1);
}
object LLIterValue(LinkedListIterator& it) {
    return *it;
}
SortedListIterator *copySLIter(SortedListIterator& it) {
  return new SortedListIterator(it);
}
void incSLIter(SortedListIterator& it) {
  advance(it,1);
}
void decSLIter(SortedListIterator& it) {
  advance(it,-1);
}
object SLIterValue(SortedListIterator& it) {
    return *it;
}

BOOST_PYTHON_MODULE(fasttypes)
{
  register_exception_translator<indexException>(&indexExceptionTranslator);
  register_exception_translator<
                        indexPopException>(&indexPopExceptionTranslator);

  class_<LinkedListIterator>("LinkedListIterator")
    .def("copy",&copyLLIter,return_value_policy<manage_new_object>())
    .def("forward",&incLLIter)
    .def("back",&decLLIter)
    .def("value",&LLIterValue)
    .def(self == self)
    .def(self != self)
  ;

  class_<SortedListIterator>("SortedListIterator")
    .def("copy",&copySLIter,return_value_policy<manage_new_object>())
    .def("forward",&incSLIter)
    .def("back",&decSLIter)
    .def("value",&SLIterValue)
    .def(self == self)
    .def(self != self)
  ;

  class_<LinkedList>("LinkedList")
    .def("__len__",&LinkedList::len)
    .def("append",&LinkedList::append)
    .def("firstIter",&LinkedList::first)
    .def("lastIter",&LinkedList::last)
    .def("prepend",&LinkedList::prepend)
    .def("pop",&LinkedList::pop)
    .def("__delitem__",LLdelItem1)
    .def("__delitem__",LLdelItem2)
    .def("remove",LLdelItem1)
    .def("remove",LLdelItem2)
    .def("insertBefore", &LinkedList::insertBefore)
    .def("__iter__",range(&LinkedList::first,&LinkedList::last))
    .def("__setitem__",LLsetItem1)
    .def("__setitem__",LLsetItem2)
    .def("__getitem__",LLgetItem1)
    .def("__getitem__",LLgetItem2)
  ;

  class_<SortedList>("SortedList", init<object>())
    .def("__len__",&SortedList::len)
    .def("append",&SortedList::append)
    .def("firstIter",&SortedList::first)
    .def("lastIter",&SortedList::last)
    .def("prepend",&SortedList::prepend)
    .def("pop",&SortedList::pop)
    .def("__delitem__",SLdelItem1)
    .def("__delitem__",SLdelItem2)
    .def("remove",SLdelItem1)
    .def("remove",SLdelItem2)
    .def("insertBefore", &SortedList::insertBefore)
    .def("__iter__",range(&SortedList::first,&SortedList::last))
    .def("__setitem__",SLsetItem1)
    .def("__setitem__",SLsetItem2)
    .def("__getitem__",SLgetItem1)
    .def("__getitem__",SLgetItem2)
  ;
}

