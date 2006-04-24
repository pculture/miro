<?php
/**
 * Broadcast Machine theme file
 *
 * An assortment of functions that control display of information in BM.
 * @package Broadcast Machine
 */

function render_channel_page($channel, $files, $keyword = NULL) {

	$out = theme_channel_videos($channel, $files, $keyword) .
		tags_for_files($files, $channel["Files"], $channel);

	front_header($channel["Name"], $channel["ID"], $channel["CSSURL"], rss_link($channel["ID"]));

	print theme_channel_wrapper(
		$out
	);

	front_footer($channel["ID"]);
}

function render_detail_page($file, $channel) {

	front_header($channel["Name"], $channel["ID"], $channel["CSSURL"], get_base_url() . "rss.php?i=" . $channel["ID"]);		
	
	$out = theme_detail_video_wrapper( $channel, $file, theme_detail_page($file, $channel) );

	print theme_detail_wrapper(
		$out
	);
			
	front_footer($_GET["c"]);
}


function theme_index_wrapper($content) {
	$out = array();
	foreach($content as $c) {
		$out[] = "<div>\n" . $c . "\n</div>\n";
	}
	return $out;
}

function theme_detail_wrapper($content) {
	return "<!--CHANNEL-->
	<div class=\"channel\">
		$content
	</div>
	<!--/CHANNEL-->";
}

function theme_detail_video_wrapper($channel, $file, $content) {
	$channel_url = channel_link($channel["ID"]);
	return '
		<div id="show_all"><a href="' . $channel_url . '">Show All Videos</a></div>
		<div class="spacer">&nbsp;</div>
		<div id="video_zone">
    ' .	$content .
		'</div>
		<div class="spacer_left">&nbsp;</div>';
}

