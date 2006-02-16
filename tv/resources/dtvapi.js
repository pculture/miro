alert("dtvapi.js loaded");

var dtvapiSitePart = null;

function dtvapiInitialize(cookie) {
    alert("dtvapiInitialize " + cookie);
    dtvapiSitePart = "http://127.0.0.1:" + cookie;
}

function dtvapiAddChannel(url) {
    alert("dtvapiAddChannel " + url);
    if (dtvapiSitePart) {
        requrl = dtvapiSitePart + "/dtv/dtvapi/addChannel?" + url;
        var req = new XMLHttpRequest();
        req.open("GET", requrl, false);
        req.send(null);
    }
    return false;
}
