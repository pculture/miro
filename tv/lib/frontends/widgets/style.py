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

    def size_request(self, layout_manager):
        return (0, 63)

    def draw(self, context, layout_manager):
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

    def get_size(self, style, layout_manager):
        if hasattr(self.data, 'tall') and self.data.tall:
            min_height = self.MIN_HEIGHT_TALL
        else:
            min_height = self.MIN_HEIGHT
        return (self.MIN_WIDTH, max(min_height,
            layout_manager.font(self.TITLE_FONT_SIZE).line_height()))

        return (self.MIN_WIDTH, max(self.MIN_HEIGHT,
            layout_manager.font(self.TITLE_FONT_SIZE).line_height()))

    def render(self, context, layout_manager, selected, hotspot, hover):
        layout_manager.set_text_color(context.style.text_color)
        bold = False
        if selected:
            bold = True
        elif not hasattr(self.data, "bolded") or self.data.bolded:
            bold = self.BOLD_TITLE
        layout_manager.set_font(self.TITLE_FONT_SIZE, bold=bold)
        titlebox = layout_manager.textbox(self.data.name)

        hbox = cellpack.HBox(spacing=4)
        if hasattr(self.data, "id") and (self.data.id == 'guide' or self.data.id == 'search'):
            hbox.pack_space(6)
        else:
            hbox.pack_space(2)
        alignment = cellpack.Alignment(self.data.icon, yalign=0.5, yscale=0.0,
                xalign=0.5, xscale=0.0, min_width=16)
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
    BOLD_TITLE = True

    def pack_bubbles(self, hbox, layout_manager):
        if self.data.unwatched > 0:
            self.pack_bubble(hbox, layout_manager, self.data.unwatched,
                    UNPLAYED_COLOR)
        if self.data.downloading > 0:
            self.pack_bubble(hbox, layout_manager, self.data.downloading,
                    DOWNLOADING_COLOR)

