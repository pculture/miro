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
import os

from miro import app
from miro import signals
from miro import displaytext
from miro import prefs
from miro import util
from miro.gtcache import gettext as _
from miro.frontends.widgets import cellpack
from miro.frontends.widgets import imagepool
from miro.frontends.widgets import widgetutil
from miro.plat import resources
from miro.plat.frontends.widgets import widgetset
from miro.plat.frontends.widgets import file_navigator_name

PI = math.pi
# dimensions
RIGHT_WIDTH = 90
RIGHT_WIDTH_DOWNLOAD_MODE = 115
IMAGE_WIDTH_SQUARE = 125
IMAGE_WIDTH_WIDE = 180
CORNER_RADIUS = 5
EMBLEM_HEIGHT = 20

# padding/spacing
PADDING = (15, 15, 6, 6)
PADDING_BACKGROUND = (5, 5, 4, 6)
EMBLEM_TEXT_PAD_START = 4
EMBLEM_TEXT_PAD_END = 20
EMBLEM_TEXT_PAD_END_SMALL = 6
EMBLEM_MARGIN_RIGHT = 12

# colors
THUMBNAIL_SEPARATOR_COLOR = widgetutil.BLACK
INFO_SEPARATOR_COLOR = widgetutil.css_to_color('#aaaaaa')
ITEM_TITLE_COLOR = widgetutil.BLACK
DOWNLOAD_INFO_COLOR = widgetutil.WHITE
DOWNLOAD_INFO_COLOR_UNEM = (0.2, 0.2, 0.2)
DOWNLOAD_INFO_SEPARATOR_COLOR = widgetutil.WHITE
DOWNLOAD_INFO_SEPARATOR_ALPHA = 0.1
TORRENT_INFO_LABEL_COLOR = (0.6, 0.6, 0.6)
TORRENT_INFO_DATA_COLOR = widgetutil.WHITE
ITEM_DESC_COLOR = (0.3, 0.3, 0.3)
FEED_NAME_COLOR = (0.5, 0.5, 0.5)
PLAYLIST_ORDER_COLOR = widgetutil.BLACK

# font sizes
EMBLEM_FONT_SIZE = widgetutil.font_scale_from_osx_points(11)
TITLE_FONT_SIZE = widgetutil.font_scale_from_osx_points(14)
EXTRA_INFO_FONT_SIZE = widgetutil.font_scale_from_osx_points(10)
ITEM_DESC_FONT_SIZE = widgetutil.font_scale_from_osx_points(11)
DOWNLOAD_INFO_FONT_SIZE = 0.70
DOWNLOAD_INFO_TORRENT_DETAILS_FONT_SIZE = 0.50

# Emblem shadow settings
EMBLEM_SHADOW_OPACITY = 0.6
EMBLEM_SHADOW_OFFSET = (0, 1)
EMBLEM_SHADOW_BLUR_RADIUS = 0

# text assets
REVEAL_IN_TEXT = (file_navigator_name and
        _("Reveal in %(progname)s", {"progname": file_navigator_name}) or _("Reveal File"))
SHOW_CONTENTS_TEXT = _("display contents")
DOWNLOAD_TEXT = _("Download")
DOWNLOAD_TO_MY_MIRO_TEXT = _("Download to My Miro")
DOWNLOAD_TORRENT_TEXT = _("Download Torrent")
ERROR_TEXT = _("Error")
CANCEL_TEXT = _("Cancel")
QUEUED_TEXT = _("Queued for Auto-download")
UNPLAYED_TEXT = _("Unplayed")
CURRENTLY_PLAYING_TEXT = _("Currently Playing")
NEWLY_AVAILABLE_TEXT = _("Newly Available")
SAVED_TEXT = _("Saved")
STOP_SEEDING_TEXT = _("Stop seeding")

class EmblemVisuals(object):
    """Holds the visual needed to draw an item's emblem."""
    def __init__(self, text_color_css, image_name, text_bold,
            pad_right_small=False):
        self.text_color = widgetutil.css_to_color(text_color_css)
        text_color_average = sum(self.text_color) / 3.0
        if text_color_average > 0.5:
            self.text_shadow = widgetutil.BLACK
        else:
            self.text_shadow = widgetutil.WHITE
        self.text_bold = text_bold
        self.image_name = image_name
        if pad_right_small:
            self.pad_right = EMBLEM_TEXT_PAD_END_SMALL
        else:
            self.pad_right = EMBLEM_TEXT_PAD_END

EMBLEM_VISUALS_RESUME = EmblemVisuals('#306219', 'resume', True,
        pad_right_small=True)
