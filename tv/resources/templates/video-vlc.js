<script type="text/javascript">
<!-- // Protect from our XML parser, which doesn't know to protect <script>
function getServerPort() {
  var port = document.location.port;
  return port;
}
// Returns a "blessed" version of an event URL for use with DTV
function blessEventURL(url) {
  var blessedURL = "http://127.0.0.1:" + getServerPort() + "/dtv/action/" + getEventCookie() + "?" + url;
  return blessedURL;
}

var videoLastTimeout = 0;

function updateVideoControls() {
  eventURL('action:updateVideoControls?elapsed='+document.video1.get_time()+'&len='+document.video1.get_length());
}

function videoOnLoad() {
  beginUpdates();
  setInterval(updateVideoControls, 500);
  eventURL('action:enableVideoControls');
}

function videoOnUnload() {
  eventURL('action:disableVideoControls');
}

function videoSetVolume(level) {
  dump("\n\nSetting volume to "+level+"\n\n");
  document.video1.set_volume(level*200);
}
function videoPlay(url) {
  //eventURL('action:videoEnablePauseButton')
  // FIXME: race condition
  if(typeof this.lastURL == 'undefined')
          this.lastURL = '';
  if(this.lastURL != url) {
    dump('\n\nplaying new\n\n');
    document.video1.stop();
    document.video1.clear_playlist();
    document.video1.add_item(url);
    document.video1.add_item(blessEventURL('action:videoNext'));
    this.lastURL = url;
    document.video1.play();
  } else {
    dump('\n\nplaying again\n\n');
    document.video1.play();
  }
}
function videoSetPos(pos) {
  pos = parseFloat(pos);
  var posInSecs = Math.floor(document.video1.get_length()*pos);
  dump('\n\nMoving to position '+pos+' ('+posInSecs+')\n\n');
  document.video1.seek(posInSecs, false);
}
function videoPause() {
  eventURL('action:videoDisablePauseButton')
  dump("\n\npausing\n\n");
  document.video1.pause();
}
function videoStop() {
  dump("\n\nstopping\n\n");
  document.video1.stop();
}
function videoReset() {
  dump("\n\nreseting\n\n");
  document.video1.seek(0,0);
}
function videoFullscreen() {
  dump("\n\nfsing\n\n");
  document.video1.fullscreen();
}
function videoSetRate(rate) {
  dump("\n\nSetting rate to "+rate+"\n\n");
  if (rate == 1.0) {
    clearInterval(videoLastTimeout);
  } else {
    //FIXME Add support for rates where -1<rate<1
    if (rate > 1.0) {
      var delay = parseInt(1000*(1/(rate-1)));
      dump("\n\nSetting timeout to "+delay+"ms\n\n");
      videoLastTimeout = setInterval(function (){document.video1.seek(1,true);}, delay);
    } else {
      if (rate < -1.0) {
        var delay = parseInt(1000*(1/(1-rate)));
        dump("\n\nSetting timeout to "+delay+"ms\n\n");
        videoLastTimeout = setInterval(function (){document.video1.seek(-1,true);}, delay);
      }
    }
  }
}
-->
</script>
