<?php
/*
Plugin Name: Tiger Style Administration
Plugin URI: http://orderedlist.com/wordpress-plugins/wp-tiger-administration/
Description: After working with WordPress for several months now, I felt the Administration area needed a little "freshening up". I wanted the utility to feel more like an application, and less like a traditional website.
Author: Steve Smith
Version: 2.01
Author URI: http://www.orderedlist.com/
*/ 

function wp_admin_tiger_css() {
	echo '<link rel="stylesheet" type="text/css" href="' . get_settings('siteurl') . '/wp-content/plugins/wp-admin-tiger/wp-admin-tiger_files/wp-admin.css" />';
}

add_action('admin_head', 'wp_admin_tiger_css');

?>