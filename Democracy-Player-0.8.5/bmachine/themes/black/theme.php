<?php

/**
 * Broadcast Machine theme file
 *
 * An assortment of functions that control display of information in BM.
 * @package BMThemes
 */


function render_index_page() {
  global $store;
  $channels = $store->getAllChannels();
  $files = $store->getAllFiles();
    
  $out = array();
  foreach ($channels as $channel) {
    if ( ! isset($channel["NotPublic"]) || ! $channel["NotPublic"] || valid_user() ) {
      $out[] = theme_channel_summary_wrapper($channel, 
                                             theme_channel_summary($channel, $files, 4));
    } // if
  } // foreach

  front_header( site_title() );
  theme_page_wrapper( theme_index_wrapper( $out ) );
  front_footer();
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


function render_channel_page($channel, $files) {

  $icon = theme_channel_icon($channel);
  $out = '<div class="channel">
   	    <div class="channel-avatar">' . $icon . '</div>' .
    theme_channel_title($channel) .
    theme_channel_videos($channel) .
    theme_channel_bar($channel) .
    '</div>';
    
  $out .= tags_for_files($files, $channel["Files"], $channel);
    
  front_header(site_title(), 
               $channel["ID"], 
               $channel["CSSURL"], 
               rss_link($channel["ID"]) );
  
  print theme_channel_wrapper($out);
  
  front_footer($channel["ID"]);
}

function theme_channel_footer($channel) {
  $link = channel_link($channel["ID"]);
  $count = count($channel["Files"]);

  // we display 4 files by default on the frontpage for this theme
  $left = $count - 4;

  if ( $left <= 0 ) {
    $out = '
	<div class="nav">
			<p>&nbsp;</p>
	</div>
   ';
  }
  else {
    $out = '
	<div class="nav">
			<p><a href="' . $link . '">Next ' . $left . '&gt;&gt;</a></p>
	</div>
    ';
  }

  return $out;
}


/*
 * Local variables:
 * tab-width: 2
 * c-basic-offset: 2
 * indent-tabs-mode: nil
 * End:
 */

?>