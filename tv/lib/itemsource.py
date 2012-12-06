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

import logging
import os.path

from miro import app
from miro import database
from miro import item
from miro import messages
from miro import metadata
from miro import models

class ItemHandler(object):
    """
    Controller base class for handling user actions on an item.
    """

    def mark_watched(self, info):
        """
        Mark the given ItemInfo as watched.  Should also send a 'changed'
        message.
        """
        logging.warn("%s: not handling mark_watched", self)

    def mark_unwatched(self, info):
        """
        Mark the given ItemInfo as unwatched.  Should also send a 'changed'
        message.
        """
        logging.warn("%s: not handling mark_unwatched", self)

    def mark_completed(self, info):
        """
        Mark the given ItemInfo as completed.  Should also send a 'changed'
        message.
        """
        logging.warn("%s: not handling mark_completed", self)

    def mark_skipped(self, info):
        """
        Mark the given ItemInfo as skipped.  Should also send a 'changed'
        message.
        """
        logging.warn("%s: not handling mark_skipped", self)

    def set_is_playing(self, info, is_playing):
        """
        Mark the given ItemInfo as playing, based on the is_playing bool.
        Should also send a 'changed' message, if the is_playing state changed.
        """
        logging.warn("%s: not handling set_is_playing", self)

    def set_rating(self, info, rating):
        """
        Rate the given ItemInfo.  Should also send a 'changed'
        message if the rating changed.
        """
        logging.warn("%s: not handling set_rating", self)

    def set_subtitle_encoding(self, info, encoding):
        """
        Set the subtitle encoding the given ItemInfo.  Should also send a
        'changed' message if the encoding changed.
        """
        logging.warn("%s: not handling set_subtitle_encoding", self)

    def set_resume_time(self, info, resume_time):
        """
        Set the resume time for the given ItemInfo.  Should also send a
        'changed' message.
        """
        logging.warn("%s: not handling set_resume_time", self)

    def delete(self, info):
        """
        Delete the given ItemInfo.  Should also send a 'removed' message.
        """
        logging.warn("%s: not handling delete", self)

    def bulk_delete(self, info_list):
        """
        Delete a list of infos.  Should also send 'removed' messages.
        """
        logging.warn("%s: not handling delete", self)

class DatabaseItemHandler(ItemHandler):
    def mark_watched(self, info):
        """
        Mark the given ItemInfo as watched.  Should also send a 'changed'
        message.
        """
        try:
            item_ = item.Item.get_by_id(info.id)
            item_.mark_watched()
        except database.ObjectNotFoundError:
            logging.warning("mark_watched: can't find item by id %s" % info.id)

    def mark_unwatched(self, info):
        """
        Mark the given ItemInfo as unwatched.  Should also send a 'changed'
        message.
        """
        try:
            item_ = item.Item.get_by_id(info.id)
            item_.mark_unwatched()
        except database.ObjectNotFoundError:
            logging.warning("mark_unwatched: can't find item by id %s" % (
                info.id,))

    def mark_completed(self, info):
        """
        Mark the given ItemInfo as completed.  Should also send a 'changed'
        message.
        """
        try:
            item_ = item.Item.get_by_id(info.id)
            item_.mark_item_completed()
        except database.ObjectNotFoundError:
            logging.warning("mark_completed: can't find item by id %s" % (
                info.id,))

    def mark_skipped(self, info):
        """
        Mark the given ItemInfo as skipped.  Should also send a 'changed'
        message.
        """
        try:
            item_ = item.Item.get_by_id(info.id)
            item_.mark_item_skipped()
        except database.ObjectNotFoundError:
            logging.warning("mark_skipped: can't find item by id %s" % info.id)

    def set_is_playing(self, info, is_playing):
        """
        Mark the given ItemInfo as playing, based on the is_playing bool.
        Should also send a 'changed' message, if the is_playing state changed.
        """
        try:
            item_ = item.Item.get_by_id(info.id)
            item_.set_is_playing(is_playing)
        except database.ObjectNotFoundError:
            logging.warning("mark_is_playing: can't find item by id %s" % (
                info.id,))

    def set_rating(self, info, rating):
        """
        Rate the given ItemInfo.  Should also send a 'changed'
        message if the rating changed.
        """
        try:
            item_ = item.Item.get_by_id(info.id)
            item_.set_rating(rating)
        except database.ObjectNotFoundError:
            logging.warning("set_rating: can't find item by id %s" % info.id)

    def set_subtitle_encoding(self, info, encoding):
        """
        Set the subtitle encoding the given ItemInfo.  Should also send a
        'changed' message if the encoding changed.
        """
        try:
            item_ = item.Item.get_by_id(info.id)
            item_.set_subtitle_encoding(encoding)
        except database.ObjectNotFoundError:
            logging.warning(
                "set_subtitle_encoding: can't find item by id %s" % info.id)

    def set_resume_time(self, info, resume_time):
        """
        Set the resume time for the given ItemInfo.  Should also send a
        'changed' message.
        """
        try:
            item_ = item.Item.get_by_id(info.id)
            item_.set_resume_time(resume_time)
        except database.ObjectNotFoundError:
            logging.warning("set_resume_time: can't find item by id %s" % (
                info.id,))

    def delete(self, info):
        """
        Delete the given ItemInfo.  Should also send a 'removed' message.
        """
        try:
            item_ = item.Item.get_by_id(info.id)
        except database.ObjectNotFoundError:
            logging.warn("delete: Item not found -- %s",  info.id)
        else:
            item_.delete_files()
            item_.expire()

    def bulk_delete(self, info_list):
        app.bulk_sql_manager.start()
        try:
            for info in info_list:
                if not app.bulk_sql_manager.will_remove(info.id):
                    self.delete(info)
        finally:
            app.bulk_sql_manager.finish()

