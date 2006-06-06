var pybridge = Components.classes["@participatoryculture.org/dtv/pybridge;1"].
                getService(Components.interfaces.pcfIDTVPyBridge);

function onload() {
  document.getElementById("runonstartup").checked = pybridge.getRunAtStartup();
  setCheckEvery(pybridge.getCheckEvery());
  setMoviesDir(pybridge.getMoviesDirectory());
  setLimitUpstream(pybridge.getLimitUpstream());
  setMaxUpstream(pybridge.getLimitUpstreamAmount());
  setHasMinDiskSpace(pybridge.getPreserveDiskSpace());
  setMinDiskSpace(pybridge.getPreserveDiskSpaceAmount());
  setExpire(pybridge.getExpireAfter());
}

function runOnStartupChange() {
  if (document.getElementById("runonstartup").checked)
      pybridge.setRunAtStartup(true);
  else
      pybridge.setRunAtStartup(false);
}

function setCheckEvery(minutes) {
  var check = document.getElementById("checkevery");
  if (minutes == 30) check.value = "30";
  else if (minutes == 60) check.value = "60";
  else check.value = "never";
}

function checkEveryChange(minutes) {
   pybridge.setCheckEvery(parseInt(minutes));
}

var originalMoviesDir = null;
function setMoviesDir(directory) {
    var moviesDirBox = document.getElementById('movies-directory');
    moviesDirBox.value = originalMoviesDir = directory;
}

function selectMoviesDirectory() {
    var moviesDirBox = document.getElementById('movies-directory');
    var fp = Components.classes["@mozilla.org/filepicker;1"]
            .createInstance(Components.interfaces.nsIFilePicker);

    fp.init(window, "Select a Directory to store Democracy downloads in",
            Components.interfaces.nsIFilePicker.modeGetFolder);
    var res = fp.show();
    if (res == Components.interfaces.nsIFilePicker.returnOK){
        moviesDirBox.value = pybridge.shortenDirectoryName(fp.file.path);
    }

}

function checkMoviesDirChanged() {
    var moviesDirBox = document.getElementById('movies-directory');
    var currentMoviesDir = moviesDirBox.value;
    if(originalMoviesDir != null && originalMoviesDir != currentMoviesDir) {
        var params = {
              "title": "Migrate existing movies?",
              "text": "You've selected a new folder to download movies to.  Should Democracy migrate your existing downloads there?  (Currently dowloading movies will not be moved until they finish)",
              "out" : null
        }
        window.openDialog('chrome://dtv/content/yesno.xul', 'yesno',
                'chrome,dependent,centerscreen,modal', params);
        pybridge.changeMoviesDirectory(currentMoviesDir, params.out);
    }
}

function setMaxUpstream(max) {
    document.getElementById("maxupstream").value = max;
}

function setLimitUpstream(limit) {
    document.getElementById("limitupstream").checked = limit;
    document.getElementById("maxupstream").disabled = !limit;
}

function limitUpstreamChange() {
  var ret = (document.getElementById("limitupstream").checked);
  var textbox = document.getElementById("maxupstream");
  textbox.disabled = !ret;
  pybridge.setLimitUpstream(ret);
}
function maxUpstreamChange() {
  var textbox = document.getElementById("maxupstream");
  var value = parseInt(textbox.value);
  if ((value == 0) || (isNaN(value))) value = 1;
  textbox.value=value;
  pybridge.setLimitUpstreamAmount(value);
}

function setMinDiskSpace(min) {
    document.getElementById("minspace").value = min;
}
function setHasMinDiskSpace(hasit) {
    document.getElementById("hasminspace").checked = hasit;
    document.getElementById("minspace").disabled = !hasit;
}

function hasMinSpaceChange() {
  var ret = document.getElementById("hasminspace").checked;
  var textbox = document.getElementById("minspace");
  textbox.disabled = !ret;
  pybridge.setPreserveDiskSpace(ret);
}

function minSpaceChange() {
  var textbox = document.getElementById("minspace");
  var value = parseFloat(textbox.value);
  if ((value == 0) || (isNaN(value))) value = 1;
  textbox.value=value;
  pybridge.setPreserveDiskSpaceAmount(value);
}

function setExpire(days) {
  var check = document.getElementById("expiration");
  if (days == "1") check.value = "1";
  else if (days == "3") check.value = "3";
  else if (days == "6") check.value = "6";
  else if (days == "10") check.value = "10";
  else if (days == "30") check.value = "30";
  else check.value = "never";
}
function expirationChange(days) {
   pybridge.setExpireAfter(parseInt(days));
}
