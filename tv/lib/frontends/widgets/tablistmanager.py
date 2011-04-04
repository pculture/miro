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

"""Manages the tab lists from a high level perspective."""

from miro import app
from miro import prefs
from miro.errors import (WidgetActionError, ActionUnavailableError,
     WidgetNotReadyError, UnexpectedWidgetError)

from miro.frontends.widgets.tablist import all_tab_lists

import logging

class TabListManager(dict):
    """TabListManager is a map of list_type:TabList which manages a selection."""
    ORDER = ('library', 'static', 'connect', 'site', 'store', 'feed', 'playlist')
    DEFAULT_TAB = ('library', '0') # guide
    # NOTE: when an OrderedDict collection is available, replace ORDER
    def __init__(self):
        dict.__init__(self)
        self.type, self.id = u'tablist', u'tablist'
        for tab_list in all_tab_lists():
            tab_list.connect('tab-added', self.on_tab_added)
            tab_list.connect('row-collapsed', self.on_row_collapsed)
            tab_list.connect('moved-tabs-to-list', self.on_moved_tabs_to_list)
            tab_list.view.connect('selection-changed',
                    self.on_selection_changed, tab_list)
            tab_list.view.connect('selection-invalid',
                    self.on_selection_invalid, tab_list)
            self[tab_list.type] = tab_list
        self._selected_tablist = None
        self._previous_selection = (None, [])
        self._before_no_tabs = self._previous_selection
        self._restored = False
        self._path_broken = None
        self._is_base_selected = False
        self._shown = False

    @property
    def tab_list_widgets(self):
        """Return the TableViews for the tab lists, in display order."""
        return (self[list_type].view for list_type in self.ORDER)

    @property
    def selected_ids(self):
        """Return a generator for the ids of the selected tabs; uses the
        currently selected tablist. May return an empty generator.
        """
        return (tab.id for tab in self.selection[1])

    @property
    def selection(self):
        """The current selection, as (type of the selected list, list of
        TabInfos). The list of TabInfos is never empty; if nothing is selected,
        the selection is changed to a fallback.
        """
        if not self._selected_tablist:
            raise WidgetNotReadyError('_selected_tablist')
        real_tabs = self._selected_tablist.view.num_rows_selected
        if not real_tabs:
            self._handle_no_tabs_selected(self._selected_tablist)
        view = self._selected_tablist.view
        iters = view.get_selection(strict=False)
        if real_tabs:
            self._previous_selection = (self._selected_tablist.type,
                    (self._get_locator(view, i) for i in iters))
        try:
            typ = self._selected_tablist.type
            if not iters:
                typ = None
            return typ, [view.model[i][0] for i in iters]
        except AttributeError:
            app.widgetapp.handle_soft_failure('selection', "iter is none",
                                              with_exception=True)
            return self._selected_tablist.type, [
                    view.model[view.model.first_iter()][0]] 

    @property
    def selection_and_children(self):
        """Return the current selection and its children, as the type of the
        selected list and a list of TabInfos. Children are returned before
        parents.
        """
        if not self._selected_tablist:
            return None, []
        selected_tabs = set()
        view = self._selected_tablist.view
        for path in view.get_selection(strict=False):
            row = view.model[path]
            # sort children before parents
            selected_tabs.add((1, row[0]))
            for children in row.iterchildren():
                selected_tabs.add((0, children[0]))
        return self._selected_tablist.type, [tab[1] for tab in
               sorted(selected_tabs)]

    def select_guide(self):
        """Select the default Source - usually, the Guide tab."""
        self._select_from_tab_list('library', self['library'].get_default())

    def select_search(self):
        """Select the Video Search tab."""
        self._select_from_tab_list('static', self['static'].get_default())

    def focus_view(self):
        """Focus the tablist that contains the current selection.

        :returns: True if we successfully focused the tablist.
        """
        if self._selected_tablist:
            self._selected_tablist.view.focus()
            return True
        else:
            return False

    def get_view(self):
        """Get the currently active tablist.

        :returns: TabList widget
        """
        if self._selected_tablist:
            return self._selected_tablist.view
        else:
            return None

    def _handle_no_tabs_selected(self, _selected_tablist, force=False):
        """No tab is selected; select a fallback. This may be about to be
        overwritten by on_row_collapsed, but there's no way to tell.

        After _handle_no_tabs_selected, something is guaranteed to be selected.
        Selection may still fail in strict mode if the selected tab is in a list
        that is trying to restore a different remembered selection.
        
        Setting force avoids this: any the remembered selection in the choosen
        tablist is dropped, and the new selection is guaranteed to be valid.
        """
        self._restored = False
        self._before_no_tabs = self._previous_selection
        logging.warn('_handle_no_tabs_selected; force=%s', repr(force))
        if force:
            self._selected_tablist.view.forget_restore()
        if hasattr(_selected_tablist, 'info'):
            root = _selected_tablist.iter_map[_selected_tablist.info.id]
        elif hasattr(_selected_tablist, 'default_info'):
            root = _selected_tablist.iter_map[_selected_tablist.default_info.id]
        else:
            root = _selected_tablist.view.model.first_iter()
        self._select_from_tab_list(_selected_tablist.type, root)

    def _select_from_tab_list(self,
            list_type=None, iter_=None, restore=False, or_bust=False):
        """Select a tab by it's type and an iter. If iter_ is None, no new
        selection will be set but the tab list will be activated.

        If restore is set, ignores other parameters and restores the last saved
        selection.

        If restore is not set, list_type must specify the tab list to select.

        or_bust should be set when all tab messages have arrived, so if the
        selection continues to fail we need to _handle_no_tabs because it's not
        going to work.
        """
        if not self._shown:
            return
        was_base_selected = self._is_base_selected
        if restore:
            if self._restored:
                logging.debug("already restored")
                return
            list_type = self._restore()
        view = self[list_type].view
        if iter_:
            # select the tab
            view.select(iter_)
        for tab_list in self.itervalues():
            if tab_list.type != list_type:
                # unselect other tabs
                tab_list.view.unselect_all()
            # keep the current selections
            tab_list.view._save_selection() 
        self._selected_tablist = self[list_type]
        try:
            iters = view.get_selection()
        except WidgetActionError, error:
            if or_bust:
                logging.debug("saved tab may be permanently unavailable: %s",
                              error.reason)
                self._handle_no_tabs_selected(self._selected_tablist, force=True)
                iters = view.get_selection() # must not fail now
            else:
                logging.debug("tab not selected: %s", error.reason)
                iters = []
        if or_bust and not iters:
            logging.debug('no tabs selected, but really need a selection')
            self._handle_no_tabs_selected(self._selected_tablist, force=True)
            iters = view.get_selection()
        tabs = [view.model[i][0] for i in iters]
        # prevent selecting base and non-base at the same time
        if tabs and hasattr(self[list_type], 'info'): # hideable
            iters, tabs = self._disallow_base_with_child(
                    view, tabs, was_base_selected)
        # open the ancestors
        if hasattr(view.model, 'parent_iter'): # not all models have parents
            for selected in iters:
                parent_iter = view.model.parent_iter(selected)
                if parent_iter and not view.is_row_expanded(parent_iter):
                    view.set_row_expanded(parent_iter, True)
        # update the display
        if tabs:
            app.display_manager.select_display_for_tabs(self[list_type], tabs)
        else:
            # no valid selection now; don't update display until the real
            # selection is set
            self._before_no_tabs = self._previous_selection
        if tabs and not restore and self._restored:
            try:
                selected = view.get_selection_as_strings()
            except WidgetActionError, error:
                logging.debug("not saving current tab: %s", error.reason)
            else:
                selected.insert(0, list_type)
                app.widget_state.set_selection(self.type, self.id, selected)
        self._restored = tabs
        if or_bust and not tabs:
            raise UnexpectedWidgetError("should have selected something")
        if tabs and iter_:
            for sel in tabs:
                if sel == view.model[iter_][0]:
                    break
            else:
                raise UnexpectedWidgetError("wrong iter selected")

    def _disallow_base_with_child(self, view, tabs, was_base):
        """Called when a base tab was selected and a child has been added to
        the selection or visa versa; keeps whichever is newer.
        """
        self._is_base_selected = any(tab.type == 'tab' for tab in tabs)
        if self._is_base_selected and len(tabs) > 1:
            root = self._selected_tablist.iter_map[self._selected_tablist.info.id]
            if was_base: # unselect base if it was already selected
                if (self._selected_tablist.type ==
                        self._previous_selection[0]):
                    view.unselect(root)
            else: # unselect everything but base if base is newly selected
                view.unselect_all(signal=False)
                view.select(root)
            view._save_selection()
        iters = view.get_selection()
        tabs = [view.model[i][0] for i in iters]
        self._is_base_selected = any(tab.type == 'tab' for tab in tabs)
        return iters, tabs

    def _restore(self):
        """Restore a saved selection."""
        sel = app.widget_state.get_selection(self.type, self.id)
        if sel is None or not app.config.get(prefs.REMEMBER_LAST_DISPLAY):
            sel = list(self.DEFAULT_TAB)
        list_type = sel.pop(0)
        view = self[list_type].view
        # select the paths to find out what the strings translate to
        view.set_selection_as_strings(sel)
        view._save_selection()
        return list_type

    def on_shown(self):
        """The window has been shown. This method is run once when the window
        has been displayed for the first time, and then whenever the window is
        restored from being minimized.
        """
        if self._shown:
            return
        # build_tabs cannot be called until now because the guide needs the
        # window already to exist
        for tab_list in self.itervalues():
            tab_list.build_tabs()
        self._shown = True
        # the default selection should have set itself by now, so now we can
        # overwrite it
        self._select_from_tab_list(restore=True)

    def on_selection_changed(self, _table_view, tab_list):
        """When the user has changed the selection, we set the selected tablist
        and then display the new tab(s).
        """
        if tab_list.changing:
            tab_list.delayed_selection_change = True
        else:
            self._select_from_tab_list(tab_list.type, or_bust=True)

    def on_tab_added(self, tab_list):
        """A tablist has gained a tab.
        
        To respond correctly to saved selections that are no longer available,
        we need to know when all messages for existing tabs have been sent. This
        relies on the fact that TabList's message batching causes all initial
        tabs to arrive in the first message.
        """
        selection = app.widget_state.get_selection(self.type, self.id)
        if not self._restored and selection and selection[0] == tab_list.type:
            # we may be waiting for this tab to switch to it
            self._select_from_tab_list(restore=True, or_bust=True)

    def on_moved_tabs_to_list(self, _tab_list, destination):
        """Handle tabs being moved between tab lists."""
        self._select_from_tab_list(destination.type)

    def _get_locator(self, view, iter_):
        """OS X doesn't have hierarchial paths; this returns whatever type of
        locator is useful on this platform.

        The ideal replacement for hack would be to implement hierarchial paths
        on OS X.
        """
        if not self._path_broken:
            path = view.model.get_path(iter_)
            if path is NotImplemented:
                self._path_broken = True
            else:
                self._path_broken = False
                return path
        try:
            return iter_.value()
        except ValueError:
            raise WidgetActionError("node deleted on OS X")
    
    def _locator_is_parent(self, model, parent, children):
        """This compares one locator with an iterable of other locators to see
        whether the one is the parent of any of the others.

        With hierarchial rows, this is O(n).
        """
        if self._path_broken:
            # breadth-first search from children upwards to the root node
            to_check = set(children)
            while to_check:
                checked = set()
                for node in to_check.copy():
                    if node == parent:
                        return True
                    checked.add(node)
                    if node.parent is not None:
                        to_check.add(node.parent.value())
                to_check.difference_update(checked)
            return False
        else:
            # if a path starts with parent but is longer than parent, it's a
            # child of parent
            depth = len(parent)
            return any(len(sel) > depth and sel[:depth] == parent
                       for sel in children)

    def on_row_collapsed(self, tab_list, iter_, path):
        """When an ancestor of a selected tab is collapsed, we lose the
        selection before we get the row-collapsed signal. The approach taken
        here is to check whether the last real selection included descendants of
        the collapsed row, and if so select the collapsed row.
        """
        previous_tab_list, selected = self._before_no_tabs
        selected = list(selected)
        if tab_list == previous_tab_list or not selected:
            return
        if self._path_broken is None:
            self._path_broken = path is NotImplemented
        if self._path_broken:
            try:
                path = self._get_locator(tab_list.view, iter_)
            except ActionUnavailableError, error:
                logging.debug("selection invalid: %s", error.reason)
                self.on_selection_invalid(tab_list.view, self._selected_tablist)
        if self._locator_is_parent(tab_list.view.model, path, selected):
            tab_list.view.unselect_all(signal=False)
            self._restored = True
            self._select_from_tab_list(tab_list.type, iter_)

    def on_selection_invalid(self, _table_view, tab_list):
        """The current selection is invalid; this happens after deleting. Select
        the root node.
        """
        logging.debug("deleted selected node?")
        root = tab_list.iter_map[tab_list.info.id]
        self._select_from_tab_list(tab_list.type, root)
