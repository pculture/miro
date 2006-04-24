<?php

/**
 * Broadcast Machine theme file
 *
 * An assortment of functions that control display of information in BM.
 * @package Broadcast Machine
 */


/**
 * display a footer for the front pages of the site
 */
function bm_footer() {

	print("
<div class=\"spacer\">&nbsp;</div>
</body>
</html>");

}


function display_internal_video($filehash, $file) {

	global $channel;

  //
  // if the publish date is in the future, then return right away - don't display it
  //
	if ($file["Publishdate"] >= time()) {
		return;
	}

  $out = "
				<!--VIDEO-->
				<div class=\"video\">";

	$url = detail_link($channel["ID"], $filehash);

  if ( isset($channel['Options']['Thumbnail']) && $channel['Options']['Thumbnail'] == 1) {

    $out .= "<div class=\"video-tnail\"><a href=\"$url\"><img src=\"";
      
    if ($file['Image'] == '' || !$channel['Options']['Thumbnail']) {
      $out .= get_base_url() . "t.gif";
    } 
    else {
      $out .= $file['Image'];
    }
    $out .= "\" width=\"150\" style=\"border: 0\" alt=\"" . encode($file["Title"]) . "\" class=\"reflect\" /></a></div>\n"; 
  }
	
	$out .= "<div class=\"video-info\">";
	
  if ( isset($channel['Options']['Title']) && $channel['Options']['Title'] == 1) {

    $out .= "
	<h1><a href=\"$url\">" . encode($file["Title"]) . "</a></h1>\n";
  }
	

  if ( isset($channel['Options']['Published']) && $channel['Options']['Published'] == 1 ) {
		
		$out .= "<h2>";

    if ($file["ReleaseYear"] || $file["ReleaseMonth"] || $file["ReleaseDay"]) {
      
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
   
    }
	
  if (isset($channel['Options']['Creator']) && $channel['Options']['Creator'] == 1 && $file["Creator"]) {
    $out .= "by <strong>" . $file["Creator"] . "</strong>\n";
  }
	
	$out .= "</h2>";

  }
	
	
  if ( isset($channel['Options']['Description']) && $channel['Options']['Description'] == 1 && $file["Description"] != "" ) {
    $out .= "<p>" . mb_substr($file["Description"],0,250) . "...</p>\n";
  }

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
	 
  $out .= "<ul>";

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
      
      $out .= "<li><a class=\"link-info\">Size: " . $size . "</a></li>";
    }
  }
		

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
			$out .= "<li><a class=\"link-duration\">" . $runtime . "</a></li>";
		}
	
		if ( isset($channel['Options']['Length']) && $channel['Options']['Length'] == 1) {
			$out .= "<li><a class=\"link-date\">Posted " . date("F j, Y", $file["Publishdate"]) . "</a></li>\n";
		}
	}
		
  $out .= "</ul>";

  $out .= "<h3>Download</h3>";
	
  $out .= "<ul>";		

  if ( isset($channel['Options']['Torrent']) && $channel['Options']['Torrent'] == 1 && is_local_torrent($file["URL"]) ) {
    $return_url = "detail.php?c=" . $channel["ID"] . "&amp;i=" . $filehash ;
    $out .= theme_torrent_info($file["URL"], $filehash, $return_url );
  }
	
  // if this is a torrent, provide two links - one to the torrent and one to Easy Downloader
	$url = download_link($channel["ID"], $filehash);
	$ezurl = download_link($channel["ID"], $filehash, true);

  if ( is_local_torrent($file["URL"]) ) {
    $out .= "
		<li><a href=\"$url\" class=\"link-download\">Torrent File</a></li>
		<li><a href=\"$ezurl\" class=\"link-download\">Easy Downloader</a></li>\n";	
  }

  // otherwise, just a direct link
  else {

		$url = download_link($channel["ID"], $filehash);
	  $out .= "<li><a href=\"$url\" class=\"link-download\">Direct Download</a></li>\n";
  }
		
  $out .= "</ul>";

	$out .= "
					</div>
				</div>
				<!--/VIDEO-->\n";

	return $out;

}


