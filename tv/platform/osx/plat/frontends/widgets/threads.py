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

"""miro.plat.frontends.widgets.threads -- Handle UI threading."""

import logging
import traceback

from PyObjCTools import AppHelper

def call_wrapper(func, args, kwargs):
    def wrapper():
        try:
            func(*args, **kwargs)
        except:
            msg = "Error when calling %s" % func
            if args:
                msg += ' (args: %s)' % args
            if kwargs:
                msg += ' (kwargs: %s)' % kwargs
            logging.warn("%s\n%s", msg, traceback.format_exc())
    return wrapper

def call_on_ui_thread(func, *args, **kwargs):
    """Call a function in the UI thread."""
    AppHelper.callAfter(call_wrapper(func, args, kwargs))

def on_ui_thread(func):
    """Decorator which specifies that a method should always be called on the 
    main GUI thread.
    """
    def scheduled(*args, **kwargs):
        call_on_ui_thread(func, *args, **kwargs)
    return scheduled
