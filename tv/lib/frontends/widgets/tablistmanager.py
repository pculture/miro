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
    # NOTE: when an OrderedDict collection is available, replace ORDER
    def __init__(self):
        dict.__init__(self)
        self.type, self.id = u'tablist', u'tablist'
        for tab_list in all_tab_lists():
            tab_list.connect('tab-added', self.on_tab_added)
            tab_list.connect('moved-tabs-to-list', self.on_moved_tabs_to_list)
            tab_list.view.connect('selection-changed',
                    self.on_selection_changed, tab_list)
            tab_list.view.connect('selection-invalid',
                    self.on_selection_invalid, tab_list)
            self[tab_list.type] = tab_list
        self._selected_tablist = None
        self._previous_selection = None
        self._before_no_tabs = self._previous_selection
        self._path_broken = None
        self._is_base_selected = False
        self._shown = False
        self._restoring = None

    def _get_restore_tab(self):
        restoring = None
        if app.config.get(prefs.REMEMBER_LAST_DISPLAY):
            restoring = app.widget_state.get_selection(self.type, self.id)
        if not restoring:
            restoring = ['library', '0'] # guide
        return restoring

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
        iters = view.get_selection()
        if real_tabs:
            self._previous_selection = self._selected_tablist.type
        return self._selected_tablist.type, [view.model[i][0] for i in iters]

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
        ordered_tabs = [tab[1] for tab in sorted(selected_tabs)]
        unique_tabs = set(ordered_tabs)
        ordered_unique_tabs = sorted(unique_tabs, key=ordered_tabs.index)
        return self._selected_tablist.type, ordered_unique_tabs

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

    def _handle_no_tabs_selected(self, _selected_tablist):
        """No tab is selected; select a fallback."""
        self._before_no_tabs = self._previous_selection
        logging.warn('_handle_no_tabs_selected')
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

        or_bust should be set when all tab messages have arrived, so if the
        selection continues to fail we need to _handle_no_tabs because it's not
        going to work.
        """
        if not self._shown:
            return
        view = self[list_type].view
        if iter_:
            # select the tab
            view.set_selection([iter_])
        for tab_list in self.itervalues():
            if tab_list.type != list_type:
                # unselect other tabs
                tab_list.view.unselect_all()
        self._selected_tablist = self[list_type]
        try:
            iters = view.get_selection()
        except WidgetActionError, error:
            if or_bust:
                logging.debug("saved tab may be permanently unavailable: %s",
                              error.reason)
                self._handle_no_tabs_selected(self._selected_tablist)
                iters = view.get_selection() # must not fail now
            else:
                logging.debug("tab not selected: %s", error.reason)
                iters = []
        if or_bust and not iters:
            logging.debug('no tabs selected, but really need a selection')
            self._handle_no_tabs_selected(self._selected_tablist)
            iters = view.get_selection()
        tabs = [view.model[i][0] for i in iters]
        # prevent selecting base and non-base at the same time
        if len(tabs) > 1 and any(tab.type == 'tab' for tab in tabs):
            bases = (i for i in iters if view.model[i][0].type == 'tab')
            not_bases = (i for i in iters if view.model[i][0].type != 'tab')
            if self._is_base_selected: # base was previous selection
                view.unselect_iters(bases)
                iters = list(not_bases)
            else: # base newly selected
                view.unselect_iters(not_bases)
                iters = [bases.next()] # keep 1 base
                view.unselect_iters(bases)
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
        if tabs and not self._restoring:
            selected = view.get_selection_as_strings()
            selected.insert(0, list_type)
            app.widget_state.set_selection(self.type, self.id, selected)
        if tabs:
            self._restoring = None
        if or_bust and not tabs:
            raise UnexpectedWidgetError("should have selected something")
        if iter_ and len(tabs) > 1 and view.model[iter_][0] != tabs[0]:
            raise UnexpectedWidgetError("wrong iter selected")

    def _restore(self, or_bust=False):
        """Restore the saved selection."""
        list_type = self._restoring[0]
        try:
            self[list_type].view.set_selection_as_strings(self._restoring[1:])
        except WidgetActionError, error:
            if or_bust:
                self._handle_no_tabs_selected(self[list_type])
            else:
                logging.debug("not restoring yet: %s", error.reason)
        else:
            self._select_from_tab_list(list_type, or_bust=or_bust)

    def on_shown(self):
        """The window has been shown. This method is run once when the window
        has been displayed for the first time, and then whenever the window is
        restored from being minimized.
        """
        if self._shown:
            return
        # waiting until on_shown to _get_restore_tab because WSS hasn't received
        # its displays yet during our __init__
        self._restoring = self._get_restore_tab()
        # build_tabs cannot be called until now because the guide needs the
        # window already to exist
        for tab_list in self.itervalues():
            tab_list.build_tabs()
        self._shown = True
        # the default selection should have set itself by now, so now we can
        # overwrite it
        if self._restoring:
            self._restore()

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
        if self._restoring and self._restoring[0] == tab_list.type:
            # we may be waiting for this tab to switch to it
            self._restore(or_bust=True)

    def on_moved_tabs_to_list(self, _tab_list, destination):
        """Handle tabs being moved between tab lists."""
        self._select_from_tab_list(destination.type)

    def on_selection_invalid(self, _table_view, tab_list):
        """The current selection is invalid; this happens after deleting. Select
        the root node.
        """
        logging.debug("deleted selected node?")
        self._handle_no_tabs_selected(tab_list)

    def update_metadata_progress(self, target, remaining, eta, total):
        if target == ('library', 'video'):
            tab_id = 'videos'
        elif target == ('library', 'audio'):
            tab_id = 'music'
        else:
            # we don't care about metadata progress for devices
            return
        if remaining > 0:
            self['library'].start_updating(tab_id)
        else:
            self['library'].stop_updating(tab_id)