function theme_detail_page($file, $channel) {
	$out = '<!--VIDEO-->
  <div class="single_video">';

    if ( !is_local_torrent($file['URL']) && beginsWith($file["Mimetype"], "video/") ) {
      $out .= '
     <div class="embed_wrap">
   		<div class="embed">
      ' . theme_embed_video($file, $channel) . '
      </div>
      ';
    }
    else {
      $out .= '
      <div class="thumb_wrap">
            <div class="thumbnail">
            ' . theme_file_thumbnail($file, $channel) . '
            </div>
      ';
    }



	// if this is a torrent, provide two links - one to the torrent and one to Easy Downloader
	$url = download_link($channel["ID"], $_GET["i"]);

	if ( is_local_torrent($file["URL"]) ) {
		$ezurl = download_link($channel["ID"], $_GET["i"], true);
		$out .= "
             <a href=\"$url\" class=\"link-download\">Torrent File</a> - 
             <a href=\"$ezurl\" class=\"link-download\">Easy Downloader</a>
    ";
	}
	// otherwise, just a direct link
	else {
		$out .= "
             <a href=\"$url\" class=\"link-download\">Direct Download</a>
    ";
	}
	
	$out .= "</div>
		<div class=\"video_info\">";

	if ( isset($file['Title']) && $file['Title'] != "") {
		$out .= "<h1>" . encode($file["Title"]) . "</h1>";
	}

	$out .= "<h2>";
	if ($file["ReleaseYear"] || $file["ReleaseMonth"] || $file["ReleaseDay"]) {
		$out .=  file_release_date($file);
	}		
	if ( isset($file['Creator']) && $file['Creator'] != "") {
		$out .= " by <strong>" . encode($file["Creator"]) . "</strong>";
	} 
	$out .= "</h2>";
	
	if ( isset($file['Description']) && $file['Description'] != "") {
		$out .= "<p>" . str_replace("\n","<br />", encode($file["Description"]) ) . "</p>";
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
	</div>
	<div class=\"spacer_left\">&nbsp;</div>";

	return $out;
}

function theme_video_list($display_files, $channel, $internal = true) {
	$out = "";
	foreach ( $display_files as $filehash => $file ) {
		$out .= "\n<!-- VIDEO -->\n" . theme_display_video($filehash, $file, $channel, $internal) . "\n<!-- /VIDEO -->\n";
	}
	return $out;
}


function theme_channel_videos($channel, $files = NULL, $keyword = NULL) {

	$show_tagged = false;
	$show_all = true;
	$show_sections = true;
	$display_files = array();

	if ($channel['Options']['Keywords'] == true && isset($_GET['kw'])) {
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

		$out .= "<div class=\"video_section\">
		<h3 class=\"section_name\">All Files</h3>
		<ul>" .
			theme_video_list($display_files, $channel) .
		"</ul>
		<div class=\"spacer_left\">&nbsp;</div>
		</div>";

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

		$out .= "<div class=\"video_section\">
		<h3 class=\"section_name\">Videos tagged with \"$keyword\"</h3>
		<ul>" .
			theme_video_list($display_files, $channel) .
      "</ul>
		<div class=\"spacer_left\">&nbsp;</div>
		</div>";

    
  } // $show_tagged


	
	return $out;
}

/**
 * display a header for the front pages of the site
 */
function front_header($pagename = "", $channelID = "", $stylesheet = "default.css", $feed = "", $onload = "" ) {

	global $settings;

	header("Content-type: text/html; charset=utf-8");

	$site = site_title();	
	if ( $site != "" && $pagename != $site ) {
		$pagename = "$site: $pagename";
	}

  $pagename = encode($pagename);

	print("<!DOCTYPE html PUBLIC \"-//W3C//DTD XHTML 1.0 Transitional//EN\" \"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd\">
<html xmlns=\"http://www.w3.org/1999/xhtml\">
<head>
<title>");

	if ($pagename) {
	  print($pagename);
	}
  else {
    print "Broadcast Machine";
  }

	print("</title>
<meta http-equiv=\"Content-Type\" content=\"text/html;charset=utf-8\" />
<link rel=\"stylesheet\" type=\"text/css\" href=\"" . get_base_url(). $stylesheet . "\"/>\n");

	if ( $feed != "" ) {
		print "<link rel=\"alternate\" type=\"application/rss+xml\" title=\"RSS 2.0\" href=\"$feed\" />";
	}

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
	print links_for_footer();
	print("</div>
	<div id=\"library_header_wrap\">
	<div id=\"library_title\">" . $pagename . "</div>\n");

	if ( $channelID ) {
		$rsslink = '<a href="rss.php?i=' . $channelID . '"><img src="' . get_base_url() . 'images/rss_button.gif" alt="rss feed" border="0" /></a>';
		print("<div id=\"rss_feed\">$rsslink</div>\n");
	}

	print("</div>\n\n");

}


/**
 * display information about a video
 */
function theme_display_video($filehash, $file, $channel, $show_internal_view = true) {

  //
  // if the publish date is in the future, then return right away - don't display it
  //
	if ($file["Publishdate"] >= time()) {
		return;
	}

  $out = "\n<li><div class='video_display'>\n";

	$url = detail_link($channel["ID"], $filehash);

  if ( isset($channel['Options']['Thumbnail']) && $channel['Options']['Thumbnail'] == 1) {
        	
    $out .= "<div class=\"thumbnail\">
			<a href=\"$url\">" . theme_file_thumbnail($file, $channel, "") . "</a>
      </div>\n"; 
  }

  if ( isset($channel['Options']['Title']) && $channel['Options']['Title'] == 1) {
    $out .= "
<div class=\"video_title\">
	<a href=\"$url\">" . encode($file["Title"]) . "</a>
</div>\n";
  }
  if (isset($channel['Options']['Creator']) && $channel['Options']['Creator'] == 1 && $file["Creator"]) {
    $out .= "\n<div class=\"creator_name\">by " . $file["Creator"] . "</div>\n";
  }
  if ( isset($channel['Options']['Desc']) && $channel['Options']['Desc'] == 1 && $file["Desc"] != "" ) {
    $out .= "\n<div class=\"video_description\">\n";
    $out .= mb_substr($file["Desc"],0,52) . "...\n</div>\n";
  }

  if ( isset($channel['Options']['Length']) && $channel['Options']['Length'] == 1) {
    $out .= "\n<div class=\"video_stats\">\n";
    $out .= "<div class=\"published_date\">Posted " . date("F j, Y", $file["Publishdate"]) . "</div>\n";
    if (($file["RuntimeHours"] || $file["RuntimeMinutes"] || $file["RuntimeSeconds"])) {
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
        $out .= "<div class=\"duration\">" . $runtime . "</div>\n";
      }
    }
		$out .= "</div>\n";
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
      
      $out .= "<div class=\"file_size\">Size: " . $size . "</div>\n";
    }
  }

  if ( isset($channel['Options']['URL']) && $channel['Options']['URL'] == 1 && $file["Webpage"] ) {
    $out .= "\n<div class=\"associated_website\"><a href=\"" . $file["Webpage"] . "\">Related Webpage</a></div>\n";
  }

  if ( isset($channel['Options']['Torrent']) && $channel['Options']['Torrent'] == 1 && is_local_torrent($file["URL"]) ) {
    $return_url = "detail.php?c=" . $channel["ID"] . "&amp;i=" . $filehash ;
    $out .= theme_torrent_info($file["URL"], $filehash, $return_url );
  }

  if ( isset($channel['Options']['Published']) && $channel['Options']['Published'] == 1 ) {

    if ($file["ReleaseYear"] || $file["ReleaseMonth"] || $file["ReleaseDay"]) {

      $out .=  "<div class=\"production_details\">\n";     
      $out .= "<div class=\"release_date\">Release Date: ";
      
      if ($file["ReleaseMonth"]) {
        $out .= date("F", strtotime($file["ReleaseMonth"] + 1 . "/1/1999"));
      }
     
      if ($file["ReleaseDay"]) {
        $out .= " " . $file["ReleaseDay"];
      }
     
      if ($file["ReleaseMonth"] || $file["ReleaseDay"]) {
        $out .= ", ";
      }
     
      $out .= $file["ReleaseYear"] . "</div>";
      $out .= "</div>\n";     
    }
  }

  if ( isset($channel['Options']['Keywords']) && $channel['Options']['Keywords'] == 1 && $file["Keywords"] ) {
    $out .= "<div class=\"tags\"><strong>Tags:</strong> ";
    
    $i = 0;
    
		$out .= join($file["Keywords"], ", ");
    $out .= "</div>\n";  
  }

  $out .= "<a href=\"$url\">more...</a>\n";

	$out .= "</div>";
  // if this is a torrent, provide two links - one to the torrent and one to Easy Downloader
	$url = download_link($channel["ID"], $filehash);
	$ezurl = download_link($channel["ID"], $filehash, true);

  if ( is_local_torrent($file["URL"]) ) {
    $out .= "\n<div class=\"dl_links\"><a href=\"$url\">Torrent File</a> - <a href=\"$ezurl\">Easy Downloader</a></div>\n";
  }

  // otherwise, just a direct link
  else {
    $out .= "\n<div class=\"dl_links\"><a href=\"download.php?c=" . $channel["ID"] . "&amp;i=" . $filehash  . "\">download</a></div>\n";
  }

	$out .= "</li>\n";
	return $out;
}

