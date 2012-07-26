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

#include <Python.h>

/*
 * miro.data.namecollation -- implement the collation for names.
 *
 * When ordering by name, we have a few special rules:
 * - We ignore case
 * - A leading "The" or "a" is ignored
 * - Names with numbers in them are sorted using natural sort ("Episode 10"
 *   comes after "Episode 9")
 *
 * The setup_collation() function creates the name collation on an sqlite3
 * Connection object.  After that's called you can use "collate name" to order
 * using the above rules
 *
 * This module is implemented in C because doing it in python resulted in a
 * serious slow down.
 *
 */

#include <Python.h>
#include <sqlite3.h>
#include <wctype.h>

/*
 * As far as I can tell there's no header file that defines the struct for a
 * sqlite3.Connection object.  We need to try to define it ourselves.  The
 * following is definitely incomplete, but all we care about is the pointer
 * to the sqlite3 struct.  As long as the actual struct has the sqlite3
 * pointer as it's first member this should work.
*/

typedef struct {
    PyObject_HEAD
    sqlite3* db;
} PySqliteConnectionStruct;

static PyTypeObject* PySqliteConnectionType;

/*
 * Define a list of strings that we want to ignore if they name starts with
 * them.  These stored in utf8-encoded format (fortunately plain ASCII works
 * fine).
 */

static const char* prefixes_to_ignore[] = {
        "the ",
        "a ",
};
#define PREFIXES_TO_IGNORE_SIZE 2

/*
 * get_utf8_char
 * Given a UTF string, get the first wide character in it
 */
wchar_t get_utf8_char(const char* string, int* char_length)
{

    int char_len;
    int i;
    char first_byte_mask;
    wint_t rv;
    char first_char;

    first_char = string[0];
    if ((first_char & 0x80) == 0) {
        char_len = 1;
        first_byte_mask = 0x7F;
    } else if (first_char >> 5 == 0x06) {
        char_len = 2;
        first_byte_mask = 0x1F;
    } else if (first_char >> 4 == 0x0E) {
        char_len = 3;
        first_byte_mask = 0x0F;
    } else if (first_char >> 5 == 0x1E) {
        char_len = 4;
        first_byte_mask = 0x07;
    } else if (first_char >> 6 == 0x3E) {
        char_len = 5;
        first_byte_mask = 0x03;
    } else {
        char_len = 6;
        first_byte_mask = 0x01;
    }

    /* Process first byte */
    rv = string[0] & first_byte_mask;
    /* Process addtional byte */
    for(i = 1; i < char_len; i++) {
        rv = (rv << 6) | (string[i] & 0x3F);
    }
    /* return results */
    *char_length = char_len;
    return rv;
}

/*
 * python-like cmp() function
 */

template <typename T>
int cmp(T left, T right) {
    if (left < right) {
        return -1;
    } else if (left > right) {
        return 1;
    } else {
        return 0;
    }
}

/*
 * Helper class to get wide characters out of a utf8 string
 */

class UTF8Stream {
    public:
        UTF8Stream(const char* string_start, int string_length) {
            this->pos = string_start;
            this->end = string_start + string_length;
            this->move_start_pos();
            this->calc_next_char();
        }

        wint_t peek() {
            return this->next_char;
        }

        // Get the next numeric value in the stream
        long peeknumber() {
            wchar_t digits[128];
            const char* digitpos = this->pos;
            int char_len;
            wchar_t next_char;

            for(int i=0; i < 127; i++) {
                if(digitpos >= this->end) {
                    next_char = '\0';
                } else {
                    next_char = get_utf8_char(digitpos, &char_len);
                    digitpos += char_len;
                }

                if(!iswdigit(next_char)) {
                    digits[i] = '\0';
                    break;
                } else {
                    digits[i] = next_char;
                }
            }
            // Ensure the digits string is NUL terminated if we never break
            // from the for loop.
            digits[127] = '\0';
            // Check if we didn't find any digits at all.  If so return -1 to
            // sort non-numbers above numbers.
            if(digits[0] == '\0') {
                return -1;
            }
            // Finally use wcstol to sort numbers.
            return wcstol(digits, NULL, 10);
        }

        void move_forward() {
            this->pos += this->next_char_length;
            this->calc_next_char();
        }

        int at_end() {
            return this->pos >= this->end;
        }

        int length_left() {
            return this->end - this->pos;
        }

