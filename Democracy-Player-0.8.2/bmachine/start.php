<?php
/**
 * start a server-shared torrent
 *
 * this starts the process of getting the files (if needed) and then
 * becoming a peer/seeder
 * @package Broadcast Machine
 */

require_once("include.php");

// don't allow non-admin to start/stop/pause (bug #1229195 )
if ( ! is_admin() ) {
	header("Location: " . get_base_url() . "index.php");
	exit;
}

if(!isset($_GET["i"]) ) {
	header('Location: ' . get_base_url() . "index.php");
	exit;
}

global $store;
global $seeder;

$file = $store->getFile($_GET['i']);
if ( !isset($file) ) {
	die("Couldn't find your file");
}


// start the process
$url = $file["URL"];
$torrentfile = local_filename($url);
$seeder->spawn($torrentfile);

// pause here for a bit just to make sure the seeder is running before we
// return to the video list
sleep(5);

// update the file entry
$file['SharingEnabled'] = true;
$store->store_file($file, $_GET["i"]);

$return = urldecode($_GET["return_url"]);
header('Location: ' . get_base_url() . $return . "");

?>