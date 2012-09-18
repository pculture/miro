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

"""startfrontend.py -- startup the a frontend

This class handles finding the correct frontend to load and starting it up.
Frontends can be in either platform-specific or portable code.  If we are
starting up frontend "foo", then we will look modules in this order: 
    miro.plat.frontends.foo
    miro.frontends.foo
    foo

The foo module should have a run_application() method, which starts up the
frontend.  It should input these arguments:
    props_to_set: dictionary of properties to set
    theme: theme to use or None for the default theme
"""
# FIXME: we could probably move the code that sets propeties and the theme to
# a place in the portable code.  This would avoid us having to set the
# theme / properties in a different place for each frontend.

import string
import logging
import threading

from miro import app
from miro import startup
from miro import threadcheck

def load_frontend(globals_, locals_, frontend):
    try:
        _temp = __import__(frontend, globals_, locals_, ['application'], -1)
        return _temp.application
    except ImportError, ie:
        # this is goofy, but to quell messages that happen when
        # trying to find which package the frontend is in
        if "No module" not in str(ie):
            print "ImportError on %s: %s" % (frontend, ie)
        return None

def run_application(frontend, props_to_set, theme):
    startup.initialize(theme)
    set_properties(props_to_set)

    goodchars = string.letters + "."
    for c in frontend:
        if c not in goodchars:
            raise ValueError("Unknown frontend: %s" % frontend)

    attempts = [
        "miro.plat.frontends.%s" % frontend,
        "miro.frontends.%s" % frontend,
        "%s" % frontend
        ]
    
    application = None
    for att in attempts:
        application = load_frontend(globals(), locals(), att)
        if application is not None:
            break
    else:
        raise ValueError("Cannot load frontend: %s" % frontend)
    threadcheck.set_ui_thread(threading.currentThread())
    application.run_application()

def set_properties(props):
    """Sets a bunch of command-line specified properites.

    :param props: a list of pref/value tuples
    """
    for pref, val in props:
        logging.info("Setting preference: %s -> %s", pref.alias, val)
        app.config.set(pref, val)

