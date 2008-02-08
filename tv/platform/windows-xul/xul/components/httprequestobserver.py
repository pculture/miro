# Miro - an RSS based video player application
# Copyright (C) 2005-2008 Participatory Culture Foundation
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