class DeviceTabRenderer(TabRenderer):

    def pack_bubbles(self, hbox, layout_manager):
        if getattr(self.data, 'fake', False):
            return
        self.hbox = None
        if self.updating_frame > -1:
            return TabRenderer.pack_bubbles(self, hbox, layout_manager)
        if self.data.mount:
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
    CHANNEL_INFO_TEXT = _("From %(channel)s")
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
    QUEUED_TEXT = _("Queued for Auto-download")
    UNPLAYED_TEXT = _("Unplayed")
    CURRENTLY_PLAYING_TEXT = _("Currently Playing")
    NEWLY_AVAILABLE_TEXT = _("Newly Available")
    KEEP_TEXT = _("Keep")
    REMOVE_TEXT = _("Remove")
    STOP_SEEDING_TEXT = _("Stop seeding")
    PLAYLIST_REMOVE_TEXT = _('Remove from playlist')

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

    def get_size(self, style, layout_manager):
        return self.MIN_WIDTH, 137

    def calc_show_progress_bar(self):
        self.show_progress_bar = (self.data.state in ('downloading', 'paused'))

    def hotspot_test(self, style, layout_manager, x, y, width, height):
        self.download_info = self.data.download_info
        self.calc_show_progress_bar()
        self.setup_style(style)
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

    def make_description(self, layout_manager):
        layout_manager.set_font(0.85, family=widgetset.ITEM_DESC_FONT)
        layout_manager.set_text_color(self.ITEM_DESC_COLOR)
        text, links = self.data.description_stripped
        textbox = layout_manager.textbox("")
        pos = 0
        for start, end, url in links:
            textbox.append_text(text[pos:start])
            textbox.append_text(text[start:end], underline=True, color=self.ITEM_DESC_COLOR)
            pos = end
        if pos < len(text):
            textbox.append_text(text[pos:])
        self.description_links = links
        return textbox

    def _make_button(self, layout_manager, text, hotspot_name, disabled=False,
            icon=None):
        button = layout_manager.button(text, self.hotspot==hotspot_name, disabled=disabled, style='webby')
        if icon:
            button.set_icon(icon)
        return button

    def download_textbox(self, layout_manager):
        dl_info = self.download_info
        layout_manager.set_font(0.80, bold=True)
        layout_manager.set_text_color((1.0, 1.0, 1.0))
        if dl_info.state == 'paused' or dl_info.rate == 0:
            if dl_info.state == 'paused':
                return layout_manager.textbox(_('paused'))
            else:
                return layout_manager.textbox(dl_info.startup_activity)
        parts = []
        if dl_info.rate > 0:
            parts.append(displaytext.download_rate(dl_info.rate))
        if self.data.size > 0 and dl_info.rate > 0:
            parts.append(displaytext.time_string(dl_info.eta))

        return layout_manager.textbox(' - '.join(parts))

    def set_info_left_color(self, layout_manager):
        if self.use_custom_style:
            layout_manager.set_text_color((0.27, 0.27, 0.27))
        else:
            layout_manager.set_text_color(self.text_color)

    def set_info_right_color(self, layout_manager):
        if self.use_custom_style:
            layout_manager.set_text_color((0.44, 0.44, 0.44))
        else:
            layout_manager.set_text_color(self.text_color)

    def layout_all(self, layout_manager, width, height):
        layout = cellpack.Layout()
        # Calculate some positions
        total_rect = cellpack.LayoutRect(0, 0, width, height)
        border_rect = total_rect.subsection(20, 20, 5, 5)
        inner_rect = border_rect.subsection(12, 20, 10, 10)
        main_rect = inner_rect.subsection(185, 0, 5, 0)
        # border gets drawn first
        if self.use_custom_style:
            layout.add_rect(border_rect, self.draw_background)
        # draw bottom part so we know where to position the rest
        self.layout_main_bottom(layout, layout_manager, main_rect)
        # draw the rest
        right_rect = main_rect.right_side(150)
        center_rect = main_rect.left_side(main_rect.width-150)
        layout.add(inner_rect.x, inner_rect.y, 154, 105, self.draw_thumbnail)
        self.layout_center(layout, layout_manager, center_rect)
        self.layout_right(layout, layout_manager, right_rect)
        return layout

    def layout_center(self, layout, layout_manager, rect):
        layout_manager.set_font(1.1, family=widgetset.ITEM_TITLE_FONT, bold=True)
        layout_manager.set_text_color(self.ITEM_TITLE_COLOR)
        title = layout_manager.textbox(self.data.name)
        layout.add_text_line(title, rect.x, rect.y, rect.width)

        if ((not self.data.is_external
             and self.display_channel
             and self.data.feed_name is not None)):
            # layout channel info just below the title

            channel_info_layout = cellpack.Layout()
            channel_info_layout.add_image(self.channel_title_icon, rect.x, 0)
            channel_info = layout_manager.textbox(self.CHANNEL_INFO_TEXT
                    % {'channel': self.data.feed_name})
            channel_info_layout.add_text_line(channel_info,
                    channel_info_layout.last_rect.right + 4, 0,
                    rect.width - self.channel_title_icon.width - 4)

            channel_info_height = channel_info_layout.max_height()
            channel_info_y = layout.last_rect.bottom + 1
            channel_info_layout.center_y(top=channel_info_y,
                    bottom=channel_info_y+channel_info_height)
            layout.merge(channel_info_layout)
            current_y = channel_info_y + channel_info_height + 6
        else:
            current_y = layout.last_rect.bottom + 6
        layout.add(rect.x, current_y, rect.width, rect.bottom - current_y,
                self.make_description(layout_manager).draw, 'description')

    def layout_right(self, layout, layout_manager, rect):
        vertical_spacing = 3

        # release date
        release_date = displaytext.date(self.data.release_date)
        layout_manager.set_text_color((0.4, 0.4, 0.4))
        layout_manager.set_font(0.75, family="Helvetica", bold=True)
        textbox = layout_manager.textbox(release_date)
        textbox.set_alignment('right')
        layout.add_text_line(textbox, rect.x, rect.y, rect.width)

        # size and duration
        duration = displaytext.duration(self.data.duration)
        size = displaytext.size_string(self.data.size)

        layout_manager.set_font(0.75, family="Helvetica")
        self.set_info_right_color(layout_manager)

        current_y = layout.last_rect.bottom + vertical_spacing
        if duration and size:
            ds_layout = cellpack.Layout()
            # size text goes on the right
            sizetext = layout_manager.textbox(size)
            sizetext_width, sizetext_height = sizetext.get_size()
            ds_layout.add(rect.right - sizetext_width, current_y,
                    sizetext_width, sizetext_height, sizetext.draw)
            # separator is 10px to the left of size
            separator_x = (rect.right - sizetext_width - 10 -
                    self.separator.width)
            ds_layout.add_image(self.separator, separator_x, current_y)
            # position duration 10 px to the left of the separator
            durationtext = layout_manager.textbox(duration)
            durationtext.set_alignment('right')
            ds_layout.add_text_line(durationtext, rect.x, current_y,
                    separator_x - rect.x - 10)
            ds_layout.center_y(top=current_y)
            layout.merge(ds_layout)
            # note that last_rect.bottom here is correct because duration and
            # size are the same size, so should have the same height
        elif duration:
            durationtext = layout_manager.textbox(duration)
            durationtext.set_alignment('right')
            layout.add_text_line(durationtext, rect.x, current_y, rect.width)
        elif size:
            sizetext = layout_manager.textbox(size)
            sizetext.set_alignment('right')
            layout.add_text_line(sizetext, rect.x, current_y, rect.width)

        current_y = layout.last_rect.bottom + vertical_spacing

        if self.data.expiration_date and self.data.is_playable:
            layout_manager.set_font(0.75, family="Helvetica")
            text = displaytext.expiration_date(self.data.expiration_date)
            layout_manager.set_text_color((0.4, 0.4, 0.4))
            textbox = layout_manager.textbox(text)
            textbox.set_alignment('right')
            layout.add_text_line(textbox, rect.x, current_y, rect.width)

    def layout_main_bottom(self, layout, layout_manager, rect):
        """layout_main_bottom lay out the bottom part of the main section.

        rect should contain the area for the entire main section.  This method
        will add elements to the bottom of that section, then modify rect to
        remove that space.
        """
        if self.show_progress_bar:
            self.layout_download_status(layout, layout_manager, rect)
            return

        button_layout = self.layout_emblem_buttons(layout_manager)
        emblem_layout = self.layout_emblem(layout_manager,
                button_layout.last_rect.right)
        if self.data.is_external or self.data.downloaded:
            right_buttons = self.layout_video_buttons(layout_manager)
            # move the buttons so they are at the end of the rect
            left_side = rect.width - right_buttons.last_rect.right
            right_buttons.translate(left_side, 0)
            emblem_layout.merge(right_buttons)

        # merge everything together
        emblem_layout.merge(button_layout)
        emblem_layout.translate(rect.x, 0)
        # middle_align things and add it to the main layout.  Adjust rect to
        # reflect the height we are taking up
        height = emblem_layout.max_height()
        emblem_layout.center_y(top=rect.bottom-height, bottom=rect.bottom)
        layout.merge(emblem_layout)
        rect.height -= height
        return

        main_hbox.pack_space(2, expand=True)

        if self.data.is_external or self.data.downloaded:
            main_hbox.pack(self.pack_video_buttons(layout_manager))

        stack.pack(main_hbox)

        return cellpack.align_bottom(cellpack.pad(stack, top=5, bottom=6))

    def layout_emblem_buttons(self, layout_manager):
        """Layout buttons on the left side of the the emblem on the bottom of
        the cell.  This includes things like play buttons, download buttons,
        etc.

        :returns: a layout containing the buttons
        """
        layout = cellpack.Layout()

        layout_manager.set_font(0.85)
        if self.data.downloaded:
            if self.data.is_playable:
                if ((app.playback_manager.get_playing_item()
                     and app.playback_manager.get_playing_item().id == self.data.id)):
                    hotspot = 'play_pause'
                    if app.playback_manager.is_paused:
                        button = self.play_button
                    else:
                        button = self.pause_playback_button
                else:
                    hotspot = 'play'
                    button = self.play_button
            else:
                button = self._make_button(layout_manager, self.REVEAL_IN_TEXT,
                        'show_local_file')
                hotspot = 'show_local_file'
            layout.add_image(button, 0, 0, hotspot)
        else:
            if self.data.mime_type == 'application/x-bittorrent':
                text = self.DOWNLOAD_TORRENT_TEXT
            else:
                text = self.DOWNLOAD_TEXT
            button = self._make_button(layout_manager, text, 'download')
            button.set_icon(self.download_arrow)
            layout.add_image(button, 0, 0, 'download')

            # if it's pending autodownload, we add a cancel button to
            # cancel the autodownload
            if self.data.pending_auto_dl:
                button = self._make_button(layout_manager, self.CANCEL_TEXT,
                        'cancel_auto_download')
                layout.add_image(button, layout.last_rect.right + 10, 0,
                        'cancel_auto_download')
        return layout

    def layout_emblem(self, layout_manager, pad_left):
        """Layout the emblem for the cell.

        The emblem is the swatch of color on the bottom of the cell, which
        displays things like 'newly-available', etc.

        As a side-effect, set self.emblem_color, which is used to draw the
        emblem

        :returns: a layout with the emblems
        """
        layout = cellpack.Layout()
        text = image = None
        self.emblem_color = (1.0, 1.0, 1.0)
        margin_right = 20
        bold = False
        text_color = self.ITEM_DESC_COLOR

        if (self.data.download_info
                and self.data.download_info.state == 'failed'):
            bold = True
            image = self.alert_image
            text = u"%s-%s" % (self.ERROR_TEXT,
                    self.data.download_info.short_reason_failed)
            self.emblem_color = (1.0, 252.0 / 255.0, 183.0 / 255.0)
        elif self.data.pending_auto_dl:
            text = self.QUEUED_TEXT
            self.emblem_color = (1.0, 252.0 / 255.0, 183.0 / 255.0)
        elif (self.data.downloaded
                and app.playback_manager.is_playing_id(self.data.id)):
            text_color = widgetutil.WHITE
            text = self.CURRENTLY_PLAYING_TEXT
            self.emblem_color = UNPLAYED_COLOR
        elif self.data.downloaded and not self.data.video_watched:
            text_color = widgetutil.WHITE
            bold = True
            text = self.UNPLAYED_TEXT
            self.emblem_color = UNPLAYED_COLOR
        elif (self.data.is_playable
              and self.data.item_viewed
              and self.data.resume_time > 0
              and app.config.get(prefs.RESUME_VIDEOS_MODE)):
            bold = True
            text_color = (154.0 / 255.0, 174.0 / 255.0, 181.0 / 255.0)
            self.emblem_color = (232.0 / 255.0, 240.0 / 255.0, 242.0 / 255.0)
            text = _("Resume at %(resumetime)s",
                     {"resumetime": displaytext.short_time_string(self.data.resume_time)})
            margin_right = 6
        elif not self.data.item_viewed and self.data.state == "new":
            bold = True
            text_color = widgetutil.WHITE
            text = self.NEWLY_AVAILABLE_TEXT
            self.emblem_color = AVAILABLE_COLOR
            margin_right = 6

        # add emblem first, since we want it drawn on the bottom.  We don't
        # know the dimensions yet, set them later
        emblem_rect = layout.add(0, 0, 0, 0, self.draw_emblem)

        # lay other stuff out.  The emblem will get 4px padding on the top,
        # bottom and left sides, and margin_right px of padding on the right
        x = pad_left + 4

        if image:
            layout.add_image(image, x, 4)
            x += image.width
        if text:
            layout_manager.set_font(0.80, bold=bold)
            layout_manager.set_text_color(text_color)
            textbox = layout_manager.textbox(text)
            text_width, text_height = textbox.get_size()
            layout.add(x, 4, text_width, text_height, textbox.draw)

        emblem_rect.width = layout.last_rect.right + margin_right
        emblem_rect.height = layout.max_height() + 8
        return layout

    def layout_video_buttons(self, layout_manager):
        layout = cellpack.Layout()
        x = 0
        layout_manager.set_font(0.85)
        if self.data.is_container_item:
            button = self._make_button(layout_manager, self.SHOW_CONTENTS_TEXT,
                    'show_contents')
            layout.add_image(button, 0, 0, 'show_contents')
            x = layout.last_rect.right + 5
        if self.data.expiration_date:
            button = self._make_button(layout_manager, self.KEEP_TEXT, 'keep')
            layout.add_image(button, x, 0, 'show_contents')
            x = layout.last_rect.right + 5

        button = self._make_button(layout_manager, self.REMOVE_TEXT, 'delete')
        layout.add_image(button, x, 0, 'delete')
        x = layout.last_rect.right + 5

        if (self.data.download_info is not None
                and self.data.download_info.torrent):
            if self.data.download_info.state in ("uploading", "uploading-paused"):
                button = self._make_button(layout_manager,
                        self.STOP_SEEDING_TEXT, 'stop_seeding')
                layout.add_image(button, x, 0, 'stop_seeding')
        return layout

    def layout_download_status(self, layout, layout_manager, rect):
        # figure out what button goes on the left
        if not self.download_info or self.download_info.state != 'paused':
            left_hotspot = 'pause'
            left_button = self.pause_button
        else:
            left_hotspot = 'resume'
            left_button = self.resume_button
        # lay stuff out.
        # - Entire display goes on the bottom 20 px of the section (or more if
        #   we need it for the text)
        # - The buttons are on the left and right sides, with 3px padding
        #   between them and the edges
        # - The text is in the center of the 2 buttons
        textbox = self.download_textbox(layout_manager)
        textbox.set_alignment('center')
        line_height = textbox.font.line_height()
        our_rect = rect.bottom_side(max(20, line_height))
        text_rect = our_rect.subsection(3 + left_button.width,
                3 + self.cancel_button.width, 0, our_rect.height-line_height)

        layout.add_rect(our_rect, ItemProgressBarDrawer(self.data).draw)
        inner_layout = cellpack.Layout()
        inner_layout.add_image(left_button, our_rect.x + 3, our_rect.y,
                left_hotspot)
        inner_layout.add_rect(text_rect, textbox.draw)
        inner_layout.add_image(self.cancel_button, text_rect.right,
                our_rect.y, 'cancel')
        inner_layout.center_y(top=our_rect.y, bottom=our_rect.bottom)

        layout.merge(inner_layout)

        # subtract our height from the rest of the main section
        rect.height -= our_rect.height

    def setup_style(self, style):
        self.use_custom_style = style.use_custom_style
        if style.use_custom_style:
            self.text_color = (0, 0, 0)
        else:
            self.text_color = style.text_color

    def render(self, context, layout_manager, selected, hotspot, hover):
        self.download_info = self.data.download_info
        self.calc_show_progress_bar()
        self.setup_style(context.style)
        self.hotspot = hotspot
        self.selected = selected
        self.hover = hover
        layout = self.layout_all(layout_manager, context.width,
                context.height)
        layout.draw(context)

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
        icon = imagepool.get_surface(self.data.thumbnail, (154, 105))
        widgetutil.draw_rounded_icon(context, icon, x, y, 154, 105)
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

    def draw_emblem(self, context, x, y, width, height):
        color = self.emblem_color
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


