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

"""miro.plat.frontends.widgets.widgetset -- Contains all the
platform-specific widgets.  This module doesn't have any actual code in it, it
just imports the widgets from their actual locations.
"""

from miro.plat.frontends.widgets.const import *
from miro.plat.frontends.widgets.control import (TextEntry, NumberEntry,
     SecureTextEntry, SearchTextEntry, VideoSearchTextEntry, MultilineTextEntry)
from miro.plat.frontends.widgets.control import Checkbox, Button, OptionMenu, RadioButtonGroup, RadioButton
from miro.plat.frontends.widgets.customcontrol import (CustomButton,
        ContinuousCustomButton, CustomSlider, DragableCustomButton)
from miro.plat.frontends.widgets.drawing import DrawingContext, ImageSurface, Gradient
from miro.plat.frontends.widgets.drawingwidgets import DrawingArea, Background
from miro.plat.frontends.widgets.rect import Rect
from miro.plat.frontends.widgets.layout import VBox, HBox, Alignment, Splitter, Table, Scroller, Expander, TabContainer, DetachedWindowHolder
from miro.plat.frontends.widgets.window import Window, MainWindow, Dialog, FileSaveDialog, FileOpenDialog
from miro.plat.frontends.widgets.window import DirectorySelectDialog, AboutDialog, AlertDialog, PreferencesWindow, DonateWindow, DialogWindow, get_first_time_dialog_coordinates
from miro.plat.frontends.widgets.browser import Browser
from miro.plat.frontends.widgets.simple import (Image, ImageDisplay, Label,
        SolidBackground, ClickableImageButton, AnimatedImageDisplay,
        ProgressBar, HLine)
from miro.plat.frontends.widgets.tableview import (TableView, TableColumn,
        CellRenderer, CustomCellRenderer, ImageCellRenderer,
        CheckboxCellRenderer, ItemListRenderer, ItemListRendererText,
        CUSTOM_HEADER_HEIGHT)
from miro.plat.frontends.widgets.tablemodel import (TableModel,
        TreeTableModel, ItemListModel)
from miro.plat.frontends.widgets.osxmenus import (Menu, Separator, MenuItem,
        RadioMenuItem, CheckMenuItem)
from miro.plat.frontends.widgets.audio import AudioPlayer
from miro.plat.frontends.widgets.video import VideoPlayer
from miro.plat.frontends.widgets.sniffer import get_item_type
from miro.plat.frontends.widgets.base import Widget
