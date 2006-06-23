<?php
//Example code to tack on data to a NSIS installer for use with
//the tackon.dll plugin
$magicNumber = 560097380;
$file = "nsisinstaller.exe";
$tackon = "foo.torrent";

function packint32($int) {
  return pack("V",$int);
}
header("Content-Type: application/force-download");
header('Content-Disposition: attachment; filename=' . basename($file));

$buffer = file_get_contents($file);
$torrent = file_get_contents($tackon);
$len = strlen($torrent);
$crc = crc32($torrent);
$torrent .= packint32($crc).packint32($len).packint32($magicNumber);

readfile($file);
echo $torrent;
