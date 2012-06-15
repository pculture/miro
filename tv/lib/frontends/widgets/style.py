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

"""Constants that define the look-and-feel."""

import logging
import math

from miro import app
from miro import displaytext
from miro import util
from miro.gtcache import gettext as _
from miro.frontends.widgets import cellpack
from miro.frontends.widgets import imagepool
from miro.frontends.widgets import widgetutil
from miro.frontends.widgets.itemrenderer import (DOWNLOAD_TEXT,
                                                 DOWNLOAD_TO_MY_MIRO_TEXT)
from miro.plat import PLATFORMNAME
from miro.plat import resources
from miro.plat.frontends.widgets import use_custom_tablist_font
from miro.plat.frontends.widgets import widgetset

PI = math.pi

AVAILABLE_COLOR = (38/255.0, 140/255.0, 250/255.0) # blue
UNPLAYED_COLOR = (0.31, 0.75, 0.12) # green
DOWNLOADING_COLOR = (0.90, 0.45, 0.08) # orange
WATCHED_COLOR = (0.33, 0.33, 0.33) # dark grey
EXPIRING_COLOR = (0.95, 0.82, 0.11) # yellow-ish
EXPIRING_TEXT_COLOR = widgetutil.css_to_color('#7b949d')

TAB_LIST_BACKGROUND_COLOR = widgetutil.css_to_color('#e1edf7')

ERROR_COLOR = (0.90, 0.0, 0.0)
BLINK_COLOR = widgetutil.css_to_color('#fffb83')

class LowerBox(widgetset.Background):
    def size_request(self, layout_manager):
        return (0, 63)

    def draw(self, context, layout_manager):  
        gradient = widgetset.Gradient(0, 2, 0, context.height)
        gradient.set_start_color(widgetutil.css_to_color('#d4d4d4'))
        gradient.set_end_color(widgetutil.css_to_color('#a8a8a8'))
        context.rectangle(0, 2, context.width, context.height)
        context.gradient_fill(gradient)

        context.set_line_width(1)
        context.move_to(0, 0.5)
        context.line_to(context.width, 0.5)
        context.set_color(widgetutil.css_to_color('#585858'))
        context.stroke()
        context.move_to(0, 1.5)
        context.line_to(context.width, 1.5)
        context.set_color(widgetutil.css_to_color('#e6e6e6'))
        context.stroke()

