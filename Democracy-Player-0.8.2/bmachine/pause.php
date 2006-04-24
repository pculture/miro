<?php
/**
 * pause a server-shared torrent
 * @package Broadcast Machine
 */


require_once("include.php");

// don't allow non-admin to start/stop/pause (bug #1229195 )
if ( ! is_admin() ) {
	header('Location: ' . get_base_url() . 'index.php');
}

if(!isset($_GET["i"]) ) {
	header('Location: ' . get_base_url() . "index.php");
	exit;
}


global $store;
global $seeder;

//$files = $store->getAllFiles();
$file = $store->getFile($_GET['i']);

if ( !isset($file) ) {
	die("Couldn't find your file");
}

// pause the file (stop the process, but don't remove the files)
$url = $file["URL"];
$torrentfile = local_filename($url);
$seeder->pause($torrentfile);

$return = urldecode($_GET["return_url"]);
header('Location: ' . get_base_url() . $return . "");
?>