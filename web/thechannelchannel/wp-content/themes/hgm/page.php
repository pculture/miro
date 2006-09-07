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

    <?php if (have_posts()) : while (have_posts()) : the_post(); ?>
		<div class="post" id="post-<?php the_ID(); ?>">
		<h2><?php the_title(); ?></h2>
			<div class="entrytext">
				<?php the_content('<p class="serif">Read the rest of this page &raquo;</p>'); ?>
	
				<?php link_pages('<p><strong>Pages:</strong> ', '</p>', 'number'); ?>
	
			</div>
		</div>
	  <?php endwhile; endif; ?>
	<?php edit_post_link('Edit this entry.', '<p>', '</p>'); ?>
</div>
<!--END MAIN BODY -->
			</td>
		<td class="rightcolumn">
			<img src="/wp-content/themes/hgm/images/spacer.gif" width="82" height="1023" alt=""></td>
	</tr>


<pclass="footer"><?php get_footer(); ?></p>