class PlaylistItemRenderer(ItemRenderer):
    def layout_video_buttons(self, layout_manager):
        layout = cellpack.Layout()
        layout_manager.set_font(0.85)
        x = 0

        if self.data.is_container_item:
            button = self._make_button(layout_manager, self.SHOW_CONTENTS_TEXT,
                    'show_contents')
            layout.add_image(button, 0, 0, 'show_contents')
            x = layout.last_rect.right + 5
        if self.data.expiration_date:
            button = self._make_button(layout_manager, self.KEEP_TEXT, 'keep')
            layout.add_image(button, x, 0, 'show_contents')
            x = layout.last_rect.right + 5

        button = self._make_button(layout_manager, self.PLAYLIST_REMOVE_TEXT,
                'remove')
        layout.add_image(button, x, 0, 'remove')
        return layout

# Renderers for the list view
class ListViewRenderer(widgetset.CustomCellRenderer):
    bold = False
    color = (0.17, 0.17, 0.17)
    font_size = 0.82
    min_width = 50
    right_aligned = False

    def get_size(self, style, layout_manager):
        return 5, self.calc_height(style, layout_manager)

    def calc_height(self, style, layout_manager):
        return layout_manager.font(self.font_size, bold=self.bold).line_height()

    def hotspot_test(self, style, layout_manager, x, y, width, height):
        self.hotspot = None
        self.selected = False
        self.style = style
        packing = self.layout_manager(layout_manager)
        hotspot_info = packing.find_hotspot(x, y, width, height)
        if hotspot_info is None:
            return None
        else:
            return hotspot_info[0]

    def render(self, context, layout_manager, selected, hotspot, hover):
        self.hotspot = hotspot
        self.style = context.style
        self.selected = selected
        packing = self.layout_manager(layout_manager)
        packing.render_layout(context)

    def layout_manager(self, layout_manager):
        self._setup_layout_manager()
        layout_manager.set_font(self.font_size, bold=self.bold)
        if not self.selected and self.style.use_custom_style:
            layout_manager.set_text_color(self.color)
        else:
            layout_manager.set_text_color(self.style.text_color)
        textbox = layout_manager.textbox(self.text)
        if self.right_aligned:
            textbox.set_alignment('right')
        hbox = cellpack.HBox()
        textline = cellpack.TruncatedTextLine(textbox)
        hbox.pack(cellpack.align_middle(textline), expand=True)
        layout_manager.set_font(self.font_size, bold=False)
        self._pack_extra(layout_manager, hbox)
        return hbox

    def _setup_layout_manager(self):
        """Prepare to layout_manager the cell.  This method must set the text
        attribute and may also set the color, bold or other attributes.
        """
        raise NotImplementedError()

    def _pack_extra(self, layout_manager, hbox):
        """Pack extra stuff in the hbox that we created in layout_manager()."""
        pass