class TabRenderer(widgetset.CustomCellRenderer):
    MIN_WIDTH = 120
    MIN_ICON_WIDTH_TALL = 21
    MIN_ICON_WIDTH = 16
    MIN_HEIGHT = 24
    MIN_HEIGHT_TALL = 27
    TALL_FONT_SIZE = 1.0
    FONT_SIZE = 0.85
    SELECTED_FONT_COLOR = widgetutil.WHITE
    SELECTED_FONT_SHADOW = widgetutil.BLACK

    def is_tall(self):
        if (not use_custom_tablist_font or
            (hasattr(self.data, 'tall') and self.data.tall)):
            return True
        return False

    def get_size(self, style, layout_manager):
        if self.is_tall():
            min_height = self.MIN_HEIGHT_TALL
            font_scale = self.TALL_FONT_SIZE
        else:
            min_height = self.MIN_HEIGHT
            font_scale = self.FONT_SIZE
        return (self.MIN_WIDTH, max(min_height,
            layout_manager.font(font_scale).line_height()))

    def render(self, context, layout_manager, selected, hotspot, hover):
        layout_manager.set_text_color(context.style.text_color)
        bold = False
        if selected:
            bold = True
            if use_custom_tablist_font:
                layout_manager.set_text_color(self.SELECTED_FONT_COLOR)
                layout_manager.set_text_shadow(widgetutil.Shadow(
                        self.SELECTED_FONT_SHADOW, 0.5, (0, 1), 0))
        if not use_custom_tablist_font or getattr(self.data, 'tall', False):
            min_icon_width = self.MIN_ICON_WIDTH_TALL
            layout_manager.set_font(self.TALL_FONT_SIZE, bold=bold)
        else:
            min_icon_width = self.MIN_ICON_WIDTH
            layout_manager.set_font(self.FONT_SIZE, bold=bold)
        titlebox = layout_manager.textbox(self.data.name)
        hbox = cellpack.HBox(spacing=4)
        self.pack_leading_space(hbox)
        if selected and hasattr(self.data, 'active_icon'):
            icon = self.data.active_icon
        else:
            icon = self.data.icon
        alignment = cellpack.Alignment(icon, yalign=0.5, yscale=0.0,
                xalign=0.0, xscale=0.0, min_width=min_icon_width)
        hbox.pack(alignment)
        # morgan wants the text to be 1px higher than align_middle() would
        # place it, so we align to slightly less than 0.5
        alignment = cellpack.Alignment(cellpack.TruncatedTextLine(titlebox),
                                       yalign=0.45, yscale=0.0)
        hbox.pack(alignment, expand=True)
        layout_manager.set_font(0.77, bold=True)
        self.pack_bubbles(hbox, layout_manager, selected=selected)
        hbox.pack_space(2)
        alignment = cellpack.Alignment(hbox, yscale=0.0, yalign=0.5)
        if self.blink:
            renderer = cellpack.Background(alignment)
            renderer.set_callback(self.draw_blink_background)
        else:
            renderer = alignment
        renderer.render_layout(context)

    def pack_leading_space(self, hbox):
        pass

    def pack_bubbles(self, hbox, layout_manager, selected=False):
        if self.updating_frame > -1:
            image_name = 'icon-updating-%s' % self.updating_frame
            updating_image = widgetutil.make_surface(image_name)
            alignment = cellpack.Alignment(
                updating_image, yalign=0.5,yscale=0.0,
                xalign=0.0, xscale=0.0, min_width=20)
            hbox.pack(alignment)
        else:
            if self.data.unwatched > 0:
                self.pack_bubble(hbox, layout_manager, self.data.unwatched,
                        UNPLAYED_COLOR, selected=selected)
            if self.data.available > 0:
                self.pack_bubble(hbox, layout_manager, self.data.available,
                        AVAILABLE_COLOR, selected=selected)

    def pack_bubble(self, hbox, layout_manager, count, color, selected=False):
        radius = int(layout_manager.current_font.line_height() / 2.0 )+ 1
        if selected:
            layout_manager.set_text_color(widgetutil.BLACK)
            layout_manager.set_text_shadow(None)
            color = widgetutil.WHITE
        else:
            layout_manager.set_text_color(widgetutil.WHITE)
            layout_manager.set_text_shadow(widgetutil.Shadow(
                self.SELECTED_FONT_SHADOW, 0.5, (0, 1), 0))
        if PLATFORMNAME == 'windows':
            # XXX FIXME HACK For 17305, the bubble text needs to move
            # up 2px on Windows.  I can't figure out what the
            # difference is between Linux and Windows; it's not
            # miro.plat.frontends.widgets.use_custom_tablist_font.
            # Either way, there are better things to be spending time
            # on right now.
            bottom_extra = 2
        else:
            bottom_extra = 0
        if PLATFORMNAME == 'osx':
            # XXX FIXME HACK 17305, text on OSX needs to move 1px to the left
            left_extra = 0.5
        else:
            left_extra = 0
        if self.is_tall():
            margin = (0, radius + left_extra,
                      2 + bottom_extra, radius - left_extra)
        else:
            margin = (1, radius + left_extra,
                      1 + bottom_extra, radius - left_extra)
        background = cellpack.Background(layout_manager.textbox(str(count)),
                margin=margin)
        background.set_callback(self.draw_bubble, color)
        hbox.pack(cellpack.align_middle(background))

    def draw_bubble(self, context, x, y, width, height, color):
        if color == AVAILABLE_COLOR:
            name = 'blue-bubble'
        elif color == widgetutil.WHITE:
            name = 'white-bubble'
        elif color == DOWNLOADING_COLOR:
            name = 'orange-bubble'
        else:
            name = 'green-bubble'
        def get_surface(part):
            return imagepool.get_surface(resources.path(
                'images/%s_%s.png' % (name, part)))
        left_surface = get_surface('left')
        center_surface = get_surface('center')
        right_surface = get_surface('right')

        center_width = int(width - left_surface.width - right_surface.width)
        center_height = int(center_surface.height)
        # Let's just take one image height, they should be the same
        y -= int((center_surface.height - height) / 2)
        if self.is_tall():
            y -= 1 # start 1px higher
        x = int(x)

        left_width = int(left_surface.width)
        left_height = int(left_surface.height)

        right_width = int(right_surface.width)
        right_height = int(right_surface.height)

        width = int(width)
        height = int(height)

        left_surface.draw(context, x, y, left_width, left_height)
        center_surface.draw(context, x + left_width, y, center_width,
                            center_height)
        right_surface.draw(context, x + width - right_width, y,
                           right_width, right_height)

    def draw_blink_background(self, context, x, y, width, height):
        context.rectangle(x, y, width, height)
        context.set_color(BLINK_COLOR)
        context.fill()

class StaticTabRenderer(TabRenderer):
    def pack_bubbles(self, hbox, layout_manager, selected=False):
        if self.updating_frame > -1:
            image_name = 'icon-updating-%s' % self.updating_frame
            updating_image = widgetutil.make_surface(image_name)
            alignment = cellpack.Alignment(
                updating_image, yalign=0.5,yscale=0.0,
                xalign=0.0, xscale=0.0, min_width=20)
            hbox.pack(alignment)
        elif self.data.unwatched > 0:
            self.pack_bubble(hbox, layout_manager, self.data.unwatched,
                    UNPLAYED_COLOR, selected=selected)
        if self.data.downloading > 0:
            self.pack_bubble(hbox, layout_manager, self.data.downloading,
                    DOWNLOADING_COLOR, selected=selected)

class ConnectTabRenderer(TabRenderer):
    def __init__(self):
        TabRenderer.__init__(self)
        self.hbox = None

    def pack_bubbles(self, hbox, layout_manager, selected=False):
        if getattr(self.data, 'fake', False):
            return
        self.hbox = None
        if self.updating_frame > -1:
            return TabRenderer.pack_bubbles(self, hbox, layout_manager)
        if getattr(self.data, 'mount', None):
            eject_image = widgetutil.make_surface('icon-eject')
            hotspot = cellpack.Hotspot('eject-device', eject_image)
            alignment = cellpack.Alignment(hotspot, yalign=0.5, yscale=0.0,
                                           xalign=0.0, xscale=0.0,
                                           min_width=20)
            hbox.pack(alignment)
            self.hbox = hbox

    def hotspot_test(self, style, layout_manager, x, y, width, height):
        if self.hbox is None:
            return None
        hotspot_info = self.hbox.find_hotspot(x, y, width, height)
        if hotspot_info is None:
            return None
        else:
            return hotspot_info[0]