function display_frontpage_video($filehash, $file) {

	global $channel;

  //
  // if the publish date is in the future, then return right away - don't display it
  //
	if ($file["Publishdate"] >= time()) {
		return;
	}

  $out .= "
				<!--VIDEO-->
				<div class=\"video-home\">";
			
				$url = detail_link($channel["ID"], $filehash);
			
					if ( isset($channel['Options']['Thumbnail']) && $channel['Options']['Thumbnail'] == 1) {
				
						$out .= "
					<div class=\"video-home-tnail\"><a href=\"$url\"><img src=\"";
							
						if ($file['Image'] == '' || !$channel['Options']['Thumbnail']) {
							$out .= "t.gif";
						} 
						else {
							$out .= $file['Image'];
						}
						$out .= "\" width=\"150\" style=\"border: 0\" alt=\"" . encode($file["Title"]) . "\" /></a></div>"; 
					}
				
					if ( isset($channel['Options']['Title']) && $channel['Options']['Title'] == 1) {
				
						$out .= "
					<div class=\"video-home-info\">
						<h1><a href=\"$url\">" . encode($file["Title"]) . "</a></h1>
					</div>\n";
				}			 
			
				$out .=  "
				</div>
				<!--/VIDEO-->\n";

	return $out;
}
/*
function tag_header($tag, $channelID) {
?>
	<div class="nav" style="text-align:center;">
	  <p><strong>Files tagged with &quot;<?php echo $tag; ?>&quot;</strong><br />
    <a href="<?php print channel_link($channelID); ?>"><< All Files in This Channel</a></p>
  </div>
<?php
}

function section_header($section) {
	print("
	<div class=\"video_section\">
		<h3 class=\"section_name\">" . $section["Name"] . "</h3>");
}

function theme_video_list($display_files) {
	foreach ( $display_files as $filehash => $file ) {
		display_video($filehash, $file);
	}
}

function tags_for_files($files) {
?>
<div class="box">
	<div class="box-bi">
		<div class="box-bt"><div></div></div>
<!-- show up 8 most popular tags -->
<?php

   $keywords = array();

  foreach ($files as $filehash) {
    
    if ($filehash[1] <= time()) {

      foreach ($files[$filehash[0]]["Keywords"] as $words) {

        if ( is_array($words) ) {
          $words = $words[0];
        }
				if (!array_key_exists($words,$keywords)) {	  
					$keywords[$words] = 0;
				}

				$keywords[$words]++;

      } // foreach

    } // if

  } // foreach

  arsort($keywords);
  reset($keywords);

  $i = 0;

	if ( count($keywords) > 0 ) {
		print "<p><a class=\"link-tags\">Tags:</a>&nbsp;";

		foreach ($keywords as $words => $count) {
			print("<a href=\"library.php?i=" . $channelID . "&amp;kw=" . urlencode($words) . "\">" . $words . "</a> (" . $count . ") ");
			$i++;
		
			if ($i == 8) {
				break;
			}
		}
		print "</p>\n";
	}
?>
		<div class="box-bb"><div></div></div>
	</div>
</div>
<?php
}


function links_for_footer() {
	$links = array();

	if (!(isset($_SESSION['user']) && is_array($_SESSION['user']))) {

		global $settings;

		$links[] = "<a href=\"login.php?f=1\">Login</a>";
		if ( isset($settings['AllowRegistration']) && $settings['AllowRegistration'] == 1 ) {
			$links[] = "<a href=\"newuser.php?f=1\">Register</a>";
		}
	} 
	else {	
		global $can_use_cookies;
		if ( $can_use_cookies ) {
			$links[] = '<a href="login.php?f=1&amp;logout=1">Logout</a>';
		}
		
		if ( is_admin() ) {
			$links[] = "<a href=\"admin.php\">Admin</a>";
		}	
	} // else

	if (can_upload()) {
		$links[] = "<a href=\"publish.php\">Post a File</a>";
	}

	print join($links, " | ");
}

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
*/


function render_channel_page($channel, $files) {
    $out = '<div class="channel">' .
      theme_channel_title($channel) .
      theme_channel_videos($channel) .
      theme_channel_bar($channel) .
      '</div>';
    
    $out .= tags_for_files($files, $channel["Files"]);
    
    front_header(site_title(), 
		 $channel["ID"], 
		 $channel["CSSURL"], 
		 rss_link($channel["ID"]) );
    
    print theme_channel_wrapper($out);
    
    front_footer($channel["ID"]);
  }

function oldrender_channel_page($channel, $files) {
	$channelID = $channel['ID'];

	$channel_files = $channel["Files"];
	usort($channel_files, "comp");
	
	if (!isset($channel['Icon']) || $channel['Icon'] == '') {
		$icon = "t.gif";
	} 
	else {
		$icon = $channel['Icon'];
	}


	front_header($channel["Name"], $channelID, $channel["CSSURL"], rss_link($_GET["i"]));
?>
	
	<!--CHANNEL-->
	<div class="channel">
		
		<!--HEADER-->
		<div class="channel-avatar"><img src="<?php echo $icon; ?>" alt="" /></div>
		<h1><?php echo $channel["Name"]; ?></h1>
		<h2 style="font-size:125%; font-weight:normal; color:#999999;"><?php echo count($channel_files); ?> files in this channel</h2>
		
		<!--SUBSCRIBE PULLDOWN-->
		<div class="channel-subscribe">
			<?php print subscribe_links($channel["ID"]); ?>
		</div>
		<!--/SUBSCRIBE PULLDOWN-->
		<!--/HEADER-->
	
	<?php
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
	
	
		if ( $show_tagged == true ) {
			tag_header($_GET["kw"], $channelID);
			theme_video_list($display_files);
		}	 // if show tagged
	?>
	</div>
	<!--/CHANNEL-->
	
	<?php
	
	if ( $show_sections == true ) {
		foreach ($channel['Sections'] as $section) {
		
			if (count($section["Files"]) > 0) {
				section_header($section);
	
				print "<ul>";			
				foreach ($section["Files"] as $filehash) {
					display_video($filehash, $files[$filehash]);
				}
				print("</ul>
					<div class=\"spacer_left\">&nbsp;</div></div>");
			} // if
		
		} // foreach section
	}
	
	if ( $show_all == true && count($channel_files) > 0 ) {
		theme_video_list($display_files, $channel);
	} // if ( files )
	
  tags_for_files($channel_files, $channel);
	front_footer($channelID);
}


/*
 * Local variables:
 * tab-width: 2
 * c-basic-offset: 2
 * indent-tabs-mode: nil
 * End:
 */

?>