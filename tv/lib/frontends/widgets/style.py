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

import math
import logging
import os

from miro import app
from miro import displaytext
from miro import prefs
from miro import signals
from miro import util
from miro.gtcache import gettext as _
from miro.frontends.widgets import cellpack
from miro.frontends.widgets import imagepool
from miro.frontends.widgets import widgetutil
from miro.plat import resources
from miro.plat.frontends.widgets import use_custom_tablist_font
from miro.plat.frontends.widgets import widgetset
from miro.plat.frontends.widgets import file_navigator_name

PI = math.pi

def css_to_color(css_string):
    parts = (css_string[1:3], css_string[3:5], css_string[5:7])
    return tuple((int(value, 16) / 255.0) for value in parts)

AVAILABLE_COLOR = (38/255.0, 140/255.0, 250/255.0) # blue
UNPLAYED_COLOR = (0.31, 0.75, 0.12) # green
DOWNLOADING_COLOR = (0.90, 0.45, 0.08) # orange
WATCHED_COLOR = (0.33, 0.33, 0.33) # dark grey
EXPIRING_COLOR = (0.95, 0.82, 0.11) # yellow-ish
EXPIRING_TEXT_COLOR = css_to_color('#7b949d')

TAB_LIST_BACKGROUND_COLOR = (221/255.0, 227/255.0, 234/255.0)

ERROR_COLOR = (0.90, 0.0, 0.0)
BLINK_COLOR = css_to_color('#fffb83')

class LowerBox(widgetset.Background):

    def size_request(self, layout_manager):
        return (0, 63)

    def draw(self, context, layout_manager):
        gradient = widgetset.Gradient(0, 2, 0, context.height)
        gradient.set_start_color(css_to_color('#d4d4d4'))
        gradient.set_end_color(css_to_color('#a8a8a8'))
        context.rectangle(0, 2, context.width, context.height)
        context.gradient_fill(gradient)

        context.set_line_width(1)
        context.move_to(0, 0.5)
        context.line_to(context.width, 0.5)
        context.set_color(css_to_color('#585858'))
        context.stroke()
        context.move_to(0, 1.5)
        context.line_to(context.width, 1.5)
        context.set_color(css_to_color('#e6e6e6'))
        context.stroke()

    def is_opaque(self):
        return True

class TabRenderer(widgetset.CustomCellRenderer):
    MIN_WIDTH = 34
    MIN_ICON_WIDTH = 25
    MIN_HEIGHT = 28
    MIN_HEIGHT_TALL = 32
    TALL_FONT_SIZE = 1.0
    FONT_SIZE = 0.85
    SELECTED_FONT_COLOR = (1, 1, 1)

    def get_size(self, style, layout_manager):
        if (not use_custom_tablist_font or
            (hasattr(self.data, 'tall') and self.data.tall)):
            min_height = self.MIN_HEIGHT_TALL
            font_scale = self.TALL_FONT_SIZE
        else:
            min_height = self.MIN_HEIGHT
            font_scale = self.FONT_SIZE
        return (self.MIN_WIDTH, max(min_height,
            layout_manager.font(font_scale).line_height()))

        return (self.MIN_WIDTH, max(self.MIN_HEIGHT,
            layout_manager.font(font_scale).line_height()))

    def render(self, context, layout_manager, selected, hotspot, hover):
        layout_manager.set_text_color(context.style.text_color)
        bold = False
        if selected:
            bold = True
            if use_custom_tablist_font:
                layout_manager.set_text_color(self.SELECTED_FONT_COLOR)
        if not use_custom_tablist_font or getattr(self.data, 'tall', False):
            layout_manager.set_font(self.TALL_FONT_SIZE, bold=bold)
        else:
            layout_manager.set_font(self.FONT_SIZE, bold=bold)
        titlebox = layout_manager.textbox(self.data.name)

        hbox = cellpack.HBox(spacing=4)
        self.pack_leading_space(hbox)
        if selected and hasattr(self.data, 'active_icon'):
            icon = self.data.active_icon
        else:
            icon = self.data.icon
        alignment = cellpack.Alignment(icon, yalign=0.5, yscale=0.0,
                xalign=0.5, xscale=0.0, min_width=self.MIN_ICON_WIDTH)
        hbox.pack(alignment)
        hbox.pack(cellpack.align_middle(cellpack.TruncatedTextLine(titlebox)), expand=True)
        layout_manager.set_font(0.77)
        layout_manager.set_text_color(widgetutil.WHITE)
        self.pack_bubbles(hbox, layout_manager)
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

    def pack_bubbles(self, hbox, layout_manager):
        if self.updating_frame > -1:
            image_name = 'icon-updating-%s' % self.updating_frame
            updating_image = widgetutil.make_surface(image_name)
            alignment = cellpack.Alignment(updating_image, yalign=0.5, yscale=0.0,
                    xalign=0.0, xscale=0.0, min_width=20)
            hbox.pack(alignment)
        else:
            if self.data.unwatched > 0:
                self.pack_bubble(hbox, layout_manager, self.data.unwatched,
                        UNPLAYED_COLOR)
            if self.data.available > 0:
                self.pack_bubble(hbox, layout_manager, self.data.available,
                        AVAILABLE_COLOR)

    def pack_bubble(self, hbox, layout_manager, count, color):
        radius = (layout_manager.current_font.line_height() + 2) / 2.0
        background = cellpack.Background(layout_manager.textbox(str(count)),
                margin=(1, radius, 1, radius))
        background.set_callback(self.draw_bubble, color)
        hbox.pack(cellpack.align_middle(background))

    def draw_bubble(self, context, x, y, width, height, color):
        radius = height / 2.0
        inner_width = width - radius * 2
        mid = y + radius

        context.move_to(x + radius, y)
        context.rel_line_to(inner_width, 0)
        context.arc(x + width - radius, mid, radius, -PI/2, PI/2)
        context.rel_line_to(-inner_width, 0)
        context.arc(x + radius, mid, radius, PI/2, -PI/2)
        context.set_color(color)
        context.fill()

    def draw_blink_background(self, context, x, y, width, height):
        context.rectangle(x, y, width, height)
        context.set_color(BLINK_COLOR)
        context.fill()

class StaticTabRenderer(TabRenderer):

    def pack_leading_space(self, hbox):
        hbox.pack_space(14)

    def pack_bubbles(self, hbox, layout_manager):
        if self.data.unwatched > 0:
            self.pack_bubble(hbox, layout_manager, self.data.unwatched,
                    UNPLAYED_COLOR)
        if self.data.downloading > 0:
            self.pack_bubble(hbox, layout_manager, self.data.downloading,
                    DOWNLOADING_COLOR)

