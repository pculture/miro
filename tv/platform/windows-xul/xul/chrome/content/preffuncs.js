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

var pybridge = Components.classes["@participatoryculture.org/dtv/pybridge;1"].
                getService(Components.interfaces.pcfIDTVPyBridge);

var originalMoviesDir = null;

function onload() {
  this.document.selectDirectoryWatch = selectDirectoryWatch;
  jsbridge.setPrefDocument(this.document);
  pybridge.startPrefs();
  selectDirectoryWatch(false);
  document.getElementById("runonstartup").checked = pybridge.getRunAtStartup();
  setCloseToTray(pybridge.minimizeToTray());
  document.getElementById('warn-on-quit').checked = pybridge.getWarnIfDownloadingOnQuit();
  setCheckEvery(pybridge.getCheckEvery());
  setMoviesDir(pybridge.getMoviesDirectory());
  originalMoviesDir = pybridge.getMoviesDirectory();
  setLimitUpstream(pybridge.getLimitUpstream());
  setMaxUpstream(pybridge.getLimitUpstreamAmount());
  setMaxManual(pybridge.getMaxManual());
  setHasMinDiskSpace(pybridge.getPreserveDiskSpace());
  setMinDiskSpace(pybridge.getPreserveDiskSpaceAmount());
  setExpire(pybridge.getExpireAfter());
  setResumeVideosMode(pybridge.getResumeVideosMode());
  setSinglePlayMode(pybridge.getSinglePlayMode());
  setBTMinPort(pybridge.getBTMinPort());
  setBTMaxPort(pybridge.getBTMaxPort());
  document.getElementById("bittorrent-use-upnp").checked =
          pybridge.getUseUpnp();
  document.getElementById("bittorrent-encryption-required").checked =
          pybridge.getBitTorrentEncReq();
}

function ondialogaccept() {
  checkMoviesDirChanged();
  checkBTPorts();
  pybridge.updatePrefs()
  jsbridge.setPrefDocument(null);
}

/* Convert a floating point object into a string to show to the user.  We
 * round it to 2 decimal places to get arround binary to decimal conversions.
 */ 
function floatToPrintable(value) {
    value = Math.round(value * 100);
    var intPart = Math.floor(value / 100);
    var decimalPart = value % 100;
    while(decimalPart % 10 == 0) {
        if(decimalPart == 0) return intPart;
        decimalPart /= 10;
    }
    return intPart + "." + decimalPart;
}


function runOnStartupChange() {
  if (document.getElementById("runonstartup").checked)
      pybridge.setRunAtStartup(true);
  else
      pybridge.setRunAtStartup(false);
}

function warnOnQuitChange() {
  if (document.getElementById("warn-on-quit").checked)
      pybridge.setWarnIfDownloadingOnQuit(true);
  else
      pybridge.setWarnIfDownloadingOnQuit(false);
}

