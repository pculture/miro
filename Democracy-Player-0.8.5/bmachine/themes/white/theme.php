<?php
/**
 * Broadcast Machine theme file
 *
 * An assortment of functions that control display of information in BM.
 * @package BMThemes
 */

function render_channel_page($channel, $files, $keyword = NULL) {

  $tmp = tags_for_files($files, $channel["Files"], $channel, false);

  $icon = theme_channel_icon($channel);
  $out = "<div class=\"channel\">
			<div class=\"channel-avatar\">$icon</div>" .
    theme_channel_title($channel);

  $out .= theme_channel_footer($channel, $tmp);

  
  if ( $keyword != NULL ) {
    $out .= theme_channel_keyword_header($channel, $keyword);
  }
  
  $out .= 
    theme_channel_videos($channel, $files, $keyword) .
    theme_channel_bar($channel) .
    '</div>';
  
  front_header($channel["Name"], 
               $channel["ID"], 
               $channel["CSSURL"], 
               rss_link($channel["ID"]) );
  
  print theme_channel_wrapper($out, $channel, false);
  
  front_footer($channel["ID"]);
}

function render_detail_page($file, $channel) {
  
  front_header($channel["Name"], $channel["ID"], $channel["CSSURL"], rss_link($channel["ID"]) );
  
  $out = theme_channel_bar($channel) .
    theme_detail_video_wrapper( $channel, $file, theme_detail_page($file, $channel) );
  
  theme_page_wrapper(
                     theme_detail_wrapper(
                                          $out
                                          )
                     );
  
  front_footer($channel["ID"]);
}


function theme_channel_summary_wrapper($channel, $content) {
  $title = $channel["Name"];
  $library_url = channel_link($channel["ID"]);
  $footer = theme_channel_footer($channel);
  $icon = theme_channel_icon($channel);

  return "
		<!--CHANNEL-->
		<div class=\"channel\"  style=\"clear:left;\">
			<div class=\"channel-avatar\">
        <a href=\"$library_url\" title=\"View all files in this Channel\">$icon</a>
      </div>
 	    <h1><a href=\"$library_url\">$title</a></h1>
    </div>

		<div class=\"channel\"  style=\"clear:left;\">
			$content
      $footer
		</div>";
		
}

function theme_channel_bar($channel) {
  return "";
}


function theme_channel_wrapper($content, $channel, $show_channel_link = true) {
  if ( $show_channel_link ) {
    $footer = theme_channel_footer($channel);
  }
  else {
    $footer = "";
  }

  return $content . $footer;
}


function theme_channel_footer($channel, $extra = "") {
	$link = channel_link($channel["ID"]);
  $count = count($channel["Files"]);

  $links = subscribe_links($channel["ID"]);

  if ( $extra == "" ) {
    $extra = "<p><a href=\"$link\">Full Channel ($count) &gt;&gt;</a></p>";
  }

  $out = "
 				<div class=\"box\">
  					<div class=\"box-bi\">
   						<div class=\"box-bt\"><div></div></div>
				<!--BOX-->
				<div class=\"channel-subscribe\">
					$links
				</div>
			<!--/BOX-->
        $extra
					<div class=\"box-bb\"><div></div></div>
				</div>
			</div>
  ";
  return $out;
}


function theme_video_list($display_files, $channel, $internal = true) {
  $out = "";
  $right = false;
  foreach ( $display_files as $filehash => $file ) {
    $out .= theme_display_video($filehash, $file, $channel, $internal, $right);
    $right = ! $right;
  }
  return "$out";
}

