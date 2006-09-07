<?php
/*
Name: DashBoard Hack
URI: http://blog.taragana.com/index.php/archive/wordpress-15-hack-how-to-trim-the-fat-resource-hogging-admin-dashboard-version-2/
Description: This hack trims the bloat from WordPress Admin DashBoard. It is a drop in replacement for wp-admin/index.php
Version: 1.2
Author: Angsuman Chakraborty
Author URI: http://blog.taragana.com/
*/
require_once('admin.php'); 
$title = __('Dashboard'); 
require_once('admin-header.php');
/* require_once (ABSPATH . WPINC . '/rss-functions.php'); */

$today = current_time('mysql', 1);
?>


<div id="zeitgeist">
<h2><?php _e('Activity'); ?></h2>
<?php
if ( $recentposts = $wpdb->get_results("SELECT ID, post_title FROM $wpdb->posts WHERE post_status = 'publish' AND post_date_gmt < '$today' ORDER BY post_date DESC LIMIT 5") ) :
?>
<div>
<h3><?php _e('Write'); ?> &raquo; </h3>
<a href="post.php" title="<?php _e('Post'); ?>"><?php _e('Post'); ?></a> / <a href="page-new.php" title="<?php _e('Page'); ?>"><?php _e('Page'); ?></a>
<h3><?php _e('Comments'); ?> &raquo; </h3>
<a href="edit-comments.php" title="<?php _e('Manage'); ?>"><?php _e('Manage'); ?></a>
<?php 
if ( $numcomments = $wpdb->get_var("SELECT COUNT(*) FROM $tablecomments WHERE comment_approved = '0'") ) :
?> / <a href="moderation.php"><?php echo sprintf(__('Moderate(%s)'), number_format($numcomments) ); ?></a>
<?php endif; ?>


<h3><?php _e('Latest Posts'); ?> <a href="edit.php" title="<?php _e('More posts...'); ?>">&raquo;</a></h3>
<ul>
<?php
foreach ($recentposts as $post) {
 if ($post->post_title == '')
  $post->post_title = sprintf(__('Post #%s'), $post->ID);
 echo "<li><a href='post.php?action=edit&amp;post=$post->ID'>";
 the_title();
?>    
</a>(<a href="<?php echo get_permalink($post->ID); ?>">view</a>)</li>
<?php
}
?>
</ul>
</div>
<?php endif; ?>

<?php
if ( $scheduled = $wpdb->get_results("SELECT ID, post_title, post_date_gmt FROM $wpdb->posts WHERE post_status = 'publish' AND post_date_gmt > '$today'") ) :
?> 
<div>
<h3><?php _e('Scheduled Entries:') ?></h3>
<ul>
<?php
foreach ($scheduled as $post) {
 if ($post->post_title == '')
  $post->post_title = sprintf(__('Post #%s'), $post->ID);
 echo "<li><a href='post.php?action=edit&amp;post=$post->ID' title='" . __('Edit this post') . "'>$post->post_title</a> in " . human_time_diff( current_time('timestamp', 1), strtotime($post->post_date_gmt) )  . "</li>";
}
?> 
</ul>
</div>
<?php endif; ?>

<?php
if ( $comments = $wpdb->get_results("SELECT comment_author, comment_author_url, comment_ID, comment_post_ID FROM $wpdb->comments WHERE comment_approved = '1' ORDER BY comment_date_gmt DESC LIMIT 5") ) :
?>
<h3><?php _e('Latest Comments'); ?> <a href="edit-comments.php" title="<?php _e('More comments...'); ?>">&raquo;</a></h3>
<ul>
<?php 
foreach ($comments as $comment) {
 echo '<li>' . sprintf('%s on %s', get_comment_author_link(), '<a href="'. get_permalink($comment->comment_post_ID) . '#comment-' . $comment->comment_ID . '">' . get_the_title($comment->comment_post_ID) . '</a>');
 edit_comment_link(__("Edit"), ' <small>(', ')</small>'); 
 echo '</li>';
}
?>
</ul>

</div>

<?php endif; ?>

<div>
<h3><?php _e('Blog Stats'); ?></h3>
<?php
$numposts = $wpdb->get_var("SELECT COUNT(*) FROM $wpdb->posts WHERE post_status = 'publish'");
if (0 < $numposts) $numposts = number_format($numposts); 

$numcomms = $wpdb->get_var("SELECT COUNT(*) FROM $wpdb->comments WHERE comment_approved = '1'");
if (0 < $numcomms) $numcomms = number_format($numcomms);

$numcats = $wpdb->get_var("SELECT COUNT(*) FROM $wpdb->categories");
if (0 < $numcats) $numcats = number_format($numcats);
?>
<p>There are currently <?php echo $numposts ?> <a href="edit.php" title="posts">posts</a> and <?php echo $numcomms ?> <a href="edit-comments.php" title="Comments">comments</a>, contained within <?php echo $numcats ?> <a href="categories.php" title="categories">categories</a>.</p>

<?php
$drafts = $wpdb->get_results("SELECT ID, post_title FROM $wpdb->posts WHERE post_status = 'draft' AND post_author = $user_ID");
if ($drafts) {
?>
<h3><?php _e('Drafts'); ?></h3>
<ul>
    <?php
 foreach ($drafts as $draft) {
  $draft->post_title = stripslashes($draft->post_title);
  if ($draft->post_title == '')
   $draft->post_title = sprintf(__('Post #%s'), $draft->ID);
  echo "<li><a href='post.php?action=edit&amp;post=$draft->ID' title='" . __('Edit this draft') . "'>$draft->post_title</a></li>";
  }
 ?>  
<?php } ?>
</ul>
</div>

<?php
$rss = @fetch_rss('http://feeds.technorati.com/cosmos/rss/?url='. trailingslashit(get_option('home')) .'&partner=wordpress');
if ( isset($rss->items) && 0 != count($rss->items) ) {
?>
<div id="incominglinks">
<h3><?php _e('Incoming Links'); ?> <cite><a href="http://www.technorati.com/cosmos/search.html?url=<?php echo trailingslashit(get_option('home')); ?>&amp;partner=wordpress"><?php _e('More'); ?> &raquo;</a></cite></h3>
<ul>
<?php
$rss->items = array_slice($rss->items, 0, 10);
foreach ($rss->items as $item ) {
?>
 <li><a href="<?php echo wp_filter_kses($item['link']); ?>"><?php echo wp_specialchars($item['title']); ?></a></li>
<?php } ?>
</ul>
</div>
<?php } ?>

<?php
require('./admin-footer.php');
?>
