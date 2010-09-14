# Miro - an RSS based video player application
# Copyright (C) 2005-2010 Participatory Culture Foundation
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
import os
import logging

from miro import app
from miro import util
from miro import displaytext
from miro import config
from miro import prefs
from miro.gtcache import gettext as _
from miro.frontends.widgets import cellpack
from miro.frontends.widgets import imagepool
from miro.frontends.widgets import widgetutil
from miro.plat import utils
from miro.plat import resources
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
TAB_LIST_HEADER_COLOR = (100/255.0, 109/255.0, 125/255.0)
TAB_LIST_SEPARATOR_COLOR = (209/255.0, 216/255.0, 220/255.0)

ERROR_COLOR = (0.90, 0.0, 0.0)
BLINK_COLOR = css_to_color('#fffb83')

class LowerBox(widgetset.Background):

    def __init__(self):
        widgetset.Background.__init__(self)

        self.image = widgetutil.make_surface('wtexture')
        self.separator_color = (64.0/255.0, 64.0/255.0, 64.0/255.0)
        self.highlight_color = (218.0/255.0, 218.0/255.0, 218.0/255.0)

        self.image_inactive = widgetutil.make_surface('wtexture_inactive')
        self.separator_color_inactive = (135.0/255.0, 135.0/255.0, 135.0/255.0)
        self.highlight_color_inactive = (239.0/255.0, 239.0/255.0, 239.0/255.0)

    def size_request(self, layout):
        return (0, 63)

    def draw(self, context, layout):
        if self.get_window().is_active():
            image = self.image
            highlight_color = self.highlight_color
            separator_color = self.separator_color
        else:
            image = self.image_inactive
            highlight_color = self.highlight_color_inactive
            separator_color = self.separator_color_inactive
        image.draw(context, 0, 0, context.width, context.height)

        context.set_line_width(1)
        context.move_to(0, 0.5)
        context.line_to(context.width, 0.5)
        context.set_color(separator_color)
        context.stroke()

        context.move_to(0, 1.5)
        context.line_to(context.width, 1.5)
        context.set_color(highlight_color)
        context.stroke()

    def is_opaque(self):
        return True


