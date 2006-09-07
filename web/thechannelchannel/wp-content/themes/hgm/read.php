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
		<td bgcolor="#FFFFFF" valign="top"><div id="inner_content">
<!-- BEGIN MAIN BODY AREA-->



<h2>Exclusive Articles</h2>


<?php query_posts('category_name=exclusive-articles&showposts=30');�?>

	<?php if (have_posts()) : ?>
		
		<?php while (have_posts()) : the_post(); ?>


<?php if ( in_category('3') ) { ?>

<div class="exclusive_article">

<h2><a href="<?php the_permalink() ?>" rel="bookmark" title="Permanent Link to <?php the_title(); ?>"><?php the_title(); ?></a></h2>

<div class="byline">
<?php the_time('F j') ?> - <?php echo c2c_get_custom('byline'); ?>
</div>

<div class="article_excerpt">
<?php the_excerpt(); ?>
</div>


</div>

<?php } else { ?>
 <?php } ?>
		<?php endwhile; ?>
	<?php else : ?>
	<?php endif; ?>


</div>


<!--END MAIN BODY -->
			</td></div>
		<td class="rightcolumn">
			<img src="/wp-content/themes/hgm/images/spacer.gif" width="82" height="1023" alt=""></td>
	</tr>


<pclass="footer"><?php get_footer(); ?></p>


