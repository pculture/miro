# Miro - an RSS based video player application
# Copyright (C) 2005-2007 Participatory Culture Foundation
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

# Almost everything is split out into files under frontend-implementation.
# Note: these can't be in just any order; there is some subtlety in the
# initialization order, so take care.

from miro.frontend_implementation.Application import Application
from miro.frontend_implementation.UIBackendDelegate import UIBackendDelegate
from miro.frontend_implementation.MainFrame import MainFrame
from miro.frontend_implementation.VideoDisplay import VideoDisplay, PlaybackController
from miro.frontend_implementation import startup
