# Miro - an RSS based video player application
# Copyright (C) 2010, 2011
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

"""miro.api -- API for extensions.

Hook functions
-------------------------
Hook functions are used to hook into core components in a well-definined way.
For example, the 'item_list_filter' hook is used to add item filters to the
top of an item list.

If your extension wants to implement a hook function, add a "hooks" section in
your config file containing a list of hooks.  For each hook, the key is the
name of the hook and the value specifies where to find the hook function.  The
values are in the form of package.module:path.to.obj.

Here's an example [hooks] section::

    [hooks]
    hook1 = myext:handle_hook
    hook2 = myext.foo:handle_hook
    hook3 = myext:hook_obj.handle_hook

In this example, hook1 will be handled by handle_hook() inside the module
myext, hook2 will be handled by the handle_hook() function inside the module
myext.foo, and hook3 will be handled by the handle() method in inside the
hook_obj object inside the module myext

Hook functions help keep a stable API for extensions over different releases
and allow extensions to coexist better.  You can probably achieve the same
results by importing core modules directly and monkey patching things, but
this approach will almost certainly break when the core code changes or when
another extension tries to do the same thing.

Your extension can also define a hook for other extensions to use.  You can
use the hook_invoke() method to call all functions registered for a hook you
define.


.. Note::

   This API is missing a lot of important stuff.  If you're interested in
   building extensions or are otherwise interested in fleshing out the
   API, come hang out with us on #miro-hackers on Freenode on IRC.
"""

__all__ = [
    "APIVERSION",
    "signals",
    "ExtensionException",
    "PlatformNotSupported",
    "FrontendNotSupported",
    "APIVersionNotSupported",
    "get_platform",
    "get_frontend",
    "get_support_directory",
    "hook_invoke",
    ]

# increase this by 1 every time the API changes
APIVERSION = 0

import logging
import os

import sqlite3
try:
    import simplejson as json
except ImportError:
    import json

from miro import app
from miro import signals

class ExtensionException(StandardError):
    """Base exception class for Extension-related exceptions.
    """
    pass

class PlatformNotSupported(ExtensionException):
    """Raise this in ``load`` when the extension doesn't support the
    platform Miro is currently running on.
    """
    pass

class FrontendNotSupported(ExtensionException):
    """Raise this in ``load`` when the extension doesn't support the
    frontend Miro is using.
    """
    pass

class APIVersionNotSupported(ExtensionException):
    """Raise this in ``load`` when the extension doesn't support this
    version of the API.
    """
    pass

def get_platform():
    """Returns the name of the platform Miro is currently running on.
    This can be used to prevent extensions from loading on platforms
    they don't support.

    Example:

    >>> if api.get_platform() not in ['linux', 'windows']:
    ...     raise api.PlatformNotSupported('Linux and Windows only.')
    ...
    """
    try:
        from miro import plat
        return plat.PLATFORMNAME.lower()
    except (ImportError, AttributeError):
        return "unknown"

def get_frontend():
    """Returns the name of the frontend Miro is currently using.  This
    can be used to prevent extensions from loading for frontends they
    don't support.

    Example:

    >>> if api.get_frontend() not in ['cli']:
    ...     raise api.FrontendNotSupported('cli only')
    ...
    """
    try:
        from miro import plat
        return plat.FRONTEND.lower()
    except (ImportError, AttributeError):
        return "unknown"

def get_support_directory():
    """Returns the absolute path of the support directory for this
    user.  This is where you could store database files or other
    similar data.

    Example:

    >>> path = api.get_support_directory()
    """
    from miro import app, prefs
    return app.config.get(prefs.SUPPORT_DIRECTORY)