    protected:
        const char* pos;
        const char* end;
        wint_t next_char;
        int next_char_length;

        void calc_next_char() {
            if(!this->at_end()) {
                this->next_char = get_utf8_char(this->pos,
                                                &(this->next_char_length));
                this->next_char = towlower(this->next_char);
            } else {
                this->next_char = WEOF;
                this->next_char_length = 0;
            }
        }

        void move_start_pos() {
            for(int i = 0; i < PREFIXES_TO_IGNORE_SIZE; i++) {
                if(this->move_past_prefix(prefixes_to_ignore[i])) {
                    return;
                }
            }
        }

        // Try to move past a prefix string and return 1 if we did
        int move_past_prefix(const char* prefix) {
            const char* search_pos = this->pos;
            const char* prefix_pos = prefix;
            while(search_pos < this->end) {
                wint_t prefix_char, search_char;
                int prefix_char_len, search_char_len;
                prefix_char = get_utf8_char(prefix_pos, &prefix_char_len);
                if(prefix_char == '\0') {
                    // Reached the end of the perfix char.  This is a match.
                    this->pos = search_pos;
                    return 1;
                }
                search_char = get_utf8_char(search_pos, &search_char_len);
                if(towlower(prefix_char) != towlower(search_char)) {
                    // No match
                    return 0;
                }
                // Move to the next character
                prefix_pos += prefix_char_len;
                search_pos += search_char_len;
            }
            // Reached the end of the our string.  No match
            return 0;
        }
};

static int name_collation(void* arg1,
                          int str1_len, const void* v_str1,
                          int str2_len, const void* v_str2)
{
    UTF8Stream string1(static_cast<const char*>(v_str1), str1_len);
    UTF8Stream string2(static_cast<const char*>(v_str2), str2_len);

    while(!string1.at_end() && !string2.at_end()) {
        if(string1.peek() == string2.peek()) {
            string1.move_forward();
            string2.move_forward();
        } else {
            if(iswdigit(string1.peek()) || iswdigit(string2.peek())) {
                // One of strings is on a numeric value.  Compare the numeric
                // values rather than the string values to achieve a natural
                // sort.
                return cmp(string1.peeknumber(), string2.peeknumber());
            } else {
                // Neither strings are numbers, use a character comparison.
                //
                // FIXME: We should use something like strcoll here that takes
                // into account accents and things like that.
                return cmp(string1.peek(), string2.peek());
            }
        }
    }

    // Both strings were the same until one ended.  Order the longer string
    // after the shorter one.
    return cmp(string1.length_left(), string2.length_left());
}

extern "C" {

static PyObject *setup_collation(PyObject* self, PyObject *arg)
{
    if(!PyObject_TypeCheck(arg, PySqliteConnectionType)) {
            PyErr_Format(PyExc_TypeError,
                         "Excepted sqlite3.Connection.  Got %s",
                         arg->ob_type->tp_name);
            return NULL;
    }
    sqlite3_create_collation(((PySqliteConnectionStruct*)arg)->db,
                             "name",
                             SQLITE_UTF8,
                             NULL,
                             name_collation);
    Py_RETURN_NONE;
}

static PyMethodDef DBCollationsMethods[] =
{
    {"setup_collation", (PyCFunction)setup_collation, METH_O,
        "Setup collations on an sqlite database"
    },
    { NULL, NULL, 0, NULL }
};

PyMODINIT_FUNC initnamecollation(void)
{
    PyObject* sqlite3_mod;
    PyObject* connection_obj;
    sqlite3_mod = PyImport_ImportModule("sqlite3");
    if (!sqlite3_mod) {
        PyErr_SetString(PyExc_ImportError, "can't import sqlite3 module");
        return;
    }
    connection_obj = PyObject_GetAttrString(sqlite3_mod, "Connection");
    if(!connection_obj) {
        PyErr_SetString(PyExc_ImportError, "Error importing sqlite3.Connection");
        Py_XDECREF(sqlite3_mod);
        return;
    }
    if(!PyType_Check(connection_obj)) {
        PyErr_SetString(PyExc_ImportError, "sqlite3.Connection is not a type");
        Py_XDECREF(sqlite3_mod);
        return;
    }
    PySqliteConnectionType = reinterpret_cast<PyTypeObject*>(connection_obj);
    Py_XDECREF(sqlite3_mod);
    Py_InitModule("miro.data.namecollation", DBCollationsMethods);
}

} /* extern "C" */
