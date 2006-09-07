<?php get_header(); ?>


<?php get_sidebar(); ?>


<?php include("nav.php") ?>


<div id="inner_content">



<div id="exclusive_articles">


<h2>Articles</h2>


<?php query_posts('category_name=exclusive-articles&showposts=6');Ê?>

	<?php if (have_posts()) : ?>
		
		<?php while (have_posts()) : the_post(); ?>


<?php if ( in_category('3') ) { ?>

<div class="exclusive_article">

<h2><a href="<?php the_permalink() ?>" rel="bookmark" title="Permanent Link to <?php the_title(); ?>"><?php the_title(); ?></a> <span class="byline">
<?php echo c2c_get_custom('byline'); ?>
</span>
</h2>


<div class="article_excerpt">
<span class="date"><?php the_time('F j') ?>:</span> <?php the_excerpt(); ?>
</div>


</div>

<?php } else { ?>
 <?php } ?>
		<?php endwhile; ?>
	<?php else : ?>
	<?php endif; ?>

	<a href="<?php bloginfo('home'); ?>/?cat=3">More Articles >></a>

	</div>

<div id="video_zone">

<h2>Videos</h2>

<?php query_posts('category_name=Videos&showposts=5');Ê?>

	<?php if (have_posts()) : ?>
		<?php while (have_posts()) : the_post(); ?>
		<?php if ( in_category('1') ) { ?>

			<div class="post" id="post-<?php the_ID(); ?>">
				
				<div class="thumbnail_hover">
							
				<a href="<?php the_permalink() ?>" rel="bookmark" title="Permanent Link to <?php the_title(); ?>"><img src="<?php echo c2c_get_custom('thumbnail'); ?>" /></a><br />
				<a style="color:#333; font-size: 10px;" href="<?php the_permalink() ?>" rel="bookmark" title="Permanent Link to <?php the_title(); ?>">click to watch</a>
				
				</div>
				
				<h2><a href="<?php the_permalink() ?>" rel="bookmark" title="Permanent Link to <?php the_title(); ?>"><?php the_title(); ?></a> 		<span class="byline">
		<?php echo c2c_get_custom('byline'); ?>
		</span>
</h2>
		
		
		
		<div class="article_excerpt">
		<span class="date"><?php the_time('F j, Y') ?>:</span> <?php the_excerpt(); ?>
		</div>
				
				<div class="comments">	
				<?php comments_popup_link('Add a Comment &#187;', '1 Comment', '% Comments'); ?> <!-- by <?php the_author() ?> --> <?php edit_post_link('Edit', '', ''); ?> 			</div>
				
		
			</div>
			
			<br style="clear: both; height: 1px;" />
			
 <?php } else { ?>
 <?php } ?>
		<?php endwhile; ?>
<br />
	<a href="<?php bloginfo('home'); ?>/?cat=1">More Videos >></a>


         </div>
	<?php else : ?>
		<h2 class="center">Not Found</h2>
		<p class="center">Sorry, but you are looking for something that isn't here.</p>
		<?php include (TEMPLATEPATH . "/searchform.php"); ?>
	<?php endif; ?>
	
	
	
</div>

<br style="clear:both;" />



<div class="lower_boxes">



<h2>Photos and Audio</h2>
<?php query_posts('category_name=photos-and-audio&showposts=3');Ê?>

	<?php if (have_posts()) : ?>
		<?php while (have_posts()) : the_post(); ?>
		<?php if ( in_category('4') ) { ?>

			<div class="post" id="post-<?php the_ID(); ?>">
				
				<div class="photo_thumbnail_hover">
							
				<a href="<?php the_permalink() ?>" rel="bookmark" title="Permanent Link to <?php the_title(); ?>"><img src="<?php echo c2c_get_custom('thumbnail'); ?>" /></a>
				
				</div>
				
				<h2><a href="<?php the_permalink() ?>" rel="bookmark" title="Permanent Link to <?php the_title(); ?>"><?php the_title(); ?></a></h2>
		
		
		<!--
		
		<div class="byline">
		<?php echo c2c_get_custom('byline'); ?>
		</div>
		
		
		<div class="article_excerpt">
		<?php the_excerpt(); ?>
		</div>
			
			
		-->	
			
				
		
			</div>
 <?php } else { ?>
 <?php } ?>
		<?php endwhile; ?>
         
	<?php else : ?>
		<h2 class="center">Not Found</h2>
		<p class="center">Sorry, but you are looking for something that isn't here.</p>
		<?php include (TEMPLATEPATH . "/searchform.php"); ?>
	<?php endif; ?>


	<a href="<?php bloginfo('home'); ?>/?cat=4">More Photos and Audio >></a>


</div>


<div class="lower_boxes">

<h2>How to Show Us the War</h2>

<p>
If you have video that you would like to present on Show Us the War, it needs to be hosted on revver.com (Revver hosts videos for us).  To do so, <a href="http://www.revver.com/signUp/">create a Revver account</a> and upload your video file (tag it as 'SUTW').  Then send us an email to editors@showusthewar.com that includes: the name of the video, a link to the video file, a link to the thumbnail for the video, a brief description, and a byline. We review every submission we receive.   
</p>



</div>



<br style="clear:both;" />





	</div>








<?php get_footer(); ?>
