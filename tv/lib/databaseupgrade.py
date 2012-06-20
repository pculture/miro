# -*- coding: utf-8 -*-
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

"""Responsible for upgrading old versions of the database.

.. Note::

    For really old versions before the ``schema.py`` module, see
    ``olddatabaseupgrade.py``.
"""

from urlparse import urlparse
import datetime
import itertools
import os
import re
import logging
import shutil
import time
import urllib

from miro.gtcache import gettext as _
from miro import schema
from miro import util
import types
from miro import app
from miro import dbupgradeprogress
from miro import prefs

# looks nicer as a return value
NO_CHANGES = set()

class DatabaseTooNewError(StandardError):
    """Error that we raise when we see a database that is newer than
    the version that we can update too.
    """
    pass

def remove_column(cursor, table, column_names):
    """Remove a column from a SQLITE table.  This was added for
    upgrade88, but it's probably useful for other ones as well.

    :param table: the table to remove the columns from
    :param column_names: list of columns to remove
    """
    alter_table_columns(cursor, table, column_names, {})

def rename_column(cursor, table, from_column, to_column, new_type=None):
    """Renames a column in a SQLITE table.

    .. Note::

       This does **NOT** handle renaming the column in an index.

       If you're going to rename columns that are involved in indexes,
       you'll need to add that feature.

    .. Note::

       Don't rename the id column--that would be bad.

    :param table: the table to remove the columns from
    :param from_column: the old name
    :param to_column: the new name
    :param new_type: new type for the column (or None to keep the old one)
    """
    if new_type is None:
        new_types = {}
    else:
        new_types = {to_column: new_type}
    alter_table_columns(cursor, table, [], {from_column: to_column}, new_types)

def alter_table_columns(cursor, table, delete_columns, rename_columns,
                        new_types=None):
    """Rename/drop multiple columns at once

    .. Note::

       This does **NOT** handle renaming the column in an index.

       If you're going to rename columns that are involved in indexes,
       you'll need to add that feature.

    .. Note::

       Don't rename the id column--that would be bad.

    :param table: the table to remove the columns from
    :param delete_columns: list of columns to delete
    :param rename_columns: dict mapping old column names to new column names
    :param new_types: dict mapping new column names to their new types
    """
    if new_types is None:
        new_types = {}
    cursor.execute("PRAGMA table_info('%s')" % table)
    old_columns = []
    new_columns = []
    columns_with_type = []
    for column_info in cursor.fetchall():
        column = column_info[1]
        col_type = column_info[2]
        if column in delete_columns:
            continue
        old_columns.append(column)
        if column in rename_columns:
            column = rename_columns[column]
        if column in new_types:
            col_type = new_types[column]
        new_columns.append(column)
        if column == 'id':
            col_type += ' PRIMARY KEY'
        columns_with_type.append("%s %s" % (column, col_type))

    # Note: This does not fix indexes that use the old column name.
    cursor.execute("PRAGMA index_list('%s')" % table)
    index_sql = []
    for index_info in cursor.fetchall():
        name = index_info[1]
        cursor.execute("SELECT sql FROM sqlite_master "
                       "WHERE name=? and type='index'", (name,))
        index_sql.append(cursor.fetchone()[0])

    cursor.execute("ALTER TABLE %s RENAME TO old_%s" % (table, table))
    cursor.execute("CREATE TABLE %s (%s)" %
                   (table, ', '.join(columns_with_type)))
    cursor.execute("INSERT INTO %s(%s) SELECT %s FROM old_%s" %
                   (table, ', '.join(new_columns), ', '.join(old_columns), table))
    cursor.execute("DROP TABLE old_%s" % table)
    for sql in index_sql:
        cursor.execute(sql)

def get_object_tables(cursor):
    """Returns a list of tables that store ``DDBObject`` subclasses.
    """
    cursor.execute("SELECT name FROM sqlite_master "
            "WHERE type='table' AND name != 'dtv_variables' AND "
            "name NOT LIKE 'sqlite%'")
    return [row[0] for row in cursor]

def get_next_id(cursor):
    """Calculate the next id to assign to new rows.

    This will be 1 higher than the max id for all the tables in the
    DB.
    """
    max_id = 0
    for table in get_object_tables(cursor):
        cursor.execute("SELECT MAX(id) from %s" % table)
        max_id = max(max_id, cursor.fetchone()[0])
    return max_id + 1

_upgrade_overide = {}
def get_upgrade_func(version):
    if version in _upgrade_overide:
        return _upgrade_overide[version]
    else:
        return globals()['upgrade%d' % version]

def new_style_upgrade(cursor, saved_version, upgrade_to):
    """Upgrade a database using new-style upgrade functions.

    This method replaces the upgrade() method.  However, we still need
    to keep around upgrade() to upgrade old databases.  We switched
    upgrade styles at version 80.

    This method will call upgradeX for each number X between
    saved_version and upgrade_to.  cursor should be a SQLite database
    cursor that will be passed to each upgrade function.  For example,
    if save_version is 2 and upgrade_to is 4, this method is
    equivelant to::

        upgrade3(cursor)
        upgrade4(cursor)
    """

    if saved_version > upgrade_to:
        msg = ("Database was created by a newer version of Miro "
               "(db version is %s)" % saved_version)
        raise DatabaseTooNewError(msg)

    dbupgradeprogress.new_style_progress(saved_version, saved_version,
                                         upgrade_to)
    for version in xrange(saved_version + 1, upgrade_to + 1):
        if util.chatter:
            logging.info("upgrading database to version %s", version)
        cursor.execute("BEGIN TRANSACTION")
        get_upgrade_func(version)(cursor)
        cursor.execute("COMMIT TRANSACTION")
        dbupgradeprogress.new_style_progress(saved_version, version,
                                             upgrade_to)

def upgrade(savedObjects, saveVersion, upgradeTo=None):
    """Upgrade a list of SavableObjects that were saved using an old
    version of the database schema.

    This method will call upgradeX for each number X between
    saveVersion and upgradeTo.  For example, if saveVersion is 2 and
    upgradeTo is 4, this method is equivelant to::

        upgrade3(savedObjects)
        upgrade4(savedObjects)

    By default, upgradeTo will be the VERSION variable in schema.
    """
    changed = set()

    if upgradeTo is None:
        upgradeTo = schema.VERSION

    if saveVersion > upgradeTo:
        msg = ("Database was created by a newer version of Miro "
               "(db version is %s)" % saveVersion)
        raise DatabaseTooNewError(msg)

    startSaveVersion = saveVersion
    dbupgradeprogress.old_style_progress(startSaveVersion, startSaveVersion,
                                         upgradeTo)
    while saveVersion < upgradeTo:
        if util.chatter:
            print "upgrading database to version %s" % (saveVersion + 1)
        upgradeFunc = get_upgrade_func(saveVersion + 1)
        thisChanged = upgradeFunc(savedObjects)
        if thisChanged is None or changed is None:
            changed = None
        else:
            changed.update (thisChanged)
        saveVersion += 1
        dbupgradeprogress.old_style_progress(startSaveVersion, saveVersion,
                                             upgradeTo)
    return changed

def upgrade2(objectList):
    """Add a dlerType variable to all RemoteDownloader objects."""
    for o in objectList:
        if o.classString == 'remote-downloader':
            # many of our old attributes are now stored in status
            o.savedData['status'] = {}
            for key in ('startTime', 'endTime', 'filename', 'state',
                    'currentSize', 'totalSize', 'reasonFailed'):
                o.savedData['status'][key] = o.savedData[key]
                del o.savedData[key]
            # force the download daemon to create a new downloader object.
            o.savedData['dlid'] = 'noid'

def upgrade3(objectList):
    """Add the expireTime variable to FeedImpl objects."""
    for o in objectList:
        if o.classString == 'feed':
            feedImpl = o.savedData['actualFeed']
            if feedImpl is not None:
                feedImpl.savedData['expireTime'] = None

def upgrade4(objectList):
    """Add iconCache variables to all Item objects."""
    for o in objectList:
        if o.classString in ['item', 'file-item', 'feed']:
            o.savedData['iconCache'] = None

def upgrade5(objectList):
    """Upgrade metainfo from old BitTorrent format to BitTornado format"""
    for o in objectList:
        if o.classString == 'remote-downloader':
            if o.savedData['status'].has_key('metainfo'):
                o.savedData['status']['metainfo'] = None
                o.savedData['status']['infohash'] = None

def upgrade6(objectList):
    """Add downloadedTime to items."""
    for o in objectList:
        if o.classString in ('item', 'file-item'):
            o.savedData['downloadedTime'] = None

def upgrade7(objectList):
    """Add the initialUpdate variable to FeedImpl objects."""
    for o in objectList:
        if o.classString == 'feed':
            feedImpl = o.savedData['actualFeed']
            if feedImpl is not None:
                feedImpl.savedData['initialUpdate'] = False

def upgrade8(objectList):
    """Have items point to feed_id instead of feed."""
    for o in objectList:
        if o.classString in ('item', 'file-item'):
            o.savedData['feed_id'] = o.savedData['feed'].savedData['id']

def upgrade9(objectList):
    """Added the deleted field to file items"""
    for o in objectList:
        if o.classString == 'file-item':
            o.savedData['deleted'] = False

def upgrade10(objectList):
    """Add a watchedTime attribute to items.  Since we don't know when
    that was, we use the downloaded time which matches with our old
    behaviour.
    """
    import datetime
    changed = set()
    for o in objectList:
        if o.classString in ('item', 'file-item'):
            if o.savedData['seen']:
                o.savedData['watchedTime'] = o.savedData['downloadedTime']
            else:
                o.savedData['watchedTime'] = None
            changed.add(o)
    return changed

def upgrade11(objectList):
    """We dropped the loadedThisSession field from ChannelGuide.  No
    need to change anything for this."""
    return set()

def upgrade12(objectList):
    from miro import filetypes
    from datetime import datetime
    changed = set()
    for o in objectList:
        if o.classString in ('item', 'file-item'):
            if not o.savedData.has_key('releaseDateObj'):
                try:
                    enclosures = o.savedData['entry'].enclosures
                    for enc in enclosures:
                        if filetypes.is_video_enclosure(enc):
                            enclosure = enc
                            break
                    o.savedData['releaseDateObj'] = datetime(*enclosure.updated_parsed[0:7])
                except StandardError:
                    try:
                        o.savedData['releaseDateObj'] = datetime(*o.savedData['entry'].updated_parsed[0:7])
                    except StandardError:
                        o.savedData['releaseDateObj'] = datetime.min
                changed.add(o)
    return changed

def upgrade13(objectList):
    """Add an isContainerItem field.  Computing this requires reading
    through files and we need to do this check anyway in onRestore, in
    case it has only been half done."""
    changed = set()
    todelete = []
    for i in xrange(len(objectList) - 1, -1, -1):
        o = objectList[i]
        if o.classString in ('item', 'file-item'):
            if o.savedData['feed_id'] == None:
                del objectList[i]
            else:
                o.savedData['isContainerItem'] = None
                o.savedData['parent_id'] = None
                o.savedData['videoFilename'] = ""
            changed.add(o)
    return changed

def upgrade14(objectList):
    """Add default and url fields to channel guide."""
    changed = set()
    todelete = []
    for o in objectList:
        if o.classString == 'channel-guide':
            o.savedData['url'] = None
            changed.add(o)
    return changed

def upgrade15(objectList):
    """In the unlikely event that someone has a playlist around,
    change items to item_ids."""
    changed = set()
    for o in objectList:
        if o.classString == 'playlist':
            o.savedData['item_ids'] = o.savedData['items']
            changed.add(o)
    return changed

def upgrade16(objectList):
    changed = set()
    for o in objectList:
        if o.classString == 'file-item':
            o.savedData['shortFilename'] = None
            changed.add(o)
    return changed

def upgrade17(objectList):
    """Add folder_id attributes to Feed and SavedPlaylist.  Add
    item_ids attribute to PlaylistFolder.
    """
    changed = set()
    for o in objectList:
        if o.classString in ('feed', 'playlist'):
            o.savedData['folder_id'] = None
            changed.add(o)
        elif o.classString == 'playlist-folder':
            o.savedData['item_ids'] = []
            changed.add(o)
    return changed

def upgrade18(objectList):
    """Add shortReasonFailed to RemoteDownloader status dicts. """
    changed = set()
    for o in objectList:
        if o.classString == 'remote-downloader':
            o.savedData['status']['shortReasonFailed'] = \
                    o.savedData['status']['reasonFailed']
            changed.add(o)
    return changed

def upgrade19(objectList):
    """Add origURL to RemoteDownloaders"""
    changed = set()
    for o in objectList:
        if o.classString == 'remote-downloader':
            o.savedData['origURL'] = o.savedData['url']
            changed.add(o)
    return changed

def upgrade20(objectList):
    """Add redirectedURL to Guides"""
    changed = set()
    for o in objectList:
        if o.classString == 'channel-guide':
            o.savedData['redirectedURL'] = None
            # set cachedGuideBody to None, to force us to update redirectedURL
            o.savedData['cachedGuideBody'] = None
            changed.add(o)
    return changed

def upgrade21(objectList):
    """Add searchTerm to Feeds"""
    changed = set()
    for o in objectList:
        if o.classString == 'feed':
            o.savedData['searchTerm'] = None
            changed.add(o)
    return changed

def upgrade22(objectList):
    """Add userTitle to Feeds"""
    changed = set()
    for o in objectList:
        if o.classString == 'feed':
            o.savedData['userTitle'] = None
            changed.add(o)
    return changed

def upgrade23(objectList):
    """Remove container items from playlists."""
    changed = set()
    toFilter = set()
    playlists = set()
    for o in objectList:
        if o.classString in ('playlist', 'playlist-folder'):
            playlists.add(o)
        elif (o.classString in ('item', 'file-item') and
                o.savedData['isContainerItem']):
            toFilter.add(o.savedData['id'])
    for p in playlists:
        filtered = [id for id in p.savedData['item_ids'] if id not in toFilter]
        if len(filtered) != len(p.savedData['item_ids']):
            changed.add(p)
            p.savedData['item_ids'] = filtered
    return changed

def upgrade24(objectList):
    """Upgrade metainfo back to BitTorrent format."""
    for o in objectList:
        if o.classString == 'remote-downloader':
            if o.savedData['status'].has_key('metainfo'):
                o.savedData['status']['metainfo'] = None
                o.savedData['status']['infohash'] = None

def upgrade25(objectList):
    """Remove container items from playlists."""
    from datetime import datetime

    changed = set()
    startfroms = {}
    for o in objectList:
        if o.classString == 'feed':
            startfroms[o.savedData['id']] = o.savedData['actualFeed'].savedData['startfrom']
    for o in objectList:
        if o.classString == 'item':
            pubDate = o.savedData['releaseDateObj']
            feed_id = o.savedData['feed_id']
            if feed_id is not None and startfroms.has_key(feed_id):
                o.savedData['eligibleForAutoDownload'] = pubDate != datetime.max and pubDate >= startfroms[feed_id]
            else:
                o.savedData['eligibleForAutoDownload'] = False
            changed.add(o)
        if o.classString == 'file-item':
            o.savedData['eligibleForAutoDownload'] = True
            changed.add(o)
    return changed

def upgrade26(objectList):
    changed = set()
    for o in objectList:
        if o.classString == 'feed':
            feedImpl = o.savedData['actualFeed']
            for field in ('autoDownloadable', 'getEverything', 'maxNew',
                          'fallBehind', 'expire', 'expireTime'):
                o.savedData[field] = feedImpl.savedData[field]
            changed.add(o)
    return changed

def upgrade27(objectList):
    """We dropped the sawIntro field from ChannelGuide.  No need to
    change anything for this."""
    return set()

def upgrade28(objectList):
    from miro import filetypes
    objectList.sort(key=lambda o: o.savedData['id'])
    changed = set()
    items = set()
    removed = set()

    def get_first_video_enclosure(entry):
        """Find the first video enclosure in a feedparser entry.
        Returns the enclosure, or None if no video enclosure is found.
        """
        try:
            enclosures = entry.enclosures
        except (KeyError, AttributeError):
            return None
        for enclosure in enclosures:
            if filetypes.is_video_enclosure(enclosure):
                return enclosure
        return None

    for i in xrange(len(objectList) - 1, -1, -1):
        o = objectList[i]
        if o.classString == 'item':
            entry = o.savedData['entry']
            videoEnc = get_first_video_enclosure(entry)
            if videoEnc is not None:
                entryURL = videoEnc.get('url')
            else:
                entryURL = None
            title = entry.get("title")
            feed_id = o.savedData['feed_id']
            if title is not None or entryURL is not None:
                if (feed_id, entryURL, title) in items:
                    removed.add(o.savedData['id'])
                    changed.add(o)
                    del objectList[i]
                else:
                    items.add((feed_id, entryURL, title))

    for i in xrange(len(objectList) - 1, -1, -1):
        o = objectList[i]
        if o.classString == 'file-item':
            if o.savedData['parent_id'] in removed:
                changed.add(o)
                del objectList[i]
    return changed

def upgrade29(objectList):
    changed = set()
    for o in objectList:
        if o.classString == 'guide':
            o.savedData['default'] = (o.savedData['url'] is None)
            changed.add(o)
    return changed

def upgrade30(objectList):
    changed = set()
    for o in objectList:
        if o.classString == 'guide':
            if o.savedData['default']:
                o.savedData['url'] = None
                changed.add(o)
    return changed

def upgrade31(objectList):
    changed = set()
    for o in objectList:
        if o.classString == 'remote-downloader':
            o.savedData['status']['retryTime'] = None
            o.savedData['status']['retryCount'] = -1
            changed.add(o)
    return changed

def upgrade32(objectList):
    changed = set()
    for o in objectList:
        if o.classString == 'remote-downloader':
            o.savedData['channelName'] = None
            changed.add(o)
    return changed

def upgrade33(objectList):
    changed = set()
    for o in objectList:
        if o.classString == 'remote-downloader':
            o.savedData['duration'] = None
            changed.add(o)
    return changed

