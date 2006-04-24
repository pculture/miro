<?php

/**
 * channel display page
 *
 * this page handles the frontend display of the files within a channel
 * @package Broadcast Machine
 */

require_once("include.php");

$channels = $store->getAllChannels();
$files = $store->getAllFiles();

// processing here in case our rewrite rules choke
if ( !isset($_GET["i"]) ) {
	$params = split("/", $_SERVER['REQUEST_URI']);
	if ( count($params) == 4 ) {
		$_GET["i"] = $params[3];
	}
}

//
// don't show anything here if we don't have a channel to display
//
if (isset($_GET['i'])) {
  $channel = $channels[$_GET['i']];
  $channelID = $_GET['i'];

  // check and see if this channel requires the user to login before displaying anything
  if ( isset($channel['RequireLogin']) && $channel['RequireLogin'] == true ) {
    requireUserAccess(true);
  }

	// if the user has an external LibraryURL, send them to that page here
	if ( isset($channel['LibraryURL']) && 
		! strstr($channel['LibraryURL'], "library.php?i=" . $channelID) ) {
			header("Location: " . $channel['LibraryURL']);
			exit;
	}
} 
else {
  header('Location: ' . get_base_url() . 'index.php');
  exit;
}

$keyword = NULL;

if ( isset($_GET["kw"]) ) {
  $keyword = $_GET["kw"];
}

render_channel_page($channel, $files, $keyword);

/*
 * Local variables:
 * tab-width: 2
 * c-basic-offset: 2
 * indent-tabs-mode: nil
 * End:
 */

?>