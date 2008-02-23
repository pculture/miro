/*
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
*/

var pybridge = makeService("@participatoryculture.org/dtv/pybridge;1",Components.interfaces.pcfIDTVPyBridge, false);

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
  setAutoDownloadDefault(pybridge.getAutoDownloadDefault());
  setMoviesDir(pybridge.getMoviesDirectory());
  originalMoviesDir = pybridge.getMoviesDirectory();
  setMaxManual(pybridge.getMaxManual());
  setMaxAuto(pybridge.getMaxAuto());
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
  document.getElementById("bittorrent-enable-uploadratio").checked =
          pybridge.getBitTorrentLimitUploadRatio();
  document.getElementById("bittorrent-uploadratio").value =
          pybridge.getBitTorrentUploadRatio();
  document.getElementById("bittorrent-uploadratio").disabled = 
          !pybridge.getBitTorrentLimitUploadRatio();

  setupBandwidthLimiter('upstream',
          function() { return pybridge.getLimitUpstream(); },
          function(value) { pybridge.setLimitUpstream(value); },
          function() { return pybridge.getLimitUpstreamAmount(); },
          function(value) { pybridge.setLimitUpstreamAmount(value); })
  setupBandwidthLimiter('downstream',
          function() { return pybridge.getLimitDownstream(); },
          function(value) { pybridge.setLimitDownstream(value); },
          function() { return pybridge.getLimitDownstreamAmount(); },
          function(value) { pybridge.setLimitDownstreamAmount(value); })
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

function setAutoDownloadDefault(value) {
  var autodefault = document.getElementById("autodownloaddefault");
  autodefault.value = value; 
}

function changeAutoDownloadDefault(value) {
  pybridge.setAutoDownloadDefault(value);
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

function setupBandwidthLimiter(domIDBase, 
        pybridgeGetEnabled, pybridgeSetEnabled,
        pybridgeGetAmount, pybridgeSetAmount)
{
    var checkbox = document.getElementById("limit" + domIDBase);
    var textbox = document.getElementById("max" + domIDBase);
    var description = document.getElementById("max" + domIDBase + "-description");

    function setWidgetDisabled(disabled) {
        if(disabled) {
            textbox.setAttribute('disabled', true);
            description.setAttribute('disabled', true);
        } else {
            textbox.removeAttribute('disabled');
            description.removeAttribute('disabled');
        }
    }

    var enabled = pybridgeGetEnabled();
    checkbox.checked = enabled;
    setWidgetDisabled(!enabled);

    textbox.value = pybridgeGetAmount();

    function onCheckboxChanged() {
        setWidgetDisabled(!checkbox.checked);
        pybridgeSetEnabled(checkbox.checked);
    }
    checkbox.addEventListener('command', onCheckboxChanged, true);

    function onTextboxChanged() {
        var value = parseInt(textbox.value);
        if ((value == 0) || (isNaN(value))) value = 1;
        textbox.value = value;
        pybridgeSetAmount(value);
    }
    textbox.addEventListener('change', onTextboxChanged, true);
}

function setMaxManual(max) {
    document.getElementById("maxmanual").value = max;
}

function setMaxAuto(max) {
    document.getElementById("maxauto").value = max;
}

function maxManualChange() {
  var textbox = document.getElementById("maxmanual");
  var value = parseInt(textbox.value);
  if ((value == 0) || (isNaN(value))) value = 1;
  textbox.value=value;
  pybridge.setMaxManual(value);
}

function maxAutoChange() {
  var textbox = document.getElementById("maxauto");
  var value = parseInt(textbox.value);
  if ((value == 0) || (isNaN(value))) value = 1;
  textbox.value=value;
  pybridge.setMaxAuto(value);
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

function btToggleUploadRatio() {
  var checkbox = document.getElementById('bittorrent-enable-uploadratio');
  var uploadratio = document.getElementById('bittorrent-uploadratio');
  uploadratio.disabled = !checkbox.checked;
  pybridge.setBitTorrentLimitUploadRatio(checkbox.checked);
}

function btChangeUploadRatio() {
  var uploadratio = document.getElementById('bittorrent-uploadratio');
  var value = parseFloat(uploadratio.value);
  if (isNaN(value)) {
    value = 1.5;
  } else if (value < 0.1) {
    value = 0.1;
  } else if (value > 100.0) {
    value = 100.0;
  }
  uploadratio.value = value;
  pybridge.setBitTorrentUploadRatio(uploadratio.value);
}