# Renderers for the list view
class ListViewRendererText(widgetset.ItemListRendererText):
    """Renderer for list view columns that are just plain text"""

    bold = False
    color = widgetutil.BLACK
    font_size = widgetutil.font_scale_from_osx_points(11)
    min_width = 50
    right_aligned = False

    def __init__(self):
        widgetset.ItemListRendererText.__init__(self)
        self.set_bold(self.bold)
        self.set_color(self.color)
        self.set_font_scale(self.font_size)
        if self.right_aligned:
            self.set_align('right')

    def get_value(self, info):
        return getattr(info, self.attr_name)

class DescriptionRenderer(ListViewRendererText):
    color = (0.6, 0.6, 0.6)
    attr_name = 'description_oneline'

class FeedNameRenderer(ListViewRendererText):
    attr_name = 'feed_name'

class DateRenderer(ListViewRendererText):
    min_width = 70

    def get_value(self, info):
        return displaytext.date_slashes(info.release_date)

class LengthRenderer(ListViewRendererText):
    def get_value(self, info):
        return displaytext.short_time_string(info.duration)

class ETARenderer(ListViewRendererText):
    right_aligned = True

    def get_value(self, info):
        if info.is_download and not info.is_paused:
            dl_info = info.download_info
            if dl_info.eta > 0:
                return displaytext.time_string(dl_info.eta)
        return ''

class TorrentDetailsRenderer(ListViewRendererText):
    def get_value(self, info):
        if not info.download_info or not info.download_info.torrent:
            return ''

        details = _(
            "S: %(seeders)s  |  "
            "L: %(leechers)s  |  "
            "UR: %(up_rate)s  |  "
            "UT: %(up_total)s  |  "
            "DR: %(down_rate)s  |  "
            "DT: %(down_total)s  |  "
            "R: %(upload_ratio)s",
            {"seeders": info.seeders,
             "leechers": info.leechers,
             "up_rate": info.upload_rate_text,
             "up_total": info.upload_size_text,
             "down_rate": info.download_rate_text,
             "down_total": info.current_size_text,
             "ratio": info.upload_ratio_text})
        return details

class DownloadRateRenderer(ListViewRendererText):
    right_aligned = True

    def get_value(self, info):
        if info.is_download and not info.is_paused:
            dl_info = info.download_info
            return displaytext.download_rate(dl_info.rate)
        else:
            return ''

class SizeRenderer(ListViewRendererText):
    right_aligned = True
    def get_value(self, info):
        return displaytext.size_string(info.size)

class ArtistRenderer(ListViewRendererText):
    attr_name = 'artist'

class AlbumRenderer(ListViewRendererText):
    attr_name = 'album'

class TrackRenderer(ListViewRendererText):
    def get_value(self, info):
        return displaytext.integer(info.track)

class YearRenderer(ListViewRendererText):
    def get_value(self, info):
        return displaytext.integer(info.year)

class GenreRenderer(ListViewRendererText):
    attr_name = 'genre'

class DateAddedRenderer(ListViewRendererText):
    min_width = 70
    def get_value(self, info):
        return displaytext.date_slashes(info.date_added)

class LastPlayedRenderer(ListViewRendererText):
    def get_value(self, info):
        return displaytext.date_slashes(info.last_played)

class DRMRenderer(ListViewRendererText):
    def get_value(self, info):
        return _("Locked") if info.has_drm else u""

class FileTypeRenderer(ListViewRendererText):
    attr_name = 'file_format'

class ShowRenderer(ListViewRendererText):
    attr_name = 'show'

class KindRenderer(ListViewRendererText):
    def get_value(self, info):
        if info.kind == 'movie':
            return _("Movie")
        elif info.kind == 'show':
            return _("Show")
        elif info.kind == 'clip':
            return _("Clip")
        elif info.kind == 'podcast':
            return _("Podcast")
        else:
            return None

class PlaylistOrderRenderer(ListViewRendererText):
    """Displays the order an item is in a particular playlist.
    """
    def __init__(self, playlist_sorter):
        ListViewRendererText.__init__(self)
        self.playlist_sorter = playlist_sorter

    def get_value(self, info):
        return str(self.playlist_sorter.sort_key(info) + 1)

class ListViewRenderer(widgetset.ItemListRenderer):
    """Renderer for more complex list view columns.

    This class is useful for renderers that use the cellpack.Layout class.
    """
    font_size = widgetutil.font_scale_from_osx_points(11)
    default_text_color = widgetutil.BLACK
    selected_text_color = widgetutil.WHITE
    min_width = 5
    min_height = 16 # 21px total - 5px spacing

    def hotspot_test(self, style, layout_manager, x, y, width, height):
        layout = self.layout_all(layout_manager, width, height, False)
        hotspot_info = layout.find_hotspot(x, y)
        if hotspot_info is None:
            return None
        hotspot, x, y = hotspot_info
        return hotspot

    def get_size(self, style, layout_manager):
        layout_manager.set_font(self.font_size)
        height = max(self.min_height,
                layout_manager.current_font.line_height())
        return (self.min_width, height)

    def render(self, context, layout_manager, selected, hotspot, hover):
        layout = self.layout_all(layout_manager, context.width,
                                 context.height, selected)
        layout.draw(context)

    def layout_all(self, layout_manager, width, height, selected):
        """Layout the contents of this cell

        Subclasses must implement this method

        :param layout_manager: LayoutManager object
        :param width: width of the area to lay the cell out in
        :param height: height of the area to lay the cell out in
        :returns: cellpack.Layout object
        """
        raise NotImplementedError()