class ConnectTabRenderer(TabRenderer):
    def pack_bubbles(self, hbox, layout_manager):
        if getattr(self.data, 'fake', False):
            return
        self.hbox = None
        if self.updating_frame > -1:
            return TabRenderer.pack_bubbles(self, hbox, layout_manager)
        if getattr(self.data, 'mount', None):
            eject_image = widgetutil.make_surface('icon-eject')
            hotspot = cellpack.Hotspot('eject-device', eject_image)
            alignment = cellpack.Alignment(hotspot, yalign=0.5, yscale=0.0,
                                           xalign=0.0, xscale=0.0, min_width=20)
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

class FakeDownloadInfo(object):
    # Fake download info object used to size items
    def __init__(self):
        self.state = 'paused'
        self.rate = 0
        self.downloaded_size = 0

class ItemRendererSignals(signals.SignalEmitter):
    """Signal emitter for ItemRenderer.

    We could make ItemRenderer subclass SignalEmitter, but since it comes from
    widgetset that seems awkward.  Instead, this class handles the signals and
    it's set as a property of ItemRenderer

    signals:
        throbber-drawn (obj, item_id) -- a progress throbber was drawn
    """
    def __init__(self):
        signals.SignalEmitter.__init__(self, 'throbber-drawn')

class ItemRenderer(widgetset.InfoListRenderer):
    # dimensions
    MIN_WIDTH = 600
    HEIGHT = 145
    RIGHT_WIDTH = 90
    RIGHT_WIDTH_DOWNLOAD_MODE = 115
    CORNER_RADIUS = 5
    EMBLEM_HEIGHT = 20
    EMBLEM_AREA_HEIGHT = 36 # contains the emblem + the button next to it
    PROGRESS_AREA_HEIGHT = 56

    # padding/spacing
    PADDING = (15, 15, 5, 5)
    PADDING_BACKGROUND = (4, 6, 4, 6)
    PADDING_INNER = (20, 15, 23, 15)
    PADDING_MIDDLE_RIGHT = 15
    TEXT_SPACING_Y = 3
    EMBLEM_PAD_TOP = 25
    EMBLEM_TEXT_PAD_START = 4
    EMBLEM_TEXT_PAD_END = 20
    EMBLEM_TEXT_PAD_END_SMALL = 6
    EMBLEM_MARGIN_RIGHT = 12
    DOWNLOAD_MODE_CONTEXT_MENU_PAD_RIGHT = 15

    # colors
    GRADIENT_TOP = css_to_color('#ffffff')
    GRADIENT_BOTTOM = css_to_color('#dfdfdf')
    SEPARATOR_COLOR = css_to_color('#cacaca')
    ITEM_TITLE_COLOR = (0.2, 0.2, 0.2)
    DOWNLOAD_INFO_COLOR = widgetutil.WHITE
    DOWNLOAD_INFO_COLOR_UNEM = (0.2, 0.2, 0.2)
    DOWNLOAD_INFO_SEPARATOR_COLOR = widgetutil.WHITE
    DOWNLOAD_INFO_SEPARATOR_ALPHA = 0.1
    TORRENT_INFO_LABEL_COLOR = (0.6, 0.6, 0.6)
    TORRENT_INFO_DATA_COLOR = widgetutil.WHITE
    ITEM_DESC_COLOR = (0.3, 0.3, 0.3)
    FEED_NAME_COLOR = (0.5, 0.5, 0.5)
    RESUME_TEXT_COLOR = css_to_color('#306219')
    RESUME_TEXT_SHADOW = css_to_color('#ecffe4')
    UNPLAYED_TEXT_COLOR = css_to_color('#d8ffc7')
    UNPLAYED_TEXT_SHADOW = css_to_color('#469226')
    EXPIRING_TEXT_COLOR = css_to_color('#6f6c28')
    EXPIRING_TEXT_SHADOW = css_to_color('#fffef6')
    NEWLY_AVAILABLE_TEXT_COLOR =  css_to_color('#e1efff')
    NEWLY_AVAILABLE_TEXT_SHADOW = css_to_color('#346ead')

    # font sizes
    EMBLEM_FONT_SIZE = 0.80
    TITLE_FONT_SIZE = 1.0
    ITEM_DESC_FONT_SIZE = 0.85
    DOWNLOAD_INFO_FONT_SIZE = 0.70
    DOWNLOAD_INFO_TORRENT_DETAILS_FONT_SIZE = 0.50

    # text assets
    REVEAL_IN_TEXT = (file_navigator_name and
            _("Reveal in %(progname)s", {"progname": file_navigator_name}) or _("Reveal File"))
    SHOW_CONTENTS_TEXT = _("display contents")
    WEB_PAGE_TEXT = _("Web Page")
    FILE_URL_TEXT = _("File URL")
    LICENSE_PAGE_TEXT = _("License Page")
    FILE_TYPE_TEXT = _("File Type")
    SEEDERS_TEXT = _("Seeders")
    LEECHERS_TEXT = _("Leechers")
    UPLOAD_RATE_TEXT = _("Upload Rate")
    UPLOAD_TOTAL_TEXT = _("Upload Total")
    DOWN_RATE_TEXT = _("Down Rate")
    DOWN_TOTAL_TEXT = _("Down Total")
    UP_DOWN_RATIO_TEXT = _("Up/Down Ratio")
    DOWNLOAD_TEXT = _("Download")
    DOWNLOAD_TORRENT_TEXT = _("Download Torrent")
    ERROR_TEXT = _("Error")
    CANCEL_TEXT = _("Cancel")
    QUEUED_TEXT = _("Queued for Auto-download")
    UNPLAYED_TEXT = _("Unplayed")
    CURRENTLY_PLAYING_TEXT = _("Currently Playing")
    NEWLY_AVAILABLE_TEXT = _("Newly Available")
    KEEP_TEXT = _("Keep")
    REMOVE_TEXT = _("Remove")
    STOP_SEEDING_TEXT = _("Stop seeding")
    PLAYLIST_REMOVE_TEXT = _('Remove from playlist')

    def __init__(self, display_channel=True):
        widgetset.InfoListRenderer.__init__(self)
        self.signals = ItemRendererSignals()
        self.display_channel = display_channel
        self.selected = False
        self.setup_images()
        self.emblem_drawer = _EmblemDrawer(self)
        self.setup_torrent_folder_description()

    def setup_torrent_folder_description(self):
        text = (u'<a href="#show-torrent-contents">%s</a>' %
                self.SHOW_CONTENTS_TEXT)
        self.torrent_folder_description = util.HTMLStripper().strip(text)

    def setup_images(self):
        all_images = [ 'background-left', 'background-middle',
                'background-right', 'dl-speed', 'dl-stats-left-cap',
                'dl-stats-middle', 'dl-stats-right-cap',
                'dl-stats-selected-left-cap', 'dl-stats-selected-middle',
                'dl-stats-selected-right-cap', 'download-pause',
                'download-pause-pressed', 'download-resume',
                'download-resume-pressed', 'download-stop',
                'download-stop-pressed', 'expiring-cap', 'expiring-middle',
                'keep', 'keep-pressed', 'menu', 'menu-pressed', 'pause',
                'pause-pressed', 'play', 'play-pressed', 'remove',
                'remove-playlist', 'remove-playlist-pressed',
                'remove-pressed', 'status-icon-alert', 'newly-cap',
                'newly-middle', 'progress-left-cap', 'progress-middle',
                'progress-right-cap', 'progress-throbber-left-1',
                'progress-throbber-left-2', 'progress-throbber-left-3',
                'progress-throbber-middle-1', 'progress-throbber-middle-2',
                'progress-throbber-middle-3', 'progress-throbber-right-1',
                'progress-throbber-right-2', 'progress-throbber-right-3',
                'progress-track', 'resume-cap',
                'resume-middle', 'selected-background-left',
                'selected-background-middle', 'selected-background-right',
                'time-left', 'ul-speed', 'unplayed-cap', 'unplayed-middle', ]
        self.images = {}
        for image_name in all_images:
            filename = 'item-renderer-%s.png' % image_name
            surface = imagepool.get_surface(resources.path(
                os.path.join('images', filename)))
            self.images[image_name] = surface
        # download-arrow is a shared icon.  It doesn't have the same prefix.
        self.images['download-arrow'] = imagepool.get_surface(
                resources.path('images/download-arrow.png'))
        # setup progress throbber stages
        self.progress_throbber_surfaces = []
        for i in xrange(3):
            left = self.images['progress-throbber-left-%d' % (i + 1)]
            middle = self.images['progress-throbber-middle-%d' % (i + 1)]
            right = self.images['progress-throbber-right-%d' % (i + 1)]
            surface = widgetutil.ThreeImageSurface()
            surface.set_images(left, middle, right)
            self.progress_throbber_surfaces.append(surface)

    def get_size(self, style, layout_manager):
        return self.MIN_WIDTH, self.HEIGHT

    def calc_download_mode(self):
        self.download_mode = (self.info.state in ('downloading', 'paused'))

    def hotspot_test(self, style, layout_manager, x, y, width, height):
        self.download_info = self.info.download_info
        self.calc_download_mode()
        self.hotspot = None
        self.selected = False
        # Assume the mouse is over the cell, since we got a mouse click
        self.hover = True
        layout = self.layout_all(layout_manager, width, height)
        hotspot_info = layout.find_hotspot(x, y)
        if hotspot_info is None:
            return None
        hotspot, x, y = hotspot_info
        if hotspot == 'description':
            textbox = self.make_description(layout_manager)
            textbox.set_width(self.description_width)
            index = textbox.char_at(x, y)
            if index is None:
                return None
            index -= self.description_text_start
            if index < 0:
                return None
            for (start, end, url) in self.description_links:
                if start <= index < end:
                    if url == '#show-torrent-contents':
                        # special link that we set up in
                        # setup_torrent_folder_description()
                        return 'show_contents'
                    else:
                        return 'description-link:%s' % url
            return None
        else:
            return hotspot

    def render(self, context, layout_manager, selected, hotspot, hover):
        self.download_info = self.info.download_info
        self.calc_download_mode()
        self.hotspot = hotspot
        self.selected = selected
        self.hover = hover
        layout = self.layout_all(layout_manager, context.width,
                context.height)
        layout.draw(context)

    def layout_all(self, layout_manager, width, height):
        layout = cellpack.Layout()

        # Calculate the area of the elements
        total_rect = cellpack.LayoutRect(0, 0, width, height)
        background_rect = total_rect.subsection(*self.PADDING)
        inner_rect = background_rect.subsection(*self.PADDING_BACKGROUND)
        image_width = inner_rect.height # make image square
        right_of_image_rect = inner_rect.subsection(image_width, 0, 0, 0)
        main_rect = right_of_image_rect.subsection(*self.PADDING_INNER)

        if self.download_mode:
            right_width = self.RIGHT_WIDTH_DOWNLOAD_MODE
        else:
            right_width = self.RIGHT_WIDTH
        middle_rect = main_rect.subsection(0, right_width +
                self.PADDING_MIDDLE_RIGHT, 0, 0)

        # layout background and borders
        layout.add_rect(background_rect, self.draw_background)
        # left side
        layout.add(inner_rect.x, inner_rect.y, image_width,
                inner_rect.height, self.draw_thumbnail)
        layout.add_rect(right_of_image_rect.left_side(1),
                self.draw_thumbnail_separator)
        # title/description/extra info
        self.layout_text(layout, layout_manager, middle_rect)
        # bottom and right side
        if self.download_mode:
            right_rect = background_rect.right_side(right_width)
            self.layout_download_bottom(layout, layout_manager, middle_rect)
            self.layout_download_right(layout, layout_manager, right_rect)
            # add the context menu just to the left of the download info
            menu_x = (right_rect.x - self.images['menu'].width -
                    self.DOWNLOAD_MODE_CONTEXT_MENU_PAD_RIGHT)
            self._add_image_button(layout, menu_x, middle_rect.y, 'menu',
                    '#show-context-menu')
        else:
            right_rect = main_rect.right_side(right_width)
            self.layout_main_bottom(layout, layout_manager, middle_rect)
            self.layout_right(layout, layout_manager, right_rect)
        return layout

    def layout_text(self, layout, layout_manager, rect):
        """layout the text for our cell

        rect should contain the area for the entire middle section.
        """
        title_y = rect.y
        layout_manager.set_font(self.TITLE_FONT_SIZE,
                family=widgetset.ITEM_TITLE_FONT, bold=True)
        layout_manager.set_text_color(self.ITEM_TITLE_COLOR)
        title = layout_manager.textbox(self.info.name)
        title.set_wrap_style('truncated-char')
        layout.add_text_line(title, rect.x, title_y, rect.width)

        extra_info_y = layout.last_rect.bottom + self.TEXT_SPACING_Y
        extra_info = self.make_extra_info(layout_manager)
        layout.add_text_line(extra_info, rect.x, extra_info_y, rect.width)

        description_y = layout.last_rect.bottom + self.TEXT_SPACING_Y
        description = self.make_description(layout_manager)
        layout.add_text_line(description, rect.x, description_y, rect.width,
                hotspot='description')
        self.description_width = rect.width

    def make_extra_info(self, layout_manager):
        layout_manager.set_font(self.DOWNLOAD_INFO_FONT_SIZE,
                family=widgetset.ITEM_DESC_FONT)
        layout_manager.set_text_color(self.ITEM_DESC_COLOR)
        parts = []
        for attr in (self.info.display_date, self.info.display_duration,
                self.info.display_size, self.info.file_format):
            if attr:
                parts.append(attr)
        return layout_manager.textbox(' | '.join(parts))

    def make_description(self, layout_manager):
        layout_manager.set_font(self.ITEM_DESC_FONT_SIZE,
                family=widgetset.ITEM_DESC_FONT)
        layout_manager.set_text_color(self.ITEM_DESC_COLOR)
        textbox = layout_manager.textbox("")
        if self.display_channel and self.info.feed_name:
            feed_text = "%s: " % self.info.feed_name
            textbox.append_text(feed_text, color=self.FEED_NAME_COLOR)
            self.description_text_start = len(feed_text)
        else:
            self.description_text_start = 0

        if (self.info.download_info and self.info.download_info.torrent and
                self.info.children):
            text, links = self.torrent_folder_description
        else:
            text, links = self.info.description_stripped

        pos = 0
        for start, end, url in links:
            textbox.append_text(text[pos:start])
            textbox.append_text(text[start:end], underline=True, color=self.ITEM_DESC_COLOR)
            pos = end
        if pos < len(text):
            textbox.append_text(text[pos:])
        self.description_links = links
        return textbox

    def layout_main_bottom(self, layout, layout_manager, rect):
        """Layout the bottom part of the main section.

        rect should contain the area for the entire middle section.  This
        method will add the progress bar, emblem and/or play button.
        """
        # allocate it enough size to fit the play button
        emblem_rect = rect.bottom_side(self.EMBLEM_AREA_HEIGHT)
        self.emblem_drawer.info = self.info
        self.emblem_drawer.hotspot = self.hotspot
        emblem_width = self.emblem_drawer.add_to_layout(layout,
                layout_manager, emblem_rect)


        extra_button_x = emblem_width + self.EMBLEM_MARGIN_RIGHT
        # add stop seeding button
        extra_button_rect = emblem_rect.subsection(extra_button_x, 0, 0, 0)
        self.add_extra_button(layout, layout_manager, extra_button_rect)

    def add_extra_button(self, layout, layout_manager, rect):
        if (self.info.download_info and
                self.info.download_info.state == 'uploading'):
            text = self.STOP_SEEDING_TEXT
            hotspot = 'stop_seeding'
        elif self.info.pending_auto_dl:
            text = self.CANCEL_TEXT
            hotspot = 'cancel_auto_download'
        else:
            return
        layout_manager.set_font(self.EMBLEM_FONT_SIZE)
        button = layout_manager.button(text, pressed=(self.hotspot==hotspot),
                    style='webby')
        button_rect = layout.add_image(button, rect.x, 0, hotspot)
        # middle-align the button
        button_rect.y = rect.y + ((rect.height - button_rect.height) // 2)

    def layout_right(self, layout, layout_manager, rect):
        # calculate positioning for the buttons.  There's a couple issues
        # here:
        # 1) the expiring emblem should line up with the resume emblem if both
        # are shown.
        # 2) The buttons should be equally spaced

        button_x = rect.right - self.images['keep'].width

        # assume all buttons have the same height
        button_height = self.images['keep'].height

        # top botton is easy
        menu_y = rect.y
        # pad the bottom button area so that it will be in the middle
        # of the emblem area.  This should also make the emblems match up.
        pad_bottom = int((self.EMBLEM_AREA_HEIGHT - button_height) // 2)
        expire_y = rect.bottom - button_height - pad_bottom
        # delete button goes in the middle
        delete_y = int((menu_y + expire_y) // 2)

        self._add_image_button(layout, button_x, menu_y, 'menu',
                '#show-context-menu')

        if ((self.info.is_external or self.info.downloaded) and 
            self.info.source_type != 'sharing'):
            self.add_remove_button(layout, button_x, delete_y)

        if self.info.expiration_date:
            expire_rect = cellpack.LayoutRect(button_x, expire_y, rect.width,
                    button_height)
            self.layout_expire(layout, layout_manager, expire_rect)

    def add_remove_button(self, layout, x, y):
        """Add the remove button to a layout.
        
        Subclasses can override this if they want different behavior/looks for
        the button.
        """
        self._add_image_button(layout, x, y, 'remove', 'delete')

    def layout_expire(self, layout, layout_manager, rect):
        # create a new Layout for the 2 elements
        expire_layout = cellpack.Layout()
        # add the background now so that it's underneath everything else.  We
        # don't know anything about the x dimensions yet, so just set them to
        # 0
        background_rect = expire_layout.add(0, 0, 0, self.EMBLEM_HEIGHT,
                self.draw_expire_background)
        # create text for the emblem
        layout_manager.set_font(self.EMBLEM_FONT_SIZE)
        layout_manager.set_text_color(self.EXPIRING_TEXT_COLOR)
        textbox = layout_manager.textbox(displaytext.expiration_date(
            self.info.expiration_date))
        # add text.  completely break the bounds of our layout rect and
        # position the text to the left of our rect
        text_width, text_height = textbox.get_size()
        text_x = rect.x - self.EMBLEM_TEXT_PAD_START - text_width
        expire_layout.add(text_x, 0, text_width, text_height, textbox.draw)
        # add button
        button_rect = self._add_image_button(expire_layout, rect.x, 0, 'keep',
                'keep')
        # now we can position the background, draw it to the middle of the
        # button.
        background_rect.x = text_x - self.EMBLEM_TEXT_PAD_END
        background_rect.width = (rect.x - background_rect.x +
                button_rect.width // 2)

        # middle align everything and add it to layout
        expire_layout.center_y(top=rect.y, bottom=rect.bottom)
        layout.merge(expire_layout)

    def layout_download_bottom(self, layout, layout_manager, rect):
        progress_bar_rect = rect.bottom_side(self.EMBLEM_AREA_HEIGHT)
        progress_text_rect = rect.subsection(0, 0,
                0,
                self.EMBLEM_AREA_HEIGHT)
        self.layout_progress_bar(layout, layout_manager, progress_bar_rect)

    def layout_progress_bar(self, layout, layout_manager, rect):
        end_button_width = 47
        progress_cap_width = 10
        bar_height = 20
        # figure out what button goes on the left
        if not self.download_info or self.download_info.state != 'paused':
            left_hotspot = 'pause'
            left_button_name = 'download-pause'
        else:
            left_hotspot = 'resume'
            left_button_name = 'download-resume'

        progress_bar_layout = cellpack.Layout()
        # add ends of the bar
        self._add_image_button(progress_bar_layout, rect.x, 0,
                left_button_name,
                left_hotspot)
        self._add_image_button(progress_bar_layout,
                rect.right-end_button_width, 0, 'download-stop', 'cancel')
        # add track in the middle
        track = self.images['progress-track']
        track_rect = cellpack.LayoutRect(rect.x + end_button_width, 0,
                rect.width - (end_button_width * 2), track.height)
        progress_bar_layout.add_rect(track_rect, track.draw)

        # add progress bar above the track
        progress_x = track_rect.x - progress_cap_width
        bar_width_total = track_rect.width + (progress_cap_width * 2)
        bar_rect = cellpack.LayoutRect(progress_x, 0,
                bar_width_total, bar_height)
        progress_bar_layout.add_rect(bar_rect, self.draw_progress_bar)

        # align progress bar in the middle of emblem area, this makes it line
        # up with where the emblem are
        progress_bar_layout.center_y(rect.bottom-self.EMBLEM_AREA_HEIGHT,
                rect.bottom)
        layout.merge(progress_bar_layout)

    def layout_download_right(self, layout, layout_manager, rect):
        dl_info = self.info.download_info
        # add some padding around the edges
        content_rect = rect.subsection(6, 12, 8, 8)

        # layout top
        layout_manager.set_font(self.DOWNLOAD_INFO_FONT_SIZE)
        line_height = layout_manager.current_font.line_height()
        ascent = layout_manager.current_font.ascent()
        # generic code to layout a line at the top
        def add_line(y, image_name, text, subtext=None):
            # position image so that it's bottom is the baseline for the text
            image = self.images[image_name]
            image_y = y + ascent - image.height + 2
            # add 2 px to account for the shadow at the bottom of the icons
            layout.add_image(image, content_rect.x, image_y)
            if text:
                layout_manager.set_text_color(self.DOWNLOAD_INFO_COLOR)
                textbox = layout_manager.textbox(text)
                textbox.set_alignment('right')
                layout.add_text_line(textbox, rect.x, y, content_rect.width)
            if subtext:
                layout_manager.set_text_color(self.DOWNLOAD_INFO_COLOR_UNEM)
                subtextbox = layout_manager.textbox(subtext)
                subtextbox.set_alignment('right')
                layout.add_text_line(subtextbox,
                        content_rect.x, y + line_height,
                        content_rect.width)
        if self.info.state == 'paused':
            eta = rate = 0
        else:
            eta = dl_info.eta
            rate = dl_info.rate

        # layout line 1
        current_y = content_rect.y
        add_line(current_y, 'time-left', displaytext.time_string_0_blank(eta))
        current_y += max(20, line_height)
        layout.add(content_rect.x, current_y-1, content_rect.width, 1,
                self.draw_download_info_separator)
        # layout line 2
        add_line(current_y, 'dl-speed',
                displaytext.download_rate(rate),
                displaytext.size_string(dl_info.downloaded_size))
        current_y += max(25, line_height * 2)
        layout.add(content_rect.x, current_y-1, content_rect.width, 1,
                self.draw_download_info_separator)
        # layout line 3
        if dl_info.torrent:
            add_line(current_y, 'ul-speed',
                    displaytext.download_rate(self.info.up_rate),
                    displaytext.size_string(self.info.up_total))
        current_y += max(25, line_height * 2)
        layout.add(content_rect.x, current_y-1, content_rect.width, 1,
                self.draw_download_info_separator)
        # layout torrent info
        if dl_info.torrent and dl_info.state != 'paused':
            torrent_info_height = content_rect.bottom - current_y
            self.layout_download_right_torrent(layout, layout_manager,
                    content_rect.bottom_side(torrent_info_height))

    def layout_download_right_torrent(self, layout, layout_manager, rect):
        if self.info.download_info.rate == 0:
            # not started yet, just display the startup activity
            layout_manager.set_text_color(self.TORRENT_INFO_DATA_COLOR)
            textbox = layout_manager.textbox(
                    self.info.download_info.startup_activity)
            height = textbox.get_size()[1]
            y = rect.bottom - height # bottom-align the textbox.
            layout.add(rect.x, y, rect.width, height,
                    textbox.draw)
            return

        layout_manager.set_font(self.DOWNLOAD_INFO_TORRENT_DETAILS_FONT_SIZE,
                family=widgetset.ITEM_DESC_FONT)
        lines = (
                (_('PEERS'), str(self.info.connections)),
                (_('SEEDS'), str(self.info.seeders)),
                (_('LEECH'), str(self.info.leechers)),
                (_('SHARE'), "%.2f" % self.info.up_down_ratio),
        )
        line_height = layout_manager.current_font.line_height()
        # check that we're not drawing more lines that we have space for.  If
        # there are extras, cut them off from the bottom
        potential_lines = int(rect.height // line_height)
        lines = lines[:potential_lines]
        total_height = line_height * len(lines)
        y = rect.bottom - total_height

        for label, value in lines:
            layout_manager.set_text_color(self.TORRENT_INFO_LABEL_COLOR)
            labelbox = layout_manager.textbox(label)
            layout_manager.set_text_color(self.TORRENT_INFO_DATA_COLOR)
            databox = layout_manager.textbox(value)
            databox.set_alignment('right')
            layout.add_text_line(labelbox, rect.x, y, rect.width)
            layout.add_text_line(databox, rect.x, y, rect.width)
            y += line_height

    def _add_image_button(self, layout, x, y, image_name, hotspot_name):
        if self.hotspot != hotspot_name:
            image = self.images[image_name]
        else:
            image = self.images[image_name + '-pressed']
        return layout.add_image(image, x, y, hotspot=hotspot_name)

    def draw_background(self, context, x, y, width, height):
        if self.selected:
            left = self.images['selected-background-left']
            middle = self.images['selected-background-middle']
            right = self.images['selected-background-right']
        else:
            left = self.images['background-left']
            middle = self.images['background-middle']
            right = self.images['background-right']

        # draw left
        left.draw(context, x, y, left.width, height)
        # draw right
        if self.download_mode:
            right_width = self.RIGHT_WIDTH_DOWNLOAD_MODE
            download_info_x = x + width - right_width
            self.draw_download_info_background(context, download_info_x, y,
                    right_width)
        else:
            right_width = right.width
            right.draw(context, x + width - right_width, y, right_width,
                    height)
        # draw middle
        middle_width = width - right_width - left.width
        middle.draw(context, x + left.width, y, middle_width, height)


    def draw_download_info_background(self, context, x, y, width):
        if self.selected:
            left = self.images['dl-stats-selected-left-cap']
            middle = self.images['dl-stats-selected-middle']
            right = self.images['dl-stats-selected-right-cap']
        else:
            left = self.images['dl-stats-left-cap']
            middle = self.images['dl-stats-middle']
            right = self.images['dl-stats-right-cap']
        background = widgetutil.ThreeImageSurface()
        background.set_images(left, middle, right)
        background.draw(context, x, y, width)

    def draw_download_info_separator(self, context, x, y, width, height):
        context.set_color(self.DOWNLOAD_INFO_SEPARATOR_COLOR,
                self.DOWNLOAD_INFO_SEPARATOR_ALPHA)
        context.rectangle(x, y, width, height)
        context.fill()

    def draw_thumbnail(self, context, x, y, width, height):
        # save context since we are setting a clip path
        context.save()
        # make a path with rounded edges on the left side and clip to it
        radius = self.CORNER_RADIUS
        context.move_to(x + radius, y)
        context.line_to(x + width, y)
        context.line_to(x + width, y + height)
        context.line_to(x + radius, y + height)
        context.arc(x + radius, y + height - radius, radius, PI/2, PI)
        context.line_to(x, y + radius)
        context.arc(x + radius, y + radius, radius, PI, PI*3/2)
        context.clip()
        # draw the thumbnail
        icon = imagepool.get_surface(self.info.thumbnail, (width, height))
        widgetutil.draw_icon_in_rect(context, icon, x, y, width, height)
        # undo the clip path
        context.restore()

    def draw_thumbnail_separator(self, context, x, y, width, height):
        """Draw the separator just to the right of the thumbnail."""
        # width should be 1px, just fill in our entire space with our color
        context.rectangle(x, y, width, height)
        context.set_color(self.SEPARATOR_COLOR)
        context.fill()

    def draw_expire_background(self, context, x, y, width, height):
        middle_image = self.images['expiring-middle']
        cap_image = self.images['expiring-cap']
        # draw the cap at the left
        cap_image.draw(context, x, y, cap_image.width, cap_image.height)
        # repeat the middle to be as long as we need.
        middle_image.draw(context, x + cap_image.width, y,
                width - cap_image.width, middle_image.height)

    def draw_progress_bar(self, context, x, y, width, height):
        if (self.info.download_info.downloaded_size > 0 and
                self.info.download_info.total_size < 0):
            # The download has started and we don't know the total size.  Draw
            # a progress throbber.
            self.draw_progress_throbber(context, x, y, width, height)
            return
        if self.info.size == 0:
            # We don't know the size yet, but we aren't sure that we won't in
            # a bit.  Probably we are starting up a download and haven't
            # gotten anything back from the server.  Don't draw the progress
            # bar or the throbber, just leave eerything blank.
            return
        progress_ratio = (float(self.info.download_info.downloaded_size) /
                self.info.size)
        progress_width = int(width * progress_ratio)
        left = self.images['progress-left-cap']
        middle = self.images['progress-middle']
        right = self.images['progress-right-cap']

        left_width = min(left.width, progress_width)
        right_width = max(0, progress_width - (width - right.width))
        middle_width = max(0, progress_width - left_width - right_width)

        left.draw(context, x, y, left_width, height)
        middle.draw(context, x + left.width, y, middle_width, height)
        right.draw(context, x + width - right.width, y, right_width, height)

    def draw_progress_throbber(self, context, x, y, width, height):
        throbber_count = self.attrs.get('throbber-value', 0)
        index = throbber_count % len(self.progress_throbber_surfaces)
        surface = self.progress_throbber_surfaces[index]
        surface.draw(context, x, y, width)
        self.signals.emit('throbber-drawn', self.info.id)

class _EmblemDrawer(object):
    """Layout and draw emblems

    This is actually a fairly complex task, so the code is split out of
    ItemRenderer to make things more managable
    """

    def __init__(self, renderer):
        self.images = renderer.images
        self.info = None
        self.hotspot = None
        # HACK: take all the style info from the renderer
        for name in dir(renderer):
            if name.isupper():
                setattr(self, name, getattr(renderer, name))

    def add_to_layout(self, layout, layout_manager, rect):
        """Add emblem elements to a Layout()

        :param layout: Layout to add to
        :param layout_manager: LayoutManager to use
        :param rect: rect sized to the area to add the emblem to
        """

        # make the button that appears to the left of the emblem
        button, button_hotspot = self.make_emblem_button(layout_manager)
        button_width, button_height = button.get_size()

        # figure out the text and/or image inside the emblem
        self._calc_emblem_parts()
        # check if we don't have anything to put inside our emblem.  Just draw
        # the button if so
        if self.image is None and self.text is None:
            button_y = rect.y + int((rect.height - button.get_size()[1]) // 2)
            layout.add_image(button, rect.x, button_y, button_hotspot)
            return layout.last_rect.width
        # make a new Layout to put the emblem contents in.  This makes
        # middle-aligning things easier
        emblem_layout = cellpack.Layout()
        # add emblem background first, since we want it drawn on the bottom.
        # Position it in the middle of the button, since we don't want it to
        # spill over on the left side.
        # We won't know the width until we lay out the text/images, so
        # set it to 0
        emblem_rect = emblem_layout.add(rect.x + button_width // 2, 0, 0,
                self.EMBLEM_HEIGHT, self.draw_emblem_background)
        # add button
        emblem_layout.add_image(button, rect.x, 0, button_hotspot)
        content_x = emblem_layout.last_rect.right + self.EMBLEM_TEXT_PAD_START
        content_width = self._add_content(emblem_layout, layout_manager,
                content_x)
        # can set emblem width now
        emblem_rect.width = (button_width + self.EMBLEM_TEXT_PAD_START +
                content_width + self.margin_right)
        # all y coordinates are set to 0.  Center them in the middle of our
        # rect.
        emblem_layout.center_y(top=rect.y, bottom=rect.bottom)
        layout.merge(emblem_layout)
        return emblem_rect.right - rect.x

    def make_emblem_button(self, layout_manager):
        """Make the button that will go on the left of the emblem.

        :returns: a tuple contaning (button, hotspot_name)
        """
        layout = cellpack.Layout()

        layout_manager.set_font(0.85)
        if self.info.downloaded:
            if self.info.is_playable:
                playing_item = app.playback_manager.get_playing_item()
                if (playing_item and playing_item.id == self.info.id):
                    hotspot = 'play_pause'
                    if app.playback_manager.is_paused:
                        button_name = 'play'
                    else:
                        button_name = 'pause'
                else:
                    button_name = 'play'
                    hotspot = 'play'
                if self.hotspot == hotspot:
                    button_name += '-pressed'
                button = self.images[button_name]
            else:
                button = layout_manager.button(self.REVEAL_IN_TEXT,
                        pressed=(self.hotspot=='show_local_file'),
                        style='webby')
                hotspot = 'show_local_file'
        else:
            if self.info.mime_type == 'application/x-bittorrent':
                text = self.DOWNLOAD_TORRENT_TEXT
            else:
                text = self.DOWNLOAD_TEXT
            button = layout_manager.button(text,
                    pressed=(self.hotspot=='download'),
                    style='webby')
            button.set_icon(self.images['download-arrow'])
            hotspot = 'download'
        return button, hotspot

    def _calc_emblem_parts(self):
        """Calculate UI details for layout_emblem().

        This will set the following attributes, which we can then use to
        render stuff:
            text -- text inside the emblem
            text_bold -- should the text be bold?
            text_color -- color of text
            image -- image inside the emblem
            margin-right -- padding to add to the right of the text/image
            emblem -- name of the image to use to draw the backgound

        """

        self.text = self.image = None
        self.margin_right = self.EMBLEM_TEXT_PAD_END
        self.text_bold = False
        self.text_color = self.ITEM_DESC_COLOR

        if self.info.has_drm:
            self.text_bold = True
            self.text = _('DRM locked')
            self.text_color = self.UNPLAYED_TEXT_COLOR
            self.emblem = 'unplayed' # FIXME need a new emblem for this
        elif (self.info.download_info
                and self.info.download_info.state == 'failed'):
            self.text_color = self.UNPLAYED_TEXT_COLOR
            self.text_bold = True
            self.image = self.images['status-icon-alert']
            self.text = u"%s-%s" % (self.ERROR_TEXT,
                    self.info.download_info.short_reason_failed)
            self.emblem = 'unplayed' # FIXME need a new emblem for this
        elif self.info.pending_auto_dl:
            self.text_color = self.UNPLAYED_TEXT_COLOR
            self.text = self.QUEUED_TEXT
            self.emblem = 'unplayed' # FIXME need a new emblem for this
        elif (self.info.downloaded
                and app.playback_manager.is_playing_id(self.info.id)):
            self.text = self.CURRENTLY_PLAYING_TEXT
            # copy the unplayed-style
            self.text_color = self.UNPLAYED_TEXT_COLOR
            self.emblem = 'unplayed'
        elif self.info.downloaded and not self.info.video_watched:
            self.text_color = self.UNPLAYED_TEXT_COLOR
            self.text_bold = True
            self.text = self.UNPLAYED_TEXT
            self.emblem = 'unplayed'
        elif (self.info.is_playable
              and self.info.item_viewed
              and self.info.resume_time > 0
              and app.config.get(prefs.RESUME_VIDEOS_MODE)):
            self.text_bold = True
            self.text_color = self.RESUME_TEXT_COLOR
            self.text = _("Resume at %(resumetime)s",
                     {"resumetime": displaytext.short_time_string(self.info.resume_time)})
            self.margin_right = self.EMBLEM_TEXT_PAD_END_SMALL
            self.emblem = 'resume'
        elif not self.info.item_viewed and self.info.state == "new":
            self.text_bold = True
            self.text_color = self.NEWLY_AVAILABLE_TEXT_COLOR
            self.text = self.NEWLY_AVAILABLE_TEXT
            self.margin_right = self.EMBLEM_TEXT_PAD_END_SMALL
            self.emblem = 'newly'

    def _add_content(self, emblem_layout, layout_manager, left_x):
        """Add the emblem text and/or image

        :returns: the width used
        """
        x = left_x

        if self.image:
            emblem_layout.add_image(self.image, x, 0)
            x += self.image.width
        if self.text:
            layout_manager.set_font(self.EMBLEM_FONT_SIZE,
                    bold=self.text_bold)
            layout_manager.set_text_color(self.text_color)
            textbox = layout_manager.textbox(self.text)
            text_width, text_height = textbox.get_size()
            emblem_layout.add(x, 0, text_width, text_height, textbox.draw)
            x += text_width
        return x - left_x

    def draw_emblem_background(self, context, x, y, width, height):
        middle_image = self.images[self.emblem + '-middle']
        cap_image = self.images[self.emblem + '-cap']
        # repeat the middle to be as long as we need.
        middle_image.draw(context, x, y, width - cap_image.width,
                middle_image.height)
        # draw the cap at the end
        cap_image.draw(context, x + width-cap_image.width, y, cap_image.width,
                cap_image.height)

class PlaylistItemRenderer(ItemRenderer):
    def add_remove_button(self, layout, x, y):
        self._add_image_button(layout, x, y, 'remove-playlist', 'remove')

# Renderers for the list view
class ListViewRendererText(widgetset.InfoListRendererText):
    """Renderer for list view columns that are just plain text"""

    bold = False
    color = (0.17, 0.17, 0.17)
    font_size = 0.82
    min_width = 50
    right_aligned = False

    def __init__(self):
        widgetset.InfoListRendererText.__init__(self, self.attr_name)
        self.set_bold(self.bold)
        self.set_color(self.color)
        self.set_font_scale(self.font_size)
        if self.right_aligned:
            self.set_align('right')

class DescriptionRenderer(ListViewRendererText):
    color = (0.6, 0.6, 0.6)
    attr_name = 'description_oneline'

class FeedNameRenderer(ListViewRendererText):
    attr_name = 'feed_name'

class DateRenderer(ListViewRendererText):
    attr_name = 'display_date'

class LengthRenderer(ListViewRendererText):
    attr_name = 'display_duration'

class ETARenderer(ListViewRendererText):
    right_aligned = True
    attr_name = 'display_eta'

class TorrentDetailsRenderer(ListViewRendererText):
    attr_name = 'display_torrent_details'

class DownloadRateRenderer(ListViewRendererText):
    right_aligned = True
    attr_name = 'display_rate'

class SizeRenderer(ListViewRendererText):
    right_aligned = True
    attr_name = 'display_size'

class ArtistRenderer(ListViewRendererText):
    attr_name = 'artist'

class AlbumRenderer(ListViewRendererText):
    attr_name = 'album'

class TrackRenderer(ListViewRendererText):
    attr_name = 'display_track'

class YearRenderer(ListViewRendererText):
    attr_name = 'display_year'

class GenreRenderer(ListViewRendererText):
    attr_name = 'genre'

class DateAddedRenderer(ListViewRendererText):
    attr_name = 'display_date_added'

class LastPlayedRenderer(ListViewRendererText):
    attr_name = 'display_last_played'

class DRMRenderer(ListViewRendererText):
    attr_name = 'display_drm'

class FileTypeRenderer(ListViewRendererText):
    attr_name = 'file_format'

class ShowRenderer(ListViewRendererText):
    attr_name = 'show'

class ListViewRenderer(widgetset.InfoListRenderer):
    """Renderer for more complex list view columns.

    This class is useful for renderers that use the cellpack.Layout class.
    """
    font_size = 0.82
    default_text_color = (0.17, 0.17, 0.17)
    min_width = 5
    min_height = 0

    def hotspot_test(self, style, layout_manager, x, y, width, height):
        layout = self.layout_all(layout_manager, width, height)
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
        layout = self.layout_all(layout_manager, context.width, context.height)
        layout.draw(context)

    def layout_all(self, layout_manager, width, height):
        """Layout the contents of this cell

        Subclasses must implement this method

        :param layout_manager: LayoutManager object
        :param width: width of the area to lay the cell out in
        :param height: height of the area to lay the cell out in
        :returns: cellpack.Layout object
        """
        raise NotImplementedError()


class NameRenderer(ListViewRenderer):
    min_width = 100
    button_font_size = 0.77

    def __init__(self):
        widgetset.InfoListRenderer.__init__(self)
        path = resources.path('images/download-arrow.png')
        self.download_icon = imagepool.get_surface(path)

    def layout_all(self, layout_manager, width, height):
        # make a Layout Object
        layout = cellpack.Layout()
        # add the button, if needed
        if self.should_show_download_button():
            button = self.make_button(layout_manager)
            button_x = width - button.get_size()[0]
            layout.add_image(button, button_x, 0, hotspot='download')
            # text should end at the start of the button
            text_width = button_x
        else:
            # text can take up the whole space
            text_width = width
        # add the text
        layout_manager.set_font(self.font_size)
        layout_manager.set_text_color(self.default_text_color)
        textbox = layout_manager.textbox(self.info.name)
        textbox.set_wrap_style('truncated-char')
        layout.add_text_line(textbox, 0, 0, text_width)
        # middle-align everything
        layout.center_y(top=0, bottom=height)
        return layout

    def make_button(self, layout_manager):
        layout_manager.set_font(self.button_font_size)
        button = layout_manager.button(_("Download"))
        button.set_icon(self.download_icon)
        return button

    def should_show_download_button(self):
        return (not self.info.downloaded and
                self.info.state not in ('downloading', 'paused'))

class StatusRenderer(ListViewRenderer):
    BUTTONS = ('pause', 'resume', 'cancel', 'keep')
    min_width = 40
    min_height = 20

    def __init__(self):
        ListViewRenderer.__init__(self)
        self.button = {}
        for button in self.BUTTONS:
            path = resources.path('images/%s-button.png' % button)
            self.button[button] = imagepool.get_surface(path)

    def layout_all(self, layout_manager, width, height):
        if (self.info.state in ('downloading', 'paused') and
            self.info.download_info.state != 'pending'):
            return self.layout_progress(layout_manager, width, height)
        else:
            return self.layout_text(layout_manager, width, height)

    def layout_progress(self, layout_manager, width, height):
        """Handle layout when we should display a progress bar """

        layout = cellpack.Layout()
        # add left button
        if self.info.state == 'downloading':
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
        elif (self.info.download_info and
                self.info.download_info.rate == 0):
            if self.info.download_info.state == 'paused':
                return (_('paused'), DOWNLOADING_COLOR)
            elif self.info.download_info.state == 'pending':
                return (_('queued'), DOWNLOADING_COLOR)
            elif self.info.download_info.state == 'failed':
                return (self.info.download_info.short_reason_failed,
                        DOWNLOADING_COLOR)
            else:
                return (self.info.download_info.startup_activity,
                        DOWNLOADING_COLOR)
        elif not self.info.item_viewed:
            return (_('Newly Available'), AVAILABLE_COLOR)
        return ('', self.default_text_color)

    def add_extra_button(self, layout, width):
        """Add a button to the right of the text, if needed"""

        if self.info.expiration_date:
            button_name = 'keep'
        elif (self.info.state == 'downloading' and
              self.info.download_info.state == 'pending'):
            button_name = 'cancel'
        else:
            return
        button = self.button[button_name]
        button_x = width - button.width # right-align
        layout.add_image(button, button_x, 0, hotspot=button_name)

class RatingRenderer(widgetset.InfoListRenderer):
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
        widgetset.InfoListRenderer.__init__(self)
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
        self.min_width = self.width = int(self.icon_width * self.ICON_COUNT)
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
        # yes/no for explicit ratings; maybe/no for hover ratings;
        # probably/no for auto ratings; unset when no explicit, auto, or hover rating
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

class StateCircleRenderer(widgetset.InfoListRenderer):
    """Renderer for the state circle column."""

    # NOTE: we don't inherit from ListViewRenderer because we handle
    # everything ourselves, without using the Layout class

    ICON_STATES = ('normal', 'unplayed', 'new', 'playing', 'downloading')
    ICON_PROPORTIONS = 7.0 / 9.0 # width / height
    min_width = 7
    min_height = 9

    def __init__(self):
        widgetset.InfoListRenderer.__init__(self)
        self.icon = {}
        self.setup_size = (-1, -1)

    def setup_icons(self, width, height):
        """Create icons that will fill our allocated area correctly. """
        if (width, height) == self.setup_size:
            return

        print "SETUP: ", width, height

        icon_width = int(height / 2.0)
        icon_height = int((icon_width / self.ICON_PROPORTIONS) + 0.5)
        # FIXME: by the time min_width is set below, it doesn't matter --Kaz
        self.width = self.min_width = icon_width
        self.height = icon_height
        icon_dimensions = (icon_width, icon_height)
        for state in StateCircleRenderer.ICON_STATES:
            path = resources.path('images/status-icon-%s.png' % state)
            self.icon[state] = imagepool.get_surface(path, icon_dimensions)
        self.setup_size = (width, height)

    def get_size(self, style, layout_manager):
        return self.min_width, self.min_height

    def hotspot_test(self, style, layout_manager, x, y, width, height):
        return None

    def render(self, context, layout_manager, selected, hotspot, hover):
        self.setup_icons(context.width, context.height)
        icon = self.calc_icon()
        # center icon vertically and horizontally
        x = int((context.width - self.width) / 2)
        y = int((context.height - self.height) / 2)
        icon.draw(context, x, y, icon.width, icon.height)

    def calc_icon(self):
        """Get the icon we should show.

        :returns: ImageSurface to display
        """
        if self.info.state == 'downloading':
            return self.icon['downloading']
        elif self.info.is_playing:
            return self.icon['playing']
        elif self.info.state == 'newly-downloaded':
            return self.icon['unplayed']
        elif self.info.downloaded and self.info.is_playable and not self.info.video_watched:
            return self.icon['new']
        elif (not self.info.item_viewed and not self.info.expiration_date and
                not self.info.is_external and not self.info.downloaded):
            return self.icon['new']
        else:
            return self.icon['normal']

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

    def __init__(self, progress_ratio, color_set):
        self.progress_ratio = progress_ratio
        self.color_set = color_set

    def _layout(self, context, x, y, width, height):
        self.x, self.y, self.width, self.height = x, y, width, height
        context.set_line_width(1)
        self.progress_width = int(width * self.progress_ratio)
        self.half_height = height / 2
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
                                      self.x + self.progress_width, self.y + self.height)
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
