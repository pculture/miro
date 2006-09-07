<?php get_header(); ?>
<tr >
		<td bgcolor="#666666" height="25">
			<img src="/wp-content/themes/hgm/images/spacer.gif" width="200" height="25" alt=""></td>
		<td bgcolor="#666666">
<!-- NAV include -->		
<?php include("nav.php") ?>

			</td>
		<td class="rightcolumn">
			<img src="/wp-content/themes/hgm/images/spacer.gif" width="82" height="25" alt=""></td>
	</tr>

<tr valign="top">

	<td class="leftcolumn"  background="/wp-content/themes/hgm/images/leftcol_bg.gif">

<!-- SIDEBAR include -->
<?php get_sidebar(); ?>
	</td>
		<td bgcolor="#FFFFFF" valign="top">
<!-- BEGIN MAIN BODY AREA-->
<div id="inner_content">
<h2> Browse by Media Type </h2>
For your convenience you can also browse through <strong>Show Us the War</strong> archives by media type. For links to the good stuff we have found on the Web, please see the <a  href="/?cat=10">"on the web"</a> .<P><br>


<h2><a href="/?cat=1">Videos</a></h2>

<?php
  $tempposts = get_posts('numberposts=3&category=1');
  foreach($tempposts as $post) :
?>
                <div class="post">
		   <?php if(c2c_get_custom('thumbnail') != '') { ?>
                     <div class="photo_thumbnail_hover">
                       <a href="<?php the_permalink() ?>" rel="bookmark" title="Permanent Link to <?php the_title(); ?>"><img src="<?php echo c2c_get_custom('thumbnail'); ?>" /></a>
                     </div>
                   <?php } ?>
															                        <a href="<?php the_permalink() ?>" rel="bookmark" title="Permanent Link to <?php the_title(); ?>"><?php the_title(); ?></a>
               </div>
<?php endforeach; ?>
<br>

<h2><a href="/?cat=3">Articles</a></h2>

<?php
  $tempposts = get_posts('numberposts=3&category=3');
  foreach($tempposts as $post) :
?>
                <div class="post">
		   <?php if(c2c_get_custom('thumbnail') != '') { ?>
                     <div class="photo_thumbnail_hover">
                       <a href="<?php the_permalink() ?>" rel="bookmark" title="Permanent Link to <?php the_title(); ?>"><img src="<?php echo c2c_get_custom('thumbnail'); ?>" /></a>
                     </div>
                   <?php } ?>
															                         <a href="<?php the_permalink() ?>" rel="bookmark" title="Permanent Link to <?php the_title(); ?>"><?php the_title(); ?></a>
               </div>
<?php endforeach; ?>
<br>

<h2><a href="/?cat=4">Photos</a></h2>

<?php
  $tempposts = get_posts('numberposts=3&category=4');
  foreach($tempposts as $post) :
?>
                <div class="post">
		   <?php if(c2c_get_custom('thumbnail') != '') { ?>
                     <div class="photo_thumbnail_hover">
                       <a href="<?php the_permalink() ?>" rel="bookmark" title="Permanent Link to <?php the_title(); ?>"><img src="<?php echo c2c_get_custom('thumbnail'); ?>" /></a>
                     </div>
                   <?php } ?>
															                        <a href="<?php the_permalink() ?>" rel="bookmark" title="Permanent Link to <?php the_title(); ?>"><?php the_title(); ?></a>
               </div>
<?php endforeach; ?>
<br>
<h2><a href="/?cat=17">Audio</a></h2>

<?php
  $tempposts = get_posts('numberposts=3&category=17');
  foreach($tempposts as $post) :
?>
                <div class="post">
		   <?php if(c2c_get_custom('thumbnail') != '') { ?>
                     <div class="photo_thumbnail_hover">
                       <a href="<?php the_permalink() ?>" rel="bookmark" title="Permanent Link to <?php the_title(); ?>"><img src="<?php echo c2c_get_custom('thumbnail'); ?>" /></a>
                     </div>
                   <?php } ?>
															                         <a href="<?php the_permalink() ?>" rel="bookmark" title="Permanent Link to <?php the_title(); ?>"><?php the_title(); ?></a>
               </div>
<?php endforeach; ?>

</div>

<!--END MAIN BODY -->
			</td>
		<td class="rightcolumn">
			<img src="/wp-content/themes/hgm/images/spacer.gif" width="82" height="1023" alt=""></td>
	</tr>


<pclass="footer"><?php get_footer(); ?></p>
