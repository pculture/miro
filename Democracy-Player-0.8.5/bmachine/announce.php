<?php
/**
 * announce page for bittorrent clients
 *
 * FBT2 - Flippy's BitTorrent Tracker v2 (GPL)
 * flippy `at` ameritech `dot` net
 * @see http://www.torrentz.com/fbt.html
 * @package BroadcastMachine
 */

require_once("include.php");

/**
 * die and send an error message back to the bittorrent client
 */
function er($txt) {
  die('d14:failure reason' . strlen($txt) . ':' . $txt . 'e');
}

if((!isset($_GET['compact'])) || $_GET['compact'] != 1) {
  er('This tracker requires new tracker protocol. Please use our Easy Downloader or check blogtorrent.com for updates.');
}

$info_hash = isset($_GET['info_hash']) ? $_GET['info_hash'] : '';

if(strlen($info_hash) != 20) {
  $info_hash = stripcslashes($info_hash);

  if(strlen($info_hash) != 20) {
    er('Invalid info_hash');
  }
}
$info_hash = bin2hex($info_hash);

$ip_address = $_SERVER['REMOTE_ADDR'];
/*
if ( isset($_GET["ip"]) && $_GET["ip"] != "" ) {

  // make sure the incoming IP is valid
  $num = "(25[0-5]|2[0-4]\d|[01]?\d\d|\d)";
  if ( preg_match("/^$num\\.$num\\.$num\\.$num$/", $_GET["ip"],$match ) ) {
    $ip_address = $_GET["ip"];
    debug_message("using specified IP address $ip_address");
  }
}*/

global $store;


$return = $store->BTAnnounce(
			     $info_hash,                                     // hash of torrent
			     isset($_GET['event']) ? $_GET['event'] : '',    // event being announced
			     $ip_address,                                    // IP of remote client
			     isset($_GET['port']) ? $_GET['port'] : '',      // port remote client is using
			     isset($_GET['left']) ? $_GET['left'] : '',      // amount left in download (if 0, this is a seeder)
			     isset($_GET['numwant']) ? $_GET['numwant'] : '' // number of client IPs requested
			     );

if (is_null($return)) {
  er($store->error);
} 
else {
  die($return);
}
