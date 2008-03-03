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


"""Functions to handle moving/deleting files, especially on windows where file
locking semantics can cause problems.
"""

import logging
import os
import shutil

from miro import eventloop

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

class DeletesInProgressTracker(set):
    def __init__(self):
        self.set = set()
    def normalize(self, path):
        return os.path.abspath(os.path.normcase(path))
    def add(self, path):
        self.set.add(self.normalize(path))
    def discard(self, path):
        self.set.discard(self.normalize(path))
    def __contains__(self, path):
        return self.normalize(path) in self.set

deletes_in_progress = DeletesInProgressTracker()

def delete(path, retry_after=10, retry_for=60):
    """Try to delete a file or directory.  If this fails because the file is
    open, we retry deleting the file every so often This probably only makes a
    difference on Windows.
    """

    try:
        if os.path.isfile(path):
            os.remove (path)
        elif os.path.isdir(path):
            shutil.rmtree (path)
    except EnvironmentError, e:
        logging.warn("Error deleting %s", path)
        if retry_for > 0 and e.errno == 13:
            # permission denied, assume this means it's open by another
            # process on windows.
            deletes_in_progress.add(path)
            logging.info('Retrying delete')
            eventloop.addTimeout(retry_after, delete, 
                    "Delete File Retry", args=(path, retry_after, 
                        retry_for - retry_after))
    else:
        deletes_in_progress.discard(path)

def miro_listdir(directory):
    """Directory listing that's safe and convenient for finding new videos in
    a directory.

    Returns the tuple (files, directories) where both elements are a list of
    absolute pathnames.  OSErrors are silently ignored.  Hidden files aren't
    returned.  Pathnames are run through os.path.normcase.
    """

    files = []
    directories = []
    directory = os.path.abspath(os.path.normcase(directory))
    if directory in deletes_in_progress:
        return
    try:
        listing = os.listdir(directory)
    except OSError:
        return [], []
    for name in listing:
        if name[0] == '.' or name.lower() == 'thumbs.db':
            # thumbs.db is a windows file that speeds up thumbnails.  We know
            # it's not a movie file.
            continue
        path = os.path.join(directory, os.path.normcase(name))
        if path in deletes_in_progress:
            continue
        try:
            if os.path.isdir(path):
                directories.append(path)
            else:
                files.append(path)
        except OSError:
            pass
    return files, directories

# FIXME -- implement this
def miro_allfiles(d):
    return []
