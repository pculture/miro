<?php
if ( !function_exists("render_index_page") ) {
  function render_index_page() {
    global $store;
    $channels = $store->getAllChannels();
    $files = $store->getAllFiles();
    
    $out = array();
    foreach ($channels as $channel) {
      if ( ! isset($channel["NotPublic"]) || ! $channel["NotPublic"] || valid_user() ) {
	$out[] = theme_channel_summary_wrapper($channel, theme_channel_summary($channel, $files));
      } // if
    } // foreach

    front_header( site_description() );
    theme_page_wrapper( theme_index_wrapper( $out ) );
    front_footer();
  }
}


if ( !function_exists("render_channel_page") ) {
  function render_channel_page($channel, $files, $keyword = NULL) {
    $out = '<div class="channel">' .
      theme_channel_title($channel);

    if ( $keyword != NULL ) {
      $out .= theme_channel_keyword_header($channel, $keyword);
    }

    $out .= 
      theme_channel_videos($channel, $files, $keyword) .
      theme_channel_bar($channel) .
      '</div>';
    
    $out .= tags_for_files($files, $channel["Files"], $channel);
    
    front_header($channel["Name"], 
		 $channel["ID"], 
		 $channel["CSSURL"], 
		 rss_link($channel["ID"]) );
    
    print theme_channel_wrapper($out, $channel, false);
    
    front_footer($channel["ID"]);
  }
}

if ( !function_exists("render_detail_page") ) {
  function render_detail_page($file, $channel) {

    front_header($channel["Name"], $channel["ID"], $channel["CSSURL"], rss_link($channel["ID"]) );
    
    $out = theme_channel_header($channel, false) .
      theme_channel_bar($channel) .
      theme_detail_video_wrapper( $channel, $file, theme_detail_page($file, $channel) );

    theme_page_wrapper(
		       theme_detail_wrapper(
					    $out
					    )
		       );
				
    front_footer($channel["ID"]);
  }
}
?>