<?php get_header(); ?>



    
    <!-- BEGIN MAIN BODY AREA-->

		<?php if (have_posts()) : ?>

		 <?php $post = $posts[0]; // Hack. Set $post so that the_date() works. ?>
<?php /* If this is a category archive */ if (is_category(1)) { ?>				
		<h2 class="pagetitle"><?php echo single_cat_title(); ?></h2>
		
 	  <?php /* If this is a daily archive */ } elseif (is_day()) { ?>
		<h2 class="pagetitle">Archive for <?php the_time('F jS, Y'); ?></h2>
		
	 <?php /* If this is a monthly archive */ } elseif (is_month()) { ?>
		<h2 class="pagetitle">Archive for <?php the_time('F, Y'); ?></h2>

		<?php /* If this is a yearly archive */ } elseif (is_year()) { ?>
		<h2 class="pagetitle">Archive for <?php the_time('Y'); ?></h2>
		
	  <?php /* If this is a search */ } elseif (is_search()) { ?>
		<h2 class="pagetitle">Search Results</h2>
		
	  <?php /* If this is an author archive */ } elseif (is_author()) { ?>
		<h2 class="pagetitle">Author Archive</h2>

		<?php /* If this is a paged archive */ } elseif (isset($_GET['paged']) && !empty($_GET['paged'])) { ?>
		<h2 class="pagetitle">Blog Archives</h2>

		<?php } ?>


		<div class="navigation">
			<div class="alignleft"><?php next_posts_link('&laquo; Previous Entries') ?></div>
			<div class="alignright"><?php previous_posts_link('Next Entries &raquo;') ?></div>
		</div>

		<?php while (have_posts()) : the_post(); ?>

<div class="preview">
      <?php if(c2c_get_custom('thumbnail') != '') { ?>
      <div class="video"> <a href="<?php the_permalink() ?>" rel="bookmark" title="Permanent Link to <?php the_title(); ?>"><img src="<?php echo c2c_get_custom('thumbnail'); ?>" /></a> <a href="<?php the_permalink() ?>" class="play"><img src="/wp-content/themes/channelchannel/images/buttons/play.png" alt="Play" width="40" height="40" /></a> </div>
      <?php } ?>
      <h2><a href="<?php the_permalink() ?>" rel="bookmark" title="Permanent Link to <?php the_title(); ?>"><?php the_title(); ?></a></h2>
      <p class="source"><?php echo c2c_get_custom('byline'); ?></p>
      <p class="date"><strong><?php the_time('F j, Y') ?></strong> <?php comments_popup_link('Add a Comment &#187;', '1 Comment', '% Comments'); ?></p> 
      <span class="desc"><?php the_excerpt(); ?></span>
      <p><a href="#"><img src="/wp-content/themes/channelchannel/images/buttons/democracy.gif" alt="+ Democracy" width="85" height="16" /></a> <a href="#"><img src="/wp-content/themes/channelchannel/images/buttons/rss.gif" alt="RSS" width="16" height="16" /></a></p>
    </div>                   
	<?php endwhile; ?>

		<div class="navigation">
			<div class="alignleft"><?php next_posts_link('&laquo; Previous Entries') ?></div>
			<div class="alignright"><?php previous_posts_link('Next Entries &raquo;') ?></div>
		</div>
	<?php else : ?>
		<h2 class="center">Not Found</h2>
		<?php include (TEMPLATEPATH . '/searchform.php'); ?>
	<?php endif; ?>
		

<!--END MAIN BODY -->
    
    
     
    
    
  </div>
  <hr />


<?php include (TEMPLATEPATH . '/sidebar.php'); ?>


</div>
</body>
</html>