def upgrade34(objectList):
    changed = set()
    for o in objectList:
        if o.classString in ('item', 'file-item'):
            o.savedData['duration'] = None
            changed.add(o)
    return changed

def upgrade35(objectList):
    changed = set()
    for o in objectList:
        if o.classString in ('item', 'file-item'):
            if hasattr(o.savedData,'entry'):
                entry = o.savedData['entry']
                if ((entry.has_key('title')
                     and type(entry.title) != types.UnicodeType)):
                    entry.title = entry.title.decode('utf-8', 'replace')
                    changed.add(o)
    return changed

def upgrade36(objectList):
    changed = set()
    for o in objectList:
        if o.classString == 'remote-downloader':
            o.savedData['manualUpload'] = False
            changed.add(o)
    return changed

def upgrade37(objectList):
    changed = set()
    removed = set()
    id = 0
    for o in objectList:
        if o.classString == 'feed':
            feedImpl = o.savedData['actualFeed']
            if feedImpl.classString == 'directory-feed-impl':
                id = o.savedData['id']
                break

    if id == 0:
        return changed

    for i in xrange(len(objectList) - 1, -1, -1):
        o = objectList[i]
        if o.classString == 'file-item' and o.savedData['feed_id'] == id:
            removed.add(o.savedData['id'])
            changed.add(o)
            del objectList[i]

    for i in xrange(len(objectList) - 1, -1, -1):
        o = objectList[i]
        if o.classString == 'file-item':
            if o.savedData['parent_id'] in removed:
                changed.add(o)
                del objectList[i]
    return changed

def upgrade38(objectList):
    changed = set()
    for o in objectList:
        if o.classString == 'remote-downloader':
            try:
                if o.savedData['status']['channelName']:
                    o.savedData['status']['channelName'] = o.savedData['status']['channelName'].translate({ ord('/')  : u'-',
                                                                                                            ord('\\') : u'-',
                                                                                                            ord(':')  : u'-' })
                    changed.add(o)
            except StandardError:
                pass
    return changed

def upgrade39(objectList):
    changed = set()
    removed = set()
    id = 0
    for i in xrange(len(objectList) - 1, -1, -1):
        o = objectList[i]
        if o.classString in ('item', 'file-item'):
            changed.add(o)
            if o.savedData['parent_id']:
                del objectList[i]
            else:
                o.savedData['isVideo'] = False
                o.savedData['videoFilename'] = ""
                o.savedData['isContainerItem'] = None
                if o.classString == 'file-item':
                    o.savedData['offsetPath'] = None
    return changed

def upgrade40(objectList):
    changed = set()
    for o in objectList:
        if o.classString in ('item', 'file-item'):
            o.savedData['resumeTime'] = 0
            changed.add(o)
    return changed

# Turns all strings in data structure to unicode, used by upgrade 41
# and 47
def unicodify(d):
    from miro.feedparser import FeedParserDict
    from types import StringType
    if isinstance(d, FeedParserDict):
        for key in d.keys():
            try:
                d[key] = unicodify(d[key])
            except KeyError:
                # Feedparser dicts sometime return names in keys()
                # that can't actually be used in keys.  I guess the
                # best thing to do here is ignore it -- Ben
                pass
    elif isinstance(d, dict):
        for key in d.keys():
            d[key] = unicodify(d[key])
    elif isinstance(d, list):
        for key in range(len(d)):
            d[key] = unicodify(d[key])
    elif type(d) == StringType:
        d = d.decode('ascii','replace')
    return d

def upgrade41(objectList):
    from miro.plat.utils import PlatformFilenameType
    # This is where John Lennon's ghost sings "Binary Fields Forever"
    if PlatformFilenameType == str:
        binaryFields = ['filename', 'videoFilename', 'shortFilename',
                        'offsetPath', 'initialHTML', 'status', 'channelName']
        icStrings = ['etag', 'modified', 'url']
        icBinary = ['filename']
        statusBinary = ['channelName', 'shortFilename', 'filename', 'metainfo']
    else:
        binaryFields = ['initialHTML', 'status']
        icStrings = ['etag', 'modified', 'url', 'filename']
        icBinary = []
        statusBinary = ['metainfo']

    changed = set()
    for o in objectList:
        o.savedData = unicodify(o.savedData)
        for field in o.savedData:
            if field not in binaryFields:
                o.savedData[field] = unicodify(o.savedData[field])

                # These get skipped because they're a level lower
                if field == 'actualFeed':
                    o.savedData[field].__dict__ = unicodify(o.savedData[field].__dict__)
                elif (field == 'iconCache' and
                      o.savedData['iconCache'] is not None):
                    for icfield in icStrings:
                        o.savedData['iconCache'].savedData[icfield] = unicodify(o.savedData['iconCache'].savedData[icfield])
                    for icfield in icBinary:
                        if (type(o.savedData['iconCache'].savedData[icfield]) == unicode):
                            o.savedData['iconCache'].savedData[icfield] = o.savedData['iconCache'].savedData[icfield].encode('ascii','replace')

            else:
                if field == 'status':
                    for subfield in o.savedData['status']:
                        if (type(o.savedData[field][subfield]) == unicode
                                and subfield in statusBinary):
                            o.savedData[field][subfield] = o.savedData[field][subfield].encode('ascii',
                                                                 'replace')
                        elif (type(o.savedData[field][subfield]) == str
                                and subfield not in statusBinary):
                            o.savedData[field][subfield] = o.savedData[field][subfield].decode('ascii',
                                                                 'replace')
                elif type(o.savedData[field]) == unicode:
                    o.savedData[field] = o.savedData[field].encode('ascii', 'replace')
        if o.classString == 'channel-guide':
            del o.savedData['cachedGuideBody']
        changed.add(o)
    return changed

def upgrade42(objectList):
    changed = set()
    for o in objectList:
        if o.classString in ('item', 'file-item'):
            o.savedData['screenshot'] = None
            changed.add(o)
    return changed

def upgrade43(objectList):
    changed = set()
    removed = set()
    id = 0
    for i in xrange(len(objectList) - 1, -1, -1):
        o = objectList[i]
        if o.classString == 'feed':
            feedImpl = o.savedData['actualFeed']
            if feedImpl.classString == 'manual-feed-impl':
                id = o.savedData['id']
                break

    for i in xrange(len(objectList) - 1, -1, -1):
        o = objectList[i]
        if ((o.classString == 'file-item'
             and o.savedData['feed_id'] == id
             and o.savedData['deleted'] == True)):
            removed.add(o.savedData['id'])
            changed.add(o)
            del objectList[i]

    for i in xrange(len(objectList) - 1, -1, -1):
        o = objectList[i]
        if o.classString == 'file-item':
            if o.savedData['parent_id'] in removed:
                changed.add(o)
                del objectList[i]
    return changed

def upgrade44(objectList):
    changed = set()
    for o in objectList:
        if (('iconCache' in o.savedData
             and o.savedData['iconCache'] is not None)):
            iconCache = o.savedData['iconCache']
            iconCache.savedData['resized_filenames'] = {}
            changed.add(o)
    return changed

def upgrade45(objectList):
    """Dropped the ChannelGuide.redirected URL attribute.  Just need
    to bump the db version number."""
    return set()

def upgrade46(objectList):
    """fastResumeData should be str, not unicode."""
    changed = set()
    for o in objectList:
        if o.classString == 'remote-downloader':
            try:
                if type (o.savedData['status']['fastResumeData']) == unicode:
                    o.savedData['status']['fastResumeData'] = o.savedData['status']['fastResumeData'].encode('ascii','replace')
                changed.add(o)
            except StandardError:
                pass
    return changed

def upgrade47(objectList):
    """Parsed item entries must be unicode"""
    changed = set()
    for o in objectList:
        if o.classString == 'item':
            o.savedData['entry'] = unicodify(o.savedData['entry'])
            changed.add(o)
    return changed

def upgrade48(objectList):
    changed = set()
    removed = set()
    ids = set()
    for o in objectList:
        if o.classString == 'feed':
            feedImpl = o.savedData['actualFeed']
            if feedImpl.classString == 'directory-watch-feed-impl':
                ids.add (o.savedData['id'])

    if len(ids) == 0:
        return changed

    for i in xrange(len(objectList) - 1, -1, -1):
        o = objectList [i]
        if o.classString == 'file-item' and o.savedData['feed_id'] in ids:
            removed.add(o.savedData['id'])
            changed.add(o)
            del objectList[i]

    for i in xrange(len(objectList) - 1, -1, -1):
        o = objectList[i]
        if o.classString == 'file-item':
            if o.savedData['parent_id'] in removed:
                changed.add(o)
                del objectList[i]
    return changed

upgrade49 = upgrade42

def upgrade50(objectList):
    """Parsed item entries must be unicode"""
    changed = set()
    for o in objectList:
        if o.classString in ('item', 'file-item'):
            if ((o.savedData['videoFilename']
                 and o.savedData['videoFilename'][0] == '\\')):
                o.savedData['videoFilename'] = o.savedData['videoFilename'][1:]
                changed.add(o)
    return changed

def upgrade51(objectList):
    """Added title field to channel guides"""
    changed = set()
    for o in objectList:
        if o.classString in ('channel-guide'):
            o.savedData['title'] = None
            changed.add(o)
    return changed

def upgrade52(objectList):
    from miro import filetypes
    changed = set()
    removed = set()
    search_id = 0
    downloads_id = 0

    def getVideoInfo(o):
        """Find the first video enclosure in a feedparser entry.
        Returns the enclosure, or None if no video enclosure is found.
        """
        entry = o.savedData['entry']
        enc = None
        try:
            enclosures = entry.enclosures
        except (KeyError, AttributeError):
            pass
        else:
            for enclosure in enclosures:
                if filetypes.is_video_enclosure(enclosure):
                    enc = enclosure
        if enc is not None:
            url = enc.get('url')
        else:
            url = None
        id = entry.get('id')
        id = entry.get('guid', id)
        title = entry.get('title')
        return (url, id, title)

    for o in objectList:
        if o.classString == 'feed':
            feedImpl = o.savedData['actualFeed']
            if feedImpl.classString == 'search-feed-impl':
                search_id = o.savedData['id']
            elif feedImpl.classString == 'search-downloads-feed-impl':
                downloads_id = o.savedData['id']

    items_by_idURL = {}
    items_by_titleURL = {}
    if search_id != 0:
        for o in objectList:
            if o.classString == 'item':
                if o.savedData['feed_id'] == search_id:
                    (url, id, title) = getVideoInfo(o)
                    if url and id:
                        items_by_idURL[(id, url)] = o
                    if url and title:
                        items_by_titleURL[(title, url)] = o
    if downloads_id != 0:
        for i in xrange(len(objectList) - 1, -1, -1):
            o = objectList[i]
            if o.classString == 'item':
                if o.savedData['feed_id'] == downloads_id:
                    remove = False
                    (url, id, title) = getVideoInfo(o)
                    if url and id:
                        if items_by_idURL.has_key((id, url)):
                            remove = True
                        else:
                            items_by_idURL[(id, url)] = o
                    if url and title:
                        if items_by_titleURL.has_key((title, url)):
                            remove = True
                        else:
                            items_by_titleURL[(title, url)] = o
                    if remove:
                        removed.add(o.savedData['id'])
                        changed.add(o)
                        del objectList[i]

        for i in xrange(len(objectList) - 1, -1, -1):
            o = objectList [i]
            if o.classString == 'file-item':
                if o.savedData['parent_id'] in removed:
                    changed.add(o)
                    del objectList[i]
    return changed

def upgrade53(objectList):
    """Added favicon and icon cache field to channel guides"""
    changed = set()
    for o in objectList:
        if o.classString in ('channel-guide'):
            o.savedData['favicon'] = None
            o.savedData['iconCache'] = None
            o.savedData['updated_url'] = o.savedData['url']
            changed.add(o)
    return changed

def upgrade54(objectList):
    changed = set()
    if app.config.get(prefs.APP_PLATFORM) != "windows":
        return changed
    for o in objectList:
        if o.classString in ('item', 'file-item'):
            o.savedData['screenshot'] = None
            o.savedData['duration'] = None
            changed.add(o)
    return changed

def upgrade55(objectList):
    """Add resized_screenshots attribute. """
    changed = set()
    for o in objectList:
        if o.classString in ('item', 'file-item'):
            o.savedData['resized_screenshots'] = {}
            changed.add(o)
    return changed

def upgrade56(objectList):
    """Added firstTime field to channel guides"""
    changed = set()
    for o in objectList:
        if o.classString in ('channel-guide'):
            o.savedData['firstTime'] = False
            changed.add(o)
    return changed

def upgrade57(objectList):
    """Added ThemeHistory"""
    changed = set()
    return changed


def upgrade58(objectList):
    """clear fastResumeData for libtorrent"""
    changed = set()
    for o in objectList:
        if o.classString == 'remote-downloader':
            try:
                o.savedData['status']['fastResumeData'] = None
                changed.add(o)
            except StandardError:
                pass
    return changed

def upgrade59(objectList):
    """
    We changed ThemeHistory to allow None in the pastTheme list.
    Since we're upgrading, we can assume that the default channels
    have been added, so we'll add None to that list manually.  We also
    require a URL for channel guides.  If it's None, eplace it with
    https://www.miroguide.com/.
    """
    changed = set()
    for o in objectList:
        if o.classString == 'channel-guide' and o.savedData['url'] is None:
            o.savedData['url'] = u'http://www.miroguide.com/'
            changed.add(o)
        elif o.classString == 'theme-history':
            if None not in o.savedData['pastThemes']:
                o.savedData['pastThemes'].append(None)
                changed.add(o)
    return changed

def upgrade60(objectList):
    """search feed impl is now a subclass of rss multi, so add the
    needed fields"""
    changed = set()
    for o in objectList:
        if o.classString == 'feed':
            feedImpl = o.savedData['actualFeed']
            if feedImpl.classString == 'search-feed-impl':
                feedImpl.savedData['etag'] = {}
                feedImpl.savedData['modified'] = {}
                changed.add(o)
    return changed

def upgrade61(objectList):
    """Add resized_screenshots attribute. """
    changed = set()
    for o in objectList:
        if o.classString in ('item', 'file-item'):
            o.savedData['channelTitle'] = None
            changed.add(o)
    return changed

def upgrade62(objectList):
    """Adding baseTitle to feedimpl."""
    changed = set()
    for o in objectList:
        if o.classString == 'feed':
            o.savedData['baseTitle'] = None
            changed.add(o)
    return changed

upgrade63 = upgrade37

def upgrade64(objectList):
    changed = set()
    for o in objectList:
        if o.classString == 'channel-guide':
            if o.savedData['url'] == app.config.get(prefs.CHANNEL_GUIDE_URL):
                allowedURLs = unicode(
                    app.config.get(prefs.CHANNEL_GUIDE_ALLOWED_URLS)).split()
                allowedURLs.append(app.config.get(
                        prefs.CHANNEL_GUIDE_FIRST_TIME_URL))
                o.savedData['allowedURLs'] = allowedURLs
            else:
                o.savedData['allowedURLs'] = []
            changed.add(o)
    return changed

def upgrade65(objectList):
    changed = set()
    for o in objectList:
        if o.classString == 'feed':
            o.savedData['maxOldItems'] = 30
            changed.add(o)
    return changed

def upgrade66(objectList):
    changed = set()
    for o in objectList:
        if o.classString in ('item', 'file-item'):
            o.savedData['title'] = u""
            changed.add(o)
    return changed

def upgrade67(objectList):
    """Add userTitle to Guides"""

    changed = set()
    for o in objectList:
        if o.classString == 'channel-guide':
            o.savedData['userTitle'] = None
            changed.add(o)
    return changed

def upgrade68(objectList):
    """
    Add the 'feed section' variable
    """
    changed = set()
    for o in objectList:
        if o.classString in ('feed', 'channel-folder'):
            o.savedData['section'] = u'video'
            changed.add(o)
    return changed

def upgrade69(objectList):
    """
    Added the WidgetsFrontendState
    """
    return NO_CHANGES

def upgrade70(objectList):
    """Added for the query item in the RSSMultiFeedImpl and
    SearchFeedImpl."""
    changed = set()
    for o in objectList:
        if o.classString == 'feed':
            feedImpl = o.savedData['actualFeed']
            if feedImpl.classString in ('search-feed-impl',
                                        'rss-multi-feed-impl'):
                feedImpl.savedData['query'] = u""
                changed.add(o)
    return changed

    return NO_CHANGES


