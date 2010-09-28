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

"""Controller for Devices tab.
"""

from miro import displaytext

from miro.frontends.widgets import imagepool
from miro.frontends.widgets import itemlistwidgets
from miro.frontends.widgets import widgetutil

from miro.plat import resources
from miro.plat.frontends.widgets import widgetset

class DeviceTitlebar(itemlistwidgets.ItemListTitlebar):
    def _build_titlebar_extra(self):
        pass

class SizeWidget(widgetset.HBox):
    def __init__(self, size=None, remaining=None):
        widgetset.HBox.__init__(self)
        self.progress = widgetset.ProgressBar()
        self.progress.set_size_request(500, -1)
        self.text = widgetset.Label()
        self.pack_start(self.progress, padding=20)
        self.pack_start(self.text)
        self.set_size(size, remaining)

    def set_size(self, size, remaining):
        self.size = size
        self.remaining = remaining
        if size and remaining:
            self.progress.set_progress(1 - float(remaining) / size)
            self.text.set_text('%s free' % displaytext.size_string(
                    remaining))
        else:
            self.progress.set_progress(0)
            self.text.set_text('not mounted')

class DeviceMountedView(widgetset.VBox):
    def __init__(self):
        widgetset.VBox.__init__(self)
        label = widgetset.Label("To copy media onto the device, drag it onto \
the sidebar.")
        label.set_size(1.5)
        self.pack_start(widgetutil.align_center(label, top_pad=50))
        self.device_size = SizeWidget()
        alignment = widgetset.Alignment(0.5, 1, 0, 0, bottom_pad=15,
                                        right_pad=20)
        alignment.add(self.device_size)
        self.pack_end(alignment)

    def set_device(self, device):
        self.device_size.set_size(device.size, device.remaining)

class DeviceUnmountedView(widgetset.VBox):
    def __init__(self):
        widgetset.VBox.__init__(self)
        label = widgetset.Label()
        label.set_text('This phone is not yet mounted.')
        label.set_bold(True)
        label.set_size(1.5)
        self.pack_start(widgetutil.align_center(label, left_pad=20, top_pad=50,
                                              bottom_pad=20))
        self.device_text = widgetset.Label()
        self.device_text.set_size(1.5)
        self.device_text.set_wrap(True)
        self.pack_start(widgetutil.align_center(self.device_text, left_pad=20))


    def set_device(self, device):
        self.device_text.set_text(device.mount_instructions.replace('\n',
                                                                    '\n\n'))


class DeviceWidget(widgetset.VBox):
    def __init__(self, device):
        widgetset.VBox.__init__(self)
        self.titlebar_vbox = widgetset.VBox()
        self.titlebar_vbox.pack_start(self.make_titlebar(device))
        self.device_view = widgetset.Background()
        self.pack_start(self.titlebar_vbox)
        self.pack_start(self.device_view, expand=True)
        self.mounted_view = DeviceMountedView()
        self.unmounted_view = DeviceUnmountedView()
        self.set_device(device)


    def set_device(self, device):
        if device.mount:
            self.mounted_view.set_device(device)
            self.device_view.set_child(self.mounted_view)
        else:
            self.unmounted_view.set_device(device)
            self.device_view.set_child(self.unmounted_view)

    @staticmethod
    def make_titlebar(device):
        image_path = resources.path("images/phone-large.png")
        icon = imagepool.get(image_path)
        return DeviceTitlebar(device.name, icon)


class DeviceController(object):
    def __init__(self, device):
        self.widget = DeviceWidget(device)

    def handle_device_changed(self, device):
        self.widget.set_device(device)
