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