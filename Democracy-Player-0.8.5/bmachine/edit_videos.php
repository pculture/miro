<?php
/**
 * backend list of videos, with links to edit/delete/download
 * @package BroadcastMachine
 */
/*
function mycomp($a, $b) {
  return ($b["Created"] - $a["Created"]);
}*/

function mycomp_title($a, $b) {
  return strcmp($a["Title"], $b["Title"]);
}

require_once("include.php");

if (!is_admin()) {
  header('Location: ' . get_base_url() . 'admin.php');
  exit;
}

$channels = $store->getAllChannels();
$files = $store->getAllFiles();

// this was just a usort and that was breaking the associative array
if ( count($files) > 0 ) {
  if ( isset($_GET["sort"]) && $_GET["sort"] == "name") {
    uasort($files, "mycomp_title");
  }
  else{
    uasort($files, "mycomp");
  }
}

bm_header();

?>

<div class="wrap">

<div class="page_name">
   <h2>Published Files</h2>
</div>

Sort By: <a href="edit_videos.php?sort=name">Name</a> || <a href="edit_videos.php">Create Date</a>

<?php

	//
	// only show the pager if there are enough files to make it worthwhile
	//
	if ( count($files) > 10 ) {

		$params = array(
				'itemData' => $files,
				'perPage' => 10,
				'delta' => 8,             // for 'Jumping'-style a lower number is better
				'append' => true,
				'clearIfVoid' => false,
				'urlVar' => 'entrant',
				'useSessions' => true,
				'closeSession' => true,
				'mode'  => 'sliding',    //try switching modes
				);

		// cjm - this is a hack until we can get away from this upper/lowercase issue
		if ( file_exists("Pager.php") ) {
		  require_once 'Pager.php';
		}
		else {
		  require_once 'pager.php';		
		}

		$pager = & Pager::factory($params);
		$files = $pager->getPageData();
		$links = $pager->getLinks();
		
		$selectBox = $pager->getPerPageSelectBox();
		
		echo "<div id=\"pager\">" . $links['all'] . "</div>\n";
	}
	
	if ( is_array($files) ) {
	  foreach ($files as $filehash => $file) {
?>

<div class="video_display">
<?php

   if (is_local_torrent($file["URL"]) ) {

     //
     // make sure this torrent is running (in case the server has crashed, etc
     //
     $torrentfile = local_filename($file["URL"]);
     $torrenthash = $store->getHashFromTorrent($torrentfile);
     $restarted = !$seeder->confirmSeederRunning($torrenthash, $torrentfile);
     
     displayTorrentInfo($file["URL"], $filehash, "edit_videos.php", "detail", $restarted );
   }

?>

 <div class="video_logo">
 <?php
	if ($file["Image"] != '') {
		print("<img src=\"" . $file["Image"] . "\" width=105/>");
	} 
	else {
		print("<img src=\"t.gif\" width=105/>");
	}
?>
</div>

<div class="video_name"><?php echo $file["Title"]; ?></div>

<div class="video_description">
<?php 
// cjm - strip tags from the description before outputing it (1201560)
echo mb_substr(strip_tags($file["Description"]), 0, 50); 
?>
</div>

<div class="video_info">
<?php

	$runtime = runtime_string($file);
	if ($runtime != "") {
		print($runtime . " - ");
	}

	print("Published " . date("F j, Y",$file["Publishdate"]));
?>

<br />

	ON CHANNELS: 
	
<?php
$file_channels = $store->channelsForFile($filehash);
$titles = array();
foreach ($file_channels as $c) {
	$titles[] = $channels[$c["ID"]]["Name"];
}
print join($titles, ", ");

$username = "NOT_LOGGED_IN";

if (isset($_SESSION['user']['Name'])) {
  $username = $_SESSION['user']['Name'];
}

print "<br>" . theme_file_stats($file["ID"]);

if ( is_admin() || $file["Publisher"] == $username ) {

	print("<br/>");
		if ( is_local_torrent($file["URL"]) ) {
			print "
			<a href=\"download.php?i=" . $filehash  . "&amp;type=torrent\">Torrent File</a> - 
			<a href=\"download.php?i=" . $filehash  . "\">Easy Downloader</a> - 
			";
		}
		else {
			print "
			<a href=\"download.php?i=" . $filehash  . "\">Download</a> - 
			";
		}

	print ("
		<a class=\"action\" href=publish.php?i=" . $filehash  . ">Edit / View Details</a> - 
		<a class=\"action\" href=\"delete.php?i=" . $filehash  . "&t=v\" onClick=\"return confirm('Are you sure you want to delete this video?');\">Delete</a>");

}
?>

</div>
</div>

<div class="spacer">&nbsp;</div>

<?php
	}
}
?>
</div>

<?php
	bm_footer();
?>