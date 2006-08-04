<?php
/**
 * Broadcast Machine theme file
 *
 * An assortment of functions that control display of information in BM.
 * @package BroadcastMachine
 */


/**
 * display a header for the front pages of the site
 */
function front_header($pagename = "", $channelID = "", $stylesheet = "default.css", $feed = "", $onload = "" ) {

	global $settings;
	header("Content-type: text/html; charset=utf-8");

	$site = site_title();	
	if ( $site != "" ) {
		$pagename = "$site: $pagename";
	}

	print '<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
<head>
<title>';

/*	
print("<!DOCTYPE html PUBLIC \"-//W3C//DTD XHTML 1.0 Transitional//EN\" \"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd\">
<html xmlns=\"http://www.w3.org/1999/xhtml\">
<head>
<title>");
*/
	if ($pagename) {
	  print($pagename);
	}

	print("</title>
<meta http-equiv=\"Content-Type\" content=\"text/html;charset=utf-8\" />
<link rel=\"stylesheet\" type=\"text/css\" href=\"" . get_base_url() . "/" . $stylesheet . "\"/>\n");

	if ( $feed != "" ) {
		print "<link rel=\"alternate\" type=\"application/rss+xml\" title=\"RSS 2.0\" href=\"" . get_base_url() . "/$feed\" />";
	}

	print "<base href=\"" . get_base_url() . "\" />\n";
	print("\n</head>\n");

  if ( $onload != "" ) {
    print "<body onload=\"$onload\">";
  }
  else {
    print "<body>";
  }

   print ("
<div id=\"wrap\">
<div id=\"inner_wrap\">
<div id=\"login_links\">");

	if (!(isset($_SESSION['user']) && is_array($_SESSION['user']))) {

		print("<a href=\"login.php?f=1\">Login</a>");
		if ( isset($settings['AllowRegistration']) && $settings['AllowRegistration'] == 1 ) {
			print (" | 
					<a href=\"newuser.php?f=1\">Register</a>");
		}

	} 
	else {

		global $can_use_cookies;
		if ( $can_use_cookies ) {
			print("<a href=\"login.php?f=1&amp;logout=1\">Logout</a> ");
		}
		
		if ( is_admin() ) {
			print("| <a href=\"admin.php\">Admin</a>");		
		}

	}

	if (can_upload()) {

		print(" | <a href=\"publish.php\">Post a File</a>");

	}

	print("</div>
	<div id=\"library_header_wrap\">
	<div id=\"library_title\">" . $pagename . "</div>\n");

	if ( $channelID ) {
		$rsslink = '<a href="rss.php?i=' . $channelID . '"><img src="images/rss_button.gif" alt="rss feed" style="border: 0" /></a>';
		print("<div id=\"rss_feed\">$rsslink</div>\n");
	}

	print("</div>\n\n");

}


/**
 * display a footer for the front pages of the site
 */