class SharingItemHandler(ItemHandler):
    def set_is_playing(self, info, is_playing):
        """
        Mark the given ItemInfo as playing, based on the is_playing bool.
        Should also send a 'changed' message, if the is_playing state changed.

        Sharing items don't have a real database to back them up so just use
        a back pointer to the item source and emit a 'changed' message.
        """
        if info.is_playing != is_playing:
            # modifying the ItemInfo in-place messes up the Tracker's
            # object-changed logic, so make a copy
            info = messages.ItemInfo(info.id, **info.__dict__)
            info.is_playing = is_playing
            info.item_source.emit("changed", info)

class DeviceItemHandler(ItemHandler):
    def delete(self, info):
        device = info.device_info
        device_item = models.DeviceItem.get_by_id(info.id,
                                                  db_info=device.db_info)
        device_item.delete_and_remove(device)
        device.remaining += device_item.size

    def bulk_delete(self, info_list):
        # calculate all the devices involved
        all_devices = set(info.device_info for info in info_list)
        # set bulk mode, delete, then unset bulk mode
        for device in all_devices:
            device.database.set_bulk_mode(True)
        try:
            for info in info_list:
                self.delete(info)
        finally:
            for device in all_devices:
                message = messages.DeviceChanged(device)
                message.send_to_frontend()
                device.database.set_bulk_mode(False)

    def set_is_playing(self, info, is_playing):
        """
        Mark the given ItemInfo as playing, based on the is_playing bool.
        Should also send a 'changed' message, if the is_playing state changed.
        """
        if info.is_playing != is_playing:
            # modifying the ItemInfo in-place messes up the Tracker's
            # object-changed logic, so make a copy
            info_cache = app.device_manager.info_cache[info.device_info.mount]
            info = info_cache[info.id] = messages.ItemInfo(
                info.id, **info.__dict__)
            database = info.device_info.database
            info.is_playing = is_playing
            database[info.file_type][info.id][u'is_playing'] = is_playing
            database.emit('item-changed', info)

def setup_handlers():
    app.source_handlers = {
            'database': DatabaseItemHandler(),
            'device': DeviceItemHandler(),
            'sharing': SharingItemHandler(),
    }

def get_handler(item_info):
    return app.source_handlers[item_info.source_type]