def upgrade71(objectList):
    """
    Add the downloader_id attribute
    """
    # So this is a crazy upgrade, because we need to use a ton of
    # functions.  Rather than import a module, all of these were
    # copied from the source code from r8953 (2009-01-17).  Some
    # slight changes were made, mostly to drop some error checking.

    def fix_file_urls(url):
        """Fix file urls that start with file:// instead of file:///.
        Note: this breaks for file urls that include a hostname, but
        we never use those and it's not so clear what that would mean
        anyway--file urls is an ad-hoc spec as I can tell.
        """
        if url.startswith('file://'):
            if not url.startswith('file:///'):
                url = 'file:///%s' % url[len('file://'):]
            url = url.replace('\\', '/')
        return url

    def default_port(scheme):
        if scheme == 'https':
            return 443
        elif scheme == 'http':
            return 80
        elif scheme == 'rtsp':
            return 554
        elif scheme == 'file':
            return None
        return 80

    def parse_url(url, split_path=False):
        url = fix_file_urls(url)
        (scheme, host, path, params, query, fragment) = util.unicodify(list(urlparse(url)))
        # Filter invalid URLs with duplicated ports
        # (http://foo.bar:123:123/baz) which seem to be part of #441.
        if host.count(':') > 1:
            host = host[0:host.rfind(':')]

        if scheme == '' and util.chatter:
            logging.warn("%r has no scheme" % url)

        if ':' in host:
            host, port = host.split(':')
            try:
                port = int(port)
            except StandardError:
                logging.warn("invalid port for %r" % url)
                port = default_port(scheme)
        else:
            port = default_port(scheme)

        host = host.lower()
        scheme = scheme.lower()

        path = path.replace('|', ':')
        # Windows drive names are often specified as "C|\foo\bar"

        if path == '' or not path.startswith('/'):
            path = '/' + path
        elif re.match(r'/[a-zA-Z]:', path):
            # Fix "/C:/foo" paths
            path = path[1:]
        fullPath = path
        if split_path:
            return scheme, host, port, fullPath, params, query
        else:
            if params:
                fullPath += ';%s' % params
            if query:
                fullPath += '?%s' % query
            return scheme, host, port, fullPath

    UNSUPPORTED_MIMETYPES = ("video/3gpp", "video/vnd.rn-realvideo",
                             "video/x-ms-asf")
    VIDEO_EXTENSIONS = ['.mov', '.wmv', '.mp4', '.m4v', '.ogg', '.ogv',
                        '.anx', '.mpg', '.avi', '.flv', '.mpeg',
                        '.divx', '.xvid', '.rmvb', '.mkv', '.m2v', '.ogm']
    AUDIO_EXTENSIONS = ['.mp3', '.m4a', '.wma', '.mka']
    FEED_EXTENSIONS = ['.xml', '.rss', '.atom']
    def is_video_enclosure(enclosure):
        """
        Pass an enclosure dictionary to this method and it will return
        a boolean saying if the enclosure is a video or not.
        """
        return (_has_video_type(enclosure) or
                _has_video_extension(enclosure, 'url') or
                _has_video_extension(enclosure, 'href'))

    def _has_video_type(enclosure):
        return ('type' in enclosure and
                (enclosure['type'].startswith(u'video/') or
                 enclosure['type'].startswith(u'audio/') or
                 enclosure['type'] == u"application/ogg" or
                 enclosure['type'] == u"application/x-annodex" or
                 enclosure['type'] == u"application/x-bittorrent" or
                 enclosure['type'] == u"application/x-shockwave-flash") and
                (enclosure['type'] not in UNSUPPORTED_MIMETYPES))

    def is_allowed_filename(filename):
        """
        Pass a filename to this method and it will return a boolean
        saying if the filename represents video, audio or torrent.
        """
        return (is_video_filename(filename) or is_audio_filename(filename)
                or is_torrent_filename(filename))

    def is_video_filename(filename):
        """
        Pass a filename to this method and it will return a boolean
        saying if the filename represents a video file.
        """
        filename = filename.lower()
        for ext in VIDEO_EXTENSIONS:
            if filename.endswith(ext):
                return True
        return False

    def is_audio_filename(filename):
        """
        Pass a filename to this method and it will return a boolean
        saying if the filename represents an audio file.
        """
        filename = filename.lower()
        for ext in AUDIO_EXTENSIONS:
            if filename.endswith(ext):
                return True
        return False

    def is_torrent_filename(filename):
        """
        Pass a filename to this method and it will return a boolean
        saying if the filename represents a torrent file.
        """
        filename = filename.lower()
        return filename.endswith('.torrent')

    def _has_video_extension(enclosure, key):
        if key in enclosure:
            elems = parse_url(enclosure[key], split_path=True)
            return is_allowed_filename(elems[3])
        return False
    def get_first_video_enclosure(entry):
        """
        Find the first "best" video enclosure in a feedparser entry.
        Returns the enclosure, or None if no video enclosure is found.
        """
        try:
            enclosures = entry.enclosures
        except (KeyError, AttributeError):
            return None

        enclosures = [e for e in enclosures if is_video_enclosure(e)]
        if len(enclosures) == 0:
            return None

        enclosures.sort(cmp_enclosures)
        return enclosures[0]

    def _get_enclosure_size(enclosure):
        if 'filesize' in enclosure and enclosure['filesize'].isdigit():
            return int(enclosure['filesize'])
        else:
            return None

    def _get_enclosure_bitrate(enclosure):
        if 'bitrate' in enclosure and enclosure['bitrate'].isdigit():
            return int(enclosure['bitrate'])
        else:
            return None

    def cmp_enclosures(enclosure1, enclosure2):
        """
        Returns -1 if enclosure1 is preferred, 1 if enclosure2 is
        preferred, and zero if there is no preference between the two
        of them.
        """
        # media:content enclosures have an isDefault which we should
        # pick since it's the preference of the feed
        if enclosure1.get("isDefault"):
            return -1
        if enclosure2.get("isDefault"):
            return 1

        # let's try sorting by preference
        enclosure1_index = _get_enclosure_index(enclosure1)
        enclosure2_index = _get_enclosure_index(enclosure2)
        if enclosure1_index < enclosure2_index:
            return -1
        elif enclosure2_index < enclosure1_index:
            return 1

        # next, let's try sorting by bitrate..
        enclosure1_bitrate = _get_enclosure_bitrate(enclosure1)
        enclosure2_bitrate = _get_enclosure_bitrate(enclosure2)
        if enclosure1_bitrate > enclosure2_bitrate:
            return -1
        elif enclosure2_bitrate > enclosure1_bitrate:
            return 1

        # next, let's try sorting by filesize..
        enclosure1_size = _get_enclosure_size(enclosure1)
        enclosure2_size = _get_enclosure_size(enclosure2)
        if enclosure1_size > enclosure2_size:
            return -1
        elif enclosure2_size > enclosure1_size:
            return 1

        # at this point they're the same for all we care
        return 0

    def _get_enclosure_index(enclosure):
        try:
            return PREFERRED_TYPES.index(enclosure.get('type'))
        except ValueError:
            return None

    PREFERRED_TYPES = [
        'application/x-bittorrent',
        'application/ogg', 'video/ogg', 'audio/ogg',
        'video/mp4', 'video/quicktime', 'video/mpeg',
        'video/x-xvid', 'video/x-divx', 'video/x-wmv',
        'video/x-msmpeg', 'video/x-flv']


    def quote_unicode_url(url):
        """Quote international characters contained in a URL according
        to w3c, see: <http://www.w3.org/International/O-URL-code.html>
        """
        quotedChars = []
        for c in url.encode('utf8'):
            if ord(c) > 127:
                quotedChars.append(urllib.quote(c))
            else:
                quotedChars.append(c)
        return u''.join(quotedChars)

    # Now that that's all set, on to the actual upgrade code.

    changed = set()
    url_to_downloader_id = {}

    for o in objectList:
        if o.classString == 'remote-downloader':
            url_to_downloader_id[o.savedData['origURL']] = o.savedData['id']

    for o in objectList:
        if o.classString in ('item', 'file-item'):
            entry = o.savedData['entry']
            videoEnclosure = get_first_video_enclosure(entry)
            if videoEnclosure is not None and 'url' in videoEnclosure:
                url = quote_unicode_url(videoEnclosure['url'].replace('+', '%20'))
            else:
                url = None
            downloader_id = url_to_downloader_id.get(url)
            if downloader_id is None and hasattr(entry, 'enclosures'):
                # we didn't get a downloader id using
                # get_first_video_enclosure(), so try other enclosures.
                # We changed the way that function worked between
                # 1.2.8 and 2.0.
                for other_enclosure in entry.enclosures:
                    if 'url' in other_enclosure:
                        url = quote_unicode_url(other_enclosure['url'].replace('+', '%20'))
                        downloader_id = url_to_downloader_id.get(url)
                        if downloader_id is not None:
                            break
            o.savedData['downloader_id'] = downloader_id
            changed.add(o)

    return changed

def upgrade72(objectList):
    """We upgraded the database wrong in upgrade64, inadvertently
    adding a str to the allowedURLs list when it should be unicode.
    This converts that final str to unicode before the database sanity
    check catches us.
    """
    changed = set()
    for o in objectList:
        if o.classString == 'channel-guide':
            if o.savedData['allowedURLs'] and isinstance(
                o.savedData['allowedURLs'][-1], str):
                o.savedData['allowedURLs'][-1] = unicode(
                    o.savedData['allowedURLs'][-1])
                changed.add(o)
    return changed

def upgrade73(objectList):
    """We dropped the resized_filename attribute for icon cache
    objects."""
    return NO_CHANGES

def upgrade74(objectList):
    """We dropped the resized_screenshots attribute for Item
    objects."""
    return NO_CHANGES

def upgrade75(objectList):
    """Drop the entry attribute for items, replace it with a bunch
    individual attributes.
    """
    from datetime import datetime

    def fix_file_urls(url):
        """Fix file urls that start with file:// instead of file:///.
        Note: this breaks for file urls that include a hostname, but
        we never use those and it's not so clear what that would mean
        anyway--file urls is an ad-hoc spec as I can tell.
        """
        if url.startswith('file://'):
            if not url.startswith('file:///'):
                url = 'file:///%s' % url[len('file://'):]
            url = url.replace('\\', '/')
        return url

    def default_port(scheme):
        if scheme == 'https':
            return 443
        elif scheme == 'http':
            return 80
        elif scheme == 'rtsp':
            return 554
        elif scheme == 'file':
            return None
        return 80

    def parse_url(url, split_path=False):
        url = fix_file_urls(url)
        (scheme, host, path, params, query, fragment) = util.unicodify(list(urlparse(url)))
        # Filter invalid URLs with duplicated ports
        # (http://foo.bar:123:123/baz) which seem to be part of #441.
        if host.count(':') > 1:
            host = host[0:host.rfind(':')]

        if scheme == '' and util.chatter:
            logging.warn("%r has no scheme" % url)

        if ':' in host:
            host, port = host.split(':')
            try:
                port = int(port)
            except StandardError:
                logging.warn("invalid port for %r" % url)
                port = default_port(scheme)
        else:
            port = default_port(scheme)

        host = host.lower()
        scheme = scheme.lower()

        path = path.replace('|', ':')
        # Windows drive names are often specified as "C|\foo\bar"
        if path == '' or not path.startswith('/'):
            path = '/' + path
        elif re.match(r'/[a-zA-Z]:', path):
            # Fix "/C:/foo" paths
            path = path[1:]
        fullPath = path
        if split_path:
            return scheme, host, port, fullPath, params, query
        else:
            if params:
                fullPath += ';%s' % params
            if query:
                fullPath += '?%s' % query
            return scheme, host, port, fullPath

    UNSUPPORTED_MIMETYPES = ("video/3gpp", "video/vnd.rn-realvideo",
                             "video/x-ms-asf")
    VIDEO_EXTENSIONS = ['.mov', '.wmv', '.mp4', '.m4v', '.ogg', '.ogv',
                        '.anx', '.mpg', '.avi', '.flv', '.mpeg', '.divx',
                        '.xvid', '.rmvb', '.mkv', '.m2v', '.ogm']
    AUDIO_EXTENSIONS = ['.mp3', '.m4a', '.wma', '.mka']
    FEED_EXTENSIONS = ['.xml', '.rss', '.atom']
    def is_video_enclosure(enclosure):
        """Pass an enclosure dictionary to this method and it will
        return a boolean saying if the enclosure is a video or not.
        """
        return (_has_video_type(enclosure) or
                _has_video_extension(enclosure, 'url') or
                _has_video_extension(enclosure, 'href'))

    def _has_video_type(enclosure):
        return ('type' in enclosure and
                (enclosure['type'].startswith(u'video/') or
                 enclosure['type'].startswith(u'audio/') or
                 enclosure['type'] == u"application/ogg" or
                 enclosure['type'] == u"application/x-annodex" or
                 enclosure['type'] == u"application/x-bittorrent" or
                 enclosure['type'] == u"application/x-shockwave-flash") and
                (enclosure['type'] not in UNSUPPORTED_MIMETYPES))

    def is_allowed_filename(filename):
        """Pass a filename to this method and it will return a boolean
        saying if the filename represents video, audio or torrent.
        """
        return (is_video_filename(filename)
                or is_audio_filename(filename)
                or is_torrent_filename(filename))

    def is_video_filename(filename):
        """Pass a filename to this method and it will return a boolean
        saying if the filename represents a video file.
        """
        filename = filename.lower()
        for ext in VIDEO_EXTENSIONS:
            if filename.endswith(ext):
                return True
        return False

    def is_audio_filename(filename):
        """Pass a filename to this method and it will return a boolean
        saying if the filename represents an audio file.
        """
        filename = filename.lower()
        for ext in AUDIO_EXTENSIONS:
            if filename.endswith(ext):
                return True
        return False

    def is_torrent_filename(filename):
        """Pass a filename to this method and it will return a boolean
        saying if the filename represents a torrent file.
        """
        filename = filename.lower()
        return filename.endswith('.torrent')

    def _has_video_extension(enclosure, key):
        if key in enclosure:
            elems = parse_url(enclosure[key], split_path=True)
            return is_allowed_filename(elems[3])
        return False

    def get_first_video_enclosure(entry):
        """Find the first "best" video enclosure in a feedparser
        entry.  Returns the enclosure, or None if no video enclosure
        is found.
        """
        try:
            enclosures = entry.enclosures
        except (KeyError, AttributeError):
            return None

        enclosures = [e for e in enclosures if is_video_enclosure(e)]
        if len(enclosures) == 0:
            return None

        enclosures.sort(cmp_enclosures)
        return enclosures[0]

    def _get_enclosure_size(enclosure):
        if 'filesize' in enclosure and enclosure['filesize'].isdigit():
            return int(enclosure['filesize'])
        else:
            return None

    def _get_enclosure_bitrate(enclosure):
        if 'bitrate' in enclosure and enclosure['bitrate'].isdigit():
            return int(enclosure['bitrate'])
        else:
            return None

    def cmp_enclosures(enclosure1, enclosure2):
        """Returns -1 if enclosure1 is preferred, 1 if enclosure2 is
        preferred, and zero if there is no preference between the two
        of them.
        """
        # media:content enclosures have an isDefault which we should
        # pick since it's the preference of the feed
        if enclosure1.get("isDefault"):
            return -1
        if enclosure2.get("isDefault"):
            return 1

        # let's try sorting by preference
        enclosure1_index = _get_enclosure_index(enclosure1)
        enclosure2_index = _get_enclosure_index(enclosure2)
        if enclosure1_index < enclosure2_index:
            return -1
        elif enclosure2_index < enclosure1_index:
            return 1

        # next, let's try sorting by bitrate..
        enclosure1_bitrate = _get_enclosure_bitrate(enclosure1)
        enclosure2_bitrate = _get_enclosure_bitrate(enclosure2)
        if enclosure1_bitrate > enclosure2_bitrate:
            return -1
        elif enclosure2_bitrate > enclosure1_bitrate:
            return 1

        # next, let's try sorting by filesize..
        enclosure1_size = _get_enclosure_size(enclosure1)
        enclosure2_size = _get_enclosure_size(enclosure2)
        if enclosure1_size > enclosure2_size:
            return -1
        elif enclosure2_size > enclosure1_size:
            return 1

        # at this point they're the same for all we care
        return 0

    def _get_enclosure_index(enclosure):
        try:
            return PREFERRED_TYPES.index(enclosure.get('type'))
        except ValueError:
            return None

    PREFERRED_TYPES = [
        'application/x-bittorrent',
        'application/ogg', 'video/ogg', 'audio/ogg',
        'video/mp4', 'video/quicktime', 'video/mpeg',
        'video/x-xvid', 'video/x-divx', 'video/x-wmv',
        'video/x-msmpeg', 'video/x-flv']


    def quote_unicode_url(url):
        """Quote international characters contained in a URL according
        to w3c, see: <http://www.w3.org/International/O-URL-code.html>
        """
        quotedChars = []
        for c in url.encode('utf8'):
            if ord(c) > 127:
                quotedChars.append(urllib.quote(c))
            else:
                quotedChars.append(c)
        return u''.join(quotedChars)

    KNOWN_MIME_TYPES = (u'audio', u'video')
    KNOWN_MIME_SUBTYPES = (u'mov', u'wmv', u'mp4', u'mp3', u'mpg', u'mpeg',
                           u'avi', u'x-flv', u'x-msvideo', u'm4v', u'mkv',
                           u'm2v', u'ogg')
    MIME_SUBSITUTIONS = {
        u'QUICKTIME': u'MOV',
    }

    def entity_replace(text):
        replacements = [
                ('&#39;', "'"),
                ('&apos;', "'"),
                ('&#34;', '"'),
                ('&quot;', '"'),
                ('&#38;', '&'),
                ('&amp;', '&'),
                ('&#60;', '<'),
                ('&lt;', '<'),
                ('&#62;', '>'),
                ('&gt;', '>'),
        ] # FIXME: have a more general, charset-aware way to do this.
        for src, dest in replacements:
            text = text.replace(src, dest)
        return text

    class FeedParserValues(object):
        """Helper class to get values from feedparser entries

        FeedParserValues objects inspect the FeedParserDict for the
        entry attribute for various attributes using in Item
        (entry_title, rss_id, url, etc...).
        """
        def __init__(self, entry):
            self.entry = entry
            self.normalized_entry = normalize_feedparser_dict(entry)
            self.first_video_enclosure = get_first_video_enclosure(entry)

            self.data = {
                    'license': entry.get("license"),
                    'rss_id': entry.get('id'),
                    'entry_title': self._calc_title(),
                    'thumbnail_url': self._calc_thumbnail_url(),
                    'raw_descrption': self._calc_raw_description(),
                    'link': self._calc_link(),
                    'payment_link': self._calc_payment_link(),
                    'comments_link': self._calc_comments_link(),
                    'url': self._calc_url(),
                    'enclosure_size': self._calc_enclosure_size(),
                    'enclosure_type': self._calc_enclosure_type(),
                    'enclosure_format': self._calc_enclosure_format(),
                    'releaseDateObj': self._calc_release_date(),
            }

        def update_item(self, item):
            for key, value in self.data.items():
                setattr(item, key, value)
            item.feedparser_output = self.normalized_entry

        def compare_to_item(self, item):
            for key, value in self.data.items():
                if getattr(item, key) != value:
                    return False
            return True

        def compare_to_item_enclosures(self, item):
            compare_keys = ('url', 'enclosure_size', 'enclosure_type',
                    'enclosure_format')
            for key in compare_keys:
                if getattr(item, key) != self.data[key]:
                    return False
            return True

        def _calc_title(self):
            if hasattr(self.entry, "title"):
                # The title attribute shouldn't use entities, but some in the
                # wild do (#11413).  In that case, try to fix them.
                return entity_replace(self.entry.title)
            else:
                if ((self.first_video_enclosure
                     and 'url' in self.first_video_enclosure)):
                    return self.first_video_enclosure['url'].decode("ascii",
                                                                    "replace")
                return None

        def _calc_thumbnail_url(self):
            """Returns a link to the thumbnail of the video."""
            # Try to get the thumbnail specific to the video enclosure
            if self.first_video_enclosure is not None:
                url = self._get_element_thumbnail(self.first_video_enclosure)
                if url is not None:
                    return url

            # Try to get any enclosure thumbnail
            if hasattr(self.entry, "enclosures"):
                for enclosure in self.entry.enclosures:
                    url = self._get_element_thumbnail(enclosure)
                    if url is not None:
                        return url

            # Try to get the thumbnail for our entry
            return self._get_element_thumbnail(self.entry)

        def _get_element_thumbnail(self, element):
            try:
                thumb = element["thumbnail"]
            except KeyError:
                return None
            if isinstance(thumb, str):
                return thumb
            elif isinstance(thumb, unicode):
                return thumb.decode('ascii', 'replace')
            try:
                return thumb["url"].decode('ascii', 'replace')
            except (KeyError, AttributeError):
                return None

        def _calc_raw_description(self):
            rv = None
            try:
                if hasattr(self.first_video_enclosure, "text"):
                    rv = self.first_video_enclosure["text"]
                elif hasattr(self.entry, "description"):
                    rv = self.entry.description
            except StandardError:
                logging.exception("_calc_raw_description threw exception:")
            if rv is None:
                return u''
            else:
                return rv

        def _calc_link(self):
            if hasattr(self.entry, "link"):
                link = self.entry.link
                if isinstance(link, dict):
                    try:
                        link = link['href']
                    except KeyError:
                        return u""
                if isinstance(link, unicode):
                    return link
                try:
                    return link.decode('ascii', 'replace')
                except UnicodeDecodeError:
                    return link.decode('ascii', 'ignore')
            return u""

        def _calc_payment_link(self):
            try:
                return self.first_video_enclosure.payment_url.decode('ascii',
                                                                     'replace')
            except (UnicodeDecodeError, AttributeError):
                try:
                    return self.entry.payment_url.decode('ascii','replace')
                except (UnicodeDecodeError, AttributeError):
                    return u""

        def _calc_comments_link(self):
            return self.entry.get('comments', u"")

        def _calc_url(self):
            if ((self.first_video_enclosure is not None
                 and 'url' in self.first_video_enclosure)):
                url = self.first_video_enclosure['url'].replace('+', '%20')
                return quote_unicode_url(url)
            else:
                return u''

        def _calc_enclosure_size(self):
            enc = self.first_video_enclosure
            if enc is not None and "torrent" not in enc.get("type", ""):
                try:
                    return int(enc['length'])
                except (KeyError, ValueError):
                    return None

        def _calc_enclosure_type(self):
            if ((self.first_video_enclosure
                 and self.first_video_enclosure.has_key('type'))):
                return self.first_video_enclosure['type']
            else:
                return None

        def _calc_enclosure_format(self):
            enclosure = self.first_video_enclosure
            if enclosure:
                try:
                    extension = enclosure['url'].split('.')[-1]
                    extension = extension.lower().encode('ascii', 'replace')
                except (SystemExit, KeyboardInterrupt):
                    raise
                except KeyError:
                    extension = u''
                # Hack for mp3s, "mpeg audio" isn't clear enough
                if extension.lower() == u'mp3':
                    return u'.mp3'
                if enclosure.get('type'):
                    enc = enclosure['type'].decode('ascii', 'replace')
                    if "/" in enc:
                        mtype, subtype = enc.split('/', 1)
                        mtype = mtype.lower()
                        if mtype in KNOWN_MIME_TYPES:
                            format = subtype.split(';')[0].upper()
                            if mtype == u'audio':
                                format += u' AUDIO'
                            if format.startswith(u'X-'):
                                format = format[2:]
                            return u'.%s' % MIME_SUBSITUTIONS.get(format, format).lower()

                if extension in KNOWN_MIME_SUBTYPES:
                    return u'.%s' % extension
            return None

        def _calc_release_date(self):
            try:
                return datetime(*self.first_video_enclosure.updated_parsed[0:7])
            except StandardError:
                try:
                    return datetime(*self.entry.updated_parsed[0:7])
                except StandardError:
                    return datetime.min

    from datetime import datetime
    from time import struct_time
    from types import NoneType
    import types

    from miro import feedparser
    # normally we shouldn't import other modules inside an upgrade
    # function.  However, it should be semi-safe to import feedparser,
    # because it would have already been imported when unpickling
    # FeedParserDict objects.

    # values from feedparser dicts that don't have to convert in
    # normalize_feedparser_dict()
    _simple_feedparser_values = (int, long, str, unicode, bool, NoneType,
                                 datetime, struct_time)
    def normalize_feedparser_dict(fp_dict):
        """Convert FeedParserDict objects to normal dictionaries."""
        retval = {}
        for key, value in fp_dict.items():
            if isinstance(value, feedparser.FeedParserDict):
                value = normalize_feedparser_dict(value)
            elif isinstance(value, dict):
                value = dict((_convert_if_feedparser_dict(k),
                    _convert_if_feedparser_dict(v)) for (k, v) in
                    value.items())
            elif isinstance(value, list):
                value = [_convert_if_feedparser_dict(o) for o in value]
            elif isinstance(value, tuple):
                value = tuple(_convert_if_feedparser_dict(o) for o in value)
            else:
                if not value.__class__ in _simple_feedparser_values:
                    raise ValueError("Can't normalize: %r (%s)" %
                            (value, value.__class__))
            retval[key] = value
        return retval

    def _convert_if_feedparser_dict(obj):
        if isinstance(obj, feedparser.FeedParserDict):
            return normalize_feedparser_dict(obj)
        else:
            return obj

    changed = set()
    for o in objectList:
        if o.classString in ('item', 'file-item'):
            entry = o.savedData.pop('entry')
            fp_values = FeedParserValues(entry)
            o.savedData.update(fp_values.data)
            o.savedData['feedparser_output'] = fp_values.normalized_entry
            changed.add(o)
    return changed

