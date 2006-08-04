<?php

/**
 * display a page on how to subscribe to this channel in democracy
 * @package BroadcastMachine
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
// get_base_url() . 

			header("Location: " . $channel['LibraryURL']);
			exit;
	}
} 
else {
  header('Location: ' . get_base_url() . 'index.php');
  exit;
}

front_header($channel["Name"], $channelID, $channel["CSSURL"]);
?>

<!--CHANNEL-->
<div class="channel">
	
	<!--HEADER-->
	<div class="channel-avatar"><img src="<?php echo $icon; ?>" alt="" /></div>
	<h1><?php echo $channel["Name"]; ?></h1>
		
<p><strong>How to subscribe to this channel in Democracy Player</strong></p>

<p>
&nbsp;
<br />
1. Copy this link into your clipboard: <?php print rss_link($channelID); ?>
</p>
<p>
2. Open Democracy Player and click the 'add channel' button on the bottom left side of the window. Paste in the URL (press control-v) and then click OK.
</p>
<p>
&nbsp;
<br />
<strong>Don't have Democracy Player?</strong><br />Democracy Player is a desktop application for watching internet TV channels. It's free and 
open-source.  Download it here: <a style="color: white;" href="http://www.getdemocracy.com">Download Democracy Player</a>. 
</p>

</div>
<?php
front_footer();
/*
 * Local variables:
 * tab-width: 2
 * c-basic-offset: 2
 * indent-tabs-mode: nil
 * End:
 */

?>