class TabRenderer(widgetset.CustomCellRenderer):
    MIN_WIDTH = 25
    MIN_HEIGHT = 24
    MIN_HEIGHT_TALL = 28
    TITLE_FONT_SIZE = 0.82
    BOLD_TITLE = False

    def get_size(self, style, layout):
        if hasattr(self.data, 'tall') and self.data.tall:
            min_height = self.MIN_HEIGHT_TALL
        else:
            min_height = self.MIN_HEIGHT
        return (self.MIN_WIDTH, max(min_height,
            layout.font(self.TITLE_FONT_SIZE).line_height()))

        return (self.MIN_WIDTH, max(self.MIN_HEIGHT,
            layout.font(self.TITLE_FONT_SIZE).line_height()))

    def render(self, context, layout, selected, hotspot, hover):
        layout.set_text_color(context.style.text_color)
        bold = False
        if selected:
            bold = True
        elif not hasattr(self.data, "bolded") or self.data.bolded:
            bold = self.BOLD_TITLE
        layout.set_font(self.TITLE_FONT_SIZE, bold=bold)
        titlebox = layout.textbox(self.data.name)

        hbox = cellpack.HBox(spacing=4)
        if hasattr(self.data, "id") and (self.data.id == 'guide' or self.data.id == 'search'):
            hbox.pack_space(6)
        else:
            hbox.pack_space(2)
        alignment = cellpack.Alignment(self.data.icon, yalign=0.5, yscale=0.0,
                xalign=0.5, xscale=0.0, min_width=16)
        hbox.pack(alignment)
        hbox.pack(cellpack.align_middle(cellpack.TruncatedTextLine(titlebox)), expand=True)
        layout.set_font(0.77)
        layout.set_text_color(widgetutil.WHITE)
        self.pack_bubbles(hbox, layout)
        hbox.pack_space(2)
        alignment = cellpack.Alignment(hbox, yscale=0.0, yalign=0.5)
        if self.blink:
            renderer = cellpack.Background(alignment)
            renderer.set_callback(self.draw_blink_background)
        else:
            renderer = alignment
        renderer.render_layout(context)

    def pack_bubbles(self, hbox, layout):
        if self.updating_frame > -1:
            image_name = 'icon-updating-%s' % self.updating_frame
            updating_image = widgetutil.make_surface(image_name)
            alignment = cellpack.Alignment(updating_image, yalign=0.5, yscale=0.0,
                    xalign=0.0, xscale=0.0, min_width=20)
            hbox.pack(alignment)
        else:
            if self.data.unwatched > 0:
                self.pack_bubble(hbox, layout, self.data.unwatched,
                        UNPLAYED_COLOR)
            if self.data.available > 0:
                self.pack_bubble(hbox, layout, self.data.available,
                        AVAILABLE_COLOR)

    def pack_bubble(self, hbox, layout, count, color):
        radius = (layout.current_font.line_height() + 2) / 2.0
        background = cellpack.Background(layout.textbox(str(count)),
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
    BOLD_TITLE = True

    def pack_bubbles(self, hbox, layout):
        if self.data.unwatched > 0:
            self.pack_bubble(hbox, layout, self.data.unwatched,
                    UNPLAYED_COLOR)
        if self.data.downloading > 0:
            self.pack_bubble(hbox, layout, self.data.downloading,
                    DOWNLOADING_COLOR)

class FakeDownloadInfo(object):
    # Fake download info object used to size items
    def __init__(self):
        self.state = 'paused'
        self.rate = 0
        self.downloaded_size = 0

class ItemRenderer(widgetset.CustomCellRenderer):
    MIN_WIDTH = 600
    BORDER_COLOR_TOP = css_to_color('#d0d0d0')
    BORDER_COLOR_BOTTOM = css_to_color('#9c9c9c')
    SELECTED_BORDER_COLOR_TOP = css_to_color('#c0ddfd')
    SELECTED_BORDER_COLOR_BOTTOM = css_to_color('#82b9f4')
    SELECTED_BACKGROUND_FLAP_COLOR = css_to_color('#82b9f4')
    SELECTED_BACKGROUND_COLOR = (0.94, 0.97, 0.99)
    SELECTED_BACKGROUND_COLOR_BOTTOM = css_to_color('#cae3fe')
    ITEM_TITLE_COLOR = (0.2, 0.2, 0.2)
    ITEM_DESC_COLOR = (0.4, 0.4, 0.4)
    EMBLEM_FONT_SIZE = 0.77
    GRADIENT_HEIGHT = 25
    FLAP_BACKGROUND_COLOR = (225.0 / 255.0, 225.0 / 255.0, 225.0 / 255.0)
    FLAP_HIGHLIGHT_COLOR = (237.0 / 255.0, 237.0 / 255.0, 237.0 / 255.0)

    FROM_TEXT = _("From")
    FILE_NAME_TEXT = _("File name:")
    SHOW_MORE_TEXT = _("Show More")
    SHOW_LESS_TEXT = _("Show Less")
    COMMENTS_TEXT = _("Comments")
    REVEAL_IN_TEXT = (file_navigator_name and
            _("Reveal in %(progname)s", {"progname": file_navigator_name}) or _("Reveal File"))
    SHOW_CONTENTS_TEXT = _("Display Contents")
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
    QUEUED_TEXT = _("Queued for Autodownload")
    UNPLAYED_TEXT = _("Unplayed")
    CURRENTLY_PLAYING_TEXT = _("Currently Playing")
    NEWLY_AVAILABLE_TEXT = _("Newly Available")
    KEEP_TEXT = _("Keep")
    REMOVE_TEXT = _("Remove")
    STOP_SEEDING_TEXT = _("Stop seeding")

    def __init__(self, display_channel=True):
        widgetset.CustomCellRenderer.__init__(self)
        self.separator = imagepool.get_surface(resources.path(
            'images/separator.png'))
        self.cancel_button = imagepool.get_surface(resources.path(
            'images/video-download-cancel.png'))
        self.pause_button = imagepool.get_surface(resources.path(
            'images/video-download-pause.png'))
        self.resume_button = imagepool.get_surface(resources.path(
            'images/video-download-resume.png'))
        self.play_button = imagepool.get_surface(resources.path(
            'images/play-button.png'))
        self.pause_playback_button = imagepool.get_surface(resources.path(
            'images/pause-item-button.png'))
        self.thumb_overlay = imagepool.get_surface(resources.path(
            'images/thumb-overlay.png'))
        self.alert_image = imagepool.get_surface(resources.path(
            'images/status-icon-alert.png'))
        self.channel_title_icon = imagepool.get_surface(resources.path(
            'images/icon-channel-title.png'))
        self.download_arrow = imagepool.get_surface(resources.path(
            'images/download-arrow.png'))
        # We cache the size of our rows to save us from re-calculating all the
        # time.  cached_size_parameters stores things like the base font size
        # that the cached value depends on.
        self.cached_size = None
        self.cached_size_parameters = None
        self.display_channel = display_channel
        self.show_details = False
        self.selected = False

    def get_size(self, style, layout):
        if self.show_details:
            return self._calculate_size(style, layout)
        cached_size_parameters = (style.use_custom_style, layout.font)
        if cached_size_parameters != self.cached_size_parameters:
            # Reset the cache values
            self.cached_size = None
            self.cached_size_parameters = cached_size_parameters
        if self.cached_size is None:
            self.cached_size = self._calculate_size(style, layout)
        return self.cached_size

    def _calculate_size(self, style, layout):
        self.download_info = FakeDownloadInfo()
        self.show_progress_bar = True
        self.setup_style(style)
        self.hotspot = None
        self.selected = False
        self.hover = False
        if self.show_details:
            left_size = self.pack_left(layout).get_size()[1]
            right_side = self.pack_right(layout)
            self.right_side_width = right_side.get_size()[0]
            main_size = self.pack_main(layout).get_size()[1]
            info_bar_size = 48
            total_size = max(left_size, main_size + info_bar_size)
            total_size += self.add_background(self.pack_flap(layout)).get_size()[1]
        else:
            sizer = self.add_background(self.pack_left(layout))
            total_size = sizer.get_size()[1]
        return self.MIN_WIDTH, max(137, total_size)

    def calc_show_progress_bar(self):
        self.show_progress_bar = (self.data.state in ('downloading', 'paused'))

    def hotspot_test(self, style, layout, x, y, width, height):
        self.download_info = self.data.download_info
        self.calc_show_progress_bar()
        self.setup_style(style)
        self.hotspot = None
        self.selected = False
        # Assume the mouse is over the cell, since we got a mouse click
        self.hover = True
        packing = self.pack_all(layout)
        hotspot_info = packing.find_hotspot(x, y, width, height)
        if hotspot_info is None:
            return None
        hotspot, x, y, width, height = hotspot_info
        if hotspot == 'description':
            textbox = self.make_description(layout)
            textbox.set_width(width)
            index = textbox.char_at(x, y)
            if index is None:
                return None
            for (start, end, url) in self.description_links:
                if start <= index < end:
                    return 'description-link:%s' % url
            return None
        else:
            return hotspot

    def add_background(self, content):
        if self.show_details:
            background_drawer = self.draw_background_details
            bottom_pad = 0 # pack_flap handles this for us
        else:
            background_drawer = self.draw_background
            bottom_pad = 12
        inner = cellpack.Background(content, margin=(11, bottom_pad, 0, 13))
        if self.use_custom_style:
            inner.set_callback(background_drawer)
        return cellpack.Background(inner, margin=(5, 20, 5, 20))

    def make_description(self, layout):
        layout.set_font(0.85, family=widgetset.ITEM_DESC_FONT)
        layout.set_text_color(self.ITEM_DESC_COLOR)
        text = self.data.description_text
        links = self.data.description_links
        textbox = layout.textbox("")
        pos = 0
        for start, end, url in links:
            textbox.append_text(text[pos:start])
            textbox.append_text(text[start:end], underline=True, color=self.ITEM_DESC_COLOR)
            pos = end
        if pos < len(text):
            textbox.append_text(text[pos:])
        self.description_links = links
        return textbox

    def pack_main(self, layout):
        vbox = cellpack.VBox()
        layout.set_font(1.1, family=widgetset.ITEM_TITLE_FONT, bold=True)
        layout.set_text_color(self.ITEM_TITLE_COLOR)
        title = layout.textbox(self.data.name)
        # FIXME - title should wrap to the next line instead of being
        # truncated; ben said this might be hard/impossible
        if not self.show_details:
            vbox.pack(cellpack.ClippedTextBox(title))
        else:
            main_width = self._calculate_main_width(layout)
            title.set_width(main_width)
            vbox.pack(title)

        if ((not self.data.is_external
             and self.display_channel
             and self.data.feed_name is not None)):
            vbox.pack_space(1)
            hbox = cellpack.HBox()
            hbox.pack(cellpack.align_middle(self.channel_title_icon))
            hbox.pack_space(4)
            layout.set_font(0.8, family="Helvetica", bold=True)
            hbox.pack(layout.textbox(self.FROM_TEXT))
            hbox.pack_space(6)
            layout.set_font(0.8, family="Helvetica")
            hbox.pack(cellpack.ClippedTextBox(layout.textbox(self.data.feed_name)), expand=True)
            vbox.pack(hbox)

        vbox.pack_space(6)

        if self.show_details:
            description = self.make_description(layout)
            description.set_wrap_style('word')
            description.set_width(main_width)
        else:
            description = cellpack.ClippedTextBox(self.make_description(layout))
        vbox.pack(cellpack.Hotspot('description', description), expand=True)

        if self.show_details and self.data.video_path:
            vbox.pack_space(6)
            layout.set_font(0.8, family="Helvetica", bold=True)
            filename_textbox = layout.textbox(self.FILE_NAME_TEXT)
            filename_textbox.append_text(" ")
            filename_textbox.append_text(utils.filename_to_unicode(self.data.video_path), font=layout.font(0.8, family="Helvetica"))
            filename_textbox.set_width(main_width)
            filename_textbox.set_wrap_style('char')
            vbox.pack(cellpack.align_bottom(filename_textbox), expand=True)

        return vbox

    def _calculate_main_width(self, layout):
        # Calculate the width available to the main area.  This lets us know
        # where to wrap the title and description in show_details mode.
        #
        # Note: self.total_width gets set in TableView.do_size_allocate(),
        # so this will fail if we haven't been allocated a size yet.
        # However, this shouldn't be a problem, because show_details is
        # set to False initially.
        static_width = (
                154 # left side
                + (12 + 20) * 2 # border padding
                + 18 # Padding between main and left
                + 20) # padding between main and right
        return self.total_width - static_width - self.right_side_width

    def set_info_left_color(self, layout):
        if self.use_custom_style:
            layout.set_text_color((0.27, 0.27, 0.27))
        else:
            layout.set_text_color(self.text_color)

    def set_info_right_color(self, layout):
        if self.use_custom_style:
            layout.set_text_color((0.44, 0.44, 0.44))
        else:
            layout.set_text_color(self.text_color)

    def create_pseudo_table(self, layout, rows):
        table = cellpack.Table(len(rows), 2, col_spacing=10, row_spacing=2)

        row_counter = 0
        for left_col, right_col, hotspot in rows:
            if left_col == None:
                table.pack(layout.textbox(""), row_counter, 0)
                table.pack(layout.textbox(""), row_counter, 1)
                row_counter += 1
                continue
            layout.set_font(0.70, bold=True)
            self.set_info_left_color(layout)
            # FIXME - change this column to right-aligned
            table.pack(layout.textbox(left_col), row_counter, 0)

            layout.set_font(0.70)
            self.set_info_right_color(layout)
            if hotspot:
                pack_widget = cellpack.Hotspot(
                    hotspot,
                    layout.textbox(right_col, underline=True))
            else:
                pack_widget = layout.textbox(right_col)
            table.pack(pack_widget, row_counter, 1, expand=True)

            row_counter += 1
        return table

    def pack_right(self, layout):
        vbox = cellpack.VBox(spacing=3)

        # release date
        release_date = displaytext.release_date(self.data.release_date)
        layout.set_text_color((0.4, 0.4, 0.4))
        layout.set_font(0.75, family="Helvetica", bold=True)
        vbox.pack(cellpack.align_right(layout.textbox(release_date)))

        # size and duration
        duration = displaytext.duration(self.data.duration)
        size = displaytext.size_string(self.data.size)

        layout.set_font(0.75, family="Helvetica")
        self.set_info_right_color(layout)

        if duration and size:
            hbox = cellpack.HBox(spacing=10)
            hbox.pack(cellpack.Alignment(layout.textbox(duration), xalign=1.0, xscale=0.0), expand=True)
            hbox.pack(cellpack.align_middle(self.separator))
            hbox.pack(cellpack.Alignment(layout.textbox(size), xalign=1.0, xscale=0.0, min_width=50))
            vbox.pack(cellpack.align_right(hbox))
        elif duration:
            vbox.pack(cellpack.align_right(layout.textbox(duration)))
        elif size:
            vbox.pack(cellpack.align_right(layout.textbox(size)))

        if self.data.expiration_date and self.data.is_playable:
            text = displaytext.expiration_date(self.data.expiration_date)
            layout.set_text_color((0.4, 0.4, 0.4))
            layout.set_font(0.75, family="Helvetica")
            vbox.pack(cellpack.align_right(layout.textbox(text)))
        else:
            layout.set_font(0.75, family="Helvetica")
            vbox.pack(layout.textbox(""))

        if not self.show_details:
            details_text = layout.textbox(self.SHOW_MORE_TEXT)
            details_image = cellpack.align_middle(widgetutil.make_surface('show-more-info'))
        else:
            details_text = layout.textbox(self.SHOW_LESS_TEXT)
            details_image = cellpack.align_middle(widgetutil.make_surface('show-less-info'))
        hbox = cellpack.HBox(spacing=5)
        hbox.pack(details_text)
        hbox.pack(details_image)
        vbox.pack_space(1)
        vbox.pack(cellpack.align_right(cellpack.Hotspot('details_toggle', hbox)))

        return cellpack.pad(vbox, right=8)

    def _make_button(self, layout, text, hotspot_name, disabled=False,
            icon=None):
        button = layout.button(text, self.hotspot==hotspot_name, disabled=disabled, style='webby')
        if disabled:
            return button
        if icon:
            button.set_icon(icon)
        hotspot = cellpack.Hotspot(hotspot_name, button)
        return hotspot

    def pack_flap(self, layout):
        vbox = cellpack.VBox()
        hbox = cellpack.HBox(spacing=15)

        layout.set_font(0.77)

        comments_hotspot = self._make_button(layout, self.COMMENTS_TEXT,
                'visit_comments', not self.data.commentslink)
        hbox.pack(cellpack.align_left(comments_hotspot), expand=True)

        reveal_hotspot = self._make_button(layout, self.REVEAL_IN_TEXT,
                'show_local_file', not self.data.downloaded)
        hbox.pack(cellpack.align_center(reveal_hotspot))

        permalink_hotspot = self._make_button(layout, self.WEB_PAGE_TEXT,
                'visit_webpage', not self.data.permalink)
        hbox.pack(cellpack.align_center(permalink_hotspot))

        fileurl_hotspot = self._make_button(layout, self.FILE_URL_TEXT,
                'visit_filelink', not (self.data.file_url and not self.data.file_url.startswith('file:')))
        hbox.pack(cellpack.align_center(fileurl_hotspot))

        license_hotspot = self._make_button(layout, self.LICENSE_PAGE_TEXT,
                                            'visit_license',
                                            not util.is_url(self.data.license))
        hbox.pack(cellpack.align_center(license_hotspot))

        # 12px between the normal content and the flap border and 8px between
        # the border and the top of the flap buttons.
        vbox.pack_space(20)
        vbox.pack(cellpack.pad(hbox, left=2, right=15))
        vbox.pack_space(8)
        self.flap_height = vbox.get_size()[1] - 12
        # don't count space between the normal content and the flap
        return vbox

    def download_textbox(self, layout):
        dl_info = self.download_info
        layout.set_font(0.80, bold=True)
        layout.set_text_color((1.0, 1.0, 1.0))
        if dl_info.state == 'paused' or dl_info.rate == 0:
            if dl_info.state == 'paused':
                return layout.textbox(_('paused'))
            else:
                return layout.textbox(dl_info.startup_activity)
        parts = []
        if dl_info.rate > 0:
            parts.append(displaytext.download_rate(dl_info.rate))
        if self.data.size > 0 and dl_info.rate > 0:
            parts.append(displaytext.time_string(dl_info.eta))

        return layout.textbox(' - '.join(parts))

    def pack_download_status(self, layout):
        hbox = cellpack.HBox()
        if not self.download_info or self.download_info.state != 'paused':
            left_button = cellpack.Hotspot('pause', self.pause_button)
        else:
            left_button = cellpack.Hotspot('resume', self.resume_button)
        hbox.pack(cellpack.pad(cellpack.align_left(left_button), left=3))
        hbox.pack(cellpack.align_middle(cellpack.align_center(self.download_textbox(layout))), expand=True)
        hbox.pack(cellpack.pad(cellpack.align_right(cellpack.Hotspot('cancel', self.cancel_button)), right=3))

        background = cellpack.Background(cellpack.align_middle(hbox), min_width=356, min_height=20)
        background.set_callback(ItemProgressBarDrawer(self.data).draw)
        return cellpack.pad(background, top=5)

    def _make_thumbnail_button(self, hotspot_name, button, xalign, yalign):
        alignment = cellpack.Alignment(button, xscale=0, xalign=xalign,
                yscale=0, yalign=yalign)
        background = cellpack.Background(alignment, 154, 105)
        background.set_callback(self.draw_thumbnail)
        return cellpack.align_top(cellpack.Hotspot(hotspot_name, background))

    def _make_thumbnail_text_button(self, layout, hotspot_name, text):
        layout.set_font(0.75, bold=True)
        layout.set_text_color((1, 1, 1))
        text = layout.textbox(text)
        radius = max(int((text.get_size()[1] + 1) / 2), 9)
        background = cellpack.Background(cellpack.align_middle(text),
                min_height=radius*2,
                margin=(4, radius+4, 4, radius+4))
        background.set_callback(self.draw_thumbnail_bubble)
        return self._make_thumbnail_button(hotspot_name, background, 0.5, 0.5)

    def pack_left(self, layout):
        vbox = cellpack.VBox(spacing=6)
        thumbnail = cellpack.DrawingArea(154, 105, self.draw_thumbnail)
        if self.data.downloaded:
            vbox.pack(cellpack.Hotspot('thumbnail-play', thumbnail))
        else:
            vbox.pack(cellpack.Hotspot('thumbnail-download', thumbnail))

        if not self.show_details:
            return vbox

        details_rows = []

        # if downloaded, then show the file type
        if self.data.downloaded:
            details_rows.append((self.FILE_TYPE_TEXT, self.data.file_format, None))

        # torrent information
        if (self.data.download_info is not None
                and self.data.download_info.torrent):
            # if self.data.leechers is None (rather than say, 0 or
            # some positive integer) then it wasn't transferring and thus
            # these next four bits don't apply
            if self.data.leechers is not None:
                details_rows.append(
                    (self.SEEDERS_TEXT, str(self.data.seeders), None))
                details_rows.append(
                    (self.LEECHERS_TEXT, str(self.data.leechers), None))
                details_rows.append((None, None, None))

            if self.data.leechers is not None:
                details_rows.append(
                    (self.UPLOAD_RATE_TEXT, displaytext.download_rate(self.data.up_rate), None))
            details_rows.append((self.UPLOAD_TOTAL_TEXT, displaytext.size_string(self.data.up_total), None))
            details_rows.append((None, None, None))

            if self.data.leechers is not None:
                details_rows.append(
                    (self.DOWN_RATE_TEXT, displaytext.download_rate(self.data.down_rate), None))
            details_rows.append(
                (self.DOWN_TOTAL_TEXT, displaytext.size_string(self.data.down_total), None))
            details_rows.append((None, None, None))
            details_rows.append(
                (self.UP_DOWN_RATIO_TEXT, "%0.2f" % self.data.up_down_ratio, None))

        if details_rows:
            details_box = self.create_pseudo_table(layout, details_rows)
            vbox.pack(cellpack.align_center(details_box), expand=True)
        return vbox

    def draw_emblem(self, context, x, y, width, height, color):
        emblem_height = min(height, 17)
        y_offset = int((height - emblem_height) / 2) + 1

        radius = emblem_height / 2.0
        inner_width = width - radius

        # draw the outline
        context.set_line_width(2)
        # border is slightly darker than the color
        context.set_color(tuple([max(0.0, c - 0.1) for c in color]))
        context.move_to(x + inner_width, y + y_offset)
        context.rel_line_to(-inner_width + 10, 0)
        context.rel_line_to(0, emblem_height)
        context.rel_line_to(inner_width-10, 0)
        context.arc(x + inner_width, y + radius + y_offset, radius, -PI/2, PI/2)
        context.stroke()

        # fill it
        context.set_line_width(0)
        context.set_color(color)
        context.move_to(x + inner_width, y + y_offset)
        context.rel_line_to(-inner_width+10, 0)
        context.rel_line_to(0, emblem_height)
        context.rel_line_to(inner_width-10, 0)
        context.arc(x + inner_width, y + radius + y_offset, radius, -PI/2, PI/2)
        context.fill()

    def pack_infobar(self, layout):
        if self.show_progress_bar:
            return cellpack.align_bottom(self.pack_download_status(layout))

        stack = cellpack.Stack()

        main_hbox = cellpack.HBox(spacing=10)

        layout.set_font(0.85)
        if self.data.downloaded:
            if self.data.is_playable:
                if ((app.playback_manager.get_playing_item()
                     and app.playback_manager.get_playing_item().id == self.data.id)):
                    if app.playback_manager.is_paused:
                        button = cellpack.Hotspot('play_pause',
                                                  self.play_button)
                    else:
                        button = cellpack.Hotspot('play_pause',
                                                  self.pause_playback_button)
                else:
                    button = cellpack.Hotspot('play', self.play_button)
            else:
                button = self._make_button(layout, self.REVEAL_IN_TEXT,
                        'show_local_file')
            main_hbox.pack(cellpack.align_middle(button))

        else:
            if self.data.mime_type == 'application/x-bittorrent':
                text = self.DOWNLOAD_TORRENT_TEXT
            else:
                text = self.DOWNLOAD_TEXT
            hotspot = self._make_button(layout, text, 'download',
                    icon=self.download_arrow)
            main_hbox.pack(cellpack.align_middle(cellpack.align_middle(hotspot)))

            # if it's pending autodownload, we add a cancel button to
            # cancel the autodownload
            if self.data.pending_auto_dl:
                hotspot = self._make_button(
                    layout, self.CANCEL_TEXT, 'cancel_auto_download')
                main_hbox.pack(cellpack.align_middle(cellpack.align_middle(hotspot)))

        # If we are going to display an emblem (unwatched, expiring, etc).
        # Then pack it now on to the stack, so the buttons and other things
        # get packed on top.

        emblem_hbox = cellpack.HBox()
        main_width = main_hbox.get_current_size()[0]
        emblem_hbox.pack_space(main_width)

        if self.data.download_info and self.data.download_info.state == 'failed':
            layout.set_font(0.80, bold=True)

            emblem_hbox.pack(cellpack.align_middle(self.alert_image))
            emblem_hbox.pack(cellpack.align_middle(layout.textbox(self.ERROR_TEXT)))
            emblem_hbox.pack(cellpack.align_middle(layout.textbox(u"-")))
            emblem_hbox.pack(cellpack.align_middle(layout.textbox(self.data.download_info.short_reason_failed)))

            emblem_color = (1.0, 252.0 / 255.0, 183.0 / 255.0)
            emblem = cellpack.Background(emblem_hbox, margin=(4, 20, 4, 4))
            emblem.set_callback(self.draw_emblem, emblem_color)

            stack.pack(cellpack.align_left(emblem))

        elif self.data.pending_auto_dl:
            # emblem_hbox.pack(cellpack.align_middle(self.alert_image))
            emblem_hbox.pack(cellpack.align_middle(layout.textbox(self.QUEUED_TEXT)))

            emblem_color = (1.0, 252.0 / 255.0, 183.0 / 255.0)
            emblem = cellpack.Background(emblem_hbox, margin=(4, 20, 4, 4))
            emblem.set_callback(self.draw_emblem, emblem_color)

            stack.pack(cellpack.align_left(emblem))

        elif (self.data.downloaded and app.playback_manager.get_playing_item() and
                app.playback_manager.get_playing_item().id == self.data.id):
            layout.set_font(0.80, bold=True)
            layout.set_text_color((1, 1, 1))

            emblem_hbox.pack(cellpack.align_middle(layout.textbox(self.CURRENTLY_PLAYING_TEXT)))
            emblem_hbox.pack_space(2)

            emblem_color = UNPLAYED_COLOR
            emblem = cellpack.Background(emblem_hbox, margin=(5, 20, 4, 4))
            emblem.set_callback(self.draw_emblem, emblem_color)

            stack.pack(cellpack.align_left(emblem))

        elif (self.data.downloaded and not self.data.video_watched and
                self.data.is_playable):
            layout.set_font(0.80, bold=True)
            layout.set_text_color((1, 1, 1))

            emblem_hbox.pack(cellpack.align_middle(layout.textbox(self.UNPLAYED_TEXT)))
            emblem_hbox.pack_space(2)

            emblem_color = UNPLAYED_COLOR
            emblem = cellpack.Background(emblem_hbox, margin=(5, 20, 4, 4))
            emblem.set_callback(self.draw_emblem, emblem_color)

            stack.pack(cellpack.align_left(emblem))
        elif (self.data.is_playable
              and self.data.item_viewed
              and self.data.resume_time > 0
              and config.get(prefs.RESUME_VIDEOS_MODE)):
            layout.set_font(0.80, bold=True)
            layout.set_text_color((154.0 / 255.0, 174.0 / 255.0, 181.0 / 255.0))

            # text = displaytext.expiration_date(self.data.expiration_date)
            text = _("Resume at %(resumetime)s",
                     {"resumetime": displaytext.short_time_string(self.data.resume_time)})
            emblem_hbox.pack(cellpack.align_middle(layout.textbox(text)))
            emblem_color = (232.0 / 255.0, 240.0 / 255.0, 242.0 / 255.0)
            emblem = cellpack.Background(emblem_hbox, margin=(4, 4, 4, 4))
            emblem.set_callback(self.draw_emblem, emblem_color)

            stack.pack(cellpack.align_left(emblem))
        elif not self.data.item_viewed and self.data.state == "new":
            layout.set_font(0.80, bold=True)
            layout.set_text_color((1, 1, 1))

            emblem_hbox.pack(cellpack.align_middle(layout.textbox(self.NEWLY_AVAILABLE_TEXT)))
            emblem_hbox.pack_space(2)

            emblem_color = AVAILABLE_COLOR
            emblem = cellpack.Background(emblem_hbox, margin=(4, 4, 4, 4))
            emblem.set_callback(self.draw_emblem, emblem_color)

            stack.pack(cellpack.align_left(emblem))

        main_hbox.pack_space(2, expand=True)

        if self.data.is_external or self.data.downloaded:
            main_hbox.pack(self.pack_video_buttons(layout))

        stack.pack(main_hbox)

        return cellpack.align_bottom(cellpack.pad(stack, top=5, bottom=6))

    def pack_video_buttons(self, layout):
        hbox = cellpack.HBox(spacing=5)
        layout.set_font(0.85)
        if self.data.is_container_item:
            hotspot = self._make_button(layout, self.SHOW_CONTENTS_TEXT,
                    'show_contents')
            hbox.pack(cellpack.align_middle(hotspot))
        if self.data.expiration_date:
            hotspot = self._make_button(layout, self.KEEP_TEXT, 'keep')
            hbox.pack(cellpack.align_middle(hotspot))

        hotspot = self._make_button(layout, self.REMOVE_TEXT, 'delete')

        hbox.pack(cellpack.align_middle(hotspot))
        if (self.data.download_info is not None
                and self.data.download_info.torrent):
            if self.data.download_info.state in ("uploading", "uploading-paused"):
                hotspot = self._make_button(layout, self.STOP_SEEDING_TEXT,
                    'stop_seeding')
                hbox.pack(cellpack.align_middle(hotspot))

        return hbox

    def pack_all(self, layout):
        outer_vbox = cellpack.VBox()

        outer_hbox = cellpack.HBox()
        outer_hbox.pack(self.pack_left(layout))
        outer_hbox.pack_space(18)

        vbox = cellpack.VBox()
        vbox.pack_space(5)
        inner_hbox = cellpack.HBox()
        right_side = self.pack_right(layout)
        self.right_side_width = right_side.get_size()[0]
        inner_hbox.pack(self.pack_main(layout), expand=True)
        inner_hbox.pack_space(20)
        inner_hbox.pack(right_side)
        vbox.pack(inner_hbox, expand=True)

        vbox.pack(self.pack_infobar(layout))

        outer_hbox.pack(vbox, expand=True)
        outer_vbox.pack(outer_hbox)
        if self.show_details:
            outer_hbox.pack_space(12)
            outer_vbox.pack_end(self.pack_flap(layout))
        return self.add_background(outer_vbox)

    def setup_style(self, style):
        self.use_custom_style = style.use_custom_style
        if style.use_custom_style:
            self.text_color = (0, 0, 0)
        else:
            self.text_color = style.text_color

    def render(self, context, layout, selected, hotspot, hover):
        self.download_info = self.data.download_info
        self.calc_show_progress_bar()
        self.setup_style(context.style)
        self.hotspot = hotspot
        self.selected = selected
        self.hover = hover
        packing = self.pack_all(layout)
        packing.render_layout(context)

    def make_border_path(self, context, x, y, width, height, inset):
        widgetutil.round_rect(context, x + inset, y + inset,
                width - inset*2, height - inset*2, 7-inset)

    def make_border_path_reverse(self, context, x, y, width, height, inset):
        widgetutil.round_rect_reverse(context, x + inset, y + inset,
                width - inset*2, height - inset*2, 7-inset)

    def draw_background(self, context, x, y, width, height):
        # Draw the gradient
        if self.selected:
            self.make_border_path(context, x, y, width, height, 0)
            context.set_color(self.SELECTED_BACKGROUND_COLOR)
            context.fill()

            bg_color_start = self.SELECTED_BACKGROUND_COLOR
            bg_color_end = self.SELECTED_BACKGROUND_COLOR_BOTTOM
            highlight_inset = 4
        else:
            bg_color_start = context.style.bg_color
            bg_color_end = tuple(c - 0.06 for c in bg_color_start)
            highlight_inset = 2
        context.save()
        self.make_border_path(context, x, y, width, height, 0)
        context.clip()
        top = y + height - self.GRADIENT_HEIGHT
        gradient = widgetset.Gradient(0, top, 0, top + self.GRADIENT_HEIGHT)
        gradient.set_start_color(bg_color_start)
        gradient.set_end_color(bg_color_end)
        context.rectangle(x, top, width, self.GRADIENT_HEIGHT)
        context.gradient_fill(gradient)
        context.restore()
        # Draw the border
        self.draw_border(context, x, y, width, height)
        # Draw the highlight
        context.set_line_width(2)
        self.make_border_path(context, x, y, width, height, highlight_inset)
        context.set_color(widgetutil.WHITE)
        context.stroke()

    def draw_border(self, context, x, y, width, height):
        if self.selected:
            start_color = self.SELECTED_BORDER_COLOR_TOP
            end_color = self.SELECTED_BORDER_COLOR_BOTTOM
            border_width = 3
        else:
            start_color = self.BORDER_COLOR_TOP
            end_color = self.BORDER_COLOR_BOTTOM
            border_width = 1
        # we want to draw the border using a gradient.  So we set the clip
        # area to be exactly where the border should be, then do a
        # gradient fill
        context.save()
        self.make_border_path(context, x, y, width, height, 0)
        self.make_border_path_reverse(context, x, y, width, height,
                border_width)
        context.clip()
        gradient = widgetset.Gradient(x, y, x, y + height)
        gradient.set_start_color(start_color)
        gradient.set_end_color(end_color)
        context.rectangle(x, y, width, height)
        context.gradient_fill(gradient)
        context.restore()

    def draw_background_details(self, context, x, y, width, height):
        # draw the normal background on top of the flap
        self.draw_background(context, x, y, width, height-self.flap_height)

        # Draw the bottom flap
        if self.selected:
            flap_bg_color = self.SELECTED_BACKGROUND_FLAP_COLOR
            border_color = self.SELECTED_BORDER_COLOR_BOTTOM
            border_width = 3
            # add a bit extra space to make the buttons appear vertically
            # centered with the larger border
            height += 2
            self.flap_height += 2
        else:
            flap_bg_color = self.FLAP_BACKGROUND_COLOR
            border_color = self.BORDER_COLOR_BOTTOM
            border_width = 1

        flap_top = y + height - self.flap_height

        # clip to the region where the flap is.
        context.save()
        context.rectangle(x, flap_top, width, self.flap_height)
        context.clip()
        # Draw flap background
        self.make_border_path(context, x, y, width, height, 0)
        context.set_color(flap_bg_color)
        context.fill()
        if not self.selected:
            # Draw the left, right and bottom highlight for the flap
            context.set_color(self.FLAP_HIGHLIGHT_COLOR)
            context.set_line_width(2)
            self.make_border_path(context, x, y, width, height, border_width + 1)
            context.stroke()
            # Draw the top highlight for the flap
            context.move_to(x, flap_top + 0.5)
            context.rel_line_to(width, 0)
            context.stroke()
        context.restore()
        if self.selected:
            # color in the pixels above the flap, but below the rounded corner
            # of the upper border.  We should do this if selected is False as
            # well, but it's not noticeable in that case.
            context.set_color(flap_bg_color)
            context.rectangle(x+3, flap_top-2, 2, 2)
            context.fill()
            context.rectangle(x+width-5, flap_top-2, 2, 2)
            context.fill()

        # Draw the flap border.  Start a little above the usual start of the
        # flap to account for the fact that the rounded corner of the normal
        # border doesn't quite reach the top of the flap.  Draw the outer
        # border
        context.save()
        context.rectangle(x, flap_top-5, width, self.flap_height+5)
        context.clip()

        self.make_border_path(context, x, y, width, height, border_width / 2.0)
        context.set_color(border_color)
        context.set_line_width(border_width)
        context.stroke()
        context.restore()

    def draw_thumbnail(self, context, x, y, width, height):
        widgetutil.draw_rounded_icon(context, self.data.icon, x, y, 154, 105)
        self.thumb_overlay.draw(context, x, y, 154, 105)

    def _thumbnail_bubble_path(self, context, x, y, radius, inner_width):
        context.move_to(x + radius, y + 1.5)
        context.rel_line_to(inner_width, 0)
        context.arc(x+radius+inner_width, y+radius, radius-1.5, -PI/2, PI/2)
        context.rel_line_to(-inner_width, 0)
        context.arc(x+radius, y+radius, radius-1.5, PI/2, -PI/2)

    def draw_thumbnail_bubble(self, context, x, y, width, height):
        radius = max(int((height + 1) / 2), 9)
        inner_width = width - radius * 2
        self._thumbnail_bubble_path(context, x, y, radius, inner_width)
        context.save()
        context.clip()
        gradient = widgetset.Gradient(x, y, x, y + height)
        gradient.set_start_color((0.25, 0.25, 0.25))
        gradient.set_end_color((0, 0, 0))
        context.rectangle(x, y, width, height)
        context.gradient_fill(gradient)
        context.restore()
        self._thumbnail_bubble_path(context, x, y, radius, inner_width)
        context.set_line_width(3)
        context.set_color((1, 1, 1))
        context.stroke()

class PlaylistItemRenderer(ItemRenderer):
    def pack_video_buttons(self, layout):
        hbox = cellpack.HBox(spacing=5)
        layout.set_font(0.85)
        if self.data.is_container_item:
            hotspot = self._make_button(layout, self.SHOW_CONTENTS_TEXT,
                    'show_contents')
            hbox.pack(cellpack.align_middle(hotspot))
        if self.data.expiration_date:
            hotspot = self._make_button(layout, _('Keep'), 'keep')
            hbox.pack(cellpack.align_middle(hotspot))
        hotspot = self._make_button(layout, _('Remove from playlist'), 'remove')
        hbox.pack(cellpack.align_middle(hotspot))
        return hbox

# Renderers for the list view
class ListViewRenderer(widgetset.CustomCellRenderer):
    bold = False
    color = (0.17, 0.17, 0.17)
    font_size = 0.82
    min_width = 50
    right_aligned = False

    def get_size(self, style, layout):
        return 5, self.calc_height(style, layout)

    def calc_height(self, style, layout):
        return layout.font(self.font_size, bold=self.bold).line_height()

    def hotspot_test(self, style, layout, x, y, width, height):
        self.hotspot = None
        self.selected = False
        self.style = style
        packing = self.layout(layout)
        hotspot_info = packing.find_hotspot(x, y, width, height)
        if hotspot_info is None:
            return None
        else:
            return hotspot_info[0]

    def render(self, context, layout, selected, hotspot, hover):
        self.hotspot = hotspot
        self.style = context.style
        self.selected = selected
        packing = self.layout(layout)
        packing.render_layout(context)

    def layout(self, layout):
        self._setup_layout()
        layout.set_font(self.font_size, bold=self.bold)
        if not self.selected and self.style.use_custom_style:
            layout.set_text_color(self.color)
        else:
            layout.set_text_color(self.style.text_color)
        textbox = layout.textbox(self.text)
        if self.right_aligned:
            textbox.set_alignment('right')
        hbox = cellpack.HBox()
        textline = cellpack.TruncatedTextLine(textbox)
        hbox.pack(cellpack.align_middle(textline), expand=True)
        layout.set_font(self.font_size, bold=False)
        self._pack_extra(layout, hbox)
        return hbox

    def _setup_layout(self):
        """Prepare to layout the cell.  This method must set the text
        attribute and may also set the color, bold or other attributes.
        """
        raise NotImplementedError()

    def _pack_extra(self, layout, hbox):
        """Pack extra stuff in the hbox that we created in layout()."""
        pass

class NameRenderer(ListViewRenderer):
    button_font_size = 0.77

    def calc_height(self, style, layout):
        default = ListViewRenderer.calc_height(self, style, layout)
        button = layout.button(_("Download"))
        return max(default, button.get_size()[1])

    def _setup_layout(self):
        self.text = self.info.name
        self.bold = self.info.downloaded

    def _pack_extra(self, layout, hbox):
        if not (self.info.downloaded or
                self.info.state in ('downloading', 'paused')):
            layout.set_font(self.button_font_size)
            button = layout.button(_('Download'))
            hbox.pack(cellpack.align_middle(cellpack.Hotspot('download',
                button)))

class DescriptionRenderer(ListViewRenderer):
    color = (0.6, 0.6, 0.6)

    def _setup_layout(self):
        self.text = self.info.description_text.replace('\n', ' ')

class FeedNameRenderer(ListViewRenderer):
    def _setup_layout(self):
        self.text = self.info.feed_name

class DateRenderer(ListViewRenderer):
    def _setup_layout(self):
        self.text = displaytext.release_date_slashes(self.info.release_date)

class LengthRenderer(ListViewRenderer):
    def _setup_layout(self):
        self.text = displaytext.duration(self.info.duration)

class StatusRenderer(ListViewRenderer):
    bold = True

    def __init__(self):
        ListViewRenderer.__init__(self)
        self.pause_button = imagepool.get_surface(resources.path(
            'images/pause-button.png'))
        self.resume_button = imagepool.get_surface(resources.path(
            'images/resume-button.png'))
        self.cancel_button = imagepool.get_surface(resources.path(
            'images/cancel-button.png'))

    def _setup_layout(self):
        if self.info.downloaded:
            if not self.info.is_playable:
                self.text = ''
            else:
                if not self.info.video_watched:
                    self.text = _('Unplayed')
                    self.color = UNPLAYED_COLOR
                elif self.info.expiration_date:
                    self.text = displaytext.expiration_date_short(
                        self.info.expiration_date)
                    self.color = EXPIRING_TEXT_COLOR
                else:
                    self.text = ''
        elif (self.info.download_info and
                self.info.download_info.rate == 0):
            if self.info.download_info.state == 'paused':
                self.text = _('paused')
            elif self.info.download_info.state == 'failed':
                self.text = self.info.download_info.short_reason_failed
            else:
                self.text = self.info.download_info.startup_activity
            self.color = DOWNLOADING_COLOR
        elif not self.info.item_viewed:
            self.text = _('Newly Available')
            self.color = AVAILABLE_COLOR
        else:
            self.text = ''

    def layout(self, layout):
        if (self.info.state in ('downloading', 'paused') and
                self.info.download_info.rate > 0):
            return self.pack_progress_bar(layout)
        else:
            return ListViewRenderer.layout(self, layout)

    def pack_progress_bar(self, layout):
        progress_bar = ItemProgressBarDrawer(self.info)
        hbox = cellpack.HBox(spacing=2)
        if self.info.state == 'downloading':
            hotspot = cellpack.Hotspot('pause', self.pause_button)
        else:
            hotspot = cellpack.Hotspot('resume', self.resume_button)
        hbox.pack(cellpack.align_middle(hotspot))
        drawing_area = cellpack.DrawingArea(20, 10, progress_bar.draw)
        hbox.pack(cellpack.align_middle(drawing_area), expand=True)
        hotspot = cellpack.Hotspot('cancel', self.cancel_button)
        hbox.pack(cellpack.align_middle(hotspot))
        return hbox

    def _pack_extra(self, layout, hbox):
        if self.info.expiration_date:
            button = layout.button(_('Keep'), self.hotspot=='keep')
            hbox.pack_space(8)
            hbox.pack(cellpack.Hotspot('keep', button))

class ETARenderer(ListViewRenderer):
    right_aligned = True

    def _setup_layout(self):
        self.text = ''
        if self.info.state == 'downloading':
            eta = self.info.download_info.eta
            if eta > 0:
                self.text = displaytext.time_string(self.info.download_info.eta)

class DownloadRateRenderer(ListViewRenderer):
    right_aligned = True
    def _setup_layout(self):
        if self.info.state == 'downloading':
            self.text = displaytext.download_rate(self.info.download_info.rate)
        else:
            self.text = ''

class SizeRenderer(ListViewRenderer):
    right_aligned = True

    def _setup_layout(self):
        self.text = displaytext.size_string(self.info.size)

class StateCircleRenderer(widgetset.CustomCellRenderer):
    min_width = 25

    def __init__(self):
        widgetset.CustomCellRenderer.__init__(self)
        self.unwatched_icon = imagepool.get_surface(resources.path(
            'images/status-icon-newly-downloaded.png'))
        self.new_icon = imagepool.get_surface(resources.path(
            'images/status-icon-new.png'))
        self.downloading_icon = imagepool.get_surface(resources.path(
            'images/status-icon-downloading.png'))
        self.width, self.height = self.unwatched_icon.get_size()

    def get_size(self, style, layout):
        return self.width, self.height

    def render(self, context, layout, selected, hotspot, hover):
        if self.info.state == 'downloading':
            icon = self.downloading_icon
        elif self.info.downloaded and self.info.is_playable and not self.info.video_watched:
            icon = self.unwatched_icon
        elif (not self.info.item_viewed and not self.info.expiration_date and
                not self.info.is_external and not self.info.downloaded):
            icon = self.new_icon
        else:
            return
        x = int((context.width - self.width) / 2)
        y = int((context.height - self.height) / 2)
        icon.draw(context, x, y, self.width, self.height)

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
            a = self.width - self.progress_width
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