function closeToTrayChange() {
  var radio = document.getElementById('close-to-tray-yes');
  pybridge.setMinimizeToTray(radio.selected);
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

function setMoviesDir(directory) {
    var moviesDirBox = document.getElementById('movies-directory');
    moviesDirBox.abspath = directory;
    moviesDirBox.value = pybridge.shortenDirectoryName(directory);
}

function selectMoviesDirectory() {
    var fp = Components.classes["@mozilla.org/filepicker;1"]
            .createInstance(Components.interfaces.nsIFilePicker);

    fp.init(window, "Select a Directory to store downloads",
            Components.interfaces.nsIFilePicker.modeGetFolder);
    var res = fp.show();
    if (res == Components.interfaces.nsIFilePicker.returnOK){
        setMoviesDir(fp.file.path);
    }

}

function addDirectoryWatch() {
    var fp = Components.classes["@mozilla.org/filepicker;1"]
            .createInstance(Components.interfaces.nsIFilePicker);

    fp.init(window, "Select a Directory to monitor",
            Components.interfaces.nsIFilePicker.modeGetFolder);
    var res = fp.show();
    if (res == Components.interfaces.nsIFilePicker.returnOK){
        pybridge.addDirectoryWatch(fp.file.path);
    }
}

function removeDirectoryWatch() {
    var xulListBox = document.getElementById('movies-collection-listbox');
    var selected = xulListBox.selectedItem;
    if (selected) {
      var id = selected.getAttribute('folder_id');
      pybridge.removeDirectoryWatch(id);
    }
}

function toggleDirectoryWatchShown(checkbox) {
    var id = checkbox.getAttribute('folder_id');
    pybridge.printOut(id);
    pybridge.toggleDirectoryWatchShown(id);
    return true;
}

function selectDirectoryWatch(always_false) {
    var xulListBox = document.getElementById('movies-collection-listbox');
    var selected = xulListBox.selectedItem;
    var removeButton = document.getElementById('movies-collection-remove-folder');
    if (selected && !always_false) {
      removeButton.disabled = false;
    } else {
      removeButton.disabled = true;
    }
}

function checkMoviesDirChanged() {
    var moviesDirBox = document.getElementById('movies-directory');
    var currentMoviesDir = moviesDirBox.abspath;
    if(originalMoviesDir != null && originalMoviesDir != currentMoviesDir) {
        var params = { "out" : null }
        window.openDialog('chrome://dtv/content/migrate.xul', 'migrate',
                'chrome,dependent,centerscreen,modal', params);
        pybridge.changeMoviesDirectory(currentMoviesDir, params.out);
    }
}

function setMaxUpstream(max) {
    document.getElementById("maxupstream").value = max;
}

function setLimitUpstream(limit) {
    document.getElementById("limitupstream").checked = limit;
    setMaxUpstreamDisabled(!limit);
}

function setMaxUpstreamDisabled(disabled) {
    var textbox = document.getElementById("maxupstream");
    var description = document.getElementById("maxupstream-description");
    if(disabled) {
        textbox.setAttribute('disabled', true);
        description.setAttribute('disabled', true);
    } else {
        textbox.removeAttribute('disabled');
        description.removeAttribute('disabled');
    }
}

function limitUpstreamChange() {
  var ret = (document.getElementById("limitupstream").checked);
  setMaxUpstreamDisabled(!ret);
  pybridge.setLimitUpstream(ret);
}
function maxUpstreamChange() {
  var textbox = document.getElementById("maxupstream");
  var value = parseInt(textbox.value);
  if ((value == 0) || (isNaN(value))) value = 1;
  textbox.value=value;
  pybridge.setLimitUpstreamAmount(value);
}

function setMaxManual(max) {
    document.getElementById("maxmanual").value = max;
}

function maxManualChange() {
  var textbox = document.getElementById("maxmanual");
  var value = parseInt(textbox.value);
  if ((value == 0) || (isNaN(value))) value = 1;
  textbox.value=value;
  pybridge.setMaxManual(value);
}

function setMinDiskSpace(min) {
    document.getElementById("minspace").value = floatToPrintable(min);
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

function singlePlayModeChange() {
  var radio = document.getElementById('single-play-mode-radio');
  pybridge.setSinglePlayMode(radio.selected);
}

function setCloseToTray(closeToTray) {
  if(closeToTray) {
    var button = document.getElementById('close-to-tray-yes');
  } else {
    var button = document.getElementById('close-to-tray-no');
  }
  document.getElementById('close-to-tray').selectedItem = button;
}

function setSinglePlayMode(value) {
  if(value) {
    var button = document.getElementById('single-play-mode-radio');
  } else {
    var button = document.getElementById('continuous-play-mode-radio');
  }
  document.getElementById('play-mode-radiogroup').selectedItem = button;
}

function resumeVideosModeChange() {
  var checkbox = document.getElementById('resumeVideos');
  pybridge.setResumeVideosMode(checkbox.checked);
}

function setResumeVideosMode(value) {
  var checkbox = document.getElementById('resumeVideos');
  checkbox.checked = value
}

function setBTMinPort(value) {
  document.getElementById('btminport').value = value;
}

function setBTMaxPort(value) {
  document.getElementById('btmaxport').value = value;
}

function btMinPortChange() {
  var value = document.getElementById('btminport').value;
  pybridge.setBTMinPort(value);
}

function btMaxPortChange() {
  var value = document.getElementById('btmaxport').value;
  pybridge.setBTMaxPort(value);
}

function checkBTPorts() {
  if(pybridge.getBTMaxPort() < pybridge.getBTMinPort()) {
    pybridge.setBTMaxPort(pybridge.getBTMinPort());
  }
}

function btUseUpnpChange() {
  var checkbox = document.getElementById('bittorrent-use-upnp');
  pybridge.setUseUpnp(checkbox.checked);
}

function btEncryptionRequiredChange() {
  var checkbox = document.getElementById('bittorrent-encryption-required');
  pybridge.setBitTorrentEncReq(checkbox.checked);
}
