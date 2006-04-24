<?php
/**
 * announce page for bittorrent clients
 *
 * FBT2 - Flippy's BitTorrent Tracker v2 (GPL)
 * flippy `at` ameritech `dot` net
 * @see http://www.torrentz.com/fbt.html
 * @package Broadcast Machine
 */


require_once("include.php");

function er($txt) {
  die('d14:failure reason' . strlen($txt) . ':' . $txt . 'e');
}

if((!isset($_GET['compact'])) || $_GET['compact'] != 1) {
  er('This tracker requires new tracker protocol. Please use our Easy Downloader or check blogtorrent.com for updates.');
}

$info_hash = isset($_GET['info_hash']) ? $_GET['info_hash'] : '';

if(strlen($info_hash) != 20) {
  $info_hash = stripcslashes($info_hash);
}
if(strlen($info_hash) != 20) {
  er('Invalid info_hash');
}

$info_hash = bin2hex($info_hash);

global $store;

$return = $store->BTAnnounce(
			     $info_hash, isset($_GET['event'])?$_GET['event']:'',
			     $_SERVER['REMOTE_ADDR'],
			     isset($_GET['port'])?$_GET['port']:'',
			     isset($_GET['left'])?$_GET['left']:'',
			     isset($_GET['numwant'])?$_GET['numwant']:''
			     );

if (is_null($return)) {
  er($store->error);
} 
else {
  die($return);
}
