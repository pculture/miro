# Miro - an RSS based video player application
# Copyright (C) 2005-2010 Participatory Culture Foundation
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
import time
import urllib

from miro import schema
from miro import util
import types
from miro import config
from miro import dbupgradeprogress
from miro import prefs

# looks nicer as a return value
NO_CHANGES = set()

class DatabaseTooNewError(Exception):
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
    cursor.execute("PRAGMA table_info('%s')" % table)
    columns = []
    columns_with_type = []
    for column_info in cursor.fetchall():
        column = column_info[1]
        col_type = column_info[2]
        if column in column_names:
            continue
        columns.append(column)
        if column == 'id':
            col_type += ' PRIMARY KEY'
        columns_with_type.append("%s %s" % (column, col_type))

    cursor.execute("PRAGMA index_list('%s')" % table)
    index_sql = []
    for index_info in cursor.fetchall():
        name = index_info[1]
        if name in column_names:
            continue
        cursor.execute("SELECT sql FROM sqlite_master "
                       "WHERE name=? and type='index'", (name,))
        index_sql.append(cursor.fetchone()[0])

    cursor.execute("ALTER TABLE %s RENAME TO old_%s" % (table, table))
    cursor.execute("CREATE TABLE %s (%s)" %
                   (table, ', '.join(columns_with_type)))
    cursor.execute("INSERT INTO %s SELECT %s FROM old_%s" %
                   (table, ', '.join(columns), table))
    cursor.execute("DROP TABLE old_%s" % table)
    for sql in index_sql:
        cursor.execute(sql)

def get_object_tables(cursor):
    """Returns a list of tables that store ``DDBObject`` subclasses.
    """
    cursor.execute("SELECT name FROM sqlite_master "
            "WHERE type='table' and name != 'dtv_variables'")
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
        get_upgrade_func(version)(cursor)
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
                except (SystemExit, KeyboardInterrupt):
                    raise
                except:
                    try:
                        o.savedData['releaseDateObj'] = datetime(*o.savedData['entry'].updated_parsed[0:7])
                    except (SystemExit, KeyboardInterrupt):
                        raise
                    except:
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
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
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
    from miro.plat.utils import FilenameType
    # This is where John Lennon's ghost sings "Binary Fields Forever"
    if FilenameType == str:
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
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
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
    if config.get(prefs.APP_PLATFORM) != "windows":
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
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
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
            o.savedData['url'] = u'https://www.miroguide.com/'
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
            if o.savedData['url'] == config.get(prefs.CHANNEL_GUIDE_URL):
                allowedURLs = unicode(
                    config.get(prefs.CHANNEL_GUIDE_ALLOWED_URLS)).split()
                allowedURLs.append(config.get(
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
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
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
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
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
            except Exception:
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
            except:
                try:
                    return self.entry.payment_url.decode('ascii','replace')
                except:
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
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
                try:
                    return datetime(*self.entry.updated_parsed[0:7])
                except (SystemExit, KeyboardInterrupt):
                    raise
                except:
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
        type = column_info[2]
        columns.append(column)
        if type == 'TIMESTAMP':
            type = 'timestamp'
        if column == 'id':
            type += ' PRIMARY KEY'
        columns_with_type.append("%s %s" % (column, type))
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
        this_folder_count = folder_count[id]
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
    from miro.plat.utils import filenameToUnicode

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
            filename = filenameToUnicode(filename)
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
    from miro.plat.utils import filenameToUnicode
    cursor.execute("SELECT id, status from remote_downloader "
            "WHERE state in ('stopped', 'finished', 'uploading', "
            "'uploading-paused')")
    for row in cursor.fetchall():
        downloader_id = row[0]
        status = eval(row[1], __builtins__,
                {'datetime': datetime, 'time': time})
        filename = status.get('filename')
        if filename:
            filename = filenameToUnicode(filename)
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
    if not config.get(prefs.THEME_NAME) == prefs.THEME_NAME.default:
        return

    audio_guide_url = u'https://www.miroguide.com/audio/'
    favicon_url = u'https://www.miroguide.com/favicon.ico'
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
