<?php
/**
 * Broadcast Machine theme file
 *
 * An assortment of functions that control display of information in BM.
 * @package Broadcast Machine
 */

if ( ! function_exists("theme_page_wrapper") ) {
	function theme_page_wrapper($content) {
		if ( is_array($content) ) {
			foreach($content as $c) {
				print $c;
			}
		}
		else {
			print $content;
		}
	}
}


if ( ! function_exists("theme_index_wrapper") ) {
	function theme_index_wrapper($content) {
		return $content;
	}
}
if ( ! function_exists("theme_channel_wrapper") ) {
	function theme_channel_wrapper($content) {
		return $content;
	}
}
if ( ! function_exists("theme_detail_wrapper") ) {
	function theme_detail_wrapper($content) {
		return "<!--CHANNEL-->
		<div class=\"channel\">
			$content
		</div>
		<!--/CHANNEL-->";
	}
}

if ( ! function_exists("theme_detail_video_wrapper") ) {
	function theme_detail_video_wrapper($channel, $file, $content) {
		return $content;
	}
}

function theme_channel_footer($channel) {
	$link = channel_link($channel["ID"]);
  $count = count($channel["Files"]);

  $out = "
 				<div class=\"box\">
  					<div class=\"box-bi\">
   						<div class=\"box-bt\"><div></div></div>
					<p><a href=\"$link\">Full Channel ($count)  >></a></p>
					<div class=\"box-bb\"><div></div></div>
				</div>
			</div>
  ";

	$out = '
	<div class="box">
		<div class="box-bi">
			<div class="box-bt"><div></div></div>
			
			<p><a href="' . $link . '">&lt;&lt; All Files in This Channel</a></p>
	
			<div class="box-bb"><div></div></div>
		</div>
	</div>';
	
	return $out;
}
		
/**
 * display a header for the front pages of the site
 */
if ( ! function_exists("front_header") ) {
	function front_header($pagename = "", $channelID = "", $stylesheet = "default.css", $feed = "", $onload = "" ) {
		$theme = active_theme();
		if ( $theme != NULL && file_exists(  theme_path() . "/header.php" ) ) {
			include theme_path() . "/header.php";
		}
		else {
			include "header.php";
		}
	}		
}	
/**
 * display a footer for the front pages of the site
 */
if ( ! function_exists("front_footer") ) {
	function front_footer() {
		$theme = active_theme();
		if ( $theme != NULL && file_exists(  theme_path() . "/footer.php" ) ) {
			include theme_path() . "/footer.php";
		}
		else {
			include "footer.php";
		}
	}
}

/**
 * display some information about a torrent in the system
 */
if ( ! function_exists("displayTorrentInfo") ) {
	function displayTorrentInfo( $url, $filehash, $return_url, $type = "basic", $restarted = false ) {
		print theme_torrent_info($url, $filehash, $return_url, $type, $restarted);
	}
}

if ( ! function_exists("theme_file_stats") ) {
  function theme_file_stats($id) {
    global $store;
    $stats = $store->layer->getOne("stats", $id);
    if ( !isset($stats["downloads"]) ) {
      $stats["downloads"] = 0;
    }
    return "Downloads: " . $stats["downloads"];
  }
}

/**
 * display a header for the admin pages of the site
 */
if ( ! function_exists("bm_header") ) {
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
}



/**
 * display a footer for the front pages of the site
 */
