// I Heart Miro - an Firefox extension to gain Amazon afilliate referrals
// Copyright (C) 2007 Participatory Culture Foundation
//
// This program is free software; you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation; either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program; if not, write to the Free Software
// Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA

const ourAffiliate = 'particculturf-20';
const STATE_START = Components.interfaces.nsIWebProgressListener.STATE_START;

function output(aMessage) {
    consoleService = Components.classes["@mozilla.org/consoleservice;1"]
        .getService(Components.interfaces.nsIConsoleService);
    consoleService.logStringMessage("I <3 Miro: " + aMessage);
}

function outputError(e) {
    output('Error: ' + e.name + '\n' + e.message);
}

var iHeartMiroListener =
{
    QueryInterface: function(aIID) {
        if (aIID.equals(Components.interfaces.nsIWebProgressListener) ||
            aIID.equals(Components.interfaces.nsISupportsWeakReference) ||
            aIID.equals(Components.interfaces.nsISupports))
             return this;
        throw Components.results.NS_NOINTERFACE;
    },

    onStateChange: function(progress, request, flag, stat) {
        if (request && (flag & STATE_START)) {
            try {
                return iHeartMiro.onLoad(progress.DOMWindow, request);
            } catch (e) {
                output('Got an error: ' + e.name + '\n' + e.message + '\n' + request.name);
            }
        }
        return 0;
    },

    onLocationChange: function(progress, request, url) {return 0;},
    onProgressChange: function() {return 0;},
    onStatusChange: function() {return 0;},
    onSecurityChange: function() {return 0;},
    onLinkIconAvailable: function() {return 0;}
}

var iHeartMiro = {

    init : function () {
        try {
            var appcontent = window.document.getElementById("appcontent");
            if (appcontent) {
                if (!appcontent.iHeartMiroLoaded) {
                    appcontent.iHeartMiroLoaded = true;
                    var browser = getBrowser();
                    iHeartMiro.addListenerToBrowser(browser);
                    browser.addEventListener("mouseover",
                            iHeartMiro.onMouseOver, false);
                }
            }
        } catch (e) {
            output ('XUL error: ' + e.name + '\n' + e.message);
        }
    },

    uninit : function () {
        var appcontent = window.document.getElementById("appcontent");
        if (appcontent) {
            if (appcontent.iHeartMiroLoaded) {
                iHeartMiro.removeListenerFromBrowser(getBrowser());
                appcontent.iHeartMiroLoaded = false;
            }
        }
    },

    addListenerToBrowser : function (browser) {
        browser.addProgressListener(iHeartMiroListener,
                Components.interfaces.nsIWebProgress.NOTIFY_STATE_DOCUMENT);
    },

    removeListenerFromBrowser : function (browser) {
        browser.removeProgressListener(iHeartMiroListener);
    },

    checkURL: function (url)  {
        var tlds = ['com', 'at', 'fr', 'ca', 'de', 'co.uk', 'co.jp'];
        for (var i = 0; i < tlds.length; i++) {
            re = RegExp("^(http(s)?:[/]{0,2})?(.*[.])?amazon[.]" + tlds[i]);
            if (re.test(url)) {
                return true;
            }
        }
        return false;
    },

    getAffiliateURL : function (url) {
        if (url.indexOf('tag=') != -1) {
            start = url.indexOf('tag=') + 4;
            var end = url.indexOf('&', start);
            if (end == -1) {
                end = url.length;
            }
            return url.slice(start, end);
        } else if (url.indexOf('rcm.amazon') != -1) { // affilate URL with t=
            url = url.replace(/t=/, "tag=");
            return iHeartMiro.getAffiliateURL(url);
        } else if (url.indexOf('path=') != -1) { // sign in/out URL
            url = url.toLowerCase();
            var start = url.indexOf('path=') + 5;
            if (url.indexOf('tag%3d', start) != -1) {
                start = url.indexOf('tag%3d', start) + 6;
                var end = url.indexOf('%26', start);
                if (end == -1) {
                    end = url.indexOf('&', start);
                    if (end == -1) {
                        end = url.length
                    }
                }
                return url.slice(start, end);
            }
        }
        match = url.match(/\/exec\/obidos\/ASIN\/[0-9A-Z]{10}\/([\w-]*)/);
        if (match) {
            return match[1];
        }
       
    },

    rewriteURL : function (url, affiliate) { 
        if (url.indexOf('path=') == -1) { // regular URL
            if (url.indexOf('?') == -1) {
                join = '?';
            } else {
                join = '&';
            }
            return url + join + 'tag=' + affiliate;
        } else { // redirect URL
            var pathStart = url.indexOf('query=') + 6;
            if (pathStart == -1 + 6) {
                url = url + '&query=';
                pathStart = url.length;
            }
            var pathEnd = url.indexOf('&', pathStart);
            if (pathEnd == -1) {
                pathEnd = url.length;
            }
            var query = url.slice(pathStart, pathEnd)
            query = query.replace(/\%3d/gi, '=').replace(/\%26/gi,
                    '&').replace(/\%3f/gi, '?');
            if (query) {
                query = iHeartMiro.rewriteURL('/?' + query,
                        affiliate).slice(2);
            } else {
                // rewrite adds an ?, so strip that off
                query = iHeartMiro.rewriteURL('/', affiliate).slice(2);
            }
            query = query.replace(/\=/gi, '%3D').replace(/\&/gi,
                    '%26').replace(/\?/gi, '%3F');
            return url.slice(0, pathStart) + query + url.slice(pathEnd,
                    url.length);
        }
    },

    onLoad : function (DOMWindow, request) {
        if (!iHeartMiro.checkURL(request.name)) {
            return;
        }
        output('checking load of ' + request.name + '\npreviously: ' + DOMWindow.location.href);
        if (iHeartMiro.checkURL(DOMWindow.location.href)) {
            // don't rewrite if we're coming from Amazon
            return;
        }
        if (!iHeartMiro.getAffiliateURL(request.name) &&
                !iHeartMiro.getAffiliateURL(DOMWindow.location.href)) {
            DOMWindow.location.href = iHeartMiro.rewriteURL(request.name,
                    ourAffiliate);
            output('redirecting ' + request.name);
            return false;
        }
    },

    onMouseOver : function (event) {
        var tag = event.target;
        if (tag.nodeName != "A") {
            return;
        }
        var url = tag.href;
        var parentURL = tag.ownerDocument.location.href;
        if (!url) {
            return;
        }
        if (iHeartMiro.checkURL(url) && !iHeartMiro.checkURL(parentURL)) {
            var affiliate = iHeartMiro.getAffiliateURL(url);
            if (!affiliate) {
                tag.href = iHeartMiro.rewriteURL(url, ourAffiliate);
            }
        }
    }
}

window.addEventListener("load", iHeartMiro.init, true);
window.addEventListener("unload", iHeartMiro.uninit, true);
