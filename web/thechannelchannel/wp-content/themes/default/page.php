<?php get_header(); ?>







<?php include("nav.php") ?>


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
	
	

</div>

<?php get_sidebar(); ?>

<?php get_footer(); ?>