function theme_display_video($filehash, $file, $channel, $show_internal_view = true, $right = false ) {
	
  if ( $show_internal_view == true ) {
    return theme_display_internal_video($filehash, $file);
  }
  else {
    return theme_display_frontpage_video($channel, $filehash, $file, $right);	
  }
}


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
				<div class=\"video\">";
	$url = detail_link($channel["ID"], $filehash);

  if ( isset($channel['Options']['Thumbnail']) && $channel['Options']['Thumbnail'] == 1) {
    $out .= "<div class=\"video-tnail\"><a href=\"$url\">". theme_file_thumbnail($file, $channel, "reflect") . "</a></div>\n"; 
  }
	
	$out .= "<div class=\"video-info\">";
	
  if ( isset($channel['Options']['Title']) && $channel['Options']['Title'] == 1) {
    $out .= "
	<h1><a href=\"$url\">" . encode($file["Title"]) . "</a></h1>\n";
  }
	

  if ( isset($channel['Options']['Published']) && $channel['Options']['Published'] == 1 ) {
		
		$out .= "<h2>";
		if ($file["ReleaseYear"] && $file["ReleaseMonth"] && $file["ReleaseDay"]) {
			$out .= file_release_date($file);		 
		}
	
		if (isset($channel['Options']['Creator']) && $channel['Options']['Creator'] == 1 && $file["Creator"]) {
			$out .= "by <strong>" . encode($file["Creator"]) . "</strong>\n";
		}
		
		$out .= "</h2>";

  }
	
  if ( isset($channel['Options']['Description']) && $channel['Options']['Description'] == 1 && $file["Description"] != "" ) {
    $out .= "<p>" . mb_substr(encode($file["Description"]), 0, 250) . "...</p>\n";
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
			$out .= "<a href=\"library.php?i=" . $channel["ID"] . "&amp;kw=" . urlencode($keyword) . "\">" . encode($keyword) . "</a>";
		}  
		$out .= "</p>";
  }
	 
  if ( isset($channel['Options']['Filesize']) && $channel['Options']['Filesize'] == 1 ) {
	  $out .= "<p><a class=\"link-info\">Size: " . theme_pretty_filesize($file["URL"]) . "</a></p>";
  }
		
	
	if ( isset($channel['Options']['Length']) && $channel['Options']['Length'] == 1) {
		$runtime = runtime_string($file);
		if ($runtime != "") {
			$out .= "<p><a class=\"link-duration\">" . $runtime . "</a></p>";
		}
	}

	$out .= "<p><a class=\"link-date\">Posted " . date("F j, Y", $file["Publishdate"]) . "</a></p>\n";
	
  $out .= "<h3>Download</h3>";

	// if this is a torrent, provide two links - one to the torrent and one to Easy Downloader
	$url = detail_link($channel["ID"], $filehash);
	$dlurl = download_link($channel["ID"], $filehash);
	$ezurl = download_link($channel["ID"], $filehash, true);

	$out .=  "<ul>";
	$out .=  "<li><a href=\"$url\" class=\"link-info\" style=\"float:none;\">Details</a></li>";
	if ( is_local_torrent($file["URL"]) ) {
		$out .= "
		<li><a href=\"$dlurl\" class=\"link-download\">Download Torrent</a></li>
		<li><a href=\"$ezurl\" class=\"link-torrent\">Easy Downloader</a></li>";
	}
	else {
		$out .=  "<li><a href=\"$dlurl\" class=\"link-download\">Download</a></li>";
	}		
	$out .=  "</ul>";

	if ( isset($channel['Options']['Torrent']) && $channel['Options']['Torrent'] == 1 && is_local_torrent($file["URL"]) ) {
		$return_url = "detail.php?c=" . $channel["ID"] . "&amp;i=" . $filehash ;
		$out .=  "<div>" . theme_torrent_info($file["URL"], $filehash, $return_url ). "</div>";
	}

	$out .= "
					</div>
				</div>
				<!--/VIDEO-->\n";

	return $out;
}


function theme_display_frontpage_video($channel, $filehash, $file, $right = false) {

  //
  // if the publish date is in the future, then return right away - don't display it
  //
	if ($file["Publishdate"] >= time()) {
		return;
	}

	$url = detail_link($channel["ID"], $filehash);
	$title = encode($file['Title']);

	$url = detail_link($channel["ID"], $filehash);
	$dlurl = download_link($channel["ID"], $filehash);
	$ezurl = download_link($channel["ID"], $filehash, true);

	if ( $right == false ) {
		$class = "video-left";
	}
	else {
		$class = "video-right";	
	}
	
	$date = file_publish_date($file);

	$out = "
			<!--VIDEO-->
			<div class=\"$class\">
				<div class=\"video-tnail\"><a href=\"$url\">" .
				theme_file_thumbnail($file, $channel, $class) . "</a></div>
				<div class=\"video-info\">
					<h1><a href=\"$url\" title=\"More info on ...\">$title</a></h1>
					<h2>$date</h2>
					<p><a href=\"$url\" class=\"link-info\" style=\"float:none;\">Details</a></p>";

	if ( is_local_torrent($file["URL"]) ) {
		$out .= "
		<p><a href=\"$dlurl\" class=\"link-download\">Download Torrent</a></p>
		<p><a href=\"$ezurl\" class=\"link-torrent\">Easy Downloader</a></p>";
	}
	else {
		$out .= "<p><a href=\"$dlurl\" class=\"link-download\">Download</a></p>";
	}

	$out .= "\n</div>
			</div>
			<!--/VIDEO-->";

	return $out;
}


function theme_css() {
	return '<link href="' . get_base_url() . '/themes/white/css/white.css" rel="stylesheet" type="text/css" />';
}

/*
 * Local variables:
 * tab-width: 2
 * c-basic-offset: 2
 * indent-tabs-mode: nil
 * End:
 */

?>