class NameRenderer(ListViewRenderer):
    button_font_size = 0.77

    def calc_height(self, style, layout_manager):
        default = ListViewRenderer.calc_height(self, style, layout_manager)
        button = layout_manager.button(_("Download"))
        return max(default, button.get_size()[1])

    def _setup_layout_manager(self):
        self.text = self.info.name
        self.bold = self.info.downloaded

    def _pack_extra(self, layout_manager, hbox):
        if not (self.info.downloaded or
                self.info.state in ('downloading', 'paused')):
            layout_manager.set_font(self.button_font_size)
            button = layout_manager.button(_('Download'))
            hbox.pack(cellpack.align_middle(cellpack.Hotspot('download',
                button)))

class DescriptionRenderer(ListViewRenderer):
    color = (0.6, 0.6, 0.6)

    def _setup_layout_manager(self):
        self.text = self.info.description_text.replace('\n', ' ')

class FeedNameRenderer(ListViewRenderer):
    def _setup_layout_manager(self):
        self.text = self.info.feed_name

class DateRenderer(ListViewRenderer):
    def _setup_layout_manager(self):
        self.text = displaytext.date_slashes(self.info.release_date)

class LengthRenderer(ListViewRenderer):
    def _setup_layout_manager(self):
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

    def _setup_layout_manager(self):
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

    def layout_manager(self, layout_manager):
        if self.info.state in ('downloading', 'paused'):
            return self.pack_progress_bar(layout_manager)
        else:
            return ListViewRenderer.layout_manager(self, layout_manager)

    def pack_progress_bar(self, layout_manager):
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

    def _pack_extra(self, layout_manager, hbox):
        if self.info.expiration_date:
            button = layout_manager.button(_('Keep'), self.hotspot=='keep')
            hbox.pack_space(8)
            hbox.pack(cellpack.Hotspot('keep', button))

