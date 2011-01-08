# Miro - an RSS based video player application
# Copyright (C) 2010 Participatory Culture Foundation
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
"""

__all__ = [
    "signals",
    "get_support_directory",
    "APIVERSION"
    ]

# increase this by 1 every time the API changes
APIVERSION = 0

from miro import signals

class ExtensionException(StandardError):
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
    except ImportError:
        return "unknown"
    try:
        return plat.PLATFORMNAME.lower()
    except AttributeError:
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
    except ImportError:
        return "unknown"
    try:
        return plat.FRONTEND.lower()
    except AttributeError:
        return "unknown"

def get_support_directory():
    from miro import app, prefs
    return app.config.get(prefs.SUPPORT_DIRECTORY)
