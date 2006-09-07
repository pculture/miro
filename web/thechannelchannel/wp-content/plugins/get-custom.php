<?php
/*
Plugin Name: Get Custom Field Values
Version: 2.1
Plugin URI: http://www.coffee2code.com/wp-plugins/
Author: Scott Reilly
Author URI: http://www.coffee2code.com
Description: Easily retrieve and control the display of any custom field values/meta data for posts, inside or outside "the loop".  The power of custom fields gives this plugin the potential to be dozens of plugins all rolled into one.

=>> Visit the plugin's homepage for more information and latest updates  <<=

Installation:

1. Download the file http://www.coffee2code.com/wp-plugins/get-custom.zip and unzip it into your 
wp-content/plugins/ directory.
-OR-
Copy and paste the contents of http://www.coffee2code.com/wp-plugins/get-custom.phps into a file 
called get-custom.php, and put that file into your wp-content/plugins/ directory.

2. Optional: Add filters for 'the_meta' to filter custom field data (see the end of the file for 
commented out samples you may wish to include).  *NEW*: Add per-meta filters by hooking 'the_meta_$field'

3. Activate the plugin from your WordPress admin 'Plugins' page.

4. Give a post a custom field with a value.

5. Use the function c2c_get_custom somewhere inside "the loop" and/or use the function c2c_get_recent_custom
outside "the loop"; use 'echo' to display the contents of the custom field; or use as an argument to 
another function


Function arguments:
    $field	: This is the name of the custom field you wish to display
    $before	: The text to display before all field value(s)
    $after	: The text to display after all field value(s)
    $none	: The text to display in place of the field value should no field value exists; if defined as ''
    		and no field value exists, then nothing (including no $before and $after) gets displayed
    $between 	: The text to display between multiple occurrences of the custom field; if defined as '', then
    		only the first instance will be used
    $before_last: The text to display between the next-to-last and last items listed when multiple occurrences of
    		the custom field; $between MUST be set to something other than '' for this to take effect
    
Additional arguments used by c2c_get_recent_custom():
   $limit	: The limit to the number of 
   $unique	: Boolean ('true' or 'false') to indicate if each custom field value in the results should be unique
   $order	: Indicates if the results should be sorted in chronological order ('ASC') (the earliest custom field value
   		listed first), or reverse chronological order ('DESC') (the most recent custom field value listed first)
   $include_static : Boolean ('true' or 'false') to indicate if static posts (i.e. "pages) should be included when
   		retrieving recent custom values; default is 'true'
   $show_pass_post : Boolean ('true' or 'false') to indicate if password protected posts should be included when 
   		retrieving recent custom values; default is 'false'
		
Examples: (visit the plugin's homepage for more examples)

	<?php echo c2c_get_custom('mymood'); ?>  // with this simple invocation, you can echo the value of any metadata field
	
	<?php echo c2c_get_custom('mymood', 'Today's moods: ', '', ', '); ?>
	
	<?php echo c2c_get_recent_custom('mymood', 'Most recent mood: '); ?>
	
	<?php echo c2c_get_custom('mymood', '(Current mood: ', ')', ''); ?>
	
	<?php echo c2c_get_custom('mylisten', 'Listening to : ', '', 'No one at the moment.'); ?>
	
	<?php echo c2c_get_custom('myread', 'I\'ve been reading ', ', if you must know.', 'nothing'); ?>
	
	<?php echo c2c_get_custom('todays_link', '<a class="tlink" href="', '" >Today\'s Link</a>'); ?>
	
	<?php echo c2c_get_custom('related_offsite_links', 
		   'Here\'s a list of offsite links related to this post:<ol><li><a href="',
		   '">Related</a></li></ol>',
		   '',
		   '">Related</a></li><li><a href="'); ?>
	
	<?php echo c2c_get_custom('more_pictures',
		   'Pictures I\'ve taken today:<br /><div class="more_pictures"><img alt="[photo]" src="',
		   '" /></div>',
		   '',
		   '" /> : <img alt="[photo]" src="'); ?>

	Custom 'more...' link text, by replacing <?php the_content(); ?> in index.php with this:
	<?php the_content(c2c_get_custom('more', '<span class="morelink">', '</span>', '(more...)')); ?>
	
*/