if ( ! function_exists("bm_footer") ) {
	function bm_footer() {
	
		print("
	<div class=\"spacer\">&nbsp;</div>
	</body>
	</html>");
	
	}
}

/**
 * display information about a video
 */
if ( ! function_exists("theme_display_video") ) {
	function theme_display_video($filehash, $file, $channel, $show_internal_view = true) {
	
		if ( $show_internal_view == true ) {
			return theme_display_internal_video($filehash, $file);
		}
		else {
			return theme_display_frontpage_video($channel, $filehash, $file);	
		}
	}
}


function theme_video_thumb_section($file, $channel) {
	$url = detail_link($channel["ID"], $file["ID"]);

	$out = "";	
	if ( isset($channel['Options']['Thumbnail']) && $channel['Options']['Thumbnail'] == 1) {
		$out .= "<div class=\"video-tnail\">
			<a href=\"$url\">" . theme_file_thumbnail($file, $channel) . "</a>
			</div>\n"; 
	}
	return $out;
}

function theme_file_description($file, $full = false) {
	if ( $full == true ) {
		return "<p>" . $file["Description"] . "</p>\n";	
	}
	else {
		return "<p>" . mb_substr($file["Description"], 0, 250) . "...</p>\n";
	}
}

function theme_file_keywords($file, $channel) {

	$out = "";

	if ( isset($channel['Options']['Keywords']) && $channel['Options']['Keywords'] == 1 && $file["Keywords"] ) {
		$out .= "<p><a class=\"link-tags\">Tags:</a>&nbsp;";
		
		$i = 0;

		foreach ($file["Keywords"] as $keyword) {
			if ($i > 0) {
				$out .= ", ";
			}
			$i++;
			if ( is_array($keyword) ) {
				$keyword = $keyword[0];
			}
			$out .= "<a href=\"library.php?i=" . $channel["ID"] . "&amp;kw=" . urlencode($keyword) . "\">" . $keyword . "</a>";
		}  
		$out .= "</p>";
	}
	 

	return $out;
}

function theme_pretty_filesize($tmpurl) {
	$size = get_filesize($tmpurl);
	if ( $size ) {
		$size /= 1024;
		if ( $size < 1024 ) {
			$size = sprintf("%0.0f KB", $size);
		}
		else {
			$size /= 1024;
			$size = sprintf("%0.0f MB", $size);
		}
	}
	else {
		$size = "???";
	}
	return $size;
}


function theme_file_size($file, $channel) {
	$out = "";
	if ( isset($channel['Options']['Filesize']) && $channel['Options']['Filesize'] == 1 ) {
		$size = theme_pretty_filesize($file["URL"]);
		$out = "<a class=\"link-info\">Size: " . $size . "</a>";
	}
	return $out;
}

function theme_runtime($file, $channel) {
	$out = "";
	$runtime = runtime_string($file);
	if ($runtime != "") {
		$out = "<a class=\"link-duration\">" . $runtime . "</a>";
	}
	return $out;
}

function theme_post_date($file, $channel) {
	$out = "";
	if ( isset($channel['Options']['Length']) && $channel['Options']['Length'] == 1) {
		$out = "<a class=\"link-date\">Posted " . date("F j, Y", $file["Publishdate"]) . "</a>";
	}
	return $out;
}

function theme_video_info_section_wrapper($content) {
	$out = "<div class=\"video-info\">$content</div>";
	return $out;
}

function theme_torrent_display($file, $channel) {
	$out = "";
	if ( isset($channel['Options']['Torrent']) && $channel['Options']['Torrent'] == 1 && is_local_torrent($file["URL"]) ) {
		$return_url = "detail.php?c=" . $channel["ID"] . "&amp;i=" . $file["ID"];
		$out .= theme_torrent_info($file["URL"], $file["ID"], $return_url );
	}
	return $out;
}

function theme_download_links($channel, $file) {

	$channelID = $channel["ID"];
	$filehash = $file["ID"];

	$out = array();

	// if this is a torrent, provide two links - one to the torrent and one to Easy Downloader
	$url = download_link($channel["ID"], $filehash);

	if ( is_local_torrent($file["URL"]) ) {
		$ezurl = download_link($channel["ID"], $filehash, true);
		$out[] = theme_torrent_display($file, $channel);
		$out[] = "<a href=\"$url\" class=\"link-download\">Torrent File</a>";
		$out[] = "<a href=\"$ezurl\" class=\"link-download\">Easy Downloader</a>";
	}

	// otherwise, just a direct link
	else {	
		$out[] = "<a href=\"$url\" class=\"link-download\">Direct Download</a>";
	}
	return $out;
}

function theme_video_info_section($file, $channel) {
	$filehash = $file["ID"];
	$url = detail_link($channel["ID"], $filehash);

	$out = "";

	if ( isset($channel['Options']['Title']) && $channel['Options']['Title'] == 1) {
		$out .= "<h1><a href=\"$url\">" . encode($file["Title"]) . "</a></h1>\n";
	}

	if ( isset($channel['Options']['Published']) && $channel['Options']['Published'] == 1 ) {
		
		$out .= "<h2>";

		if ($file["ReleaseYear"] || $file["ReleaseMonth"] || $file["ReleaseDay"]) {
			$out .=  file_release_date($file);
		}
	
		if (isset($channel['Options']['Creator']) && $channel['Options']['Creator'] == 1 && $file["Creator"]) {
			$out .= "by <strong>" . $file["Creator"] . "</strong>\n";
		}
		
		$out .= "</h2>";

	}
	
	
	if ( isset($channel['Options']['Description']) && $channel['Options']['Description'] == 1 && $file["Description"] != "" ) {
		$out .= "<p>" . theme_file_description($file) . "</p>\n";
	}
	$out .= theme_file_keywords($file, $channel);

	$out .= "<ul>";
	$out .= "<li>" . theme_file_size($file, $channel) . "</li>\n";
	$out .= "<li>" . theme_runtime($file, $channel) . "</li>\n";
	$out .= "<li>" . theme_post_date($file, $channel) . "</li>\n";
	$out .= "</ul>";

	$out .= "<h3>Download</h3>";
	
	$out .= "<ul>";
	$links = theme_download_links($channel, $file);
	foreach( $links as $l ) {
		$out .= "<li>$l</li>\n";
	}
	$out .= "</ul>\n";

	return theme_video_info_section_wrapper($out);
}

if ( ! function_exists("theme_display_internal_video") ) {
	function theme_display_internal_video($filehash, $file) {
	
		global $channel;
	
		//
		// if the publish date is in the future, then return right away - don't display it
		//
		if ($file["Publishdate"] >= time()) {
			return;
		}
			
		$out = "
					<!--VIDEO-->
					<div class=\"video\">" .
					theme_video_thumb_section($file, $channel) .
					theme_video_info_section($file, $channel) .
					"</div>
					<!--/VIDEO-->\n";	

		return $out;
	}	
}

if ( ! function_exists("theme_display_frontpage_video") ) {
	function theme_display_frontpage_video($channel, $filehash, $file) {
			//
		// if the publish date is in the future, then return right away - don't display it
		//
		if ($file["Publishdate"] >= time()) {
			return;
		}
	
		$out = "
					<!--VIDEO-->
					<div class=\"video-home\">";
				
		$url = detail_link($channel["ID"], $filehash);

		if ( isset($channel['Options']['Thumbnail']) && $channel['Options']['Thumbnail'] == 1) {
					
			$out .= "
				<div class=\"video-home-tnail\"><a href=\"$url\">" . 
				theme_file_thumbnail($file, $channel ) . "</a></div>";
		}
					
		if ( isset($channel['Options']['Title']) && $channel['Options']['Title'] == 1) {
		
				$out .= "
			<div class=\"video-home-info\">
				<h1><a href=\"$url\">" . encode($file["Title"]) . "</a></h1>
			</div>\n";
		}			 
				
		$out .= "
		</div>
		<!--/VIDEO-->\n";
		
		return $out;
	}
}

if ( ! function_exists("theme_detail_page") ) {
	function theme_detail_page($file, $channel) {

		$out = '<!--VIDEO-->
		<div class="video">';

    if ( !is_local_torrent($file['URL']) && beginsWith($file["Mimetype"], "video/") ) {
      $out .= '
   		<div class="video-tnail">' . theme_embed_video($file, $channel) . '</div>
      ';
    }
    else {
      $out .= '
   		<div class="video-tnail">' . theme_file_thumbnail($file, $channel) . '</div>
      ';
    }

    $out .= '
		<div class="video-info">';
		
		if ( isset($file['Title']) && $file['Title'] != "") {
			$out .= "<h1>" . $file["Title"] . "</h1>";
		}

		$out .= "<h2>";
		if ($file["ReleaseYear"] || $file["ReleaseMonth"] || $file["ReleaseDay"]) {
			$out .=  file_release_date($file);
		}		
		if ( isset($file['Creator']) && $file['Creator'] != "") {
			$out .= " by <strong>" . $file["Creator"] . "</strong>";
		} 
		$out .= "</h2>";
		
		if ( isset($file['Description']) && $file['Description'] != "") {
			$out .= "<p>" . str_replace("\n","<br />",$file["Description"]) . "</p>";
		}
		
		$out .= theme_file_tags($file, $channel);

		//
		// if this is a torrent, then display the seeder/downloader info here
		//
		if ( is_local_torrent($file["URL"]) ) {
			$return_url = "detail.php?c=" . $_GET["c"] . "&amp;i=" . $_GET["i"] ;
			$out .= theme_torrent_info($file["URL"], $_GET["i"], $return_url );
		}


		$items = array();

		$items[] = "<a class=\"link-info\">Size: " . theme_pretty_filesize($file["URL"]) . "</a>";

		$runtime = runtime_string($file);

		if ($runtime != "") {
			$items[] = "<a class=\"link-duration\">" . $runtime . "</a>";
		}

		$items[] = "<a class=\"link-date\">Posted " . date("F j, Y", $file["Publishdate"]) . "</a>";
		$out .= theme_file_section("", $items);

		$items = array();
		// if this is a torrent, provide two links - one to the torrent and one to Easy Downloader
		$url = download_link($channel["ID"], $_GET["i"]);
		if ( is_local_torrent($file["URL"]) ) {
			$ezurl = download_link($channel["ID"], $_GET["i"], true);
			$items[] = "<a href=\"$url\" class=\"link-download\">Torrent File</a>";
			$items[] = "<a href=\"$ezurl\" class=\"link-download\">Easy Downloader</a>";
		}
		// otherwise, just a direct link
		else {
			$items[] = "<a href=\"$url\" class=\"link-download\">Direct Download</a>";
		}

		$out .= theme_file_section("Download", $items);

		$items = array();		
		if ($file["Webpage"]) {
			$items[] = "<a href=\"" . $file["Webpage"] . "\" class=\"link-website\">Related Webpage</a>";
		}
		if ($file["People"]) {
			foreach ($file["People"] as $people) {
			 if ($people[0] != '') {
				 $items[] = "<a class=\"link-user\">" . $people[0] . " - " . $people[1] . "</a>";
			 }
			}
		}

		$out .= theme_file_section("Credits", $items);

		$items = array();

		//
		// if there's some donation text for this file, then let's display it
		//
		if ( isset($file["donation_id"]) && $file["donation_id"] != "" ) {
      global $store;
			$donation = $store->getDonation($file["donation_id"]);
	
			if ( isset($donation) && isset($donation["text"]) && $donation["text"] != "" ) {
				$items[] = $donation["text"];		
			} // if ( donation exists )
		} // if ( donation specified )

		if ($file["Explicit"]) {
			$items[] = "<a class=\"link-warning\">Contains Explicit Content</a>";
		}

		if ($file["LicenseName"] && isset($file["LicenseURL"])) {
			$items[] = "<a rel=\"license\" href=\"" . $file["LicenseURL"] . "\" class=\"link-license\">" . $file["LicenseName"] . "</a>";
			$out .= theme_cc_metadata($file);
		}

		if ($file["Transcript"]) {
			if ( isset($_GET["t"]) ) {
				$trans_text = file_get_contents($file["Transcript"]);
				$trans_text = str_replace("\n", "<br />", $trans_text);
				$items[] = "<p style=\"margin-top:15px;\"><a class=\"link-transcript\">Transcript</a></p> $trans_text";
			}
			else {
				$items[] = "<a href=\"detail.php?c=" . $channel["ID"] . "&amp;i=" . $_GET["i"] . "&amp;t=1\" class=\"link-transcript\">Transcript</a>";
			}
		}

		$out .= theme_file_section("Other Stuff", $items);

		$out .= "
			</div>
		</div>";

		return $out;
	}
}

if ( ! function_exists("theme_torrent_info") ) {
	function theme_torrent_info( $url, $filehash, $return_url, $type = "basic", $restarted = false ) {
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
		
		if ( isset($settings['sharing_enable']) && isset($settings['sharing_auto']) && 
			$settings['sharing_enable'] == 1 && $settings['sharing_auto'] == 1 ) {
			$file["SharingEnabled"] = true;
		}
	
		$out = "<div class=\"video_stats\">";
	
		// always show this basic info
		$out .= "
			<strong>Torrent Status</strong>
			<br />
			SEEDERS: " . $stats["complete"] . "<br />
			DOWNLOADERS: " . $stats["incomplete"] . "<br /><br />";
	
	
		if ( $type != "basic" && $sharing == true && $seeder->enabled() ) {
			if ( !isset($file["SharingEnabled"]) || $file["SharingEnabled"] == false ) {
				$out .=  "<strong>Server Sharing STOPPED</strong><br />
					<a href=\"$start_url\">Start</a><br />";	
			}	
			else if (
				( isset($details["time left"]) && trim($details["time left"]) == "shutting down" ) ||
					file_exists("$data_dir/" . $torrenthash . ".paused")
					) {
				$out .=  "<strong>Server Sharing PAUSED</strong><br />
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
	
				$out .=  "
					<strong>Server Sharing ON</strong><br />
					Status: " . $status . "<br />
					<a href=\"$pause_url\">Pause</a> | <a href=\"$stop_url\">Stop</a><br /><br />
					Bandwidth Used: " . $tally . " MB";
			}
			else {
				$out .=  "<strong>Server Sharing STOPPED</strong><br />";
				
				if ( $restarted ) {
					$out .=  "(Restarting)<br />";
				}
				else {
					$out .=  "<a href=\"$start_url\">Start</a><br />";	
				}
			}
	
		} // if ( not basic display )
	
		$out .=  "</div>";
		return $out;
	}
}

if ( ! function_exists("subscribe_links") ) {
	function subscribe_links($id) {
		$iTunes = rss_link($id, true);
		$rss_link = rss_link($id);

		$out = <<<EOF
			<p><a href="javascript:toggleLayer('channel-subscribe-links-$id');">Subscribe</a></p>
			<div id="channel-subscribe-links-$id" class="channel-subscribe-links">
				<ul>
					<li><a href="demsub.php?i=$id" class="link-dtv">Democracy</a></li>
					<li><a href="$iTunes" class="link-itunes">iTunes</a></li>
					<li><a href="$rss_link">RSS Feed</a></li>
				</ul>
			</div>
EOF;

    return $out;
	}
}

if ( ! function_exists("section_header") ) {
	function section_header($section) {
		return "
		<div class=\"video_section\">
			<h3 class=\"section_name\">" . $section["Name"] . "</h3>";
	}
}

if ( ! function_exists("theme_video_list") ) {
	function theme_video_list($display_files, $channel, $internal = true) {
		$out = "";
		foreach ( $display_files as $filehash => $file ) {
			$out .= theme_display_video($filehash, $file, $channel, $internal);
		}
		return "$out";
	}
}

if ( !function_exists("theme_file_tags") ) {
	function theme_file_tags($file, $channel) {
		if ( $file["Keywords"] ) {
			$out = "<p><a class=\"link-tags\">Tags:</a>&nbsp;";
			
			$i = 0;
			
			foreach ($file["Keywords"] as $keyword) {
				if ($i > 0) {
					$out .= ", ";
				}
				$i++;
				if ( is_array($keyword) ) {
					$keyword = $keyword[0];
				}
				
				$out .= "<a href=\"library.php?i=" . $channel["ID"] . "&amp;kw=" . urlencode($keyword) . "\">" . $keyword . "</a>";
			}  
			$out .= "</p>";
			return $out;
		}
	}
}

if ( ! function_exists("tags_for_files") ) {
	function tags_for_files($files, $channel_files, $channel) {
	
    $channelID = $channel["ID"];

		$keywords = array();
	
		foreach ($channel_files as $filehash) {
			if ($filehash[1] <= time()) {	
				foreach ($files[$filehash[0]]["Keywords"] as $words) {	
					if ( is_array($words) ) {
						$words = $words[0];
					}
          $words = trim($words);

          if ( $words != "" ) {
            if (!array_key_exists($words, $keywords)) {
              $keywords[$words] = 0;
            }
	
            $keywords[$words]++;
          }
				} // foreach
			} // if
		} // foreach
	
		arsort($keywords);
		reset($keywords);
	
		$i = 0;
	
		if ( count($keywords) > 0 ) {
			$out = <<<EOF
	<div class="box">
		<div class="box-bi">
			<div class="box-bt"><div></div></div>
	<!-- show up 8 most popular tags -->
	<p><a class="link-tags">Tags:</a>&nbsp;
EOF;
	
			foreach ($keywords as $words => $count) {
				$out .= "<a href=\"library.php?i=" . $channelID . "&amp;kw=" . urlencode($words) . "\">" . $words . "</a> (" . $count . ") ";
				$i++;
			
				if ($i == 8) {
					break;
				}
			}

			$out .= <<<EOF
			</p>
			<div class="box-bb"><div></div></div>
		</div>
	</div>
EOF;
			return $out;
		} // if
	}
}

if ( ! function_exists("links_for_footer") ) {
	function links_for_footer() {
		$links = array();
	
    global $store;
    $users = $store->getAllUsers();

    $base = get_base_url();
    if (!(isset($_SESSION['user']) && is_array($_SESSION['user']) ) || 
				!isset($users[$_SESSION['user']['Username']]) ) {
	
			global $settings;
			$links[] = "<a href=\"" . $base . "login.php?f=1\">Login</a>";
			if ( isset($settings['AllowRegistration']) && $settings['AllowRegistration'] == 1 ) {
				$links[] = "<a href=\"" . $base . "newuser.php?f=1\">Register</a>";
			}
		} 
		else {	
			global $can_use_cookies;
			if ( $can_use_cookies ) {
				$links[] = '<a href="' . $base . 'login.php?f=1&amp;logout=1">Logout</a>';
			}
			
			if ( is_admin() ) {
				$links[] = "<a href=\"" . $base . "admin.php\">Admin</a>";
			}	
		} // else
	
		if (can_upload()) {
			$links[] = "<a href=\"" . $base . "publish.php\">Post a File</a>";
		}
	
		return join($links, " | ");
	}
}

if ( ! function_exists("runtime_string") ) {
	function runtime_string($file) {
		$runtime = "";
		if ($file["RuntimeHours"] != "") {
			$runtime .= $file["RuntimeHours"] . " hr. ";
		}
	
		if ($file["RuntimeMinutes"] != "") {
			$runtime .= $file["RuntimeMinutes"] . " min. ";
		}
	
		if ($file["RuntimeSeconds"] != "") {
			$runtime .= $file["RuntimeSeconds"] . " seconds ";
		}
		return $runtime;
	}
}

if ( ! function_exists("theme_css") ) {
	function theme_css() {
		return "<link href=\"" . get_base_url() . "/themes/default/css/black.css\" rel=\"stylesheet\" type=\"text/css\" />\n";
	}
}

if ( ! function_exists("theme_javascript") ) {
	function theme_javascript() {
		return '
	<script type="text/javascript" src="' . get_base_url() . '/themes/default/includes/prototype.js"></script>
	<script type="text/javascript" src="' . get_base_url() . '/themes/default/includes/reflection.js"></script>
	<script type="text/javascript" src="' . get_base_url() . '/themes/default/includes/shide.js"></script>
		';
	}
}

if ( !function_exists("file_release_date") ) {
	function file_release_date($file) {
		$out = "";

		if ($file["ReleaseMonth"]) {
			$out .= date("F", strtotime($file["ReleaseMonth"] + 1 . "/1/1999"));
		}
		
		if ($file["ReleaseDay"]) {
			$out .= " " . $file["ReleaseDay"];
		}
		
		if ($file["ReleaseMonth"] || $file["ReleaseDay"]) {
			$out .= ", ";
		}
		
		$out .= $file["ReleaseYear"] . "&nbsp;";

		return $out;
	}
}

if ( !function_exists("file_publish_date") ) {
	function file_publish_date($file) {
		return date("F j, Y",$file["Publishdate"]);
	}
}

/**
 * generate some embedded Creative Commons metadata
 */
if ( !function_exists("display_cc_metadata") ) {
	function display_cc_metadata($file) {
		$out = <<<EOF
	<!--
	<rdf:RDF xmlns="http://web.resource.org/cc/" 
			xmlns:dc="http://purl.org/dc/elements/1.1/"
			xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
	<Work rdf:about=""> 
EOF;
		$out .= '<license rdf:resource="' . $file["LicenseURL"] . '" />';

		if ( isset($file["Title"]) && $file["Title"] != "" ) {
			$out .= '<dc:title>' . $file["Title"] . '</dc:title>';
		}

	 	if ( isset($file[Description]) && $file["Description"] != "" ) {
			$out .= '<dc:description>' . $file["Description"] . '</dc:description>';
		}

		if ($file["ReleaseYear"] || $file["ReleaseMonth"] || $file["ReleaseDay"]) {
			$out .= '<dc:date>' . $file["ReleaseYear"] . '</dc:date>';
		}
		if (isset($file["Creator"]) && $file["Creator"]) {
			$out .= '
				 <dc:creator>
					 <Agent> 
						 <dc:title>' . $file["Creator"] . '</dc:title>
					 </Agent>
					</dc:creator>';
		}

		$out .= '
		</Work>
		</License>
		</rdf:RDF>
		-->';
	
		return $out;
	}
}

if ( !function_exists("theme_channel_summary_wrapper") ) {
	function theme_channel_summary_wrapper($channel, $content) {
		$title = $channel["Name"];
		$library_url = channel_link($channel["ID"]);
    $count = count($channel["Files"]);
		$icon = theme_channel_icon($channel);

    $footer = theme_channel_footer($channel);

		return "
		<!--CHANNEL-->
		<div class=\"channel\">
			<!--HEADER-->
			<div class=\"channel-avatar\">
        <a href=\"$library_url\" title=\"View all files in this Channel\">$icon</a>
      </div>
			<h1><a href=\"$library_url\" title=\"View all files in this Channel\">$title</a></h1>
			<h2 style=\"font-size:125%; font-weight:normal; color:#999999;\">" . count($channel["Files"]) . " files in this channel</h2>
     " . theme_channel_bar($channel) . 
			"<!--/HEADER-->
			<!--VIDEOS-->
		$content
			<!--/VIDEOS-->
    $footer
		</div>";
	}
	
}

if ( !function_exists("theme_channel_summary") ) {
	function theme_channel_summary($channel, $files) {
		$channel_files = $channel["Files"];
		usort($channel_files, "comp");
	
		$show_tagged = false;
		$show_all = true;
		$show_sections = true;
		$display_files = array();
	
		if ($channel['Options']['Keywords'] == true && isset($_GET['kw'])) {
			$show_sections = false;
			$show_all = false;
			$show_tagged = true;
	
			if ( count($channel_files) > 0 ) {		
				foreach ($channel_files as $filehash) {
			
					$filehash = $filehash[0];
					$file = $files[$filehash];
			
					foreach ($file["Keywords"] as $words) {
						if ($words == $_GET['kw']) {
							$display_files[$filehash] = $file;
						}
					} // foreach $file
			
				} // foreach $channel_files
	
			} // if $channel_files
	
		} // if show keywords
		else {
			foreach ($channel_files as $filehash) {
				$display_files[$filehash[0]] = $files[$filehash[0]];
			}
		}
	
	
		$out = "";

		if ( $show_tagged == true ) {
			$out .= tag_header($_GET["kw"], $channelID);
		}	 // if show tagged

		$out .= theme_video_list($display_files, $channel, false);
		
		return $out;
	}
}

if ( !function_exists("theme_channel_bar") ) {
	function theme_channel_bar($channel) {

		$links = subscribe_links($channel["ID"]);
		$channel_link = channel_link($channel["ID"]);
		$count = count($channel["Files"]);

		$out = <<<EOF
				<!--BOX-->
				<div class="channel-subscribe">
					$links
				</div>
			<!--/BOX-->
EOF;
		return $out;
	}
}

if ( !function_exists("theme_channel_title") ) {
	function theme_channel_title($channel) {
		return "<h1><a href=\"" . channel_link($channel["ID"]) . "\">" . $channel["Name"] . "</a></h1>";
	}
}

if ( !function_exists("theme_channel_keyword_header") ) {
	function theme_channel_keyword_header($channel, $keyword) {
		return "<h2>Files Matching \"$keyword\"</h2>\n";
	}
}

if ( !function_exists("theme_channel_videos") ) {
	function theme_channel_videos($channel, $files = NULL, $keyword = NULL) {

    if ( $files == NULL ) {
      global $store;
      $files = $store->getAllFiles();
    }
	
		$show_tagged = false;
		$show_all = true;
		$show_sections = true;
		$display_files = array();
	
		if ($channel['Options']['Keywords'] == true && isset($keyword)) {
			$show_sections = false;
			$show_all = false;
			$show_tagged = true;
		}
	
	
		$out = "";
		if ( $show_sections == true ) {
			foreach ($channel['Sections'] as $section) {
			
				if (count($section["Files"]) > 0) {
					$out .= section_header($section);
		
					$out .= "<ul>";			
					foreach ($section["Files"] as $filehash) {
						$out .= theme_display_video($filehash, $files[$filehash], $channel);
					}
					$out .= "</ul>
						<div class=\"spacer_left\">&nbsp;</div></div>";
				} // if
			
			} // foreach section
		}
		
		if ( $show_all == true && count($channel["Files"]) > 0 ) {
			foreach ($channel["Files"] as $filehash) {
				$display_files[$filehash[0]] = $files[$filehash[0]];
			}
		} // if ( files )
    else if ( $show_tagged == true ) {

      $channel_files = $channel["Files"];

			if ( count($channel_files) > 0 ) {		
				foreach ($channel_files as $filehash) {
					$filehash = $filehash[0];
					$file = $files[$filehash];
			
					foreach ($file["Keywords"] as $words) {
						if ($words == $keyword) {
							$display_files[$filehash] = $file;
						}
					} // foreach $file
			
				} // foreach $channel_files
	
			} // if $channel_files
	
    }

    $out .= theme_video_list($display_files, $channel);		
		return $out;
	}
}

if ( ! function_exists("theme_channel_icon") ) {
	function theme_channel_icon($channel, $with_sub_links = true) {
		if (!isset($channel['Icon']) || $channel['Icon'] == '') {
			$icon = get_base_url() . "t.gif";
		} 
		else {
			$icon = $channel['Icon'];
		}

    //  border=\"0\" 
		return "<img src=\"$icon\" alt=\"\" />";
	}
}

if ( ! function_exists("theme_channel_header") ) {
	function theme_channel_header($channel, $with_sub_links = true) {
		$icon = theme_channel_icon($channel);

		$link = channel_link($channel["ID"]);
		$name = $channel["Name"];
		$count = count($channel["Files"]);

		$out = <<<EOF
		<div class="channel-avatar"><a href="$link" title="View all files in this Channel">$icon</a></div>
		<h1><a href="$link">$name</a></h1>
		<h2 style="font-size:125%; font-weight:normal; color:#999999;">$count files in this channel</h2>
EOF;

		if ( $with_sub_links == true ) { 
			$links = subscribe_links($channel["ID"]);
			$out .= <<<EOF
		<!--SUBSCRIBE PULLDOWN-->
		<div class="channel-subscribe">
			$links
		</div>
		<!--/SUBSCRIBE PULLDOWN-->
EOF;
		} // if

		return $out;

	}
}



if ( ! function_exists("theme_file_thumbnail") ) {
	function theme_file_thumbnail($file, $channel, $class = "reflect") {
		
		if ($file['Image'] == '' || ! $channel['Options']['Thumbnail']) {
			$fname = get_base_url() . "t.gif";
		} 
		else {
			$fname = $file['Image'];
		}

		$alt = encode($file["Title"]);
		$out = "<img src=\"$fname\" width=\"150\" height=\"150\" style=\"border: 0\" alt=\"$alt\"";
    // border=\"0\" 
		if ( $class != "" ) {
			$out .= " class=\"$class\"";
		}
		$out .= " />";
		return $out;
	}
}


if ( ! function_exists("theme_embed_video") ) {
	function theme_embed_video($file, $channel, $class = "reflect") {		
		$url = $file['URL'];
		$out = "<embed src=\"$url\" width=\"250\" height=\"250\"></embed>";
		return $out;
	}
}

if ( ! function_exists("theme_file_section") ) {
	function theme_file_section($title, $items) {
		if ( !isset($items) || count($items) == 0 ) {
			return;
		}

		$out = "";
		if ( $title != "" ) {
			$out .= "<h3>$title</h3>";
		}
		
		if ( count($items) > 0 ) {
			$out .= "<ul>";
			foreach($items as $i) {
				$out .= "<li>$i</li>";
			}
			$out .= "</ul>";
		}
		
		return $out;
	}
}

if ( ! function_exists("tag_header") ) {
	function tag_header($tag, $channelID) {
		$channel_link = channel_link($channelID);
		$out = <<<EOF
		<div class="nav" style="text-align:center;">
			<p><strong>Files tagged with &quot;<?php echo $tag; ?>&quot;</strong><br />
			<a href="$channel_link><< All Files in This Channel</a></p>
		</div>
EOF;
		return $out;
	}
}

/*
 * Local variables:
 * tab-width: 2
 * c-basic-offset: 2
 * indent-tabs-mode: nil
 * End:
 */

?>