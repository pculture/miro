<?php
  $file = "Democracy-Installer.exe";
  header("Content-Type: application/force-download");
  header('Content-Disposition: attachment; filename=' . basename($file));
  include "opml-string.php";
  include "tackon.php";
  $tackon = tackon(getOPML());
  $length = strlen($tackon) + filesize ($file);
  header("Content-Length: $length");
  readfile ($file);
  echo $tackon;
?>
