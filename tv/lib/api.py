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
