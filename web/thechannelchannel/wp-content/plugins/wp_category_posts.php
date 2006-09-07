<?php
/*
Plugin Name: WP Category Posts
Plugin URI: http://watershedstudio.com/portfolio/software/wp-category-posts.html
Description: List the posts in a specific category
Author: Brian Groce
Version: 1.0
Author URI: http://briangroce.com/
*/ 

function wp_cat_posts( $catID ) {
	
	global $wpdb;

		$get_posts_in_cat = "SELECT $wpdb->posts.ID, $wpdb->posts.post_title, ";
		$get_posts_in_cat .= "$wpdb->post2cat.post_id, $wpdb->post2cat.category_id ";	
		$get_posts_in_cat .= "FROM $wpdb->posts, $wpdb->post2cat ";
		$get_posts_in_cat .= "WHERE $wpdb->posts.ID = $wpdb->post2cat.post_ID ";
		$get_posts_in_cat .= "AND $wpdb->post2cat.category_id = '$catID' ";
		$get_posts_in_cat .= "AND $wpdb->posts.post_status = 'publish' ";
		$get_posts_in_cat .= "ORDER BY $wpdb->posts.post_title ";
				
		$get_posts_in_cat_result = mysql_query($get_posts_in_cat);

	while ($posts_in_cat_row = mysql_fetch_assoc($get_posts_in_cat_result)) {	
	  $post_title = $posts_in_cat_row['post_title'];
		$postID = $posts_in_cat_row['ID'];	
				
		echo '<a href="' . get_permalink($postID) . '">' . $post_title . '</a><br />';		
		}		
}

?>