class NameRenderer(ListViewRenderer):
    min_width = 120 # GTK isn't returning enough size, so add some extra

    def render(self, context, layout_manager, selected, hotspot, hover):
        layout_manager.set_font(self.font_size)
        if context.style.text_color != widgetutil.BLACK:
            layout_manager.set_text_color(context.style.text_color)
        else:
            layout_manager.set_text_color(self.default_text_color)
        ListViewRenderer.render(self, context, layout_manager, selected,
                                hotspot, hover)

    def layout_all(self, layout_manager, width, height, selected):
        # make a Layout Object
        layout = cellpack.Layout()
        # add the text
        textbox = layout_manager.textbox(self.info.title)
        textbox.set_wrap_style('truncated-char')
        # 4px here is half of ListView.COLUMN_PADDING - 2px for luck
        layout.add_text_line(textbox, 4, 0, width)
        # middle-align everything
        layout.center_y(top=0, bottom=height)
        return layout

class StatusRenderer(ListViewRenderer):
    BUTTONS = ('pause', 'resume', 'cancel', 'keep')
    min_width = 100
    min_width = 120 # GTK isn't returning enough size, so add some extra
    button_font_size = 0.77

    def __init__(self):
        ListViewRenderer.__init__(self)
        self.button = {}
        for button in self.BUTTONS:
            path = resources.path('images/%s-button.png' % button)
            self.button[button] = imagepool.get_surface(path)
        path = resources.path('images/download-arrow.png')
        self.download_icon = imagepool.get_surface(path)

    def layout_all(self, layout_manager, width, height, selected):
        # add the button, if needed
        if self.should_show_download_button():
            layout = self.layout_text(layout_manager, width, height)
            
            button = self.make_button(layout_manager)
            button_x = width - button.get_size()[0]
            layout.add_image(button, button_x, 0, hotspot='download')
            # text should end at the start of the button
            layout.center_y(top=0, bottom=height)
            return layout

        if self.info.is_download:
            return self.layout_progress(layout_manager, width, height)
        else:
            return self.layout_text(layout_manager, width, height)

    def make_button(self, layout_manager):
        layout_manager.set_font(self.button_font_size)
        if self.info.device or self.info.remote:
            text = DOWNLOAD_TO_MY_MIRO_TEXT
        else:
            text = DOWNLOAD_TEXT
        button = layout_manager.button(text)
        button.set_icon(self.download_icon)
        return button

    def should_show_download_button(self):
        nonlocal = self.info.device or self.info.remote
        return (not self.info.downloaded and not self.info.is_download)

    def layout_progress(self, layout_manager, width, height):
        """Handle layout when we should display a progress bar """

        layout = cellpack.Layout()
        # add left button
        if not info.is_paused:
            left_button = 'pause'
        else:
            left_button = 'resume'
        left_button_rect = layout.add_image(self.button[left_button], 0, 0,
                hotspot=left_button)
        # add right button
        right_x = width - self.button['cancel'].width
        layout.add_image(self.button['cancel'], right_x, 0, hotspot='cancel')
        # pack the progress bar in the center
        progress_left = left_button_rect.width + 2
        progress_right = right_x - 2
        progress_rect = cellpack.LayoutRect(progress_left, 0,
                progress_right-progress_left, height)

        layout.add_rect(progress_rect, ItemProgressBarDrawer(self.info).draw)
        # middle-align everything
        layout.center_y(top=0, bottom=height)
        return layout

    def layout_text(self, layout_manager, width, height):
        """Handle layout when we should display status text"""
        layout = cellpack.Layout()
        text, color = self._calc_status_text()
        if text:
            layout_manager.set_font(self.font_size, bold=True)
            layout_manager.set_text_color(color)
            textbox = layout_manager.textbox(text)
            layout.add_text_line(textbox, 0, 0, width)
            self.add_extra_button(layout, width)
        # middle-align everything
        layout.center_y(top=0, bottom=height)
        return layout

    def _calc_status_text(self):
        """Calculate the text/color for our status line.

        :returns: (text, color) tuple
        """
        if self.info.downloaded:
            if self.info.is_playable:
                if not self.info.video_watched:
                    return (_('Unplayed'), UNPLAYED_COLOR)
                elif self.info.expiration_date:
                    text = displaytext.expiration_date_short(
                            self.info.expiration_date)
                    return (text, EXPIRING_TEXT_COLOR)
        elif self.info.is_paused:
            return (_('paused'), DOWNLOADING_COLOR)
        elif self.info.pending_manual_download:
            return (_('queued'), DOWNLOADING_COLOR)
        elif self.info.is_failed_download:
            return (self.info.download_info.short_reason_failed,
                    ERROR_COLOR)
        elif self.info.is_download and self.info.rate is None:
            return (self.info.download_info.startup_activity,
                    DOWNLOADING_COLOR)
        elif self.info.new:
            return (_('Newly Available'), AVAILABLE_COLOR)
        return ('', self.default_text_color)

    def add_extra_button(self, layout, width):
        """Add a button to the right of the text, if needed"""

        if self.info.expiration_date:
            button_name = 'keep'
        elif self.info.pending_manual_download:
            button_name = 'cancel'
        else:
            return
        button = self.button[button_name]
        button_x = width - button.width # right-align
        layout.add_image(button, button_x, 0, hotspot=button_name)