function front_footer() {

	print("
<div id=\"footer\">Powered by 
<a href=\"http://www.participatoryculture.org/bm/\">Broadcast Machine</a> for 
<a href=\"http://participatoryculture.org/download.php\">Internet TV</a></div>

</div>
</div>
</body>
</html>");

}



/**
 * display a header for the admin pages of the site
 */
function bm_header($pagename = "") {

	global $settings;

	header("Content-type: text/html; charset=utf-8");

	print <<<EOF
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<title>Broadcast Machine
EOF;

	if ($pagename) {
		print(" - " . $pagename);
	}

	print <<<EOF
</title>
<meta http-equiv="Content-Type" content="text/html;charset=utf-8" />
<link rel="stylesheet" type="text/css" href="pub_css.css"/>
</head>
<body>
<div id="head">
<h1 id="preview">&nbsp;</h1>
</div>
<div id="logged_in">

EOF;

	if (!(isset($_SESSION['user']))) {

		print("<a href=\"login.php\">Sign In</a>");
		if ( allowAddNewUser() ) {
			print(" | <a href=\"newuser.php\">Sign Up</a>");
		}

	} 
  else {

		print("<span style=\"color: #444\"><a href=\"index.php\">View Front Page &gt;&gt;</a> ");
		if ( isset($_SESSION['user']['Name']) ) { 
			print( "| <strong><a href=\"user_edit.php?i=" . $_SESSION['user']['Name']  . "\">" . $_SESSION['user']['Name'] . "</a></strong>");
			global $can_use_cookies;
			
			// if we're using DTV or a cookieless browser, logging out doesn't work
			if ( $can_use_cookies == true ) {
				print " - <a href=\"login.php?logout=1\">logout</a>";
			}
		}
	}

	print("</div>
<div id=\"adminmenu\">
<div id=\"inner_nav\">
<a href=\"admin.php\">Dashboard</a>\n");

	if (can_upload()) {

		print("\n<a href=\"publish.php\">Publish</a>\n<a href=\"edit_videos.php\">Files</a>");

	} else {

		print("<span>Files</span>\n" );

	}

	if (is_admin()) {

		print("<a href=\"channels.php\">Channels</a>
		<a href=\"donations.php\">Donations</a>
		<a href=\"settings.php\">Settings</a>
		<a href=\"users.php\">Users</a>");

	} else {

		print("<span>Channels</span>
			<span>Donations</span>
			<span>Settings</span>
			<span>Users</span>\n");

	}

	print("<a href=\"http://www.participatoryculture.org/bm/help/\" target=\"_blank\"  style=\"color: #B55;\">Help</a>
</div>
</div>");

}




/**
 * display a footer for the front pages of the site
 */
function bm_footer() {

	print("
<div class=\"spacer\">&nbsp;</div>
</body>
</html>");

}



/**
 * display information about a video on the front/main pages of the site
 */
function front_display_video($filehash, $file) {
	display_video($filehash, $file);
}

/**
 * display information about a video
 */
function display_video($filehash, $file) {

	global $channel;

  //
  // if the publish date is in the future, then return right away - don't display it
  //
	if ($file["Publishdate"] >= time()) {
		return;
	}

  print("
<li><div class='video_display'>");

	$url = detail_link($channel["ID"], $filehash);

  if ( isset($channel['Options']['Thumbnail']) && $channel['Options']['Thumbnail'] == 1) {

    print("<div class=\"thumbnail\">
<a href=\"$url\"><img src=\"");
      
    if ($file['Image'] == '' || !$channel['Options']['Thumbnail']) {
      print("t.gif");
    } 
    else {
      print($file['Image']);
    }
    print("\" width=\"180\" style=\"border: 0\" alt=\"" . $file["Title"] . "\" /></a>
</div>\n"); 
  }

  if ( isset($channel['Options']['Title']) && $channel['Options']['Title'] == 1) {

    print("
<div class=\"video_title\">
	<a href=\"$url\">" . $file["Title"] . "</a>
</div>\n");
  }
  if (isset($channel['Options']['Creator']) && $channel['Options']['Creator'] == 1 && $file["Creator"]) {
    print("<div class=\"creator_name\">by " . $file["Creator"] . "</div>\n");
  }
  if ( isset($channel['Options']['Description']) && $channel['Options']['Description'] == 1 && $file["Description"] != "" ) {
    print("<div class=\"video_description\">\n");
    print(mb_substr($file["Description"],0,52) . "...\n</div>\n");
  }

  if ( isset($channel['Options']['Length']) && $channel['Options']['Length'] == 1) {
    print("<div class=\"video_stats\">\n");
    print("<div class=\"published_date\">Posted " . date("F j, Y", $file["Publishdate"]) . "</div>\n");

    if (
      ($file["RuntimeHours"] || $file["RuntimeMinutes"] || $file["RuntimeSeconds"]) &&
        ($file["RuntimeHours"] > 0 || $file["RuntimeMinutes"] > 0 || $file["RuntimeSeconds"] > 0 )
        ) {
      $runtime = "";
      
      if ($file["RuntimeHours"] != "") {	
        $runtime .= $file["RuntimeHours"] . " hr. ";
      }
      
      if ($file["RuntimeMinutes"] != "") {
        $runtime .= $file["RuntimeMinutes"] . " min. ";
      }
    
      if ($file["RuntimeSeconds"] != "") {
        $runtime .= $file["RuntimeSeconds"] . " sec. ";
      }
    
      if ($runtime != "") {
        print("<div class=\"duration\">" . $runtime . "</div>\n");
      }
    }
		print "</div>\n";
  }

  if ( isset($channel['Options']['Filesize']) && $channel['Options']['Filesize'] == 1 ) {
    $size = get_filesize($file["URL"]);
    if ( $size ) {
      $size /= 1024;
      if ( $size < 1024 ) {
        $size = sprintf("%0.0f KB", $size);
      }
      else {
        $size /= 1024;
        $size = sprintf("%0.0f MB", $size);
      }
      
      print "<div class=\"file_size\">Size: " . $size . "</div>\n";
    }
  }

  if ( isset($channel['Options']['URL']) && $channel['Options']['URL'] == 1 && $file["Webpage"] ) {
    print("<div class=\"associated_website\"><a href=\"" . $file["Webpage"] . "\">Related Webpage</a></div>\n");
  }

  if ( isset($channel['Options']['Torrent']) && $channel['Options']['Torrent'] == 1 && is_local_torrent($file["URL"]) ) {
    $return_url = "detail.php?c=" . $channel["ID"] . "&amp;i=" . $filehash ;
    displayTorrentInfo($file["URL"], $filehash, $return_url );
  }

  if ( isset($channel['Options']['Published']) && $channel['Options']['Published'] == 1 ) {

    if ($file["ReleaseYear"] || $file["ReleaseMonth"] || $file["ReleaseDay"]) {

      print "<div class=\"production_details\">\n";     
      print("<div class=\"release_date\">Release Date: ");
      
      if ($file["ReleaseMonth"]) {
        print(date("F", strtotime($file["ReleaseMonth"] + 1 . "/1/1999")));
      }
     
      if ($file["ReleaseDay"]) {
        print(" " . $file["ReleaseDay"]);
      }
     
      if ($file["ReleaseMonth"] || $file["ReleaseDay"]) {
        print(", ");
      }
     
      print($file["ReleaseYear"] . "</div>");

      print "</div>\n";     
    }

  }

  if ( isset($channel['Options']['Keywords']) && $channel['Options']['Keywords'] == 1 && $file["Keywords"] ) {
    print("<div class=\"tags\"><strong>Tags:</strong> ");
    
    $i = 0;
    
    foreach ($file["Keywords"] as $keyword) {
      if ($i > 0) {
        print(", ");
      }
      $i++;
      print($keyword);
    }
  
    print("</div>\n");
  
  }

	$detail_url = detail_link($channel["ID"], $filehash);
  print("<a href=\"$detail_url\">more...</a>\n");

print "</div>";
  // if this is a torrent, provide two links - one to the torrent and one to Easy Downloader
	$url = download_link($channel["ID"], $filehash);
	$ezurl = download_link($channel["ID"], $filehash, true);

  if ( is_local_torrent($file["URL"]) ) {
    print ("<div class=\"dl_links\">
		<a href=\"$url\">Torrent File</a> - 
		<a href=\"$ezurl\">Easy Downloader</a></div>\n");	  
  }

  // otherwise, just a direct link
  else {

		$url = download_link($channel["ID"], $filehash);
	  print ("<div class=\"dl_links\"><a href=\"$url\">download</a></div>\n");
  }

	print "</li>\n";

}

/**
 * display some information about a torrent in the system
 */
function displayTorrentInfo( $url, $filehash, $return_url, $type = "basic", $restarted = false ) {

	global $store;
	global $seeder;
	global $settings;
	global $data_dir;

	$file = $store->getFile($filehash);

	$torrentfile = local_filename($url);
	$torrenthash = $store->getHashFromTorrent($torrentfile);
	$stats = $store->getStat($torrenthash);
	$details = $seeder->getSpawnStatus($torrenthash);

	$pause_url = "pause.php?i=" . $filehash  . "&return_url=" . urlencode($return_url);
	$start_url = "start.php?i=" . $filehash  . "&return_url=" . urlencode($return_url);
	$stop_url = "stop.php?i=" . $filehash  . "&return_url=" . urlencode($return_url);


	if ( ( isset($settings['sharing_enable']) && $settings['sharing_enable'] == 1 ) ) {
		$sharing = true;
	}
	else {
		$sharing = false;
	}
	
//	if ( ! ( isset($settings['sharing_enable']) && $settings['sharing_enable'] == 1 ) ) {
//		$file["SharingEnabled"] = false;
//	}
	//else 
	if ( isset($settings['sharing_enable']) && isset($settings['sharing_auto']) && 
		$settings['sharing_enable'] == 1 && $settings['sharing_auto'] == 1 ) {
		$file["SharingEnabled"] = true;
	}

	print("<div class=\"video_stats\">");

	// always show this basic info
	print "
		<strong>Torrent Status</strong>
		<br />
		SEEDERS: " . $stats["complete"] . "<br />
		DOWNLOADERS: " . $stats["incomplete"] . "<br /><br />";


	if ( $type != "basic" && $sharing == true && $seeder->enabled() ) {
		if ( !isset($file["SharingEnabled"]) || $file["SharingEnabled"] == false ) {
			print "<strong>Server Sharing STOPPED</strong><br />
				<a href=\"$start_url\">Start</a><br />";	
		}	
		else if (
			( isset($details["time left"]) && trim($details["time left"]) == "shutting down" ) ||
				file_exists("$data_dir/" . $torrenthash . ".paused")
				) {
			print "<strong>Server Sharing PAUSED</strong><br />
				<a href=\"$start_url\">Start</a> | <a href=\"$stop_url\">Stop</a><br /><br />";
		}
		else if ( isset($details["Running"]) && $details["Running"] == 1 ) {
	
			$details["percent done"] = trim($details["percent done"]);
	
			if ( $details["percent done"] == "100.0" ) {
				$status = "seeding file";
			}
			else {
				$status = "downloading file to server: " . $details["percent done"] . "%";
			}
		
			$teststr = $details["share rating"];
			$teststr = str_replace(" (", "|", $teststr);
			$teststr = str_replace(" MB up / ", "|", $teststr);
			$teststr = str_replace(" MB down)", "", $teststr);
		
			$bandwidth = explode("|", $teststr);
			if ( isset($bandwidth[1]) && isset($bandwidth[2]) ) {
				$tally = $bandwidth[1] + $bandwidth[2];
			}
			else {
				$tally = "0.0";
			}

			print "
				<strong>Server Sharing ON</strong><br />
				Status: " . $status . "<br />
				<a href=\"$pause_url\">Pause</a> | <a href=\"$stop_url\">Stop</a><br /><br />
				Bandwidth Used: " . $tally . " MB";
		}
		else {
			print "<strong>Server Sharing STOPPED</strong><br />";
			
			if ( $restarted ) {
				print "(Restarting)<br />";
			}
			else {
				print "<a href=\"$start_url\">Start</a><br />";	
			}
		}

	} // if ( not basic display )

	print "</div>";

}

/*
 * Local variables:
 * tab-width: 2
 * c-basic-offset: 2
 * indent-tabs-mode: nil
 * End:
 */

?>