EMBLEM_VISUALS_UNPLAYED = EmblemVisuals('#d8ffc7', 'unplayed', True)
EMBLEM_VISUALS_EXPIRING = EmblemVisuals('#6f6c28', 'expiring', True)
EMBLEM_VISUALS_NEWLY_AVAILABLE = EmblemVisuals( '#e1efff', 'newly', True,
        pad_right_small=True)
EMBLEM_VISUALS_DRM = EmblemVisuals('#582016', 'drm', True)
EMBLEM_VISUALS_QUEUED = EmblemVisuals('#4a2c00', 'queued', False)
EMBLEM_VISUALS_FAILED = EmblemVisuals('#ffe7e7', 'failed', False)

class ItemRendererSignals(signals.SignalEmitter):
    """Signal emitter for ItemRenderer.

    We could make ItemRenderer subclass SignalEmitter, but since it comes from
    widgetset that seems awkward.  Instead, this class handles the signals and
    it's set as a property of ItemRenderer

    signals:
        throbber-drawn (obj, item_info) -- a progress throbber was drawn
    """
    def __init__(self):
        signals.SignalEmitter.__init__(self, 'throbber-drawn')

class ItemRenderer(widgetset.InfoListRenderer):
    MIN_WIDTH = 600
    HEIGHT = 147

    def __init__(self, display_channel=True, is_podcast=False,
            wide_image=False):
        widgetset.InfoListRenderer.__init__(self)
        self.signals = ItemRendererSignals()
        self.display_channel = display_channel
        self.is_podcast = is_podcast
        self.selected = False
        if wide_image:
            self.image_width = IMAGE_WIDTH_WIDE
        else:
            self.image_width = IMAGE_WIDTH_SQUARE
        self.setup_images()
        self.emblem_drawer = _EmblemDrawer(self)
        self.extra_info_drawer = _ExtraInfoDrawer()
        self.setup_torrent_folder_description()

    def setup_torrent_folder_description(self):
        text = (u'<a href="#show-torrent-contents">%s</a>' %
                SHOW_CONTENTS_TEXT)
        self.torrent_folder_description = util.HTMLStripper().strip(text)

    def setup_images(self):
        all_images = [ 'background-left', 'background-middle',
                'background-right', 'dl-speed', 'dl-stats-left-cap',
                'dl-stats-middle', 'dl-stats-right-cap',
                'dl-stats-selected-left-cap', 'dl-stats-selected-middle',
                'dl-stats-selected-right-cap', 'download-icon',
                'download-pause', 'download-pause-pressed', 'download-resume',
                'download-resume-pressed', 'download-stop',
                'download-stop-pressed', 'drm-middle', 'drm-cap',
                'expiring-cap', 'expiring-middle', 'failed-middle',
                'failed-cap', 'keep', 'keep-pressed', 'menu', 'menu-pressed',
                'pause', 'pause-pressed', 'play', 'play-pressed', 'remove',
                'remove-playlist', 'remove-playlist-pressed',
                'remove-pressed', 'saved', 'status-icon-alert', 'newly-cap',
                'newly-middle', 'progress-left-cap', 'progress-middle',
                'progress-right-cap', 'progress-throbber-1-left',
                'progress-throbber-1-middle', 'progress-throbber-1-right',
                'progress-throbber-2-left', 'progress-throbber-2-middle',
                'progress-throbber-2-right', 'progress-throbber-3-left',
                'progress-throbber-3-middle', 'progress-throbber-3-right',
                'progress-throbber-4-left', 'progress-throbber-4-middle',
                'progress-throbber-4-right', 'progress-throbber-5-left',
                'progress-throbber-5-middle', 'progress-throbber-5-right',
                'progress-throbber-6-left', 'progress-throbber-6-middle',
                'progress-throbber-6-right', 'progress-throbber-7-left',
                'progress-throbber-7-middle', 'progress-throbber-7-right',
                'progress-throbber-8-left', 'progress-throbber-8-middle',
                'progress-throbber-8-right', 'progress-throbber-9-left',
                'progress-throbber-9-middle', 'progress-throbber-9-right',
                'progress-throbber-10-left', 'progress-throbber-10-middle',
                'progress-throbber-10-right',
                'progress-track', 'queued-middle', 'queued-cap', 'resume-cap',
                'resume-middle', 'selected-background-left',
                'selected-background-middle', 'selected-background-right',
                'time-left', 'ul-speed', 'unplayed-cap', 'unplayed-middle', ]
        self.images = {}
        for image_name in all_images:
            filename = 'item-renderer-%s.png' % image_name
            surface = imagepool.get_surface(resources.path(
                os.path.join('images', filename)))
            self.images[image_name] = surface

    def get_size(self, style, layout_manager):
        return self.MIN_WIDTH, self.HEIGHT

    def calc_download_mode(self):
        self.download_mode = (self.info.state in ('downloading', 'paused'))
        # If the download has started and we don't know the total size.  Draw
        # a progress throbber.
        if self.download_mode:
            dl_info = self.info.download_info
            self.throbber_mode = (dl_info.downloaded_size > 0 and
                    dl_info.total_size < 0)

    def hotspot_test(self, style, layout_manager, x, y, width, height):
        self.download_info = self.info.download_info
        self.calc_download_mode()
        self.hotspot = None
        self.selected = False
        # Assume the mouse is over the cell, since we got a mouse click
        self.hover = True
        layout = self.layout_all(layout_manager, width, height)
        hotspot_info = layout.find_hotspot(x, y)
        self.extra_info_drawer.reset()
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
        self.extra_info_drawer.reset()

    def layout_all(self, layout_manager, width, height):
        self.setup_guides(width, height)
        layout = cellpack.Layout()
        self.layout_simple_elements(layout, layout_manager)
        self.layout_text(layout, layout_manager)
        if self.download_mode:
            self.layout_progress_bar(layout, layout_manager)
            self.layout_download_right(layout, layout_manager)
        else:
            self.layout_main_bottom(layout, layout_manager)
            self.layout_right(layout, layout_manager)
        return layout

    def setup_guides(self, width, height):
        """Setup a few dimensions to help us layout the cell:

        This method sets the following attributes:
            background_rect - area where the background image should be drawn
            image_rect - area for the thumbnail
            middle_rect - area for the text/badges
            right_rect - area for the buttons/download information
        """
        total_rect = cellpack.LayoutRect(0, 0, width, height)
        # NOTE: background image extends a few pixels beyond the actual
        # boundaries so that it can draw shadows and other things
        self.background_rect = total_rect.subsection(*PADDING)
        # area inside the boundaries of the background
        inner_rect = self.background_rect.subsection(*PADDING_BACKGROUND)
        self.image_rect = inner_rect.left_side(self.image_width)
        if self.download_mode:
            right_width = RIGHT_WIDTH_DOWNLOAD_MODE
        else:
            right_width = RIGHT_WIDTH
        self.right_rect = inner_rect.right_side(right_width)
        self.middle_rect = inner_rect.subsection(self.image_width + 20,
                right_width + 15, 0 ,0)
        # emblem/progress bar should start 29px above the top of the cell
        self.emblem_bottom = total_rect.bottom - 29

    def layout_simple_elements(self, layout, layout_manager):
        # this is a place to put layout calls that are simple enough that they
        # don't need their own function
        layout.add_rect(self.background_rect, self.draw_background)
        layout.add_rect(self.image_rect, self.draw_thumbnail,
                self.calc_thumbnail_hotspot())
        layout.add_rect(self.image_rect.past_right(1),
                self.draw_thumbnail_separator)

    def calc_thumbnail_hotspot(self):
        """Decide what hotspot clicking on the thumbnail should activate."""
        if not self.info.downloaded:
            return 'thumbnail-download'
        elif self.info.is_playable:
            return 'thumbnail-play'
        else:
            return None

    def layout_text(self, layout, layout_manager):
        """layout the text for our cell """
        # setup title
        layout_manager.set_font(TITLE_FONT_SIZE,
                family=widgetset.ITEM_TITLE_FONT, bold=True)
        layout_manager.set_text_color(ITEM_TITLE_COLOR)
        title = layout_manager.textbox(self.info.name)
        title.set_wrap_style('truncated-char')
        # setup info lin
        layout_manager.set_font(EXTRA_INFO_FONT_SIZE,
                family=widgetset.ITEM_INFO_FONT)
        layout_manager.set_text_color(ITEM_DESC_COLOR)
        self.extra_info_drawer.setup(self.info, layout_manager,
            INFO_SEPARATOR_COLOR)
        # setup description
        description = self.make_description(layout_manager)

        # position the parts.

        total_height = (title.font.line_height() +
                + self.extra_info_drawer.height +
                description.font.line_height() + 16)
        x = self.middle_rect.x
        width = self.middle_rect.width
        # Ideally, we want to start it at 28px from the start of the top of
        # the cell.  However, if our text is big enough, don't let it overflow
        # the play button.
        text_bottom = min(25 + total_height, self.middle_rect.y + 80)
        self.text_top = text_bottom - total_height
        if self.download_mode:
            # quick interlude.  If we are in download mode, draw the menu on
            # the right side of the title line.
            menu_x = x + width - self.images['menu'].width
            self._add_image_button(layout, menu_x, self.text_top, 'menu',
                    '#show-context-menu')
            title_width = width - self.images['menu'].width - 5
        else:
            title_width = width

        layout.add_text_line(title, x, self.text_top, title_width)
        y = layout.last_rect.bottom + 6
        layout.add(x, y, width, self.extra_info_drawer.height,
            self.extra_info_drawer.draw)
        y = layout.last_rect.bottom + 6
        layout.add_text_line(description, x, y, width, hotspot='description')
        self.description_width = width

    def make_description(self, layout_manager):
        layout_manager.set_font(ITEM_DESC_FONT_SIZE,
                family=widgetset.ITEM_DESC_FONT)
        layout_manager.set_text_color(ITEM_DESC_COLOR)
        textbox = layout_manager.textbox("")
        self.description_text_start = self.add_description_preface(textbox)

        if (self.info.download_info and self.info.download_info.torrent and
                self.info.children):
            text, links = self.torrent_folder_description
        else:
            text, links = self.info.description_stripped

        pos = 0
        for start, end, url in links:
            textbox.append_text(text[pos:start])
            textbox.append_text(text[start:end], underline=True, color=ITEM_DESC_COLOR)
            pos = end
        if pos < len(text):
            textbox.append_text(text[pos:])
        self.description_links = links
        return textbox

    def add_description_preface(self, textbox):
        if (self.display_channel and self.info.feed_name and
                not self.info.is_external):
            feed_preface = "%s: " % self.info.feed_name
            textbox.append_text(feed_preface, color=FEED_NAME_COLOR)
            return len(feed_preface)
        else:
            return 0

    def layout_main_bottom(self, layout, layout_manager):
        """Layout the bottom part of the main section.

        rect should contain the area for the entire middle section.  This
        method will add the progress bar, emblem and/or play button.
        """

        # allocate it enough size to fit the play button
        self.emblem_drawer.info = self.info
        self.emblem_drawer.hotspot = self.hotspot
        emblem_width = self.emblem_drawer.add_to_layout(layout,
                layout_manager, self.middle_rect, self.emblem_bottom)
        # add stop seeding and similar buttons
        extra_button_x = (self.middle_rect.x + emblem_width +
                EMBLEM_MARGIN_RIGHT)
        self.add_extra_button(layout, layout_manager, extra_button_x)

    def add_extra_button(self, layout, layout_manager, left):
        button_info = self.calc_extra_button()
        if button_info is None:
            return
        else:
            text, hotspot = button_info
        layout_manager.set_font(EMBLEM_FONT_SIZE)
        button = layout_manager.button(text, pressed=(self.hotspot==hotspot),
                    style='webby')
        button_height = button.get_size()[1]
        y = (self.emblem_bottom - (EMBLEM_HEIGHT - button_height) // 2 -
                button_height)
        layout.add_image(button, left, y, hotspot)

    def calc_extra_button(self):
        """Calculate the button to put to the right of the emblem.

        :returns: (text, hotspot_name) tuple, or None
        """
        if (self.info.download_info and
                self.info.download_info.state == 'uploading'):
            return (STOP_SEEDING_TEXT, 'stop_seeding')
        elif self.info.pending_auto_dl:
            return (CANCEL_TEXT, 'cancel_auto_download')
        return None

    def layout_right(self, layout, layout_manager):
        button_width, button_height = self.images['keep'].get_size()
        x = self.right_rect.right - button_width - 20
        # align the buttons based on where other parts get laid out.
        top = self.text_top - 1
        bottom = self.emblem_bottom

        # top botton is easy
        menu_y = top
        expire_y = bottom - button_height
        delete_y = ((top + bottom - button_height) // 2)

        self._add_image_button(layout, x, menu_y, 'menu',
                '#show-context-menu')

        if ((self.info.is_external or self.info.downloaded) and 
            self.info.source_type != 'sharing'):
            self.add_remove_button(layout, x, delete_y)

        if self.info.expiration_date:
            expire_rect = cellpack.LayoutRect(x, expire_y, button_width,
                    button_height)
            text = displaytext.expiration_date(self.info.expiration_date)
            image = self._make_image_button('keep', 'keep')
            hotspot = 'keep'
            self.layout_expire(layout, layout_manager, expire_rect, text,
                    image, hotspot)
            self.expire_background_alpha = 1.0
        elif self.attrs.get('keep-animation-alpha', 0) > 0:
            expire_rect = cellpack.LayoutRect(x, expire_y, button_width,
                    button_height)
            text = SAVED_TEXT
            image = self.images['saved']
            hotspot = None
            self.layout_expire(layout, layout_manager, expire_rect, text,
                    image, hotspot)
            self.expire_background_alpha = self.attrs['keep-animation-alpha']

    def add_remove_button(self, layout, x, y):
        """Add the remove button to a layout.
        
        Subclasses can override this if they want different behavior/looks for
        the button.
        """
        self._add_image_button(layout, x, y, 'remove', 'delete')

    def layout_expire(self, layout, layout_manager, rect, text, image, hotspot):
        # create a new Layout for the 2 elements
        expire_layout = cellpack.Layout()
        # add the background now so that it's underneath everything else.  We
        # don't know anything about the x dimensions yet, so just set them to
        # 0
        background_rect = expire_layout.add(0, 0, 0, EMBLEM_HEIGHT,
                self.draw_expire_background)
        # create text for the emblem
        layout_manager.set_font(EMBLEM_FONT_SIZE)
        layout_manager.set_text_color(EXPIRING_TEXT_COLOR)
        textbox = layout_manager.textbox(text)
        # add text.  completely break the bounds of our layout rect and
        # position the text to the left of our rect
        text_width, text_height = textbox.get_size()
        text_x = rect.x - EMBLEM_TEXT_PAD_START - text_width
        expire_layout.add(text_x, 0, text_width, text_height, textbox.draw)
        # add button
        button_rect = expire_layout.add_image(image, rect.x, 0, hotspot)
        # now we can position the background, draw it to the middle of the
        # button.
        background_rect.x = round(text_x - EMBLEM_TEXT_PAD_END)
        background_rect.width = (rect.x - background_rect.x +
                button_rect.width // 2)
        # middle align everything and add it to layout
        expire_layout.center_y(top=rect.y, bottom=rect.bottom)
        layout.merge(expire_layout)

    def layout_progress_bar(self, layout, layout_manager):
        left = self.middle_rect.x
        width = self.middle_rect.width
        top = self.emblem_bottom - self.images['progress-track'].height
        height = 22
        end_button_width = 47
        progress_cap_width = 10
        # figure out what button goes on the left
        if not self.download_info or self.download_info.state != 'paused':
            left_hotspot = 'pause'
            left_button_name = 'download-pause'
        else:
            left_hotspot = 'resume'
            left_button_name = 'download-resume'

        # add ends of the bar
        self._add_image_button(layout, left, top, left_button_name,
                left_hotspot)
        right_button_x = left + width - end_button_width
        self._add_image_button(layout, right_button_x, top, 'download-stop',
                'cancel')
        # add track in the middle
        track = self.images['progress-track']
        track_x = left + end_button_width
        track_rect = cellpack.LayoutRect(track_x, top, right_button_x - track_x,
                height)
        layout.add_rect(track_rect, track.draw)

        # add progress bar above the track
        progress_x = track_x - progress_cap_width
        bar_width_total = (right_button_x - progress_x) + progress_cap_width
        bar_rect = cellpack.LayoutRect(progress_x, top, bar_width_total, height)
        layout.add_rect(bar_rect, self.draw_progress_bar)

    def layout_download_right(self, layout, layout_manager):
        dl_info = self.info.download_info
        # add some padding around the edges
        content_rect = self.right_rect.subsection(6, 12, 8, 8)
        x = content_rect.x
        width = content_rect.width

        # layout top
        layout_manager.set_font(DOWNLOAD_INFO_FONT_SIZE)
        line_height = layout_manager.current_font.line_height()
        ascent = layout_manager.current_font.ascent()
        # generic code to layout a line at the top
        def add_line(y, image_name, text, subtext=None):
            # position image so that it's bottom is the baseline for the text
            image = self.images[image_name]
            image_y = y + ascent - image.height + 3
            # add 3 px to account for the shadow at the bottom of the icons
            layout.add_image(image, x, image_y)
            if text:
                layout_manager.set_text_color(DOWNLOAD_INFO_COLOR)
                textbox = layout_manager.textbox(text)
                textbox.set_alignment('right')
                layout.add_text_line(textbox, x, y, width)
            if subtext:
                layout_manager.set_text_color(DOWNLOAD_INFO_COLOR_UNEM)
                subtextbox = layout_manager.textbox(subtext)
                subtextbox.set_alignment('right')
                layout.add_text_line(subtextbox, x, y + line_height, width)
        if self.info.state == 'paused':
            eta = rate = 0
        else:
            eta = dl_info.eta
            rate = dl_info.rate

        # layout line 1
        current_y = self.right_rect.y + 10
        add_line(current_y, 'time-left', displaytext.time_string_0_blank(eta))
        current_y += max(19, line_height)
        layout.add(x, current_y-1, width, 1,
                self.draw_download_info_separator)
        # layout line 2
        add_line(current_y, 'dl-speed',
                displaytext.download_rate(rate),
                displaytext.size_string(dl_info.downloaded_size))
        current_y += max(25, line_height * 2)
        layout.add(x, current_y-1, width, 1,
                self.draw_download_info_separator)
        # layout line 3
        if dl_info.torrent:
            add_line(current_y, 'ul-speed',
                    displaytext.download_rate(self.info.up_rate),
                    displaytext.size_string(self.info.up_total))
        current_y += max(25, line_height * 2)
        layout.add(x, current_y-1, width, 1,
                self.draw_download_info_separator)
        # layout torrent info
        if dl_info.torrent and dl_info.state != 'paused':
            torrent_info_height = content_rect.bottom - current_y
            self.layout_download_right_torrent(layout, layout_manager,
                    content_rect.bottom_side(torrent_info_height))

    def layout_download_right_torrent(self, layout, layout_manager, rect):
        if self.info.download_info.rate == 0:
            # not started yet, just display the startup activity
            layout_manager.set_text_color(TORRENT_INFO_DATA_COLOR)
            textbox = layout_manager.textbox(
                    self.info.download_info.startup_activity)
            height = textbox.get_size()[1]
            y = rect.bottom - height # bottom-align the textbox.
            layout.add(rect.x, y, rect.width, height,
                    textbox.draw)
            return

        layout_manager.set_font(DOWNLOAD_INFO_TORRENT_DETAILS_FONT_SIZE,
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
            layout_manager.set_text_color(TORRENT_INFO_LABEL_COLOR)
            labelbox = layout_manager.textbox(label)
            layout_manager.set_text_color(TORRENT_INFO_DATA_COLOR)
            databox = layout_manager.textbox(value)
            databox.set_alignment('right')
            layout.add_text_line(labelbox, rect.x, y, rect.width)
            layout.add_text_line(databox, rect.x, y, rect.width)
            y += line_height

    def _make_image_button(self, image_name, hotspot_name):
        if self.hotspot != hotspot_name:
            return self.images[image_name]
        else:
            return self.images[image_name + '-pressed']

    def _add_image_button(self, layout, x, y, image_name, hotspot_name):
        image = self._make_image_button(image_name, hotspot_name)
        return layout.add_image(image, x, y, hotspot=hotspot_name)

    def draw_background(self, context, x, y, width, height):
        if self.selected:
            left = self.images['selected-background-left']
            thumb = self.images['dl-stats-selected-middle']
            middle = self.images['selected-background-middle']
            right = self.images['selected-background-right']
        else:
            left = self.images['background-left']
            thumb = self.images['dl-stats-middle']
            middle = self.images['background-middle']
            right = self.images['background-right']


        # draw left
        left.draw(context, x, y, left.width, height)
        # draw right
        if self.download_mode:
            right_width = RIGHT_WIDTH_DOWNLOAD_MODE
            download_info_x = x + width - right_width
            self.draw_download_info_background(context, download_info_x, y,
                    right_width)
        else:
            right_width = right.width
            right.draw(context, x + width - right_width, y, right_width,
                    height)
        image_end_x = self.image_rect.right
        # draw middle
        middle_end_x = x + width - right_width
        middle_width = middle_end_x - image_end_x
        middle.draw(context, image_end_x, y, middle_width, height)

        # draw thumbnail background
        thumbnail_background_width = image_end_x - (x + left.width)
        thumb.draw(context, x + left.width, y, thumbnail_background_width,
                height)

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
        context.set_color(DOWNLOAD_INFO_SEPARATOR_COLOR,
                DOWNLOAD_INFO_SEPARATOR_ALPHA)
        context.rectangle(x, y, width, height)
        context.fill()

    def draw_thumbnail(self, context, x, y, width, height):
        icon = imagepool.get_surface(self.info.thumbnail, (width, height))
        icon_x = x + (width - icon.width) // 2
        icon_y = y + (height - icon.height) // 2
        # if our thumbnail is far enough to the left, we need to set a clip
        # path to take off the left corners.
        make_clip_path = (icon_x < x + CORNER_RADIUS)
        if make_clip_path:
            # save context since we are setting a clip path
            context.save()
            # make a path with rounded edges on the left side and clip to it.
            radius = CORNER_RADIUS
            context.move_to(x + radius, y)
            context.line_to(x + width, y)
            context.line_to(x + width, y + height)
            context.line_to(x + radius, y + height)
            context.arc(x + radius, y + height - radius, radius, PI/2, PI)
            context.line_to(x, y + radius)
            context.arc(x + radius, y + radius, radius, PI, PI*3/2)
            context.clip()
        # draw the thumbnail
        icon.draw(context, icon_x, icon_y, icon.width, icon.height)
        if make_clip_path:
            # undo the clip path
            context.restore()

    def draw_thumbnail_separator(self, context, x, y, width, height):
        """Draw the separator just to the right of the thumbnail."""
        # width should be 1px, just fill in our entire space with our color
        context.rectangle(x, y, width, height)
        context.set_color(THUMBNAIL_SEPARATOR_COLOR)
        context.fill()

    def draw_expire_background(self, context, x, y, width, height):
        middle_image = self.images['expiring-middle']
        cap_image = self.images['expiring-cap']
        # draw the cap at the left
        cap_image.draw(context, x, y, cap_image.width, cap_image.height,
                fraction=self.expire_background_alpha)
        # repeat the middle to be as long as we need.
        middle_image.draw(context, x + cap_image.width, y,
                width - cap_image.width, middle_image.height,
                fraction=self.expire_background_alpha)

    def draw_progress_bar(self, context, x, y, width, height):
        if self.throbber_mode:
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
        index = throbber_count % 10
        # The middle image is 10px wide, which means that we won't be drawing
        # an entire image if width isn't divisible by 10.  Adjust the right
        # image so that it matches.
        right_index = (index - width) % 10

        surface = widgetutil.ThreeImageSurface()
        surface.set_images(
            self.images['progress-throbber-%d-left' % (index + 1)],
            self.images['progress-throbber-%d-middle' % (index + 1)],
            self.images['progress-throbber-%d-right' % (right_index + 1)])
        surface.draw(context, x, y, width)
        self.signals.emit('throbber-drawn', self.info)

class _ExtraInfoDrawer(object):
    """Layout an draw the line below the item title."""
    def setup(self, info, layout_manager, separator_color):
        self.separator_color = separator_color
        self.textboxes = []
        for attr in (info.display_date, info.display_duration,
                info.display_size, info.file_format):
            if attr:
                self.textboxes.append(layout_manager.textbox(attr))
        self.height = layout_manager.current_font.line_height()

    def reset(self):
        self.textboxes = []

    def draw(self, context, x, y, width, height):
        for textbox in self.textboxes:
            text_width, text_height = textbox.get_size()
            textbox.draw(context, x, y, text_width, text_height)
            # draw separator
            separator_x = round(x + text_width + 4)
            context.set_color(self.separator_color)
            context.rectangle(separator_x, y, 1, height)
            context.fill()
            x += text_width + 8

class _EmblemDrawer(object):
    """Layout and draw emblems

    This is actually a fairly complex task, so the code is split out of
    ItemRenderer to make things more managable
    """

    def __init__(self, renderer):
        self.images = renderer.images
        self.is_podcast = renderer.is_podcast
        self.info = None
        self.hotspot = None
        # HACK: take all the style info from the renderer
        for name in dir(renderer):
            if name.isupper():
                setattr(self, name, getattr(renderer, name))

    def add_to_layout(self, layout, layout_manager, middle_rect, emblem_bottom):
        """Add emblem elements to a Layout()

        :param layout: Layout to add to
        :param layout_manager: LayoutManager to use
        :param middle_rect: middle area of the cell
        """

        x = middle_rect.x
        emblem_top = emblem_bottom  - EMBLEM_HEIGHT
        # make the button that appears to the left of the emblem
        button, button_hotspot = self.make_emblem_button(layout_manager)
        button_width, button_height = button.get_size()
        # make the button middle aligned along the emblem
        button_y = emblem_top - (button_height - EMBLEM_HEIGHT) // 2
        # figure out the text and/or image inside the emblem
        self._calc_emblem_parts()
        # check if we don't have anything to put inside our emblem.  Just draw
        # the button if so
        if self.image is None and self.text is None:
            layout.add_image(button, x, button_y, button_hotspot)
            return layout.last_rect.width
        # add emblem background first, since we want it drawn on the bottom.
        # We won't know the width until we lay out the text/images, so
        # set it to 0
        emblem_rect = layout.add(x + button_width // 2, emblem_top, 0,
                EMBLEM_HEIGHT, self.draw_emblem_background)
        # make a new Layout to vertically center the emblem images/text
        content_layout = cellpack.Layout()
        # Position it in the middle of the button, since we don't want it to
        # spill over on the left side.
        content_x = x + button_width + EMBLEM_TEXT_PAD_START
        content_width = self._add_text_images(content_layout, layout_manager,
                content_x)
        emblem_rect.right = round(content_x + content_width +
                self.visuals.pad_right)
        content_layout.center_y(top=emblem_top, bottom=emblem_bottom)
        layout.merge(content_layout)
        # add button and we're done
        layout.add_image(button, x, button_y, button_hotspot)
        return emblem_rect.right - x

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
                button = layout_manager.button(REVEAL_IN_TEXT,
                        pressed=(self.hotspot=='show_local_file'),
                        style='webby')
                hotspot = 'show_local_file'
        else:
            if self.info.mime_type == 'application/x-bittorrent':
                text = DOWNLOAD_TORRENT_TEXT
            else:
                text = DOWNLOAD_TEXT
            button = layout_manager.button(text,
                    pressed=(self.hotspot=='download'),
                    style='webby')
            button.set_icon(self.images['download-icon'])
            hotspot = 'download'
        return button, hotspot

    def _calc_emblem_parts(self):
        """Calculate UI details for layout_emblem().

        This will set the following attributes, which we can then use to
        render stuff:
            text -- text inside the emblem
            image -- image inside the emblem
            visuals -- text inside the emblem
        """

        self.text = self.image = None

        if self.info.has_drm:
            # FIXME need a new emblem for this
            self.visuals = EMBLEM_VISUALS_DRM
            self.text = _('DRM locked')
        elif (self.info.download_info
                and self.info.download_info.state == 'failed'):
            self.visuals = EMBLEM_VISUALS_FAILED
            self.image = self.images['status-icon-alert']
            self.text = u"%s-%s" % (ERROR_TEXT,
                    self.info.download_info.short_reason_failed)
        elif self.info.pending_auto_dl:
            self.visuals = EMBLEM_VISUALS_QUEUED
            self.text = QUEUED_TEXT
        elif (self.info.downloaded
                and app.playback_manager.is_playing_id(self.info.id)):
            # copy the unplayed-style
            self.visuals = EMBLEM_VISUALS_UNPLAYED
            self.text = CURRENTLY_PLAYING_TEXT
        elif (self.info.downloaded and not self.info.video_watched and
                self.info.is_playable):
            self.visuals = EMBLEM_VISUALS_UNPLAYED
            self.text = UNPLAYED_TEXT
        elif self.should_resume_item():
            self.visuals = EMBLEM_VISUALS_RESUME
            self.text = _("Resume at %(resumetime)s",
                     {"resumetime": displaytext.short_time_string(self.info.resume_time)})
        elif not self.info.item_viewed and self.info.state == "new":
            self.visuals = EMBLEM_VISUALS_NEWLY_AVAILABLE
            self.text = NEWLY_AVAILABLE_TEXT

    def should_resume_item(self):
        if self.is_podcast:
            resume_pref = prefs.RESUME_PODCASTS_MODE
        elif self.info.file_type == u'video':
            resume_pref = prefs.RESUME_VIDEOS_MODE
        else:
            resume_pref = prefs.RESUME_MUSIC_MODE
        return (self.info.is_playable
              and self.info.item_viewed
              and self.info.resume_time > 0
              and app.config.get(resume_pref))

    def _add_text_images(self, emblem_layout, layout_manager, left_x):
        """Add the emblem text and/or image

        :returns: the width used
        """
        x = left_x

        if self.image:
            emblem_layout.add_image(self.image, x, 0)
            x += self.image.width
        if self.text:
            layout_manager.set_font(EMBLEM_FONT_SIZE,
                    bold=self.visuals.text_bold)
            layout_manager.set_text_color(self.visuals.text_color)
            shadow = widgetutil.Shadow(self.visuals.text_shadow,
                    EMBLEM_SHADOW_OPACITY, EMBLEM_SHADOW_OFFSET,
                    EMBLEM_SHADOW_BLUR_RADIUS)
            layout_manager.set_text_shadow(shadow)
            textbox = layout_manager.textbox(self.text)
            text_width, text_height = textbox.get_size()
            emblem_layout.add(x, 0, text_width, text_height, textbox.draw)
            x += text_width
            layout_manager.set_text_shadow(None)
        return x - left_x

    def draw_emblem_background(self, context, x, y, width, height):
        middle_image = self.images[self.visuals.image_name + '-middle']
        cap_image = self.images[self.visuals.image_name + '-cap']
        # repeat the middle to be as long as we need.
        middle_image.draw(context, x, y, width - cap_image.width,
                middle_image.height)
        # draw the cap at the end
        cap_image.draw(context, x + width-cap_image.width, y, cap_image.width,
                cap_image.height)

class PlaylistItemRenderer(ItemRenderer):
    def __init__(self, playlist_sorter):
        ItemRenderer.__init__(self, display_channel=False)
        self.playlist_sorter = playlist_sorter

    def add_remove_button(self, layout, x, y):
        self._add_image_button(layout, x, y, 'remove-playlist', 'remove')

    def add_description_preface(self, textbox):
        order_number = self.playlist_sorter.sort_key(self.info) + 1
        if self.info.description_stripped[0]:
            sort_key_preface = "%s - " % order_number
        else:
            sort_key_preface = str(order_number)
        textbox.append_text(sort_key_preface, color=PLAYLIST_ORDER_COLOR)
        return len(sort_key_preface)

class SharingItemRenderer(ItemRenderer):
    def calc_extra_button(self):
        return DOWNLOAD_TO_MY_MIRO_TEXT, 'download-sharing-item'

class DeviceItemRenderer(ItemRenderer):
    DOWNLOAD_SHARING_ITEM_TEXT = _("Download to My Miro")

    def calc_extra_button(self):
        return DOWNLOAD_TO_MY_MIRO_TEXT, 'download-device-item'