def upgrade76(objectList):
    changed = set()
    for o in objectList:
        if o.classString == 'feed':
            feed_impl = o.savedData['actualFeed']
            o.savedData['visible'] = feed_impl.savedData.pop('visible')
            changed.add(o)
    return changed

def upgrade77(objectList):
    """Drop ufeed and actualFeed attributes, replace them with id
    values."""
    changed = set()
    last_id = 0
    feeds = []
    for o in objectList:
        last_id = max(o.savedData['id'], last_id)
        if o.classString == 'feed':
            feeds.append(o)

    next_id = last_id + 1
    for feed in feeds:
        feed_impl = feed.savedData['actualFeed']
        feed_impl.savedData['ufeed_id'] = feed.savedData['id']
        feed.savedData['feed_impl_id'] = feed_impl.savedData['id'] = next_id
        del feed_impl.savedData['ufeed']
        del feed.savedData['actualFeed']
        changed.add(feed)
        changed.add(feed_impl)
        objectList.append(feed_impl)
        next_id += 1
    return changed

def upgrade78(objectList):
    """Drop iconCache attribute.  Replace it with icon_cache_id.  Make
    IconCache objects into top-level entities.
    """
    changed = set()
    last_id = 0
    icon_cache_containers = []

    for o in objectList:
        last_id = max(o.savedData['id'], last_id)
        if o.classString in ('feed', 'item', 'file-item', 'channel-guide'):
            icon_cache_containers.append(o)

    next_id = last_id + 1
    for obj in icon_cache_containers:
        icon_cache = obj.savedData['iconCache']
        if icon_cache is not None:
            obj.savedData['icon_cache_id'] = icon_cache.savedData['id'] = next_id
            changed.add(icon_cache)
            objectList.append(icon_cache)
        else:
            obj.savedData['icon_cache_id'] = None
        del obj.savedData['iconCache']
        changed.add(obj)
        next_id += 1
    return changed

def upgrade79(objectList):
    """Convert RemoteDownloader.status from SchemaSimpleContainer to
    SchemaReprContainer.
    """
    changed = set()
    def convert_to_repr(obj, key):
        obj.savedData[key] = repr(obj.savedData[key])
        changed.add(o)

    for o in objectList:
        if o.classString == 'remote-downloader':
            convert_to_repr(o, 'status')
        elif o.classString in ('item', 'file-item'):
            convert_to_repr(o, 'feedparser_output')
        elif o.classString == 'scraper-feed-impl':
            convert_to_repr(o, 'linkHistory')
        elif o.classString in ('rss-multi-feed-impl', 'search-feed-impl'):
            convert_to_repr(o, 'etag')
            convert_to_repr(o, 'modified')
        elif o.classString in ('playlist', 'playlist-folder'):
            convert_to_repr(o, 'item_ids')
        elif o.classString == 'taborder-order':
            convert_to_repr(o, 'tab_ids')
        elif o.classString == 'channel-guide':
            convert_to_repr(o, 'allowedURLs')
        elif o.classString == 'theme-history':
            convert_to_repr(o, 'pastThemes')
        elif o.classString == 'widgets-frontend-state':
            convert_to_repr(o, 'list_view_displays')

    return changed

# There is no upgrade80.  That version was the version we switched how
# the database was stored.

def upgrade81(cursor):
    """Add the was_downloaded column to downloader."""
    import datetime
    import time
    cursor.execute("ALTER TABLE remote_downloader ADD state TEXT")
    to_update = []
    for row in cursor.execute("SELECT id, status FROM remote_downloader"):
        id = row[0]
        status = eval(row[1], __builtins__,
                {'datetime': datetime, 'time': time})
        state = status.get('state', u'downloading')
        to_update.append((id, state))
    for id, state in to_update:
        cursor.execute("UPDATE remote_downloader SET state=? WHERE id=?",
                (state, id))

def upgrade82(cursor):
    """Add the state column to item."""
    cursor.execute("ALTER TABLE item ADD was_downloaded INTEGER")
    cursor.execute("ALTER TABLE file_item ADD was_downloaded INTEGER")
    cursor.execute("UPDATE file_item SET was_downloaded=0")

    downloaded = []
    for row in cursor.execute("SELECT id, downloader_id, expired FROM item"):
        if row[1] is not None or row[2]:
            # item has a downloader, or was expired, either way it was
            # downloaded at some point.
            downloaded.append(row[0])
    cursor.execute("UPDATE item SET was_downloaded=0")
    # sqlite can only handle 999 variables at once, which can be less
    # then the number of downloaded items (#11717).  Let's go for
    # chunks of 500 at a time to be safe.
    for start_pos in xrange(0, len(downloaded), 500):
        downloaded_chunk = downloaded[start_pos:start_pos+500]
        placeholders = ', '.join('?' for i in xrange(len(downloaded_chunk)))
        cursor.execute("UPDATE item SET was_downloaded=1 "
                "WHERE id IN (%s)" % placeholders, downloaded_chunk)

def upgrade83(cursor):
    """Merge the items and file_items tables together."""

    cursor.execute("ALTER TABLE item ADD is_file_item INTEGER")
    cursor.execute("ALTER TABLE item ADD filename TEXT")
    cursor.execute("ALTER TABLE item ADD deleted INTEGER")
    cursor.execute("ALTER TABLE item ADD shortFilename TEXT")
    cursor.execute("ALTER TABLE item ADD offsetPath TEXT")
    # Set values for existing Item objects
    cursor.execute("UPDATE item SET is_file_item=0, filename=NULL, "
            "deleted=NULL, shortFilename=NULL, offsetPath=NULL")
    # Set values for FileItem objects coming from the file_items table
    columns = ('id', 'feed_id', 'downloader_id', 'parent_id', 'seen',
            'autoDownloaded', 'pendingManualDL', 'pendingReason', 'title',
            'expired', 'keep', 'creationTime', 'linkNumber', 'icon_cache_id',
            'downloadedTime', 'watchedTime', 'isContainerItem',
            'videoFilename', 'isVideo', 'releaseDateObj',
            'eligibleForAutoDownload', 'duration', 'screenshot', 'resumeTime',
            'channelTitle', 'license', 'rss_id', 'thumbnail_url',
            'entry_title', 'raw_descrption', 'link', 'payment_link',
            'comments_link', 'url', 'enclosure_size', 'enclosure_type',
            'enclosure_format', 'feedparser_output', 'was_downloaded',
            'filename', 'deleted', 'shortFilename', 'offsetPath',)
    columns_connected = ', '.join(columns)
    cursor.execute('INSERT INTO item (is_file_item, %s) '
            'SELECT 1, %s FROM file_item' % (columns_connected,
                columns_connected))
    cursor.execute("DROP TABLE file_item")

def upgrade84(cursor):
    """Fix "field_impl" typo"""
    cursor.execute("ALTER TABLE field_impl RENAME TO feed_impl")

def upgrade85(cursor):
    """Set seen attribute for container items"""

    cursor.execute("UPDATE item SET seen=0 WHERE isContainerItem")
    cursor.execute("UPDATE item SET seen=1 "
            "WHERE isContainerItem AND NOT EXISTS "
            "(SELECT 1 FROM item AS child WHERE "
            "child.parent_id=item.id AND NOT child.seen)")

def upgrade86(cursor):
    """Move the lastViewed attribute from feed_impl to feed."""
    cursor.execute("ALTER TABLE feed ADD last_viewed TIMESTAMP")

    feed_impl_tables = ('feed_impl', 'rss_feed_impl', 'rss_multi_feed_impl',
            'scraper_feed_impl', 'search_feed_impl',
            'directory_watch_feed_impl', 'directory_feed_impl',
            'search_downloads_feed_impl', 'manual_feed_impl',
            'single_feed_impl',)
    selects = ['SELECT ufeed_id, lastViewed FROM %s' % table \
            for table in feed_impl_tables]
    union = ' UNION '.join(selects)
    cursor.execute("UPDATE feed SET last_viewed = "
            "(SELECT lastViewed FROM (%s) WHERE ufeed_id = feed.id)" % union)

def upgrade87(cursor):
    """Make last_viewed a "timestamp" column rather than a "TIMESTAMP"
    one."""
    # see 11716 for details
    columns = []
    columns_with_type = []
    cursor.execute("PRAGMA table_info('feed')")
    for column_info in cursor.fetchall():
        column = column_info[1]
        typ = column_info[2]
        columns.append(column)
        if typ == 'TIMESTAMP':
            typ = 'timestamp'
        if column == 'id':
            typ += ' PRIMARY KEY'
        columns_with_type.append("%s %s" % (column, typ))
    cursor.execute("ALTER TABLE feed RENAME TO old_feed")
    cursor.execute("CREATE TABLE feed (%s)" % ', '.join(columns_with_type))
    cursor.execute("INSERT INTO feed (%s) SELECT %s FROM old_feed" %
            (', '.join(columns), ', '.join(columns)))
    cursor.execute("DROP TABLE old_feed")

