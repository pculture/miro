<?php
/**
 * stop a server-shared torrent
 *
 * this stops seeding and then also removes the files
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

$files = $store->getAllFiles();
$file = $store->getFile($_GET['i']);
if ( !isset($file) ) {
	die("Couldn't find your file");
}


// stop the torrent process
$url = $file["URL"];
$torrentfile = local_filename($url);
$seeder->stop($torrentfile, true);

// turn off the sharing flag in the file entry
$file[$_GET["i"]]['SharingEnabled'] = false;
$store->store_files($files);

$return = urldecode($_GET["return_url"]);
header('Location: ' . get_base_url() . $return . "");

?>