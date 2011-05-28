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

"""``miro.messagetools`` -- Framework for message passing.

This module defines a very basic message passing framework.  It's extended by
messages/messagehandler to implement the frontend-backend communication and
subprocessmanager to implement miro-subprocess communication.
"""


import logging
import re

from miro import util

class MessageHandler(object):
    def __init__(self):
        self.message_map = {} # maps message classes to method names
        self.complained_about = set()

    def call_handler(self, method, message):
        """Arrange for a message handler method to be called in the correct
        thread.  Must be implemented by subclasses.
        """
        raise NotImplementedError()

    def handle(self, message):
        """Handles a given message.
        """
        handler_name = self.get_message_handler_name(message)
        try:
            handler = getattr(self, handler_name)
        except AttributeError:
            if handler_name not in self.complained_about:
                logging.warn("MessageHandler doesn't have a %s method "
                        "to handle the %s message" % (handler_name,
                            message.__class__))
                self.complained_about.add(handler_name)
        else:
            self.call_handler(handler, message)

    def get_message_handler_name(self, message):
        try:
            return self.message_map[message.__class__]
        except KeyError:
            self.message_map[message.__class__] = \
                    self.calc_message_handler_name(message.__class__)
            return self.message_map[message.__class__]

    def calc_message_handler_name(self, message_class):
        def replace(match):
            return '%s_%s' % (match.group(1), match.group(2))
        underscores = re.sub(r'([a-z])([A-Z])', replace,
                message_class.__name__)
        return 'handle_' + util.ascii_lower(underscores)

class Message(object):
    """Base class for all Messages.
    """
    @classmethod
    def install_handler(cls, handler):
        """Install a new message handler for this class.  When
        send_to_frontend() or send_to_backend() is called, this handler will
        be invoked.
        """
        cls.handler = handler

    @classmethod
    def reset_handler(cls):
        del cls.handler

