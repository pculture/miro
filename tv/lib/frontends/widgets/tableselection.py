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

"""tableselection.py -- High-level selection management. Subclasses defined in
the platform tableview modules provide the platform-specific methods used here.
"""

from __future__ import with_statement # neccessary for python2.5
from contextlib import contextmanager

import logging

from miro.errors import WidgetActionError

class SelectionOwnerMixin(object):
    """Encapsulates the selection functionality of a TableView, for
    consistent behavior across platforms.

    Emits:
    :signal selection-changed: the selection has been changed
    :signal selection-invalid: the item selected can no longer be selected
    :signal deselected: all items have been deselected
    """
    def __init__(self):
        self._real_selection = None
        self._ignore_selection_changed = 0
        self._restoring_selection = None
        self._allow_multiple_select = None
        self.create_signal('selection-changed')
        self.create_signal('selection-invalid')
        self.create_signal('deselected')

    @property
    def allow_multiple_select(self):
        """Return whether the widget allows multiple selection."""
        if self._allow_multiple_select is None:
            self._allow_multiple_select = self._get_allow_multiple_select()
        return self._allow_multiple_select

    @allow_multiple_select.setter
    def allow_multiple_select(self, allow):
        """Set whether to allow multiple selection; this method is expected
        always to work.
        """
        if self._allow_multiple_select != allow:
            self._set_allow_multiple_select(allow)
            self._allow_multiple_select = allow

    @property
    def num_rows_selected(self):
        """Override on platforms with a way to count rows without having to
        retrieve them.
        """
        if self.allow_multiple_select:
            return len(self._get_selected_iters())
        else:
            return int(self._get_selected_iter() is not None)

    def select(self, iter_):
        """Try to select an iter. Succeeds or raises WidgetActionError. Sends
        no signals.
        """
        self._validate_iter(iter_)
        with self._ignoring_changes():
            self._select(iter_)
        if not self._is_selected(iter_):
            raise WidgetActionError("the specified iter cannot be selected")

    def unselect(self, iter_):
        """Unselect an Iter. Fails silently if the Iter is not selected, but
        raises an exception if the Iter is not selectable at all. Sends no
        signals.
        """
        self._validate_iter(iter_)
        with self._ignoring_changes():
            self._unselect(iter_)

    def unselect_all(self, signal=True):
        """Unselect all. emits only the 'deselected' signal."""
        with self._ignoring_changes():
            self._unselect_all()
            if signal:
                self.emit('deselected')

    def on_selection_changed(self, _widget_or_notification):
        """When we receive a selection-changed signal, we forward it if we're
        not in a 'with _ignoring_changes' block. Selection-changed
        handlers are run in an ignoring block, and anything that changes the
        selection to reflect the current state.
        """
        # don't bother sending out a second selection-changed signal if
        # the handler changes the selection (#15767)
        if not self._ignore_selection_changed:
            self._save_selection()
            with self._ignoring_changes():
                self.emit('selection-changed')

    def get_selection_as_strings(self):
        """Returns the current selection as a list of strings."""
        return [self._iter_to_string(iter_) for iter_ in self.get_selection()]

    def set_selection_as_strings(self, selected):
        """Given a list of selection strings, selects each Iter represented by
        the strings. Returns True if immediately successful, or False if the
        selection given cannot be restored yet and has been postponed. Emits no
        signals.
        """
        self._restoring_selection = None
        self.unselect_all(signal=False)
        for sel_string in selected:
            try:
                # iter may not be destringable (yet)
                iter_ = self._iter_from_string(sel_string)
                # destringed iter not selectable if parent isn't open (yet)
                self.select(iter_)
            except WidgetActionError:
                self._restoring_selection = selected
                return False
        self._save_selection() # overwrite old _save_selection
        return True

    def get_selection(self, strict=True):
        """Returns a list of GTK Iters.
        
        If strict is set (default), will fail with WidgetActionError if there
        is a selection waiting to be restored; unset strict to get whatever is
        selected (though it should be about to be overwritten).

        Works regardless of whether multiple selection is enabled.
        """
        # FIXME: non-strict mode is transitional. when everything is fixed not
        # to need it, remove it
        if self._restoring_selection:
            self.set_selection_as_strings(self._restoring_selection)
        if strict and self._restoring_selection:
            raise WidgetActionError("current selection is temporary")
        return self._get_selected_iters()

    def get_selected(self, strict=False):
        """Return the single selected item.
        
        If strict is set (disabled by default), will fail with
        WidgetActionError if there is a selection waiting to be restored.
        
        Raises a WidgetActionError if multiple select is enabled.
        """
        if self._restoring_selection:
            self.set_selection_as_strings(self._restoring_selection)
        if self.allow_multiple_select:
            raise WidgetActionError("table allows multiple selection")
        if strict and self._restoring_selection:
            raise WidgetActionError("current selection is temporary")
        return self._get_selected_iter()

    def select_path(self, path):
        """Select an item by path (rather than by iter).
        
        NOTE: not currently implemented on OS X.
        """
        raise NotImplementedError

    def forget_restore(self):
        """This method is to be used when a selection has been given in
        set_selection_as_strings, but that selection is not likely to be
        restorable.
        """
        self._restoring_selection = None

    def _save_selection(self):
        """Save the current selection to restore with _restore_selection.

        Selection needs to be saved/restored whenever the model is set to None
        (bulk edits).
        """
        try:
            selected = self._get_selected_iters()
        except WidgetActionError, error:
            logging.debug("not saving selection: %s", error.reason)
        else:
            self._real_selection = [self._iter_to_smart_selector(iter_)
                                            for iter_ in selected]

    def _restore_selection(self):
        """Restore the selection after making changes that would unset it. If
        there is a selection from set_selection_as_strings, restore that if
        possible; otherwise, use what was set in _save_selection.
        """
        if self._restoring_selection is not None:
            if self.set_selection_as_strings(self._restoring_selection):
                return
        if self._ignore_selection_changed:
            return
        if self._real_selection is None:
            return
        self.unselect_all(signal=False)
        for selector in self._real_selection:
            try:
                iter_ = self._iter_from_smart_selector(selector)
            except WidgetActionError:
                self._real_selection = None
                logging.warning("can't restore selection - deleted?", exc_info=True)
                self.emit('selection-invalid')
                break
            else:
                self.select(iter_)

    def _iter_to_smart_selector(self, iter_):
        """Smart selectors are objects that keep track of selection; they don't
        need to be persistable between sessions, so they may be able to work
        despite changes in order. Platforms with anything smarter than iters
        should override this method.
        """
        self._validate_iter(iter_)
        return iter_

    def _iter_from_smart_selector(self, selector):
        """Smart selectors are objects that keep track of selection; they don't
        need to be persistable between sessions, so they may be able to work
        despite changes in order. Platforms with anything smarter than iters
        should override this method.
        """
        return selector

    def _validate_iter(self, iter_):
        """Check whether an iter is valid.

        :raises WidgetDomainError: the iter is not valid
        :raises WidgetActionError: there is no model right now
        """

    @contextmanager
    def _ignoring_changes(self):
        """Use this with with to prevent sending signals when we're changing our
        own selection; that way, when we get a signal, we know it's something
        important.
        """
        self._ignore_selection_changed += 1
        try:
            yield
        finally:
            self._ignore_selection_changed -= 1