def upgrade88(cursor):
    """Replace playlist.item_ids, with PlaylistItemMap objects."""

    id_counter = itertools.count(get_next_id(cursor))

    folder_count = {}
    for table_name in ('playlist_item_map', 'playlist_folder_item_map'):
        cursor.execute("SELECT COUNT(*) FROM sqlite_master "
                "WHERE name=? and type='table'", (table_name,))
        if cursor.fetchone()[0] > 0:
            logging.warn("dropping %s in upgrade88", table_name)
            cursor.execute("DROP TABLE %s " % table_name)
    cursor.execute("CREATE TABLE playlist_item_map (id integer PRIMARY KEY, "
            "playlist_id integer, item_id integer, position integer)")
    cursor.execute("CREATE TABLE playlist_folder_item_map "
            "(id integer PRIMARY KEY, playlist_id integer, item_id integer, "
            " position integer, count integer)")

    sql = "SELECT id, folder_id, item_ids FROM playlist"
    for row in list(cursor.execute(sql)):
        id, folder_id, item_ids = row
        item_ids = eval(item_ids, {}, {})
        for i, item_id in enumerate(item_ids):
            cursor.execute("INSERT INTO playlist_item_map "
                    "(id, item_id, playlist_id, position) VALUES (?, ?, ?, ?)",
                    (id_counter.next(), item_id, id, i))
            if folder_id is not None:
                if folder_id not in folder_count:
                    folder_count[folder_id] = {}
                try:
                    folder_count[folder_id][item_id] += 1
                except KeyError:
                    folder_count[folder_id][item_id] = 1

    sql = "SELECT id, item_ids FROM playlist_folder"
    for row in list(cursor.execute(sql)):
        id, item_ids = row
        item_ids = eval(item_ids, {}, {})
        this_folder_count = folder_count.get(id, {})
        for i, item_id in enumerate(item_ids):
            try:
                count = this_folder_count[item_id]
            except KeyError:
                # item_id is listed for this playlist folder, but none
                # of it's child folders.  It's not clear how it
                # happened, but forget about it.  (#12301)
                continue
            cursor.execute("INSERT INTO playlist_folder_item_map "
                    "(id, item_id, playlist_id, position, count) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (id_counter.next(), item_id, id, i, count))
    for table in ('playlist_folder', 'playlist'):
        remove_column(cursor, table, ['item_id'])

def upgrade89(cursor):
    """Set videoFilename column for downloaded items."""
    import datetime
    from miro.plat.utils import filename_to_unicode

    # for Items, calculate from the downloader
    for row in cursor.execute("SELECT id, downloader_id FROM item "
            "WHERE NOT is_file_item AND videoFilename = ''").fetchall():
        item_id, downloader_id = row
        if downloader_id is None:
            continue
        cursor.execute("SELECT state, status FROM remote_downloader "
                "WHERE id=?", (downloader_id,))
        results = cursor.fetchall()
        if len(results) == 0:
            cursor.execute("SELECT origURL FROM feed "
                    "JOIN item ON item.feed_id=feed.id "
                    "WHERE item.id=?", (item_id,))
            row = cursor.fetchall()[0]
            if row[0] == 'dtv:manualFeed':
                # external download, let's just delete the row.
                cursor.execute("DELETE FROM item WHERE id=?", (item_id,))
            else:
                cursor.execute("UPDATE item "
                        "SET downloader_id=NULL, seen=NULL, keep=NULL, "
                        "pendingManualDL=0, filename=NULL, watchedTime=NULL, "
                        "duration=NULL, screenshot=NULL, "
                        "isContainerItem=NULL, expired=1 "
                        "WHERE id=?",
                        (item_id,))
            continue

        row = results[0]
        state = row[0]
        status = row[1]
        status = eval(status, __builtins__, {'datetime': datetime})
        filename = status.get('filename')
        if (state in ('stopped', 'finished', 'uploading', 'uploading-paused')
                and filename):
            filename = filename_to_unicode(filename)
            cursor.execute("UPDATE item SET videoFilename=? WHERE id=?",
                (filename, item_id))
    # for FileItems, just copy from filename
    cursor.execute("UPDATE item set videoFilename=filename "
            "WHERE is_file_item")

def upgrade90(cursor):
    """Add the was_downloaded column to downloader."""
    cursor.execute("ALTER TABLE remote_downloader ADD main_item_id integer")
    for row in cursor.execute("SELECT id FROM remote_downloader").fetchall():
        downloader_id = row[0]
        cursor.execute("SELECT id FROM item WHERE downloader_id=? LIMIT 1",
                (downloader_id,))
        row = cursor.fetchone()
        if row is not None:
            # set main_item_id to one of the item ids, it doesn't matter which
            item_id = row[0]
            cursor.execute("UPDATE remote_downloader SET main_item_id=? "
                    "WHERE id=?", (item_id, downloader_id))
        else:
            # no items for a downloader, delete the downloader
            cursor.execute("DELETE FROM remote_downloader WHERE id=?",
                    (downloader_id,))

def upgrade91(cursor):
    """Add lots of indexes."""
    cursor.execute("CREATE INDEX item_feed ON item (feed_id)")
    cursor.execute("CREATE INDEX item_downloader ON item (downloader_id)")
    cursor.execute("CREATE INDEX item_feed_downloader ON item "
            "(feed_id, downloader_id)")
    cursor.execute("CREATE INDEX downloader_state ON remote_downloader (state)")

def upgrade92(cursor):
    feed_impl_tables = ('feed_impl', 'rss_feed_impl', 'rss_multi_feed_impl',
            'scraper_feed_impl', 'search_feed_impl',
            'directory_watch_feed_impl', 'directory_feed_impl',
            'search_downloads_feed_impl', 'manual_feed_impl',
            'single_feed_impl',)
    for table in feed_impl_tables:
        remove_column(cursor, table, ['lastViewed'])
    remove_column(cursor, 'playlist', ['item_ids'])
    remove_column(cursor, 'playlist_folder', ['item_ids'])

def upgrade93(cursor):
    VIDEO_EXTENSIONS = ['.mov', '.wmv', '.mp4', '.m4v', '.ogv', '.anx',
                        '.mpg', '.avi', '.flv', '.mpeg', '.divx', '.xvid',
                        '.rmvb', '.mkv', '.m2v', '.ogm']
    AUDIO_EXTENSIONS = ['.mp3', '.m4a', '.wma', '.mka', '.ogg', '.flac']

    video_filename_expr = '(%s)' % ' OR '.join("videoFilename LIKE '%%%s'" % ext
            for ext in VIDEO_EXTENSIONS)

    audio_filename_expr = '(%s)' % ' OR '.join("videoFilename LIKE '%%%s'" % ext
            for ext in AUDIO_EXTENSIONS)

    cursor.execute("ALTER TABLE item ADD file_type text")
    cursor.execute("CREATE INDEX item_file_type ON item (file_type)")
    cursor.execute("UPDATE item SET file_type = 'video' "
            "WHERE " + video_filename_expr)
    cursor.execute("UPDATE item SET file_type = 'audio' "
            "WHERE " + audio_filename_expr)
    cursor.execute("UPDATE item SET file_type = 'other' "
            "WHERE file_type IS NULL AND videoFilename IS NOT NULL AND "
            "videoFilename != ''")

def upgrade94(cursor):
    cursor.execute("UPDATE item SET downloadedTime=NULL "
        "WHERE deleted OR downloader_id IS NULL")

def upgrade95(cursor):
    """Delete FileItem objects that are duplicates of torrent files. (#11818)
    """
    cursor.execute("SELECT item.id, item.videoFilename, rd.status "
            "FROM item "
            "JOIN remote_downloader rd ON item.downloader_id=rd.id "
            "WHERE rd.state in ('stopped', 'finished', 'uploading', "
            "'uploading-paused')")
    for row in cursor.fetchall():
        id, videoFilename, status = row
        status = eval(status, __builtins__,
                {'datetime': datetime, 'time': time})
        if (videoFilename and videoFilename != status.get('filename')):
            pathname = os.path.join(status.get('filename'), videoFilename)
            # Here's the situation: We downloaded a torrent and that
            # torrent had a single video as it's child.  We then made
            # the torrent's videoFilename be the path to that video
            # instead of creating a new FileItem.  This is broken for
            # a bunch of reasons, so we're getting rid of it.  Undo
            # the trickyness that we did and delete any duplicate
            # items that may have been created.  The next update will
            # remove the videoFilename column.
            cursor.execute("DELETE FROM item "
                    "WHERE is_file_item AND videoFilename =?", (pathname,))
            cursor.execute("UPDATE item "
                    "SET file_type='other', isContainerItem=1 "
                    "WHERE id=?", (id,))

def upgrade96(cursor):
    """Delete the videoFilename and isVideo column."""
    remove_column(cursor, 'item', ['videoFilename', 'isVideo'])

def upgrade97(cursor):
    """Add another indexes, this is make tab switching faster.
    """
    cursor.execute("CREATE INDEX item_feed_visible ON item (feed_id, deleted)")

def upgrade98(cursor):
    """Add an index for item parents
    """
    cursor.execute("CREATE INDEX item_parent ON item (parent_id)")

def upgrade99(cursor):
    """Set the filename attribute for downloaded Item objects
    """
    from miro.plat.utils import filename_to_unicode
    cursor.execute("SELECT id, status from remote_downloader "
            "WHERE state in ('stopped', 'finished', 'uploading', "
            "'uploading-paused')")
    for row in cursor.fetchall():
        downloader_id = row[0]
        status = eval(row[1], __builtins__,
                {'datetime': datetime, 'time': time})
        filename = status.get('filename')
        if filename:
            filename = filename_to_unicode(filename)
            cursor.execute("UPDATE item SET filename=? WHERE downloader_id=?",
                    (filename, downloader_id))

class TimeModuleShadow:
    """In Python 2.6, time.struct_time is a named tuple and evals
    poorly, so we have struct_time_shadow which takes the arguments
    that struct_time should have and returns a 9-tuple
    """
    def struct_time(self, tm_year=0, tm_mon=0, tm_mday=0, tm_hour=0,
                    tm_min=0, tm_sec=0, tm_wday=0, tm_yday=0, tm_isdst=0):
        return (tm_year, tm_mon, tm_mday, tm_hour, tm_min, tm_sec,
                tm_wday, tm_yday, tm_isdst)

_TIME_MODULE_SHADOW = TimeModuleShadow()

def eval_container(repr):
    """Convert a column that's stored using repr to a python
    list/dict."""
    return eval(repr, __builtins__, {'datetime': datetime,
                                     'time': _TIME_MODULE_SHADOW})

def upgrade100(cursor):
    """Adds the Miro audio guide as a site for anyone who doesn't
    already have it and isn't using a theme.
    """
    # if the user is using a theme, we don't do anything
    if not app.config.get(prefs.THEME_NAME) == prefs.THEME_NAME.default:
        return

    audio_guide_url = u'http://www.miroguide.com/audio/'
    favicon_url = u'http://www.miroguide.com/favicon.ico'
    cursor.execute("SELECT count(*) FROM channel_guide WHERE url=?",
                   (audio_guide_url,))
    count = cursor.fetchone()[0]
    if count > 0:
        return

    next_id = get_next_id(cursor)

    cursor.execute("INSERT INTO channel_guide "
                   "(id, url, allowedURLs, updated_url, favicon, firstTime) VALUES (?, ?, ?, ?, ?, ?)",
                   (next_id, audio_guide_url, "[]", audio_guide_url,
                    favicon_url, True))

    # add the new Audio Guide to the site tablist
    cursor.execute('SELECT tab_ids FROM taborder_order WHERE type=?',
                   ('site',))
    row = cursor.fetchone()
    if row is not None:
        try:
            tab_ids = eval_container(row[0])
        except StandardError:
            tab_ids = []
        tab_ids.append(next_id)
        cursor.execute('UPDATE taborder_order SET tab_ids=? WHERE type=?',
                       (repr(tab_ids), 'site'))
    else:
        # no site taborder (#11985).  We will create the TabOrder
        # object on startup, so no need to do anything here
        pass

def upgrade101(cursor):
    """For torrent folders where a child item has been deleted, change
    the state from 'stopped' to 'finished' and set child_deleted to
    True"""

    cursor.execute("ALTER TABLE remote_downloader ADD child_deleted INTEGER")
    cursor.execute("UPDATE remote_downloader SET child_deleted = 0")
    cursor.execute("SELECT id, status FROM remote_downloader "
            "WHERE state = 'stopped'")
    for row in cursor.fetchall():
        id, status = row
        try:
            status = eval_container(status)
        except StandardError:
            # Not sure what to do here.  I think ignoring is not
            # ideal, but won't result in anything too bad (BDK)
            continue
        if status['endTime'] == status['startTime']:
            # For unfinished downloads, unset the filename which got
            # set in upgrade99
            cursor.execute("UPDATE item SET filename=NULL "
                    "WHERE downloader_id=?", (id,))
        elif status['dlerType'] != 'BitTorrent':
            status['state'] = 'finished'
            cursor.execute("UPDATE remote_downloader "
                    "SET state='finished', child_deleted=1, status=? "
                    "WHERE id=?", (repr(status), id))

def upgrade102(cursor):
    """Fix for the embarrasing bug in upgrade101

    This statement was exactly the opposite of what we want::

        elif status['dlerType'] != 'BitTorrent':
    """
    cursor.execute("SELECT id, status, child_deleted FROM remote_downloader "
            "WHERE state = 'stopped'")
    for row in cursor.fetchall():
        id, status, child_deleted = row
        status = eval_container(status)
        if status['dlerType'] != 'BitTorrent' and child_deleted:
            # I don't think that it's actually possible, but fix HTTP
            # downloaders that were changed in upgrade101
            status['state'] = 'stopped'
            cursor.execute("UPDATE remote_downloader "
                    "SET state='stopped', child_deleted=0, status=? "
                    "WHERE id=?", (repr(status), id))
        elif (status['endTime'] != status['startTime'] and
                status['dlerType'] == 'BitTorrent'):
            # correctly execute what upgrade101 was trying to do
            status['state'] = 'finished'
            cursor.execute("UPDATE remote_downloader "
                    "SET state='finished', child_deleted=1, status=? "
                    "WHERE id=?", (repr(status), id))

def upgrade103(cursor):
    """Possible fix for #11730.

    Delete downloaders with duplicate origURL values.
    """
    cursor.execute("SELECT MIN(id), origURL FROM remote_downloader "
            "GROUP BY origURL "
            "HAVING count(*) > 1")
    for row in cursor.fetchall():
        id_, origURL = row
        cursor.execute("SELECT id FROM remote_downloader "
                "WHERE origURL=? and id != ?", (origURL, id_))
        for row in cursor.fetchall():
            dup_id = row[0]
            cursor.execute("UPDATE item SET downloader_id=? "
                    "WHERE downloader_id=?", (id_, dup_id))
            cursor.execute("DELETE FROM remote_downloader WHERE id=?",
                    (dup_id,))

def upgrade104(cursor):
    cursor.execute("UPDATE item SET seen=0 WHERE seen IS NULL")
    cursor.execute("UPDATE item SET keep=0 WHERE keep IS NULL")

def upgrade105(cursor):
    """Move metainfo and fastResumeData out of the status dict."""
    # create new colums
    cursor.execute("ALTER TABLE remote_downloader ADD metainfo BLOB")
    cursor.execute("ALTER TABLE remote_downloader ADD fast_resume_data BLOB")
    # move things
    cursor.execute("SELECT id, status FROM remote_downloader")
    for row in cursor.fetchall():
        id, status_repr = row
        try:
            status = eval_container(status_repr)
        except StandardError:
            status = {}
        metainfo = status.pop('metainfo', None)
        fast_resume_data = status.pop('fastResumeData', None)
        new_status = repr(status)
        if metainfo is not None:
            metainfo_value = buffer(metainfo)
        else:
            metainfo_value = None
        if fast_resume_data is not None:
            fast_resume_data_value = buffer(fast_resume_data)
        else:
            fast_resume_data_value = None
        cursor.execute("UPDATE remote_downloader "
                "SET status=?, metainfo=?, fast_resume_data=? "
                "WHERE id=?",
                (new_status, metainfo_value, fast_resume_data_value, id))


def upgrade106(cursor):
    tables = get_object_tables(cursor)
    # figure out which ids, if any are duplicated
    id_union = ' UNION ALL '.join(['SELECT id FROM %s' % t for t in tables])
    cursor.execute("SELECT count(*) as id_count, id FROM (%s) "
            "GROUP BY id HAVING id_count > 1" % id_union)
    duplicate_ids = set([r[1] for r in cursor])
    if len(duplicate_ids) == 0:
        return

    id_counter = itertools.count(get_next_id(cursor))

    def update_value(table, column, old_value, new_value):
        cursor.execute("UPDATE %s SET %s=%s WHERE %s=%s" % (table, column,
            new_value, column, old_value))

    for table in tables:
        if table == 'feed':
            # let feed objects keep their id, it's fairly annoying to
            # have to update the ufeed atribute for all the FeedImpl
            # subclasses.  The id won't be a duplicate anymore once we
            # update the other tables
            continue
        cursor.execute("SELECT id FROM %s" % table)
        for row in cursor.fetchall():
            id = row[0]
            if id in duplicate_ids:
                new_id = id_counter.next()
                # assign a new id to the object
                update_value(table, 'id', id, new_id)
                # fix foreign keys
                if table == 'icon_cache':
                    update_value('item', 'icon_cache_id', id, new_id)
                    update_value('feed', 'icon_cache_id', id, new_id)
                    update_value('channel_guide', 'icon_cache_id', id, new_id)
                elif table.endswith('feed_impl'):
                    update_value('feed', 'feed_impl_id', id, new_id)
                elif table == 'channel_folder':
                    update_value('feed', 'folder_id', id, new_id)
                elif table == 'remote_downloader':
                    update_value('item', 'downloader_id', id, new_id)
                elif table == 'item_id':
                    update_value('item', 'parent_id', id, new_id)
                    update_value('downloader', 'main_item_id', id, new_id)
                    update_value('playlist_item_map', 'item_id', id, new_id)
                    update_value('playlist_folder_item_map', 'item_id', id,
                                 new_id)
                elif table == 'playlist_folder':
                    update_value('playlist', 'folder_id', id, new_id)
                elif table == 'playlist':
                    update_value('playlist_item_map', 'playlist_id', id, new_id)
                    update_value('playlist_folder_item_map', 'playlist_id',
                                 id, new_id)
                # note we don't handle TabOrder.tab_ids here.  That's
                # because it's a list of ids, so it's hard to fix
                # using SQL.  Also, the TabOrder code is able to
                # recover from missing/extra ids in its list.  The
                # only bad thing that will happen is the user's tab
                # order will be changed.

def upgrade107(cursor):
    cursor.execute("CREATE TABLE db_log_entry ("
            "id integer, timestamp real, priority integer, description text)")

def upgrade108(cursor):
    """Drop the feedparser_output column from item.
    """
    remove_column(cursor, "item", ["feedparser_output"])

def upgrade109(cursor):
    """Add the media_type_checked column to item """
    cursor.execute("ALTER TABLE item ADD media_type_checked integer")
    cursor.execute("UPDATE item SET media_type_checked=0")

def upgrade110(cursor):
    """Make set last_viewed on the  manual feed to datetime.max"""
    cursor.execute("select ufeed_id from manual_feed_impl")
    for row in cursor:
        cursor.execute("UPDATE feed SET last_viewed=? WHERE id=?",
                (datetime.datetime.max, row[0]))

def upgrade111(cursor):
    """Create the active_filters column."""
    cursor.execute("ALTER TABLE widgets_frontend_state "
            "ADD active_filters PYTHONREPR")
    cursor.execute("UPDATE widgets_frontend_state "
            "SET active_filters = '{}'")

def upgrade112(cursor):
    """Create the sort_states column."""
    cursor.execute("ALTER TABLE widgets_frontend_state "
            "ADD sort_states PYTHONREPR")
    cursor.execute("UPDATE widgets_frontend_state "
            "SET sort_states = '{}'")

def upgrade113(cursor):
    """Change Feed URLs to not include search terms."""

    cursor.execute("SELECT id, origURL FROM feed "
            "WHERE origURL LIKE 'dtv:searchTerm:%'")
    search_re = re.compile(r"^dtv:searchTerm:(.*)\?(.*)$")
    for (id, url) in cursor.fetchall():
        m = search_re.match(url)
        url2 = m.group(1)
        cursor.execute("UPDATE feed SET origURL=? WHERE id=?",
                (url2, id))

    cursor.execute("SELECT id, origURL FROM feed "
            "WHERE origURL LIKE 'dtv:multi:%'")
    for (id, url) in cursor.fetchall():
        urls = url.split(',')
        if not urls[-1].startswith('http'):
            url2 = ','.join(urls[:-1])
            cursor.execute("UPDATE feed SET origURL=? WHERE id=?",
                    (url2, id))

def upgrade114(cursor):
    """Remove the query column from rss_multi_feed_impl and subclasses."""
    for table in ('rss_multi_feed_impl', 'search_feed_impl',):
        remove_column(cursor, table, ('query',))

def upgrade115(cursor):
    """Upgrade search feed tables."""

    # replace dtv:multi feeds with dtv:savedsearch feeds.
    cursor.execute("CREATE TABLE saved_search_feed_impl "
            "(id integer PRIMARY KEY, url text, ufeed_id integer, "
            "title text, created timestamp, thumbURL text, "
            "updateFreq integer, initialUpdate integer, etag pythonrepr, "
            "modified pythonrepr)");
    cursor.execute("INSERT INTO saved_search_feed_impl "
            "(id, url, ufeed_id, title, created, thumbURL, updateFreq, "
            "initialUpdate, etag, modified) "
            "SELECT id, url, ufeed_id, title, created, thumbURL, "
            "updateFreq, initialUpdate, etag, modified "
            "FROM rss_multi_feed_impl");
    cursor.execute("DROP TABLE rss_multi_feed_impl")
    # fix the URL attribute
    cursor.execute("SELECT id, ufeed_id, url FROM saved_search_feed_impl")
    def _calc_query(multi_url):
        url_list = multi_url[len("dtv:multi:"):]
        url_list = [urllib.unquote (x) for x in url_list.split(",")]
        revver_prefix = 'http://feeds.revver.com/2.0/mrss/qt/search/'
        for url in url_list:
            if url.startswith(revver_prefix):
                query = url[len(revver_prefix):]
                # the decoding gymnastics on the next line are what we're
                # trying to avoid with this update.
                return urllib.unquote(query.encode('ascii')).decode('utf-8')
        return u'unknown'

    for (id, ufeed_id, url) in cursor.fetchall():
        query = _calc_query(url)
        new_url = u'dtv:savedsearch/all?q=%s' % query
        new_title = unicode(_("%(engine)s for '%(query)s'",
                {'engine': 'Search All', 'query': query}))
        cursor.execute("UPDATE saved_search_feed_impl SET url=?, title=? "
                "WHERE id=?", (new_url, new_title, id))
        cursor.execute("UPDATE feed SET origURL=? WHERE id=?",
                (new_url, ufeed_id))


    # for the search feed, we just need to rename things a bit
    remove_column(cursor, 'search_feed_impl', ('searching',))
    cursor.execute("ALTER TABLE search_feed_impl ADD engine TEXT")
    cursor.execute("ALTER TABLE search_feed_impl ADD query TEXT")
    cursor.execute("SELECT id, lastEngine, lastQuery FROM search_feed_impl")
    for (id, engine, query) in cursor.fetchall():
        cursor.execute("UPDATE search_feed_impl SET engine=?, query=? "
                "WHERE id=?", (engine, query, id))
    remove_column(cursor, 'search_feed_impl', ('lastEngine', 'lastQuery'))

def upgrade116(cursor):
    """Convert filenames in the status container to unicode."""
    cursor.execute("SELECT id, status FROM remote_downloader")
    filename_fields = ('channelName', 'shortFilename', 'filename')
    for row in cursor.fetchall():
        id, status = row
        status = eval(status, __builtins__,
                {'datetime': datetime, 'time': time})
        changed = False
        for key in filename_fields:
            value = status.get(key)
            if value is not None and not isinstance(value, unicode):
                try:
                    status[key] = value.decode("utf-8")
                except UnicodeError:
                    # for channelNames with bad unicode, try some kludges to
                    # get things working.  (#14003)
                    try:
                        # kludge 1: latin-1 charset
                        status[key] = value.decode("iso-8859-1")
                    except UnicodeError:
                        # kludge 2: replace bad values
                        logging.warn("replacing invalid unicode for status "
                                "dict %r (id: %s, key: %s)", value, id, key)
                        status[key] = value.decode("utf-8", 'replace')
                changed = True
        if changed:
            cursor.execute("UPDATE remote_downloader SET status=? "
                    "WHERE id=?", (repr(status), id))

def upgrade117(cursor):
    """Add the subtitle_encoding column to items."""

    cursor.execute("ALTER TABLE item ADD subtitle_encoding TEXT")

def upgrade118(cursor):
    """Changes raw_descrption (it's mispelled) to entry_description
    and add the description column.
    """
    rename_column(cursor, "item", "raw_descrption", "entry_description")
    cursor.execute("ALTER TABLE item ADD description TEXT")

def upgrade119(cursor):
    """Drop the http_auth_password table from the database
    """
    cursor.execute("DROP TABLE http_auth_password")

def upgrade120(cursor):
    """Create the item_info_cache table"""
    cursor.execute("CREATE TABLE item_info_cache"
            "(id INTEGER PRIMARY KEY, pickle BLOB)")

def upgrade121(cursor):
    """Create the metadata column in item; reread all metadata accordingly;
    add column to item to store ratings;
    add column to view table for keeping track of enabled ListView columns
    initialize enabled columns to reasonable default
    """
    enabled_columns = [u'state', u'name', u'feed-name',
            u'artist', u'album', u'track', u'year', u'genre']
    cursor.execute("ALTER TABLE item ADD COLUMN metadata pythonrepr")
    cursor.execute("ALTER TABLE item ADD COLUMN rating integer")
    cursor.execute("ALTER TABLE widgets_frontend_state "
            "ADD COLUMN list_view_columns pythonrepr")
    cursor.execute("UPDATE widgets_frontend_state SET list_view_columns=?",
            (repr(enabled_columns),))

def upgrade122(cursor):
    """Commit 9764e4c and previous changes left metadata in a potentially
    incorrect state. This triggers a rescan of all items that claim to
    have no attached metadata to resolve the issue.
    """
    cursor.execute("UPDATE item SET metadata=NULL WHERE metadata='{}'")

def upgrade123(cursor):
    """Add field to track column widths; NULL uses defaults
    """
    cursor.execute("ALTER TABLE widgets_frontend_state "
            "ADD COLUMN list_view_column_widths pythonrepr")

def upgrade124(cursor):
    """Change dict entries in WidgetsFrontendState to rows in DisplayState.
    Values not set in WFS will be None in DS, meaning "default".
    Since we're changing columns over to display-dependent defaults,
    it's probably best to ignore existing column settings.
    """
    cursor.execute("CREATE TABLE display_state "
        "(id integer PRIMARY KEY, type text, id_ text, is_list_view integer, "
        "active_filters pythonrepr, sort_state blob, columns pythonrepr)")
    cursor.execute("CREATE INDEX display_state_display "
        "ON display_state (type, id_)")
    cursor.execute("SELECT list_view_displays, active_filters, sort_states "
        "FROM widgets_frontend_state")
    row = cursor.fetchone()
    if row is not None:
        (list_view_displays, all_active_filters, sort_states) = row
        list_view_displays = eval(list_view_displays, {})
        all_active_filters = eval(all_active_filters, {})
        sort_states = eval(sort_states, {})
    else:
        list_view_displays = {}
        all_active_filters = {}
        sort_states = {}

    displays = (set(list_view_displays) | set(all_active_filters.keys()) |
        set(sort_states.keys()))
    for display in displays:
        typ, id_ = display.split(':')
        is_list_view = None
        active_filters = None
        sort_state = None
        columns = None
        if display in list_view_displays:
            is_list_view = 1
            list_view_displays.remove(display)
        if display in all_active_filters:
            active_filters = repr(all_active_filters[display])
            del all_active_filters[display]
        if display in sort_states:
            sort_state = sort_states[display]
            del sort_states[display]
        cursor.execute("INSERT INTO display_state "
            "(id, type, id_, is_list_view, active_filters, sort_state, columns) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (get_next_id(cursor),
                typ, id_, is_list_view, active_filters, sort_state, columns))
    if list_view_displays or all_active_filters or sort_states:
        logging.warn("Values unconverted in upgrade124: (%s), (%s), (%s)" %
            (repr(list_view_displays), repr(all_active_filters),
            repr(sort_states)))
    cursor.execute("DROP TABLE widgets_frontend_state")

