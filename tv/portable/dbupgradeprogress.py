# Miro - an RSS based video player application
# Copyright (C) 2005-2009 Participatory Culture Foundation
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

"""dbupgradeprogress.py -- Send updates about progress upgrading the database.
"""

from miro.gtcache import gettext as _
from miro import messages

_doing_20_upgrade = False

def doing_20_upgrade():
    """Call this if we are upgrading from a 2.0-style database.

    This will calibrate the progress bar to take into account the fact that we
    are running old-style upgrades and running the code in
    convert20database.py.
    """
    global _doing_20_upgrade
    _doing_20_upgrade = True

def upgrade_start():
    """Call at the begining of the database upgrades."""
    messages.DatabaseUpgradeStart().send_to_frontend()

def upgrade_end():
    """Call at the end of the database upgrades."""
    messages.DatabaseUpgradeEnd().send_to_frontend()

def old_style_progress(start_version, current_version, end_version):
    """Call while stepping through old-style upgrades"""

    progress = _calc_progress(start_version, current_version, end_version)
    total = 0.05 * progress # old style upgrades take us from 0% -> 5%
    _send_message(_('Upgrading Old Database'), progress, total)

def convert20_progress(current_step, total_step):
    """Call while stepping through 2.0 DB conversion code."""

    progress = _calc_progress(0, current_step, total_step)
    total = 0.05 + 0.80 * progress # conversion take us from 5% -> 85%
    _send_message(_('Converting Old Database'), progress, total)

def new_style_progress(start_version, current_version, end_version):
    """Call while stepping through new-style upgrades"""

    progress = _calc_progress(start_version, current_version, end_version)
    if _doing_20_upgrade:
        total = 0.85 + 0.15 * progress
        # new style upgrades take us from 85% -> 100%
    else:
        total = progress
        # we didn't do 2.0 conversion.  New style upgrades take us from 0% to
        # 100%
    _send_message(_('Upgrading Database'), progress, total)

def _send_message(stage, stage_progress, total_progress):
    messages.DatabaseUpgradeProgress(stage, stage_progress,
            total_progress).send_to_frontend()

def _calc_progress(start, current, end):
    total = end - start
    # if total is 0.0 or less, then we return 0.0 to avoid the
    # ZeroDivisionError.  this happens in unit testing.
    if total <= 0.0:
        return 0.0
    return float(current - start) / (end - start)
