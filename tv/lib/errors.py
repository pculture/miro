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

"""``miro.errors`` -- Miro exceptions.
"""

class ActionUnavailableError(ValueError):
    """The action attempted can not be done in the current state."""
    def __init__(self, reason):
        self.reason = reason

class WidgetActionError(ActionUnavailableError):
    """The widget is not in the right state to perform the requested action.
    This usually is not serious, but if not handled the UI will likely be in an
    incorrect state.
    """

class WidgetDomainError(WidgetActionError):
    """The widget element requested is not available at this time. This may be a
    temporary condition or a result of permanent changes.
    """
    def __init__(self, domain, needle, haystack, details=None):
        self.domain = domain
        self.needle = needle
        self.haystack = haystack
        self.details = details

    @property
    def reason(self):
        reason = "looked for {0} in {2}, but found only {1}".format(
                 repr(self.needle), repr(self.haystack), self.domain)
        if self.details:
            reason += ": " + self.details
        return reason

class WidgetRangeError(WidgetDomainError):
    """Class to handle neat display of ranges in WidgetDomainErrors. Handlers
    should generally catch a parent of this.
    """
    def __init__(self, domain, needle, start_range, end_range, details=None):
        haystack = "{0} to {1}".format(repr(start_range), repr(end_range))
        WidgetDomainError.__init__(self, domain, needle, haystack, details)

class WidgetNotReadyError(WidgetActionError):
    """The widget is not ready to perfom the action given; this must be a
    temporary condition that will be resolved when the widget finishes setting
    up.
    """
    def __init__(self, waiting_for):
        self.waiting_for = waiting_for

    @property
    def reason(self):
        return "waiting for {0}".format(self.waiting_for)

class UnexpectedWidgetError(ActionUnavailableError):
    """The Spanish Inquisition of widget errors. A widget was asked to do
    something, had every reason to do so, yet refused. This should always cause
    at least a soft_failure; the UI is now in an incorrect state.
    """

class WidgetUsageError(UnexpectedWidgetError):
    """A widget error that is likely the result of incorrect widget usage."""
