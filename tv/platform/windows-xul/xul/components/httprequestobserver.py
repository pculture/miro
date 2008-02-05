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

import logging
from xpcom import components
import locale

nsIObserver = components.interfaces.nsIObserver
nsIHttpChannel = components.interfaces.nsIHttpChannel

class HTTPRequestObserver:
    _com_interfaces_ = [ nsIObserver ]
    _reg_clsid_ = "{59a204b1-7304-45bc-807f-4d108249770f}"
    _reg_contractid_ = "@participatoryculture.org/dtv/httprequestobserver;1"
    _reg_desc_ = "Democracy HTTP Request Observer"

    def observe(self, subject, topic, data):
        if topic == "http-on-modify-request":
              channel = subject.queryInterface(nsIHttpChannel)
              currentLanguages = channel.getRequestHeader('Accept-Language')
              language = locale.getdefaultlocale()[0].replace('_', '-')
              channel.setRequestHeader("Accept-Language", language, False)
              channel.setRequestHeader("Accept-Lanugage", currentLanguages, True)
              channel.setRequestHeader("X-Miro", "1", False);