def upgrade125(cursor):
    """Remove old dtv:singleFeed table."""
    cursor.execute("DROP TABLE single_feed_impl")

def upgrade126(cursor):
    """Remove dtv:singleFeed data from the database.
    """
    cursor.execute("SELECT id FROM feed WHERE origURL='dtv:singleFeed'")
    row = cursor.fetchone()
    if row is not None:
        single_feed_id = row[0]
        cursor.execute("SELECT id from feed WHERE origURL='dtv:manualFeed'")
        manual_feed_id = cursor.fetchone()[0]
        cursor.execute("UPDATE item SET feed_id=? WHERE feed_id=?",
                       (manual_feed_id, single_feed_id))
        cursor.execute("DELETE FROM feed WHERE origURL='dtv:singleFeed'")

def upgrade127(cursor):
    """Add play_count and skip_count to item.
    Set them all to 0, since there's no way to know.
    """
    cursor.execute("ALTER TABLE item ADD COLUMN play_count integer")
    cursor.execute("ALTER TABLE item ADD COLUMN skip_count integer")
    cursor.execute("UPDATE item SET play_count=0, skip_count=0")

def upgrade128(cursor):
    """Add cover_art to item.
    """
    cursor.execute("ALTER TABLE item ADD COLUMN cover_art TEXT")

def upgrade129(cursor):
    """Separate DisplayState.columns into columns_enabled and column_widths
    """
    cursor.execute("SELECT id, columns FROM display_state")
    columns = {}
    for id_, column_state in cursor.fetchall():
        if column_state is None:
            name_list, width_map = None, None
        else:
            column_state = eval(column_state)
            names, widths = zip(*column_state)
            name_list = repr(list(names))
            width_map = repr(dict(column_state))
        columns[id_] = (name_list, width_map)
    remove_column(cursor, 'display_state', ['columns'])
    cursor.execute("ALTER TABLE display_state ADD COLUMN columns_enabled pythonrepr")
    cursor.execute("ALTER TABLE display_state ADD COLUMN column_widths pythonrepr")
    for id_, column_state in columns.items():
        name_list, width_map = column_state[0], column_state[1]
        cursor.execute("UPDATE display_state SET columns_enabled=?,"
            "column_widths=? WHERE id=?", (name_list, width_map, id_))

def upgrade130(cursor):
    """
    Adds a 'store' flag to the Guide table.  We'll use this for new things like
    Amazon, eMusic, etc.
    """
    cursor.execute("ALTER TABLE channel_guide ADD COLUMN store integer")
    cursor.execute('UPDATE channel_guide SET store=?', (0,)) # 0 is a regular
                                                             # site

def upgrade131(cursor):
    """Adds the Amazon MP3 Store as a site for anyone who doesn't
    already have it and isn't using a theme.
    """
    # if the user is using a theme, we don't do anything
    if not app.config.get(prefs.THEME_NAME) == prefs.THEME_NAME.default:
        return

    store_url = (u'http://www.amazon.com/b?_encoding=UTF8&site-redirect=&'
                 'node=163856011&tag=pcultureorg-20&linkCode=ur2&camp=1789&'
                 'creative=9325')
    favicon_url = u'http://www.amazon.com/favicon.ico'
    cursor.execute("SELECT count(*) FROM channel_guide WHERE url=?",
                   (store_url,))
    count = cursor.fetchone()[0]
    if count > 0:
        return

    next_id = get_next_id(cursor)

    cursor.execute("INSERT INTO channel_guide "
                   "(id, url, allowedURLs, updated_url, favicon, firstTime, "
                   "store, userTitle) "
                   "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                   (next_id, store_url, "[]", store_url,
                    favicon_url, True, 1, u"Amazon MP3 Store")) # 1 is a
                                                                # visible store

    # add the new Audio Guide to the site tablist
    cursor.execute('SELECT tab_ids FROM taborder_order WHERE type=?',
                   ('site',))
    row = cursor.fetchone()
    if row is not None:
        try:
            tab_ids = eval_container(row[0])
        except StandardError:
            tab_ids = []
        tab_ids.append(next_id)
        cursor.execute('UPDATE taborder_order SET tab_ids=? WHERE type=?',
                       (repr(tab_ids), 'site'))
    else:
        # no site taborder (#11985).  We will create the TabOrder
        # object on startup, so no need to do anything here
        pass


def upgrade132(cursor):
    base_url = "http://www.amazon.com/gp/redirect.html?ie=UTF8&location=%s&tag=pcultureorg-20&linkCode=ur2&camp=1789&creative=9325"
    favicon_url = u'http://www.amazon.com/favicon.ico'
    direct_urls = (
        ('http://www.amazon.fr/T%C3%A9l%C3%A9charger-Musique-mp3/b/ref=sa_menu_mp31?ie=UTF8&node=77196031', u'Amazon Téléchargements MP3 (FR)'),
        ('http://www.amazon.de/MP3-Musik-Downloads/b/ref=sa_menu_mp31?ie=UTF8&node=77195031', u'Amazon MP3-Downloads (DE/AT/CH)'),
        ('http://www.amazon.co.jp/MP3-%E3%83%80%E3%82%A6%E3%83%B3%E3%83%AD%E3%83%BC%E3%83%89-%E9%9F%B3%E6%A5%BD%E9%85%8D%E4%BF%A1-DRM%E3%83%95%E3%83%AA%E3%83%BC/b/ref=sa_menu_dmusic1?ie=UTF8&node=2128134051', u'Amazon MP3ダウンロード (JP)'),
        ('http://www.amazon.co.uk/MP3-Music-Download/b/ref=sa_menu_dm1?ie=UTF8&node=77197031', u'Amazon MP3 Downloads (UK)'))

    for url, name in direct_urls:
        store_url = base_url % urllib.quote(url, safe='')
        cursor.execute("SELECT count(*) FROM channel_guide WHERE url=?",
                       (store_url,))
        count = cursor.fetchone()[0]
        if count > 0:
            continue

        next_id = get_next_id(cursor)

        cursor.execute("INSERT INTO channel_guide "
                   "(id, url, allowedURLs, updated_url, favicon, firstTime, "
                   "store, userTitle) "
                   "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                   (next_id, store_url, "[]", store_url,
                    favicon_url, True, 2, name)) # 2 is a
                                                 # non-visible store

    # the stores aren't visible by default, so don't worry about putting them
    # in the taborder

def upgrade133(cursor):
    """
    Moves the tab ids from the 'audio-channel' TabOrder to the bottom of the
    'channel' TabOrder.
    """
    cursor.execute('SELECT tab_ids FROM taborder_order WHERE type=?',
                   ('audio-channel',))
    row = cursor.fetchone()
    if row is not None:
        try:
            audio_tab_ids = eval_container(row[0])
        except StandardError:
            audio_tab_ids = []
    else:
        # no audio channel tab order, so we're done
        return

    cursor.execute('DELETE FROM taborder_order WHERE type=?',
                   ('audio-channel',))


    cursor.execute('SELECT tab_ids FROM taborder_order WHERE type=?',
                   ('channel',))
    row = cursor.fetchone()
    if row is not None:
        try:
            channel_tab_ids = eval_container(row[0])
        except StandardError:
            channel_tab_ids = []
        tab_ids = channel_tab_ids + audio_tab_ids
        cursor.execute('UPDATE taborder_order SET tab_ids=? WHERE type=?',
                       (repr(tab_ids), 'channel'))
    else:
        # no channel tab order? the user is out of luck for saving their tab
        # order
        pass

def upgrade134(cursor):
    """Split item.metadata into scalar fields.
    """
    cursor.execute("SELECT id, metadata FROM item")
    items = []
    for id_, metadata in cursor.fetchall():
        try:
            data = eval(metadata)
        except TypeError:
            data = {}
        album = data.get('album', None)
        artist = data.get('artist', None)
        title_tag = data.get('title', None)
        track = data.get('track', None)
        year = data.get('year', None)
        genre = data.get('genre', None)
        items.append((album, artist, title_tag, track, year, genre, id_))
    remove_column(cursor, 'item', ['metadata'])
    cursor.execute("ALTER TABLE item ADD COLUMN album text")
    cursor.execute("ALTER TABLE item ADD COLUMN artist text")
    cursor.execute("ALTER TABLE item ADD COLUMN title_tag text")
    cursor.execute("ALTER TABLE item ADD COLUMN track integer")
    cursor.execute("ALTER TABLE item ADD COLUMN year integer")
    cursor.execute("ALTER TABLE item ADD COLUMN genre text")
    for data in items:
        cursor.execute("UPDATE item SET album=?, artist=?, title_tag=?,"
            "track=?, year=?, genre=? WHERE id=?", data)
 
def upgrade135(cursor):
    """Basic metadata versioning
    """
    cursor.execute("ALTER TABLE item ADD COLUMN metadata_version integer")
    cursor.execute("UPDATE item SET metadata_version=1")
    cursor.execute("UPDATE item SET metadata_version=0 WHERE album IS NULL AND "
        "artist IS NULL AND title_tag IS NULL AND track IS NULL AND year IS NULL "
        "AND genre IS NULL")

def upgrade136(cursor):
    """Create ViewState; move some things from DisplayState to
    ViewState; drop some orphaned DisplayState entries.
    """
    cursor.execute("DELETE FROM display_state WHERE id_ IS NULL")
    remove_column(cursor, 'display_state', ['sort_state', 'is_list_view'])
    rename_column(cursor, 'display_state', 'columns_enabled', 'list_view_columns')
    rename_column(cursor, 'display_state', 'column_widths', 'list_view_widths')
    cursor.execute("ALTER TABLE display_state ADD COLUMN selected_view integer")
    cursor.execute("CREATE TABLE view_state (id integer PRIMARY KEY, "
        "display_type text, display_id text, view_type integer, "
        "sort_state text, scroll_position pythonrepr)")
    cursor.execute("CREATE INDEX view_state_key ON view_state "
        "(display_type, display_id, view_type)")