class RatingRenderer(ListViewRenderer):
    def _setup_layout_manager(self):
        self.text = "todo"

class ETARenderer(ListViewRenderer):
    right_aligned = True

    def _setup_layout_manager(self):
        self.text = ''
        if self.info.state == 'downloading':
            eta = self.info.download_info.eta
            if eta > 0:
                self.text = displaytext.time_string(self.info.download_info.eta)

class DownloadRateRenderer(ListViewRenderer):
    right_aligned = True
    def _setup_layout_manager(self):
        if self.info.state == 'downloading':
            self.text = displaytext.download_rate(self.info.download_info.rate)
        else:
            self.text = ''

class SizeRenderer(ListViewRenderer):
    right_aligned = True

    def _setup_layout_manager(self):
        self.text = displaytext.size_string(self.info.size)

class ArtistRenderer(ListViewRenderer):
    def _setup_layout_manager(self):
        self.text = self.info.artist

class AlbumRenderer(ListViewRenderer):
    def _setup_layout_manager(self):
        self.text = self.info.album

class TrackRenderer(ListViewRenderer):
    def _setup_layout_manager(self):
        self.text = displaytext.integer(self.info.track)

class YearRenderer(ListViewRenderer):
    def _setup_layout_manager(self):
        self.text = displaytext.integer(self.info.year)

class GenreRenderer(ListViewRenderer):
    def _setup_layout_manager(self):
        self.text = self.info.genre

class DateAddedRenderer(ListViewRenderer):
    def _setup_layout_manager(self):
        self.text = displaytext.date_slashes(self.info.date_added)

class LastPlayedRenderer(ListViewRenderer):
    def _setup_layout_manager(self):
        self.text = displaytext.date_slashes(self.info.last_played)

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

    def get_size(self, style, layout_manager):
        return self.width, self.height

    def render(self, context, layout_manager, selected, hotspot, hover):
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