function theme_channel_summary_wrapper($channel, $content) {
	return $content;
}

function theme_channel_summary($channel, $files) {

	$id = $channel["ID"];
	$name = encode($channel["Name"]);
	$channel_link = channel_link($channel["ID"]);
	$rss_link = rss_link($channel["ID"]);

	$out = <<<EOF
	<div class="video_section">
	<h3 class="section_name"><a href="$channel_link">$name</a> 
	<a href="$rss_link"><img src="images/rss_button.gif" alt="rss feed" border="0" /></a></h3>
EOF;

	$channel_files = $channel["Files"];
	if ( count($channel_files) > 0 ) {
  	$out .= "<ul>";

		usort($channel_files, "comp");
		$i=0;
		
		foreach ($channel_files as $file_arr) {
			$filehash = $file_arr[0];
			if ( isset($files[$filehash]) ) {
				$file = $files[$filehash];
			
				if ($file["Publishdate"] <= time()) {
					$out .= theme_display_video($filehash, $file, $channel);
					$i++;
				}
			}
		
			if ($i == 3) {
			 break;
			}
		}
		$out .= "</ul>";
	}

	$count = count($channel_files);

	$out .= <<<EOF
<div class="spacer_left">&nbsp;</div>
<div class="channel_more">
<a href="$channel_link">$count videos in this channel &gt;&gt;</a>
</div>
</div>
EOF;
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