# Miro - an RSS based video player application
# Copyright (C) 2005-2007 Participatory Culture Foundation
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


"""Functions to handle migrating the movies directory."""

import logging
import os
import shutil

import eventloop

def migrate_file(source, dest, callback, retry_after=10, retry_for=60):
    """Try to migrate a file, if this works, callback is called.  If we fail
    because the file is open, we retry migrating the file every so often (by
    default every 10 seconds, stopping after 60 seconds).  This probably only
    makes a difference on Windows.
    """

    try:
        shutil.move(source, dest)
    except EnvironmentError, e:
        logging.warn("Error migrating %s to %s (Error: %s)", source, dest, e)
        try:
            os.remove(dest)
        except EnvironmentError:
            pass
        if retry_for > 0:
            if e.errno == 13:
                # permission denied, assume this means it's open by another
                # process on windows.
                logging.info('Retrying migration')
                eventloop.addTimeout(retry_after, migrate_file, 
                        "Migrate File Retry", args=(source, dest, callback,
                            retry_after, retry_for - retry_after))
    except TypeError, e:
        logging.warn ("Type error migrating %s (%s) to %s (%s) (Error %s)",
                source, type(source), dest, type(dest), e)
        raise
    else:
        callback()
