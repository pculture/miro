<?php
/**
 * load and display an RSS feed for the specified channel
 * @package BroadcastMachine
 */

require_once("include.php");

// processing here in case our rewrite rules choke
if ( !isset($_GET["i"]) ) {
  $params = split("/", $_SERVER['REQUEST_URI']);
  $_GET["i"] = $params[count($params) - 1];
  //  $_SERVER["PHP_SELF"] = $_SERVER["SCRIPT_NAME"];
}

$channelID = $_GET["i"];
$forceLoad = isset($_GET["force"]) ? true : false;
$noHeaders = isset($_GET["noheaders"]) ? true : false;

$channels = $store->getAllChannels();
if ( !isset($channels[$channelID]) ) {
  header("HTTP/1.0 404 Not Found");
  exit;
}


$channel = $channels[$channelID];

if ( isset($channel['RequireLogin']) && $channel['RequireLogin'] == 1 ) {
  // fix bug #1229059 Can view passworded feeds without password
  do_http_auth();
}


global $rss_dir;
$rss_file = "$rss_dir/" . $channelID . ".rss";

if ( !file_exists($rss_file) || $forceLoad == true ) {
  makeChannelRss($channelID);
}


if ( $noHeaders == true ) {
  header('Content-Type: application/xml');
}
else {
  header('Content-Type: application/rss+xml; charset=utf-8');
  header('Content-Disposition: inline; filename="' . $channelID . '.rss"');
}

$filedate = gmdate("D, d M Y H:i:s", filemtime($rss_file)) . " GMT";

// see if the file has been modified or not.  if not, this function
// will return a 304 code and exit processing
doConditionalGet($filedate);

// otherwise, return the file
print( file_get_contents($rss_file));

?>