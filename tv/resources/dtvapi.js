/*
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
*/

var dtvapiSitePart = null;

function dtvapiInitialize(cookie) {
    dtvapiSitePart = "http://127.0.0.1:" + cookie;
}

function dtvapiAddChannel(url) {
    // alert("dtvapiAddChannel " + url);
    dtvapi_doSend("/dtv/dtvapi/addChannel?" + url);
}

function dtvapiGoToChannel(url) {
    // alert("dtvapiGoToChannel " + url);
    dtvapi_doSend("/dtv/dtvapi/goToChannel?" + url);
}

function dtvapi_doSend(request) {
    if (dtvapiSitePart) {
        request = dtvapiSitePart + request;
        // alert("DTVAPI sending " + request);
        /*
          var req = new XMLHttpRequest();
          req.open("GET", request, false);
          req.send(null);
        */

        // We are loaded from the channel guide, so we don't fall
        // under the same-origin exemption and can't XMLHttpRequest to
        // 127.0.0.1. No matter; drive our truck through the large
        // hole in the browser security model.
        elt = document.createElement("script");
        elt.src = request;
        elt.type = "text/javascript";
        document.getElementsByTagName("head")[0].appendChild(elt);
    }
    else {
        dump("DTVAPI: Can't send request (not initialized): " + request);
    }
}
