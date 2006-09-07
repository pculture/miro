<?php get_header(); ?>





   <?php if (have_posts()) : while (have_posts()) : the_post(); ?>

				<?php the_content('<p class="serif">Read the rest of this page &raquo;</p>'); ?>
	
				<?php link_pages('<p><strong>Pages:</strong> ', '</p>', 'number'); ?>
	
	  <?php endwhile; endif; ?>
	<?php edit_post_link('Edit this entry.', '<p>', '</p>'); ?>

	
  
     
    
    
  </div>
  <hr />


<?php include (TEMPLATEPATH . '/sidebar.php'); ?>


</div>
</body>
</html>