class StorageManager(object):
    """Manages data for an extension.

    StorageManagers allow two kinds of data storage:

    - Simple Storage: simple key/value pair storage.  Useful for extensions
      with basic storage needs.  See the set_value(), get_value(), and
      clear_value() methods.

    - SQLite Storage: Use an SQLite connection.  Use this if you have complex
      storage needs and want a relational database to handle it.  Call
      get_sqlite_connection() to use this.

    A StorageManager object is passed into each extension's load() function
    via the context argument.  Extensions must use this object for their
    storage needs.  Do not create a new StorageManager object.

    Simple and SQLite storage can be used together if needed, however they
    share the same underlying SQLite connection.  You should avoid using the
    simple storage API while in the middle of an SQLite transation.
    """

    def __init__(self, unique_name):
        """Create a StorageManager

        :param unique_name: unique string to name the sqlite file with
        """
        self._unique_name = unique_name
        # Sqlite connection/cursor.  We create these lazily because many
        # extensions won't use their StorageManager
        self._connection = None
        self._cursor = None
        # stores if we've run through _ensure_simple_api_table()
        self._checked_for_simple_api_table = False

    def _ensure_connection(self):
        if self._connection is None:
            self._connection = sqlite3.connect(self._sqlite_path(),
                    isolation_level=None)
            self._cursor = self._connection.cursor()

    def _sqlite_path(self):
        filename = 'extension-db-%s.sqlite' % self._unique_name
        return os.path.join(get_support_directory(), filename)

    def get_sqlite_connection(self):
        self._ensure_connection()
        return self._connection

    def _ensure_simple_api_table(self):
        """Ensure the table we need for the simple API has been created.
        """
        if self._checked_for_simple_api_table:
            return
        self._ensure_connection()
        self._cursor.execute("SELECT COUNT(*) FROM sqlite_master "
                "WHERE type='table' and name = 'simple_data'")
        if self._cursor.fetchone()[0] == 0:
            self._cursor.execute("CREATE TABLE simple_data "
                    "(key TEXT PRIMARY KEY, value TEXT)")
        self._checked_for_simple_api_table = True

    def set_value(self, key, value):
        """Set a value using the simple API

        set_value() stores a value that you can later retrieve with
        get_value()

        :param key: key to set (unicode or an ASCII bytestring)
        :param value: value to set
        """
        self._ensure_simple_api_table()
        self._cursor.execute("INSERT OR REPLACE INTO simple_data "
                "(key, value) VALUES (?, ?)",
                (key, json.dumps(value)))
        self._connection.commit()

    def get_value(self, key):
        """Get a value using the simple API

        get_value() retrieves a value that was previously set with set_value().

        :param key: key to retrieve
        :returns: value set with set_value()
        :raises KeyError: key not set
        """
        self._ensure_simple_api_table()
        self._cursor.execute("SELECT value FROM simple_data WHERE key=?",
                (key,))
        row = self._cursor.fetchone()
        if row is None:
            raise KeyError(key)
        else:
            return json.loads(row[0])

    def key_exists(self, key):
        """Test if a key is stored using the simple API

        :param key: key to retrieve
        :returns: True if a value set with set_value()
        """
        self._ensure_simple_api_table()
        self._cursor.execute("SELECT value FROM simple_data WHERE key=?",
                (key,))
        return self._cursor.fetchone() is not None

    def clear_value(self, key):
        """Clear a value using the simple API

        clear_value() unsets a value that was set with set_value().

        Calling clear_value() with a key that has not been set results in a
        no-op.

        :param key: key to clear
        """
        self._ensure_simple_api_table()
        self._cursor.execute("DELETE FROM simple_data WHERE key=?", (key,))
        self._connection.commit()

class ExtensionContext(object):
    """ExtensionContext -- Stores objects specific to an extension

    ExtensionContexts are passed in to the load() method for each extension.

    Attributes:
      - storage_manager: StorageManager for the extension

    New attributes will be added as we add to the extension system
    """
    def __init__(self, unique_name):
        self.storage_manager = StorageManager(unique_name)

def hook_invoke(hook_name, *args, **kwargs):
    """Call all functions registered for a hook.

    We will call each function registered with hook_register() with hook_name.
    args and kwargs are used to call the hook functions.

    We will return a list of return values, one for each registered hook.
    """
    results = []
    for ext in app.extension_manager.extensions_for_hook(hook_name):
        try:
            retval = ext.invoke_hook(hook_name, *args, **kwargs)
        except StandardError:
            # hook func raised an error.  Log it, then ignore
            logging.exception("exception calling hook function %s ", ext.name)
            continue
        else:
            results.append(retval)
    return results