def upgrade137(cursor):
    """Change filters to integers
    """
    remove_column(cursor, 'display_state', ['active_filters'])
    cursor.execute("ALTER TABLE display_state ADD active_filters integer")

def upgrade138(cursor):
    """Support album_artist field.
    """
    cursor.execute("ALTER TABLE item ADD COLUMN album_artist text")

def upgrade139(cursor):
    """Add ViewState field for selection."""
    cursor.execute("ALTER TABLE view_state ADD COLUMN selection pythonrepr")

def upgrade140(cursor):
    """Add shuffle/repeat states to DisplayState
    """
    cursor.execute("ALTER TABLE display_state ADD COLUMN shuffle integer")
    cursor.execute("ALTER TABLE display_state ADD COLUMN repeat integer")

def upgrade141(cursor):
    """Removes the fast_resume_data column.
    """
    remove_column(cursor, 'remote_downloader', ['fast_resume_data'])

def upgrade142(cursor):
    """Move selection from view_state to display_state"""
    remove_column(cursor, 'view_state', ['selection'])
    cursor.execute("ALTER TABLE display_state ADD COLUMN selection pythonrepr")

def upgrade143(cursor):
    """Move sort_state from view_state to display_state"""
    remove_column(cursor, 'view_state', ['sort_state'])
    cursor.execute("ALTER TABLE display_state ADD COLUMN sort_state text")

def upgrade144(cursor):
    cursor.execute("ALTER TABLE item ADD COLUMN has_drm integer")

def upgrade145(cursor):
    cursor.execute("ALTER TABLE display_state "
            "ADD COLUMN last_played_item_id integer")

def upgrade146(cursor):
    cursor.execute("ALTER TABLE item ADD COLUMN album_tracks integer")
    # starting a couple commits in the future, ratings are stored as 1-5:
    cursor.execute("UPDATE item SET rating = rating + 1 WHERE rating IS NOT NULL")

def upgrade147(cursor):
    """Add global widget state"""
    cursor.execute("CREATE TABLE global_state (id integer PRIMARY KEY, "
            "item_details_expanded integer)")

def upgrade148(cursor):
    """Make item_details_expanded a dict"""
    # Nuke the global state data so that we get the default values after this
    # upgrade
    cursor.execute("DELETE FROM global_state")
    # change item_details_expanded to a pythonrepr column, so that we can use
    # SchemaDict with it
    rename_column(cursor, 'global_state', 'item_details_expanded',
            'item_details_expanded', 'pythonrepr')

def upgrade149(cursor):
    """Add some Video properties (now settable in Edit Item)"""
    cursor.execute("ALTER TABLE item ADD COLUMN show text")
    cursor.execute("ALTER TABLE item ADD COLUMN episode_id text")
    cursor.execute("ALTER TABLE item ADD COLUMN episode_number integer")
    cursor.execute("ALTER TABLE item ADD COLUMN season_number integer")

def upgrade150(cursor):
    """Add Kind field (for Video categories)"""
    cursor.execute("ALTER TABLE item ADD COLUMN kind text")

def upgrade151(cursor):
    """Add table for root node expansion state of hideable tabs."""
    cursor.execute("CREATE TABLE hideable_tab (id integer PRIMARY KEY, "
            "expanded integer, type text)")
    cursor.execute("CREATE INDEX hideable_tab_type ON hideable_tab (type)")

def upgrade152(cursor):
    #removed upgrade
    pass

def upgrade153(cursor):
    """
    Adds the lastWatched column to Item, and sets its value to that of
    'watchedTime'.
    """
    cursor.execute("ALTER TABLE item ADD COLUMN lastWatched timestamp")
    cursor.execute("UPDATE item SET lastWatched=watchedTime")

def upgrade154(cursor):
    """
    Adds the Amazon and Google Android stores.
    """
        # if the user is using a theme, we don't do anything
    if not app.config.get(prefs.THEME_NAME) == prefs.THEME_NAME.default:
        return

    new_ids = []
    for name, store_url, favicon_url in (
        (u"Amazon Android Store",
         u"http://www.amazon.com/gp/redirect.html?ie=UTF8&location="
         u"http%3A%2F%2Fwww.amazon.com%2Fmobile-apps%2Fb%3Fie%3DUTF8"
         u"%26node%3D2350149011&tag=pcultureorg-20&linkCode=ur2&camp="
         u"1789&creative=9325", u'http://www.amazon.com/favicon.ico'),
        (u"Google Android Store", u"http://market.android.com/",
         u"https://market.android.com/static/client/images/favicon.ico")):
        cursor.execute("SELECT count(*) FROM channel_guide WHERE url=?",
                   (store_url,))
        count = cursor.fetchone()[0]
        if count > 0:
            continue

        next_id = get_next_id(cursor)

        cursor.execute("INSERT INTO channel_guide "
                       "(id, url, allowedURLs, updated_url, favicon, "
                       "firstTime, store, userTitle) "
                       "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                       (next_id, store_url, "[]", store_url,
                        favicon_url, True, 1, name)) # 1 is a visible store
        new_ids.append(next_id)

    cursor.execute('SELECT tab_ids FROM taborder_order WHERE type=?',
                   ('site',))
    row = cursor.fetchone()
    if row is not None:
        try:
            tab_ids = eval_container(row[0])
        except StandardError:
            tab_ids = []
        tab_ids.extend(new_ids)
        cursor.execute('UPDATE taborder_order SET tab_ids=? WHERE type=?',
                       (repr(tab_ids), 'site'))
    else:
        # no site taborder (#11985).  We will create the TabOrder
        # object on startup, so no need to do anything here
        pass

def upgrade155(cursor):
    """Reset display_state.selection, since the format changed."""
    cursor.execute("UPDATE display_state SET selection=NULL")

def upgrade156(cursor):
    """drop media_type_checked; add mdp_state; change duration==-1 to None.

    Set mdp_state where we can tell it's been run or _should_process_item would
    definitely return False; there may be less clear cases that will be
    reexamined.
    """
    # media_type_checked is not useful now that we track more specifically
    remove_column(cursor, 'item', ['media_type_checked'])

    # the difference between where it's currently -1 and None does not seem to
    # provide useful information, so just dropping it
    cursor.execute("UPDATE item SET duration=NULL WHERE duration == -1")

    # the new system
    cursor.execute("ALTER TABLE item ADD COLUMN mdp_state integer")

    # setting mdp_state==State.RAN where we can be sure it's already been run:
    cursor.execute("UPDATE item SET mdp_state=1 WHERE "
            "(screenshot IS NOT NULL)")

    # and marking State.SKIPPED where it can clearly be (has been) skipped:
    cursor.execute("UPDATE item SET mdp_state=0 WHERE "
            "file_type == 'other'")
    cursor.execute("UPDATE item SET mdp_state=0 WHERE "
            "(duration IS NOT NULL) AND file_type != 'video'")

def upgrade157(cursor):
    """Delete Items without filenames (#17306) - these invalid items are
    probably coming from Miro <= 3.5.1
    """
    # this was:
    # cursor.execute("DELETE FROM item WHERE filename IS NULL OR filename = ''")
    # but that's insane because it whacks all podcast history of what
    # miro has seen!
    pass

def upgrade158(cursor):
    cursor.execute("ALTER TABLE global_state ADD COLUMN guide_sidebar_expanded integer")
    cursor.execute("UPDATE global_state SET guide_sidebar_expanded=1")

def upgrade159(cursor):
    """Get rid of bad dropdown field values created by revisions prior to
    9113dbb (#17450).
    """
    # if file_type has been borked, we have to rerun MDP to fix it
    cursor.execute("UPDATE item SET mdp_state=NULL, file_type=NULL "
            "WHERE file_type='_mixed'")
    # for video kind, just drop the bad data
    cursor.execute("UPDATE item SET kind=NULL WHERE kind='_mixed'")
    # rating is unaffected because it's an integer

def upgrade160(cursor):
    cursor.execute("ALTER TABLE global_state ADD COLUMN tabs_width integer")
    cursor.execute("UPDATE global_state SET tabs_width=200")

def upgrade161(cursor):
    """Set the album view data to widget state tables ."""
    # update item_details_expanded
    ALBUM_VIEW = 3

    cursor.execute("SELECT item_details_expanded FROM global_state")
    row = cursor.fetchone()
    if row is None:
        # defaults not set yet, just ignore
        return
    item_details_expanded = eval(row[0])
    item_details_expanded[ALBUM_VIEW] = False
    cursor.execute("UPDATE global_state set item_details_expanded=?",
            (repr(item_details_expanded),))

def upgrade162(cursor):
    """Convert the active_filters column to string values."""

    FILTER_VIEW_ALL = 0
    FILTER_UNWATCHED = 1
    FILTER_NONFEED = 2
    FILTER_DOWNLOADED = 4
    FILTER_VIEW_VIDEO = 8
    FILTER_VIEW_AUDIO = 16
    FILTER_VIEW_MOVIES = 32
    FILTER_VIEW_SHOWS = 64
    FILTER_VIEW_CLIPS = 128
    FILTER_VIEW_PODCASTS = 256

    # map the old integer constants to strings.  Rename "unwatched" to
    # "unplayed" since we've done it other places so we might as well do it
    # here during the upgrade.
    value_map = {
            FILTER_VIEW_ALL: 'all',
            FILTER_UNWATCHED: 'unplayed',
            FILTER_NONFEED: 'nonfeed',
            FILTER_DOWNLOADED: 'downloaded',
            FILTER_VIEW_VIDEO: 'video',
            FILTER_VIEW_AUDIO: 'audio',
            FILTER_VIEW_MOVIES: 'movies',
            FILTER_VIEW_SHOWS: 'shows',
            FILTER_VIEW_CLIPS: 'clips',
            FILTER_VIEW_PODCASTS: 'podcasts',
    }

    # convert old int values to strings
    converted_values = []
    cursor.execute("SELECT type, id_, active_filters FROM display_state")
    for row in cursor.fetchall():
        type, id_, active_filters = row
        if active_filters is None:
            continue
        filters = []
        for int_value, string_value in value_map.iteritems():
            if active_filters & int_value:
                filters.append(string_value)
        new_active_filters = ":".join(filters)
        converted_values.append((type, id_, new_active_filters))
    # drop old integer column
    remove_column(cursor, 'display_state', ['active_filters'])
    # add new text column
    cursor.execute("ALTER TABLE display_state ADD COLUMN active_filters text")
    # fill in the new values
    for (type, id_, new_active_filters) in converted_values:
        cursor.execute("UPDATE display_state "
                "SET active_filters=? "
                "WHERE type = ? AND id_ = ?",
                (new_active_filters, type, id_))

def upgrade163(cursor):
    """Add eMusic as a store."""
        # if the user is using a theme, we don't do anything
    if not app.config.get(prefs.THEME_NAME) == prefs.THEME_NAME.default:
        return

    store_url = u'http://www.kqzyfj.com/click-5294129-10364534'
    favicon_url = u'http://www.emusic.com/favicon.ico'
    cursor.execute("SELECT count(*) FROM channel_guide WHERE url=?",
                   (store_url,))
    count = cursor.fetchone()[0]
    if count > 0:
        return

    next_id = get_next_id(cursor)

    cursor.execute("INSERT INTO channel_guide "
                   "(id, url, allowedURLs, updated_url, favicon, firstTime, "
                   "store, userTitle) "
                   "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                   (next_id, store_url, "[]", store_url,
                    favicon_url, True, 1, u"eMusic")) # 1 is a visible store

    cursor.execute('SELECT tab_ids FROM taborder_order WHERE type=?',
                   ('site',))
    row = cursor.fetchone()
    if row is not None:
        try:
            tab_ids = eval_container(row[0])
        except StandardError:
            tab_ids = []
        tab_ids.append(next_id)
        cursor.execute('UPDATE taborder_order SET tab_ids=? WHERE type=?',
                       (repr(tab_ids), 'site'))
    else:
        # no site taborder (#11985).  We will create the TabOrder
        # object on startup, so no need to do anything here
        pass

def upgrade164(cursor):
    """Move column info from DisplayState to ViewState.

    This makes it easier to store different data for list, album, and standard
    view.
    """

    # view type constants
    STANDARD_VIEW = 0
    LIST_VIEW = 1
    ALBUM_VIEW = 3

    # make new columns in view state
    cursor.execute("ALTER TABLE view_state "
            "ADD COLUMN columns_enabled pythonrepr")
    cursor.execute("ALTER TABLE view_state "
            "ADD COLUMN column_widths pythonrepr")

    # copy data from display_state
    cursor.execute("UPDATE view_state "
            "SET columns_enabled = "
            "(SELECT list_view_columns FROM display_state "
            "WHERE display_state.type=view_state.display_type AND "
            "display_state.id_ = view_state.display_id) "
            "WHERE view_type in (?, ?, ?)",
            (STANDARD_VIEW, LIST_VIEW, ALBUM_VIEW))
    cursor.execute("UPDATE view_state "
            "SET column_widths = "
            "(SELECT list_view_widths FROM display_state "
            "WHERE display_state.type=view_state.display_type AND "
            "display_state.id_ = view_state.display_id) "
            "WHERE view_type in (?, ?)", (LIST_VIEW, ALBUM_VIEW))
    # drop old columns
    remove_column(cursor, 'display_state', ['list_view_columns'])
    remove_column(cursor, 'display_state', ['list_view_widths'])

def upgrade165(cursor):
    """Add lots of indexes."""
    indices = [
      ('playlist_item_map_item_id', 'playlist_item_map', 'item_id'),
      ('playlist_folder_item_map_item_id', 'playlist_folder_item_map',
       'item_id'),
      ('feed_impl_key', 'feed', 'feed_impl_id')
    ]
    for n, t, c in indices:
        cursor.execute("CREATE INDEX %s ON %s (%s)" % (n, t, c))

def upgrade166(cursor):
    """Create the metadata table and migrate data from item to it."""

    # create new tables
    cursor.execute("""
    CREATE TABLE metadata_status (id integer PRIMARY KEY, path text,
                                  mutagen_status text, moviedata_status text,
                                  mutagen_thinks_drm integer,
                                  max_entry_priority integer)
                   """)
    cursor.execute("""\
    CREATE TABLE metadata (id integer PRIMARY KEY, path text, source text,
                           priority integer, file_type text, duration integer,
                           album text, album_artist text, album_tracks
                           integer, artist text, cover_art_path text,
                           screenshot_path text, drm integer, genre text,
                           title text, track integer, year integer,
                           description text, rating integer, show text,
                           episode_id text, episode_number integer,
                           season_number integer, kind text)
                   """)
    cursor.execute("CREATE INDEX metadata_mutagen ON metadata_status "
                   "(mutagen_status)")
    cursor.execute("CREATE INDEX metadata_moviedata ON metadata_status "
                   "(moviedata_status)")
    cursor.execute("CREATE UNIQUE INDEX metadata_path ON metadata_status "
                   "(path)")
    cursor.execute("CREATE INDEX metadata_entry_path ON metadata (path)")
    cursor.execute("CREATE UNIQUE INDEX metadata_entry_path_and_source "
                   "ON metadata (path, source)")
    # add new index to item
    cursor.execute("CREATE INDEX item_filename ON item (filename)")


    # map old MDP states to their new values
    mdp_state_map = {
        None : 'N',
        0 : 'S',
        1 : 'C',
        2 : 'F',
    }

    # currently get_title() returns the contents of title and falls back on
    # title_tag.  Set the title column to be that value for the conversion.
    # As a side-effect this makes the title column the same as what
    # get_metadata() would return.
    cursor.execute("UPDATE item SET title=title_tag "
                   "WHERE title IS NULL OR title == ''")

    # map columns in metadata table to their old name in item
    column_map = {
        'path': 'filename',
        'file_type': 'file_type',
        'duration': 'duration',
        'album': 'album',
        'album_artist': 'album_artist',
        'album_tracks': 'album_tracks',
        'artist':'artist',
        'cover_art_path': 'cover_art',
        'screenshot_path': 'screenshot',
        'drm': 'has_drm',
        'genre': 'genre',
        'title ': 'title',
        'track': 'track',
        'year': 'year',
        'description': 'description',
        'rating': 'rating',
        'show': 'show',
        'episode_id': 'episode_id',
        'episode_number': 'episode_number',
        'season_number': 'season_number',
        'kind': 'kind',
    }

    insert_columns = ['id', 'source', 'priority']
    select_columns = ['mdp_state']

    filenames_seen = set()

    for key, value in column_map.items():
        insert_columns.append(key)
        select_columns.append(value)
    sql = "SELECT %s FROM item WHERE filename NOT NULL ORDER BY id ASC" % (
        ', '.join(select_columns))
    next_id = get_next_id(cursor)
    filename_index = select_columns.index('filename')
    has_drm_index = select_columns.index('has_drm')
    for row in list(cursor.execute(sql)):
        path = row[filename_index]
        has_drm = row[has_drm_index]
        if path in filenames_seen:
            # duplicate filename, just skip this data
            continue
        else:
            filenames_seen.add(path)
        # Make an entry in the metadata table with the metadata that was
        # stored.  We don't know if it came from mutagen, movie data, torrent
        # data or wherever, so we use "old-item" as the source and give it a
        # low priority.
        values = [next_id, 'old-item', 10]
        for old_value in row[1:]:
            if old_value != '':
                values.append(old_value)
            else:
                values.append(None)
        mdp_state = row[0]
        sql = "INSERT INTO metadata (%s) VALUES (%s)" % (
            ', '.join(insert_columns),
            ', '.join('?' for i in xrange(len(insert_columns))))
        cursor.execute(sql, values)
        next_id += 1

        OLD_ITEM_PRIORITY = 10
        # Make an entry in the metadata_status table.  We're not sure if
        # mutagen completed successfully or not, so we just call its status
        # SKIPPED.  moviedata_status is based on the old mdp_state column
        sql = ("INSERT INTO metadata_status "
               "(id, path, mutagen_status, moviedata_status, "
               "mutagen_thinks_drm, max_entry_priority) "
               "VALUES (?, ?, ?, ?, ?, ?)")
        cursor.execute(sql, (next_id, path, 'S', mdp_state_map[mdp_state],
                             has_drm, OLD_ITEM_PRIORITY))
        next_id += 1

    # We need to alter the item table to:
    #   - drop the columns now handled by metadata_status
    #   - make column names match the keys in MetadataManager.get_metadata()
    #   - add a new column for torrent titles

    rename_columns={
        'cover_art': 'cover_art_path',
        'screenshot': 'screenshot_path',
    }
    delete_columns=['mdp_state', 'metadata_version', 'title_tag']
    alter_table_columns(cursor, 'item', delete_columns, rename_columns)

    cursor.execute("ALTER TABLE item ADD torrent_title TEXT")

