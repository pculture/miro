# Miro - an RSS based video player application
# Copyright (C) 2012
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

"""miro.data.dberrors -- handle database errors.

This module is responsible for handling database errors on both the frontend
and backend threads.  This is tricky for a couple reasons:

- Errors can happen in both threads at the same time, or near one and
  other.  In that case, we don't want to show 2 dialog windows
- On GTK at least, errors can happen while we're waiting for a user
  choice in our dialog window

Here's how we handle it:
- The backend system creates the DatabaseErrorDialog just like before and asks
  the frontend to show it.  This is pretty similir to the situation before.
- If we get an error in the frontend, then we show a similar dialog.  The
  frontend code shouldn't block on the dialog.  Instead it can provide a
  function to call if the user clicks the RETRY button.
- We avoid showing multiple dialog windows at once and instead reuse the
  response from the first dialog.
"""

import itertools
import logging

from miro import app
from miro import dialogs

class DBErrorHandler(object):
    def __init__(self, frontend=None):
        if frontend is None:
            frontend = app.frontend
        self.frontend = frontend
        self.running_dialog = False
        self.retry_callbacks = []
        self.backend_dialogs = []
        self.logged_warning = False
        # The last button clicked on the dialog
        self.last_response = None
        # Which threads we sent last_response to.
        self.last_response_sent_to = set()

    def run_dialog(self, title, description, retry_callback=None):
        if retry_callback is not None:
            self.retry_callbacks.append(retry_callback)
        self.frontend.call_on_ui_thread(self._run_dialog,
                                        title, description, 'ui thread')

    def run_backend_dialog(self, dialog):
        self.backend_dialogs.append(dialog)
        self.frontend.call_on_ui_thread(self._run_dialog,
                                        dialog.title, dialog.description,
                                        'eventloop thread')

    def _run_dialog(self, title, description, thread):
        if self.running_dialog:
            return
        self.running_dialog = True
        try:
            response = self._get_dialog_response(title, description, thread)
        finally:
            self.running_dialog = False
        if response is None:
            logging.warn("DB Error dialog closed, assuming QUIT")
            response = dialogs.BUTTON_QUIT
        self.last_response = response
        self.last_response_sent_to.add(thread)
        self._handle_response(response)

    def _get_dialog_response(self, title, description, thread):
        if self._should_reuse_last_response(thread):
            return self.last_response
        else:
            self.last_response_sent_to.clear()
        try:
            response = self.frontend.run_choice_dialog(
                title, description, [dialogs.BUTTON_RETRY,
                                     dialogs.BUTTON_QUIT])
        except NotImplementedError:
            if not self.logged_warning:
                logging.warn("Frontend.run_choice_dialog not "
                             "implemented assuming QUIT was chosen")
            response = dialogs.BUTTON_QUIT
        return response

    def _should_reuse_last_response(self, thread):
        """Check if we should reuse the last button response without popping
        up a new dialog.
        """
        if self.last_response == dialogs.BUTTON_QUIT:
            return True
        if (self.last_response == dialogs.BUTTON_RETRY and
            thread not in self.last_response_sent_to):
            return True
        return False

    def _handle_response(self, response):
        if response == dialogs.BUTTON_RETRY:
            for callback in self.retry_callbacks:
                try:
                    callback()
                except StandardError:
                    logging.warn("DBErrorHandler: error calling response "
                                 "callback: %s", callback, exc_info=True)
        for dialog in self.backend_dialogs:
            dialog.run_callback(response)

        self.retry_callbacks = []
        self.backend_dialogs = []