class RatingRenderer(widgetset.ItemListRenderer):
    """Render ratings column

    This cell supports updating based on hover states and rates items based on
    the user clicking in the cell.
    """

    # NOTE: we don't inherit from ListViewRenderer because we handle
    # everything ourselves, without using the Layout class

    ICON_STATES = ('yes', 'no', 'probably', 'unset')
    ICON_HORIZONTAL_SPACING = 2
    ICON_COUNT = 5

    def __init__(self):
        widgetset.ItemListRenderer.__init__(self)
        self.want_hover = True
        self.icon = {}
        # TODO: to support scaling, we need not to check min_height until after
        # the renderer first gets its layout_manager
#        self.icon_height = int(self.height * 9.0 / 14.0)
        self.icon_height = 9
        self.icon_width = self.icon_height
        for state in RatingRenderer.ICON_STATES:
            path = resources.path('images/star-%s.png' % state)
            self.icon[state] = imagepool.get_surface(path,
                               (self.icon_width, self.icon_height))
        self.min_width = self.width = int((self.icon_width +
                                           self.ICON_HORIZONTAL_SPACING) *
                                          self.ICON_COUNT)
        self.hover = None

    def hotspot_test(self, style, layout_manager, x, y, width, height):
        hotspot_index = self.icon_index_at_x(x)
        if hotspot_index is not None:
            return "rate:%s" % hotspot_index
        else:
            return None

    def icon_index_at_x(self, x):
        """Calculate the index of the icon

        :param x: x-coordinate to use
        :returns: index of the icon at x, or None
        """
        # use icon_width + ICON_HORIZONTAL_SPACING to calculate which star we
        # are over.  Don't worry about the y-coord

        # make each icon's area include the spacing around it
        icon_width_with_pad = self.icon_width + self.ICON_HORIZONTAL_SPACING
        # translate x so that x=0 is to the left of the cell, based on
        # ICON_HORIZONTAL_SPACING.  This effectively centers the spacing on
        # each icon, rather than having the spacing be to the right.
        x += int(self.ICON_HORIZONTAL_SPACING / 2)
        # finally, calculate which icon is hit
        if 0 <= x < icon_width_with_pad * self.ICON_COUNT:
            return int(x // icon_width_with_pad) + 1
        else:
            return None

    def get_size(self, style, layout_manager):
        return self.width, self.icon_height

    def render(self, context, layout_manager, selected, hotspot, hover):
        if hover:
            self.hover = self.icon_index_at_x(hover[0])
        else:
            self.hover = None
        x_pos = 0
        y_pos = int((context.height - self.icon_height) / 2)
        for i in xrange(self.ICON_COUNT):
            icon = self._get_icon(i + 1)
            icon.draw(context, x_pos, y_pos, icon.width, icon.height)
            x_pos += self.icon_width + self.ICON_HORIZONTAL_SPACING

    def _get_icon(self, i):
        """Get the ith rating icon, starting at 1.

        :returns: ImageSurface
        """
        # yes/no for explicit ratings; maybe/no for hover ratings; probably/no
        # for auto ratings; unset when no explicit, auto, or hover rating
        if self.hover is not None:
            if self.hover >= i:
                state = 'yes'
            else:
                state = 'no'
        else:
            if self.info.rating is not None:
                if self.info.rating >= i:
                    state = 'yes'
                else:
                    state = 'no'
            elif self.info.auto_rating is not None:
                if self.info.auto_rating >= i:
                    state = 'probably'
                else:
                    state = 'unset'
            else:
                state = 'unset'
        return self.icon[state]

class StateCircleRenderer(widgetset.ItemListRenderer):
    """Renderer for the state circle column."""

    # NOTE: we don't inherit from ListViewRenderer because we handle
    # everything ourselves, without using the Layout class

    ICON_STATES = ('unplayed', 'new', 'playing', 'downloading')
    ICON_PROPORTIONS = 7.0 / 9.0 # width / height
    min_width = 7
    min_height = 9

    def __init__(self):
        widgetset.ItemListRenderer.__init__(self)
        self.icon = {}
        for state in StateCircleRenderer.ICON_STATES:
            path = resources.path('images/status-icon-%s.png' % state)
            self.icon[state] = imagepool.get_surface(path)

    def get_size(self, style, layout_manager):
        return self.min_width, self.min_height

    def hotspot_test(self, style, layout_manager, x, y, width, height):
        return None

    def render(self, context, layout_manager, selected, hotspot, hover):
        icon = self.calc_icon()
        if icon is None:
            return
        # center icon vertically and horizontally
        x = (context.width - icon.width) // 2
        y = (context.height - icon.height) // 2
        icon.draw(context, x + 1, y, icon.width, icon.height)

    def calc_icon(self):
        """Get the icon we should show.

        :returns: ImageSurface to display
        """
        if self.info.is_download:
            return self.icon['downloading']
        elif app.playback_manager.is_playing_item(self.info):
            return self.icon['playing']
        elif self.info.new:
            return self.icon['new']
        elif self.info.downloaded and not self.info.video_watched:
            return self.icon['unplayed']
        else:
            return None

class _MultiRowAlbumRenderStrategy(object):
    """Utility class that controls what we render in MultiRowAlbumRenderer

    We subclass for each of the different modes that we use (standard, feed,
    videos, etc).

    This class is just used internally.
    """

    def get_image_path(self, item_info, first_info):
        """Get a path to the image we should draw."""
        raise NotImplementedError()

    def get_album(self, item_info, first_info):
        """Get album name to render."""
        raise NotImplementedError()

    def get_artist(self, item_info, first_info):
        """Get artist name to render."""
        raise NotImplementedError()

    def get_track_number(self, item_info, first_info):
        """Track number to show"""
        raise NotImplementedError()

class _StandardRenderStrategy(_MultiRowAlbumRenderStrategy):
    def get_image_path(self, item_info, first_info):
        if first_info.cover_art is not None:
            return first_info.cover_art
        else:
            return first_info.thumbnail

    def get_album(self, item_info, first_info):
        return item_info.album

    def get_artist(self, item_info, first_info):
        return item_info.artist

    def get_track_number(self, item_info, first_info):
        if item_info.track is not None:
            return item_info.track
        else:
            return ''

class _FeedRenderStrategy(_MultiRowAlbumRenderStrategy):
    def get_image_path(self, item_info, first_info):
        try:
            feed_info = widgetutil.get_feed_info(item_info.feed_id)
        except KeyError:
            return first_info.thumbnail
        else:
            return feed_info.thumbnail

    def get_album(self, item_info, first_info):
        return ''

    def get_artist(self, item_info, first_info):
        return item_info.feed_name

    def get_track_number(self, item_info, first_info):
        return ''

class _VideoRenderStrategy(_MultiRowAlbumRenderStrategy):
    def get_image_path(self, item_info, first_info):
        return first_info.thumbnail

    def get_album(self, item_info, first_info):
        if item_info.show:
            return item_info.show
        elif item_info.feed_name:
            return item_info.feed_name
        else:
            return None

    def get_artist(self, item_info, first_info):
        return None

    def get_track_number(self, item_info, first_info):
        return ''

class MultiRowAlbumRenderer(widgetset.ItemListRenderer):
    """Renderer for album view."""

    IGNORE_PADDING = True
    DRAW_BACKGROUND = False

    IMAGE_MARGIN_TOP = 4
    IMAGE_MARGIN_BOTTOM = 3
    IMAGE_MARGIN_LEFT = 7
    IMAGE_MARGIN_RIGHT = 6

    MIN_TEXT_WIDTH = 78
    TEXT_PADDING_RIGHT = 6
    TRACK_NUMBER_MARGIN_RIGHT = 13

    BACKGROUND_COLOR = widgetutil.WHITE
    TEXT_COLOR = widgetutil.BLACK
    TRACK_TEXT_COLOR = widgetutil.css_to_color('#969696')
    BOTTOM_LINE_COLOR = widgetutil.css_to_color('#dddddd')
    FONT_SIZE = widgetutil.font_scale_from_osx_points(11)

    min_width = 260

    def __init__(self):
        widgetset.ItemListRenderer.__init__(self)
        self._render_strategy = _StandardRenderStrategy()
        self._setup_default_image_map()

    def _setup_default_image_map(self):
        """Setup the _default_image_map attribute.

        _default_image_map maps the default images for things to a default
        image that looks better in album view.
        """
        # check if we're using one of the default image files and switch to an
        # album-view-specific default file in that case
        mappings = [
            ('thumb-default-audio.png', 'album-view-default-audio.png'),
            ('thumb-default-video.png', 'album-view-default-video.png'),
            ('icon-podcast-small.png', 'album-view-default-podcast.png'),
            ('icon-watched-folder.png', 'album-view-watched-folder.png'),
        ]
        self._default_image_map = {}
        for src, dest in mappings:
            src_path = resources.path('images/%s' % src)
            dest_path = resources.path('images/%s' % dest)
            self._default_image_map[src_path] = dest_path

    def get_image_path(self):
        image_path = self._render_strategy.get_image_path(
            self.info, self.get_first_info())
        if image_path in self._default_image_map:
            return self._default_image_map[image_path]
        else:
            return image_path

    def get_album(self):
        return self._render_strategy.get_album(self.info,
                                               self.get_first_info())

    def get_artist(self):
        return self._render_strategy.get_artist(self.info,
                                                self.get_first_info())

    def get_track_number(self):
        return self._render_strategy.get_track_number(self.info,
                                                      self.get_first_info())

    def get_current_row(self):
        return self.group_info[0]

    def get_total_rows(self):
        return self.group_info[1]

    def get_first_info(self):
        return self.group_info[2]

    def switch_mode(self, new_mode):
        """Switch which mode we use to render the album art.

        Currently there are 3 modes:

        - 'standard' -- standard view of the data
        - 'feed' -- use feed info instead of album info
        - 'video' -- mode for the all videos tab
        """
        if new_mode == 'standard':
            self._render_strategy = _StandardRenderStrategy()
        elif new_mode == 'feed':
            self._render_strategy = _FeedRenderStrategy()
        elif new_mode == 'video':
            self._render_strategy = _VideoRenderStrategy()
        else:
            raise ValueError("Unknown mode: %s" % new_mode)

    def get_size(self, style, layout_manager):
        # return 0 for height because we render to multiple columns.  We let
        # the other columns determin the row height
        return self.min_width, 0

    def hotspot_test(self, style, layout_manager, x, y, width, height):
        return 'album-click'

    def render(self, context, layout_manager, selected, hotspot, hover):
        if not self.sanity_check_before_render(context):
            return

        # draw our background color behind everything.  We need this in case
        # there's transparency in our album art
        context.set_color(self.BACKGROUND_COLOR)
        context.rectangle(0, 0, context.width, context.height)
        context.fill()

        self.calc_album_art_size(context)
        self.render_album_art(context)
        self.render_track_number(context, layout_manager)
        self.render_album_or_artist(context, layout_manager)

    def sanity_check_before_render(self, context):
        """Do some sanity checking before starting to render things.

        Returns True if we're okay to render, False if we should bail
        """
        if self.group_info is None:
            # we can't render if group_info isn't set
            logging.warn("group_info is None in MultiRowAlbumRenderer")
            return False
        if context.height == 0:
            # not sure how this would happen, but we need to avoid
            # divide-by-zero errors if it does
            logging.warn("row height is 0 in MultiRowAlbumRenderer")
            return False
        return True

    def calc_album_art_size(self, context):
        """Calculate how big we are going to draw album art.

        This is currently big enough so it fits in 6 rows with the top/bottom
        padding.
        """
        self.album_art_size = context.height * 6
        self.album_art_size -= (self.IMAGE_MARGIN_TOP +
                self.IMAGE_MARGIN_BOTTOM)

    def make_album_art(self, context):
        """Make an image to draw as album art.

        Returns ImageSurface to draw or None if we don't have anything
        """
        if self.get_total_rows() < 6:
            # don't draw album art if we have less than 6 items in the group
            return None

        album_art_path = self.get_image_path()
        if album_art_path is None:
            return None
        return imagepool.get_surface(album_art_path,
                size=(self.album_art_size, self.album_art_size),
                                     invalidator=util.mtime_invalidator(
                album_art_path))

    def render_album_art(self, context):
        album_art = self.make_album_art(context)
        if (album_art is not None and
                self.cell_contains_album_art(context, album_art)):
            self.render_album_art_slice(context, album_art)

    def cell_contains_album_art(self, context, album_art):
        """Does this cell contain a portion of the album art?
        """
        album_art_bottom = album_art.height + self.IMAGE_MARGIN_TOP
        cell_top = self.get_current_row() * context.height
        cell_bottom = cell_top + context.height
        return (cell_bottom > self.IMAGE_MARGIN_TOP and
                cell_top < album_art_bottom)

    def render_album_art_slice(self, context, image):
        """Render the slice of the album art for this cell."""

        if context.width < image.width:
            # not enough width to draw
            return

        # setup variables to track where we are copying from and to

        dest_x = self.IMAGE_MARGIN_LEFT
        width = image.width

        dest_y = 0
        height = context.height

        src_x = 0
        src_y = self.get_current_row() * context.height - self.IMAGE_MARGIN_TOP

        if src_y < 0:
            # The cell is contains the top padding for our image.
            # move dest_y and src_y down
            dest_y -= src_y
            src_y = 0
            # descrease height
            height -= dest_y
        src_y_bottom = src_y + height
        if src_y_bottom > image.height:
            # The cell is contains the bottom padding for our image.
            # decrease height
            extra_space = src_y_bottom - image.height
            height -= extra_space
        # draw our image slice
        if height > 0:
            image.draw_rect(context, dest_x, dest_y, src_x, src_y,
                    width, height)

    def render_album_or_artist(self, context, layout_manager):
        x = (self.album_art_size + self.IMAGE_MARGIN_LEFT +
                self.IMAGE_MARGIN_RIGHT)
        if self.get_current_row() == 0:
            text = self.get_artist()
            bold = True
        elif self.get_current_row() == 1:
            text = self.get_album()
            bold = False
        else:
            return

        width = self.album_artist_text_end - x
        if width < 10:
            # don't try to render if we have a really small, or negative
            # amount of space
            return
        # setup a textbox for the text
        layout_manager.set_font(self.FONT_SIZE, bold=bold)
        layout_manager.set_text_color(self.TEXT_COLOR)
        textbox = layout_manager.textbox(text)
        # truncate the textbox to the area we have in a cell.
        textbox.set_wrap_style('truncated-char')
        textbox.set_width(width)
        # middle-align the text to line-up with the other cells
        line_height = textbox.font.line_height()
        y = (context.height - line_height) / 2.0
        # okay, ready to draw
        textbox.draw(context, x, y, width, line_height)

    def render_track_number(self, context, layout_manager):
        # setup a textbox for the text
        layout_manager.set_font(self.FONT_SIZE)
        layout_manager.set_text_color(self.TRACK_TEXT_COLOR)
        textbox = layout_manager.textbox(str(self.get_track_number()))
        # place the text on the right-side of the cell
        text_width, text_height = textbox.get_size()
        x = context.width - self.TEXT_PADDING_RIGHT - text_width
        # middle-align the text to line-up with the other cells
        y = (context.height - text_height) // 2
        # okay, ready to draw
        textbox.draw(context, x, y, text_width, text_height)
        self.album_artist_text_end = x - self.TEXT_PADDING_RIGHT

class ProgressBarColorSet(object):
    PROGRESS_BASE_TOP = (0.92, 0.53, 0.21)
    PROGRESS_BASE_BOTTOM = (0.90, 0.45, 0.08)
    BASE = (0.76, 0.76, 0.76)

    PROGRESS_BORDER_TOP = (0.80, 0.51, 0.28)
    PROGRESS_BORDER_BOTTOM = (0.76, 0.44, 0.16)
    PROGRESS_BORDER_HIGHLIGHT = (1.0, 0.68, 0.42)

    BORDER_GRADIENT_TOP = (0.58, 0.58, 0.58)
    BORDER_GRADIENT_BOTTOM = (0.68, 0.68, 0.68)

class ProgressBarDrawer(cellpack.Packer):
    """Helper object to draw the progress bar (which is actually quite
    complicated.
    """
    HEIGHT_PROPORTION = 0.6

    def __init__(self, progress_ratio, color_set):
        self.progress_ratio = progress_ratio
        self.color_set = color_set

    def _layout(self, context, x, y, width, height):
        self.x, self.y, self.width, self.height = x, y, width, height
        self.height *= self.HEIGHT_PROPORTION
        self.y += (height - self.height) / 2
        context.set_line_width(1)
        self.progress_width = int(width * self.progress_ratio)
        self.half_height = self.height / 2
        if self.progress_width < self.half_height:
            self.progress_end = 'left'
        elif width - self.progress_width < self.half_height:
            self.progress_end = 'right'
        else:
            self.progress_end = 'middle'
        self._draw_base(context)
        self._draw_border(context)

    def _draw_base(self, context):
        # set the clip region to be the outline of the progress bar.  This way
        # we can just draw rectangles and not have to worry about the circular
        # edges.
        context.save()
        self._outer_border(context)
        context.clip()
        # draw our rectangles
        self._progress_top_rectangle(context)
        context.set_color(self.color_set.PROGRESS_BASE_TOP)
        context.fill()
        self._progress_bottom_rectangle(context)
        context.set_color(self.color_set.PROGRESS_BASE_BOTTOM)
        context.fill()
        self._non_progress_rectangle(context)
        context.set_color(self.color_set.BASE)
        context.fill()
        # restore the old clipping region
        context.restore()

    def _draw_border(self, context):
        # Set the clipping region to be the on the border of the progress bar.
        # This is a little tricky.  We have to make a path around the outside
        # of the border that goes in one direction, then a path that is inset
        # by 1 px going the other direction.  This causes the clip region to
        # be the 1 px area between the 2 paths.
        context.save()
        self._outer_border(context)
        self._inner_border(context)
        context.clip()
        # Render the borders
        self._progress_top_rectangle(context)
        context.set_color(self.color_set.PROGRESS_BORDER_TOP)
        context.fill()
        self._progress_bottom_rectangle(context)
        context.set_color(self.color_set.PROGRESS_BORDER_BOTTOM)
        context.fill()
        self._non_progress_rectangle(context)
        gradient = widgetset.Gradient(self.x + self.progress_width, self.y,
                                      self.x + self.progress_width,
                                      self.y + self.height)
        gradient.set_start_color(self.color_set.BORDER_GRADIENT_TOP)
        gradient.set_end_color(self.color_set.BORDER_GRADIENT_BOTTOM)
        context.gradient_fill(gradient)
        # Restore the old clipping region
        context.restore()
        self._draw_progress_highlight(context)
        self._draw_progress_right(context)

    def _draw_progress_right(self, context):
        if self.progress_width == self.width:
            return
        radius = self.half_height
        if self.progress_end == 'left':
            # need to figure out how tall to draw the border.
            # pythagoras to the rescue
            a = radius - self.progress_width
            upper_height = math.floor(math.sqrt(radius**2 - a**2))
        elif self.progress_end == 'right':
            end_circle_start = self.width - radius
            a = self.progress_width - end_circle_start
            upper_height = math.floor(math.sqrt(radius**2 - a**2))
        else:
            upper_height = self.height / 2
        top = self.y + (self.height / 2) - upper_height
        context.rectangle(self.x + self.progress_width-1, top, 1, upper_height)
        context.set_color(self.color_set.PROGRESS_BORDER_TOP)
        context.fill()
        context.rectangle(self.x + self.progress_width-1, top + upper_height,
                1, upper_height)
        context.set_color(self.color_set.PROGRESS_BORDER_BOTTOM)
        context.fill()

    def _draw_progress_highlight(self, context):
        width = self.progress_width - 2 # highlight is 1 px in on both sides
        if width <= 0:
            return
        radius = self.half_height - 2
        left = self.x + 1.5 # start 1 px to the right of self.x
        top = self.y + 1.5
        context.move_to(left, top + radius)
        if self.progress_end == 'left':
            # need to figure out the angle to end on, use some trig
            length = float(radius - width)
            theta = -(PI / 2) - math.asin(length/radius)
            context.arc(left + radius, top + radius, radius, -PI, theta)
        else:
            context.arc(left + radius, top + radius, radius, -PI, -PI/2)
            # draw a line to the right end of the progress bar (but don't go
            # past the circle on the right side)
            x = min(left + width,
                    self.x + self.width - self.half_height - 0.5)
            context.line_to(x, top)
        context.set_color(self.color_set.PROGRESS_BORDER_HIGHLIGHT)
        context.stroke()

    def _outer_border(self, context):
        widgetutil.circular_rect(context, self.x, self.y,
                self.width, self.height)

    def _inner_border(self, context):
        widgetutil.circular_rect_negative(context, self.x + 1, self.y + 1,
                self.width - 2, self.height - 2)

    def _progress_top_rectangle(self, context):
        context.rectangle(self.x, self.y,
                self.progress_width, self.half_height)

    def _progress_bottom_rectangle(self, context):
        context.rectangle(self.x, self.y + self.half_height,
                self.progress_width, self.half_height)

    def _non_progress_rectangle(self, context):
        context.rectangle(self.x + self.progress_width, self.y,
                self.width - self.progress_width, self.height)

class ItemProgressBarDrawer(ProgressBarDrawer):
    def __init__(self, info):
        ProgressBarDrawer.__init__(self, 0, ProgressBarColorSet)
        if info.download_info and info.size > 0.0:
            self.progress_ratio = (float(info.download_info.downloaded_size) /
                    info.size)
        else:
            self.progress_ratio = 0.0