def upgrade167(cursor):
    """Drop the cover_art_path on the metadata table."""

    cover_art_dir = app.config.get(prefs.COVER_ART_DIRECTORY)

    # Move all current cover art so that it's in at the path
    # <support-dir>/cover-art/<album-name>
    already_moved = set()
    cursor.execute("SELECT path, album, cover_art_path from metadata "
                   "WHERE cover_art_path IS NOT NULL AND "
                      "album IS NOT NULL")
    for (path, album, cover_art_path) in cursor.fetchall():
        # quote the filename using the same logic as
        # filetags.calc_cover_art_filename()
        dest_filename = urllib.quote(album.encode('utf-8'), safe=' ,.')
        dest_path = os.path.join(cover_art_dir, dest_filename)

        if album in already_moved:
            cursor.execute("UPDATE item SET cover_art_path=? "
                           "WHERE filename=?", (dest_path, path))
            try:
                os.remove(cover_art_path)
            except StandardError:
                logging.warn("upgrade167: Error deleting %s", cover_art_path)
            continue
        if not os.path.exists(cover_art_path):
            logging.warn("upgrade167: Error moving cover art.  Source path "
                         "doesn't exist: %s", cover_art_path)
            continue
        try:
            shutil.move(cover_art_path, dest_path)
        except StandardError:
            logging.warn("upgrade167: Error moving %s -> %s", cover_art_path,
                         dest_path)
            # update item table
            cursor.execute("UPDATE item SET cover_art_path=NULL "
                           "WHERE filename=?", (path,))
        else:
            # update item table
            cursor.execute("UPDATE item SET cover_art_path=? "
                           "WHERE filename=?", (dest_path, path))

            already_moved.add(album)

    # Now that the cover art is in the correct place, we don't need to store
    # it in the database anymore.
    remove_column(cursor, 'metadata', ['cover_art_path'])

def upgrade168(cursor):
    """Add echonest_status and echonest_id."""
    # make the columns
    cursor.execute("ALTER TABLE metadata_status "
                   "ADD COLUMN echonest_status text")
    cursor.execute("ALTER TABLE metadata_status "
                   "ADD COLUMN echonest_id text")
    # Set status to SKIPPED since the user didn't opt-in to internet
    # lookups
    cursor.execute("UPDATE metadata_status "
                   "SET echonest_status='S'")

def upgrade169(cursor):
    """Add disabled to metadata."""
    cursor.execute("ALTER TABLE metadata "
                   "ADD COLUMN disabled integer")
    cursor.execute("UPDATE metadata SET disabled=0")

def upgrade170(cursor):
    """Add net_lookup_enabled."""
    cursor.execute("ALTER TABLE metadata_status "
                   "ADD COLUMN net_lookup_enabled integer")
    cursor.execute("ALTER TABLE item "
                   "ADD COLUMN net_lookup_enabled integer")
    cursor.execute("UPDATE item SET net_lookup_enabled=0")

def upgrade171(cursor):
    """Add current_processor and calculate its value."""

    cursor.execute("ALTER TABLE metadata_status "
                   "ADD COLUMN current_processor TEXT")
    STATUS_NOT_RUN = 'N'

    cursor.execute("UPDATE metadata_status SET current_processor=? "
                   "WHERE mutagen_status == ?", (u'mutagen', STATUS_NOT_RUN))

    cursor.execute("UPDATE metadata_status SET current_processor=? "
                   "WHERE mutagen_status != ? AND moviedata_status == ?",
                   (u'movie-data', STATUS_NOT_RUN, STATUS_NOT_RUN))

    cursor.execute("UPDATE metadata_status SET current_processor=? "
                   "WHERE mutagen_status != ? AND moviedata_status != ? AND "
                   "echonest_status == ?", (u'echonest', STATUS_NOT_RUN,
                                            STATUS_NOT_RUN, STATUS_NOT_RUN))

    cursor.execute("DROP INDEX metadata_mutagen")
    cursor.execute("DROP INDEX metadata_moviedata")
    cursor.execute("CREATE INDEX metadata_processor "
                   "ON metadata_status (current_processor)")

def upgrade172(cursor):
    """Remove the path column from the metadata table."""
    # Create new column and set it based on the old path column
    cursor.execute("ALTER TABLE metadata ADD COLUMN status_id integer")
    cursor.execute("UPDATE metadata SET status_id = "
                   "(SELECT metadata_status.id FROM metadata_status "
                   "WHERE metadata_status.path=metadata.path)")
    # Delete any rows that don't have an associated metadata_status.  This
    # shouldn't be any, but delete just in case
    cursor.execute("DELETE FROM metadata "
                   "WHERE NOT EXISTS "
                   "(SELECT metadata_status.id FROM metadata_status "
                   "WHERE metadata_status.path=metadata.path)")
    # Fix indexes
    cursor.execute("DROP INDEX metadata_entry_path")
    cursor.execute("DROP INDEX metadata_entry_path_and_source")
    cursor.execute("CREATE INDEX metadata_entry_status "
                   "ON metadata (status_id)")
    cursor.execute("CREATE UNIQUE INDEX metadata_entry_status_and_source "
                   "ON metadata (status_id, source)")
    # drop old column
    remove_column(cursor, 'metadata', 'path')

def upgrade173(cursor):
    """Make sure net_lookup_enabled is always non-null."""
    # This code should have been in upgrade170, but it's okay to run it now

    cursor.execute("UPDATE metadata_status SET net_lookup_enabled=0 "
                   "WHERE net_lookup_enabled IS NULL")

def upgrade174(cursor):
    """Set some echonest_status to STATUS_SKIP_FROM_PREF instead of skipped."""

    # for audio files, echonest_status should be STATUS_SKIP_FROM_PREF so that
    # if the user enables echonest for that file it will run.  We keep
    # video/other items as STATUS_SKIP, so that echonest will never run.
    cursor.execute("UPDATE metadata_status SET echonest_status='P' "
                   "WHERE id IN "
                      "(SELECT status_id FROM metadata "
                      "WHERE source = "
                          "(SELECT source FROM metadata "
                          "WHERE status_id=status_id AND "
                          "file_type IS NOT NULL "
                          "ORDER BY priority DESC LIMIT 1) AND "
                      "file_type = 'audio')")

def upgrade175(cursor):
    """Rename screenshot_path and cover_art_path back to their old names."""

    rename_column(cursor, 'metadata', 'screenshot_path', 'screenshot')
    alter_table_columns(cursor, 'item', [], rename_columns={
        'screenshot_path': 'screenshot',
        'cover_art_path': 'cover_art',
    })

def upgrade176(cursor):
    """Add file_type to metadata_status."""
    # Add file_type to metadata_status and set it to the file_type from the
    # metadata table
    cursor.execute("ALTER TABLE metadata_status ADD file_type TEXT")
    cursor.execute("UPDATE metadata_status "
                   "SET file_type=("
                      "SELECT file_type FROM metadata "
                      "WHERE status_id=metadata_status.id AND "
                      "file_type IS NOT NULL "
                      "ORDER BY priority DESC LIMIT 1)")
    # Set file_type to other for items that the subquery returned 0 rows for
    cursor.execute("UPDATE metadata_status SET file_type='other' "
                   "WHERE file_type IS NULL")

def upgrade177(cursor):
    """Add finished_status, remove current_processor from metadata_status."""
    cursor.execute("ALTER TABLE metadata_status ADD finished_status INTEGER")
    # set finished_status to 1 (the current versionas of 5.0) if
    # current_processor was None
    cursor.execute("UPDATE metadata_status "
                   "SET finished_status=1 "
                   "WHERE current_processor IS NULL")
    # set finished_status to 0 (unfinished) for all other rows)
    cursor.execute("UPDATE metadata_status "
                   "SET finished_status=0 "
                   "WHERE current_processor IS NOT NULL")
    cursor.execute("CREATE INDEX metadata_finished ON "
                   "metadata_status (finished_status)")
    # drop the current_processor column
    cursor.execute("DROP INDEX metadata_processor")
    remove_column(cursor, 'metadata_status', ['current_processor'])

def upgrade178(cursor):
    """Remove metadata for items flaged as deleted."""
    cursor.execute("DELETE FROM metadata WHERE status_id IN "
                   "(SELECT ms.id FROM metadata_status ms "
                   "JOIN item on ms.path = item.filename "
                   "WHERE item.deleted)")
    cursor.execute("DELETE FROM metadata_status WHERE path IN "
                   "(SELECT filename FROM item WHERE item.deleted)")

def upgrade179(cursor):
    # Rename title -> metadata_title and add a title column that stores the
    # computed title (AKA what get_title() returned)

    # translated from Item.get_title() circa 5ed4c4a6
    def get_title(metadata_title, torrent_title, entry_title, filename):
        if metadata_title:
            return metadata_title
        elif torrent_title is not None:
            return torrent_title
        elif entry_title is not None:
            return entry_title
        elif filename:
            return filename_to_unicode(os.path.basename(filename))
        else:
            return _('no title')
    cursor.execute("ALTER TABLE item ADD COLUMN metadata_title text")
    cursor.execute("UPDATE item SET metadata_title=title")
    cursor.execute("SELECT id, metadata_title, torrent_title, entry_title, "
                   "filename FROM item")
    rows = cursor.fetchall()
    for id_, metadata_title, torrent_title, entry_title, filename in rows:
        title = get_title(metadata_title, torrent_title, entry_title,
                          filename)
        if title != metadata_title:
            cursor.execute("UPDATE item SET title=? WHERE id=?", (title, id_))

def upgrade180(cursor):
    # Rename columns in the item table
    rename_columns = {
        'autoDownloaded': 'auto_downloaded',
        'pendingManualDL': 'pending_manual_download',
        'pendingReason': 'pending_reason',
        'creationTime': 'creation_time',
        'linkNumber': 'link_number',
        'downloadedTime': 'downloaded_time',
        'watchedTime': 'watched_time',
        'lastWatched': 'last_watched',
        'isContainerItem': 'is_container_item',
        'releaseDateObj': 'release_date',
        'eligibleForAutoDownload': 'eligible_for_autodownload',
        'resumeTime': 'resume_time',
        'channelTitle': 'channel_title',
        'shortFilename': 'short_filename',
        'offsetPath': 'offset_path',
    }

    alter_table_columns(cursor, 'item', [], rename_columns)

def upgrade181(cursor):
    """Drop the feed.last_viewed column and add item.new.

    This means we can tell an item's state without data from the feed table.
    """
    cursor.execute("ALTER TABLE item ADD COLUMN new integer")
    # These next lines set new=1 for all items that would have matched the
    # feed_available_view() before.
    # Make a subquery for items that were created after we last viewed a feed
    subquery = ("SELECT item.id "
                "FROM item "
                "JOIN feed "
                "ON feed.id = item.feed_id "
                "WHERE feed.last_viewed <= item.creation_time")
    cursor.execute("UPDATE item SET new=1 "
                   "WHERE NOT auto_downloaded AND "
                   "downloaded_time IS NULL AND "
                   "NOT is_file_item AND "
                   "id in (%s)" % subquery)
    # remove the last_viewed column
    remove_column(cursor, 'feed', ['last_viewed'])

def upgrade182(cursor):
    """Unroll the remote_downloader.status column """

    cursor.execute("ALTER TABLE remote_downloader "
                   "ADD COLUMN total_size integer")
    cursor.execute("ALTER TABLE remote_downloader "
                   "ADD COLUMN current_size integer")
    cursor.execute("ALTER TABLE remote_downloader "
                   "ADD COLUMN start_time integer")
    cursor.execute("ALTER TABLE remote_downloader "
                   "ADD COLUMN end_time integer")
    cursor.execute("ALTER TABLE remote_downloader "
                   "ADD COLUMN short_filename text")
    cursor.execute("ALTER TABLE remote_downloader "
                   "ADD COLUMN filename text")
    cursor.execute("ALTER TABLE remote_downloader "
                   "ADD COLUMN reason_failed text")
    cursor.execute("ALTER TABLE remote_downloader "
                   "ADD COLUMN short_reason_failed text")
    cursor.execute("ALTER TABLE remote_downloader "
                   "ADD COLUMN type text")
    cursor.execute("ALTER TABLE remote_downloader "
                   "ADD COLUMN retry_time timestamp")
    cursor.execute("ALTER TABLE remote_downloader "
                   "ADD COLUMN retry_count integer")
    cursor.execute("ALTER TABLE remote_downloader "
                   "ADD COLUMN upload_size integer")
    cursor.execute("ALTER TABLE remote_downloader "
                   "ADD COLUMN info_hash text")
    columns = [ 'total_size', 'current_size', 'start_time', 'end_time',
               'short_filename', 'filename', 'retry_time', 'retry_count',
               'upload_size', 'info_hash', 'reason_failed',
               'short_reason_failed', 'type',
              ]
    # map new column names to their old keys in the status dict
    rename_map = {
        'short_filename': 'shortFilename',
        'short_reason_failed': 'shortReasonFailed',
        'reason_failed': 'reasonFailed',
        'type': 'dlerType',
        'start_time': 'startTime',
        'end_time': 'endTime',
        'retry_time': 'retryTime',
        'retry_count': 'retryCount',
        'channel_name': 'channelName',
        'current_size': 'currentSize',
        'total_size': 'totalSize',
        'upload_size': 'uploadSize',
    }

    cursor.execute("SELECT id, status from remote_downloader")
    update_sql = ("UPDATE remote_downloader SET %s WHERE id=?" %
                  ", ".join("%s=? " % name for name in columns))
    for id_, status_repr in cursor.fetchall():
        try:
            status = eval(status_repr, {}, {'datetime': datetime})
        except StandardError:
            logging.warn("Error evaluating status repr: %r" % status_repr)
            continue
        values = []
        for column in columns:
            status_key = rename_map.get(column, column)
            value = status.get(status_key)
            # Most of the time we can just use the value from status column,
            # but for some special cases we need to tweak it.
            if (column == 'end_time' and
                value == status.get('startTime')):
                value = None
            elif column in ('current_size', 'upload_size') and value is None:
                value = 0
            elif column in ('retry_count', 'total_size') and value == -1:
                value = None
            elif (column in ['start_time', 'end_time'] and value is not None):
                value = int(value)
            values.append(value)
        values.append(id_)
        cursor.execute(update_sql, values)

    remove_column(cursor, 'remote_downloader', ['status'])

def upgrade183(cursor):
    """Rename downloader columns to use PEP 8."""
    rename_columns = {
        'contentType': 'content_type',
        'origURL': 'orig_url',
        'channelName': 'channel_name',
    }
    alter_table_columns(cursor, 'remote_downloader', [], rename_columns)
    # as long as we're changing origURL, change if for feed too
    rename_column(cursor, 'feed', 'origURL', 'orig_url')

def upgrade184(cursor):
    """Drop the seen column from item."""
    remove_column(cursor, 'item', ['seen'])

def upgrade185(cursor):
    """Use NULL for empty item descriptions."""
    cursor.execute("UPDATE item SET description=NULL WHERE description=''")

def upgrade186(cursor):
    """Add columns no the remote_downloader table to track stats."""

    cursor.execute("ALTER TABLE remote_downloader ADD COLUMN eta integer")
    cursor.execute("ALTER TABLE remote_downloader ADD COLUMN rate integer")
    cursor.execute("ALTER TABLE remote_downloader "
                   "ADD COLUMN upload_rate integer")
    cursor.execute("ALTER TABLE remote_downloader ADD COLUMN activity text")
    cursor.execute("ALTER TABLE remote_downloader "
                   "ADD COLUMN seeders integer")
    cursor.execute("ALTER TABLE remote_downloader "
                   "ADD COLUMN leechers integer")
    cursor.execute("ALTER TABLE remote_downloader "
                   "ADD COLUMN connections integer")

def upgrade187(cursor):
    """Add the item_fts table"""

    columns = ['title', 'description', 'artist', 'album', 'genre',
               'filename', ]
    column_list = ', '.join(c for c in columns)
    column_list_for_new = ', '.join("new.%s" % c for c in columns)
    column_list_with_types = ', '.join('%s text' % c for c in columns)
    cursor.execute("CREATE VIRTUAL TABLE item_fts USING fts4"
                   "(content='item', %s)" % column_list_with_types)
    cursor.execute("INSERT INTO item_fts(docid, %s)"
                   "SELECT item.id, %s FROM item" %
                   (column_list, column_list))
    # make triggers to keep item_fts up to date
    cursor.execute("CREATE TRIGGER item_bu "
                   "BEFORE UPDATE ON item BEGIN "
                   "DELETE FROM item_fts WHERE docid=old.id; "
                   "END;")

    cursor.execute("CREATE TRIGGER item_bd "
                   "BEFORE DELETE ON item BEGIN "
                   "DELETE FROM item_fts WHERE docid=old.id; "
                   "END;")

    cursor.execute("CREATE TRIGGER item_au "
                   "AFTER UPDATE ON item BEGIN "
                   "INSERT INTO item_fts(docid, %s) "
                   "VALUES(new.id, %s); "
                   "END;" % (column_list, column_list_for_new))

    cursor.execute("CREATE TRIGGER item_ai "
                   "AFTER INSERT ON item BEGIN "
                   "INSERT INTO item_fts(docid, %s) "
                   "VALUES(new.id, %s); "
                   "END;" % (column_list, column_list_for_new))