/*
Copyright (c) 2004-2005 by Scott Reilly (aka coffee2code)

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation 
files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, 
modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the 
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR
IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
*/

if (!isset($wpdb->posts)) {	// For WP 1.2 compatibility
	global $tableposts, $tablepostmeta;
	$wpdb->posts = $tableposts;
	$wpdb->postmeta = $tablepostmeta;
}

// This works inside "the loop"
function c2c_get_custom ($field, $before='', $after='', $none='', $between='', $before_last='') {
	return c2c__format_custom($field, (array)get_post_custom_values($field), $before, $after, $none, $between, $before_last);
} //end c2c_get_custom()

// This works outside "the loop"
function c2c_get_recent_custom ($field, $before='', $after='', $none='', $between=', ', $before_last='', $limit=1, $unique=false, $order='DESC', $include_static=true, $show_pass_post=false) {
	global $wpdb;
	if (empty($between)) $limit = 1;
	if ($order != 'ASC') $order = 'DESC';
	$now = current_time('mysql');

	$sql = "SELECT ";
	if ($unique) $sql .= "DISTINCT ";
	$sql .= "meta_value FROM $wpdb->posts AS posts, $wpdb->postmeta AS postmeta ";
	$sql .= "WHERE posts.ID = postmeta.post_id AND postmeta.meta_key = '$field' ";
	$sql .= "AND ( posts.post_status = 'publish' ";
	if ($include_static) $sql .= " OR posts.post_status = 'static' ";
	$sql .= " ) AND posts.post_date < '$now' ";
	if (!$show_pass_post) $sql .= "AND posts.post_password = '' ";
	$sql .= "AND postmeta.meta_value != '' ";
	$sql .= "ORDER BY posts.post_date $order LIMIT $limit";
	$results = array(); $values = array();
	$results = $wpdb->get_results($sql);
	if (!empty($results))
		foreach ($results as $result) { $values[] = $result->meta_value; };
	return c2c__format_custom($field, $values, $before, $after, $none, $between, $before_last);
} //end c2c_get_recent_custom()

/* Helper function */
function c2c__format_custom ($field, $meta_values, $before='', $after='', $none='', $between='', $before_last='') {
	$values = array();
	if (empty($between)) $meta_values = array_slice($meta_values,0,1);
	if (!empty($meta_values))
		foreach ($meta_values as $meta) {
			$meta = apply_filters("the_meta_$field", $meta);
			$values[] = apply_filters('the_meta', $meta);
		}

	if (empty($values)) $value = '';
	else {
		$values = array_map('trim', $values);
		if (empty($before_last)) $value = implode($values, $between);
		else {
			switch ($size = sizeof($values)) {
				case 1:
					$value = $values[0];
					break;
				case 2:
					$value = $values[0] . $before_last . $values[1];
					break;
				default:
					$value = implode(array_slice($values,0,$size-1), $between) . $before_last . $values[$size-1];
			}
		}
	}
	if (empty($value)) {
		if (empty($none)) return;
		$value = $none;
	}
	return $before . $value . $after;
} //end c2c__format_custom()

// Some filters you may wish to perform: (these are filters typically done to 'the_content' (post content))
//add_filter('the_meta', 'convert_chars');
//add_filter('the_meta', 'wptexturize');

// Other optional filters (you would need to obtain and activate these plugins before trying to use these)
//add_filter('the_meta', 'c2c_hyperlink_urls', 9);
//add_filter('the_meta', 'text_replace', 2);
//add_filter('the_meta', 'textile', 6);

?>