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
        real_tabs = self._selected_tablist.view.num_rows_selected()
        if not real_tabs:
            self._handle_no_tabs_selected(self._selected_tablist)
        view = self._selected_tablist.view
        iters = view.get_selection()
        if real_tabs:
            self._previous_selection = (self._selected_tablist.type,
                    (self._get_locator(view, i) for i in iters))
        try:
            return self._selected_tablist.type, [view.model[i][0]
                   for i in iters]
        except AttributeError:
            logging.error('iter is None')
            return self._selected_tablist.type, [
                    table_view.model[table_view.model.first_iter()][0]] 

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
        for path in view.get_selection():
            row = view.model[path]
            # sort children before parents
            selected_tabs.add((1, row[0]))
            for children in row.iterchildren():
                selected_tabs.add((0, children[0]))
        return self._selected_tablist.type, [tab[1] for tab in
               sorted(selected_tabs)]

    def select_guide(self):
        """Select the default Source - usually, the Guide tab."""
        self._select_from_tab_list('site', self['site'].get_default())

    def select_search(self):
        """Select the Video Search tab."""
        self._select_from_tab_list('static', self['static'].get_default())

    def _handle_no_tabs_selected(self, _selected_tablist):
        """No tab is selected; select a fallback. This may be about to be
        overwritten by on_row_collapsed, but there's no way to tell.
        """
        self._restored = False
        self._before_no_tabs = self._previous_selection
        logging.warn('_handle_no_tabs_selected')
        model = _selected_tablist.view.model
        # select the top-level tab for of the list
        iter_ = model.first_iter()
        if not iter_:
            # somehow there's no tabs left in the list.  select the guide as a
            # fallback
            self.select_guide()
            app.widgetapp.handle_soft_failure("handle_no_tabs_selected",
                    'first_iter is None', with_exception=False)
            return
        self._select_from_tab_list(_selected_tablist.type, iter_)

    def _select_from_tab_list(self, list_type=None, iter_=None, restore=False):
        """Select a tab by it's type and an iter. If iter_ is None, no new
        selection will be set but the tab list will be activated.

        If restore is set, ignores other parameters and restores the last saved
        selection.

        If restore is not set, list_type must specify the tab list to select.
        """
        was_base_selected = self._is_base_selected
        if restore:
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
        iters = view.get_selection()
        tabs = [view.model[i][0] for i in iters]
        # prevent selecting base and non-base at the same time
        if tabs and hasattr(self[list_type], 'info'): # hideable
            self._is_base_selected = any(tab.type == 'tab' for tab in tabs)
            if self._is_base_selected and len(tabs) > 1:
                root = self[list_type].iter_map[self[list_type].info.id]
                if was_base_selected: # unselect base if it was already selected
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
            # save the selection
            selected = view.get_selection_as_strings()
            selected.insert(0, list_type)
            logging.debug('saving: %s', repr(selected))
            app.widget_state.set_selection(self.type, self.id, selected)
        self._restored = tabs
        if iter_ is None:
            return
        # verify success
        for sel in tabs:
            if (sel == view.model[iter_][0]):
                break
        logging.warn('_sftl failed')

    def _restore(self):
        """Restore a saved selection."""
        sel = app.widget_state.get_selection(self.type, self.id)
        if sel is None:
            sel = list(self.DEFAULT_TAB)
        list_type = sel.pop(0)
        view = self[list_type].view
        # select the paths to find out what the strings translate to
        view.set_selection_as_strings(sel)
        view._save_selection()
        if not hasattr(self[list_type], 'info'):
            logging.debug('not hideable')
            # not hideable
            return list_type
        logging.debug('hideable')
        # OS X won't expand the root automatically
        root = self[list_type].iter_map[self[list_type].info.id]
        view.set_row_expanded(root, True)
        # now that the root is definitely open, we can really set the sel
        logging.debug('restoring.1: %s/%s', repr(list_type), repr(sel))
        view.set_selection_as_strings(sel)
        view._save_selection()
        return list_type

    def on_shown(self):
        """The window has been shown."""
        # build_tabs cannot be called until now because the guide needs the
        # window already to exist
        for tab_list in self.itervalues():
            tab_list.build_tabs()
        # the default selection should have set itself by now, so now we can
        # overwrite it
        self._select_from_tab_list(restore=True)

    def on_selection_changed(self, _table_view, tab_list):
        """When the user has changed the selection, we set the selected tablist
        and then display the new tab(s).
        """
        if tab_list._adding or tab_list._removing:
            return
        self._select_from_tab_list(tab_list.type)

    def on_tab_added(self, tab_list):
        """A tablist has gained a tab."""
        selection = app.widget_state.get_selection(self.type, self.id)
        if not self._restored and selection and selection[0] == tab_list.type:
            # we may be waiting for this tab to switch to it
            self._select_from_tab_list(restore=True)

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
        return iter_.value()
    
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
            path = self._get_locator(tab_list.view, iter_)
        if self._locator_is_parent(tab_list.view.model, path, selected):
            tab_list.view.unselect_all(signal=False)
            self._restored = True
            self._select_from_tab_list(tab_list.type, iter_)

    def on_selection_invalid(self, _table_view, tab_list):
        """The current selection is invalid; this happens after deleting. Select
        the root node.
        """
        root = tab_list.iter_map[tab_list.info.id]
        self._select_from_tab_list(tab_list.type, root)
