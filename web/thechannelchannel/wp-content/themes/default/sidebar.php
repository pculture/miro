	<div id="sidebar">
			

			<?php /* If this is a 404 page */ if (is_404()) { ?>
			<?php /* If this is a category archive */ } elseif (is_category()) { ?>
			<p>You are currently browsing the archives for the <?php single_cat_title(''); ?> category.</p>
			
			<?php /* If this is a yearly archive */ } elseif (is_day()) { ?>
			<p>You are currently browsing the <a href="<?php bloginfo('home'); ?>/"><?php echo bloginfo('name'); ?></a> weblog archives
			for the day <?php the_time('l, F jS, Y'); ?>.</p>
			
			<?php /* If this is a monthly archive */ } elseif (is_month()) { ?>
			<p>You are currently browsing the <a href="<?php bloginfo('home'); ?>/"><?php echo bloginfo('name'); ?></a> weblog archives
			for <?php the_time('F, Y'); ?>.</p>

      <?php /* If this is a yearly archive */ } elseif (is_year()) { ?>
			<p>You are currently browsing the <a href="<?php bloginfo('home'); ?>/"><?php echo bloginfo('name'); ?></a> weblog archives
			for the year <?php the_time('Y'); ?>.</p>
			
		 <?php /* If this is a monthly archive */ } elseif (is_search()) { ?>
			<p>You have searched the <a href="<?php echo bloginfo('home'); ?>/"><?php echo bloginfo('name'); ?></a> weblog archives
			for <strong>'<?php echo wp_specialchars($s); ?>'</strong>. If you are unable to find anything in these search results, you can try one of these links.</p>

			<?php /* If this is a monthly archive */ } elseif (isset($_GET['paged']) && !empty($_GET['paged'])) { ?>
			<p>You are currently browsing the <a href="<?php echo bloginfo('home'); ?>/"><?php echo bloginfo('name'); ?></a> weblog archives.</p>

			<?php } ?>



<!--
	<?php wp_list_pages('title_li=<h2>Pages</h2>' ); ?>
-->

<h2>Exclusive</h2> 
 
 <p>
<img src="/feature_images/chasing_ghosts_small.jpg" />
<br /><br />
<img src="/feature_images/plougshareslogo.jpg" />
<br /><br />
<img src="/feature_images/young_turks.jpg" />
<br />

- Joe Cirincionne
<br />
- graphic for GQ interview
<br />
- Brave Photo Journalist exclusive
	</p>


<h2>Partners</h2> 

<div class="partners">

<p><a href="http://www.ploughshares.org/">Ploughshares</a></p>
<p><a href="http://www.washingtonmonthly.com/">The Washington Monthly</a></p>
<p><a href="http://www.motherjones.com/">Mother Jones</a></p>
<p><a href="http://www.inthesetimes.com/">In These Times</a></p>
<p><a href="http://www.freespeech.org/">FreeSpeech TV</a></p>
<p><a href="http://www.huffingtonpost.com/">The Huffington Post</a></p>
<p><a href="http://www.revver.com/">Revver.com</a></p>
<p><a href="http://www.participatoryculture.org">Participatory Culture</a></p>
<p>and dedicated independent media makers across the world</p>

</div>
 

<h2>Weekly Podcasts</h2> 



<?php query_posts('category_name=podcast-links&showposts=6');Ê?>

	<?php if (have_posts()) : ?>
		
		<?php while (have_posts()) : the_post(); ?>


<?php if ( in_category('7') ) { ?>



		
<div class="publication_name">
<?php the_title(); ?>
</div>

<div class="news_link">
<?php the_time('F j') ?>: <?php the_content('Read the rest of this entry &raquo;'); ?>
</div>
		
		

 <?php } else { ?>



 <?php } ?>

		<?php endwhile; ?>


	<?php else : ?>


	<?php endif; ?>
	

<br /><Br />



<h2>News Stream</h2> 
 

<?php query_posts('category_name=news-links&showposts=6');Ê?>

	<?php if (have_posts()) : ?>
		
		<?php while (have_posts()) : the_post(); ?>


<?php if ( in_category('2') ) { ?>



		
<div class="publication_name">
<?php the_title(); ?>
</div>

<div class="news_link">
<?php the_time('F j') ?>: <?php the_content('Read the rest of this entry &raquo;'); ?>
</div>
		
		

 <?php } else { ?>



 <?php } ?>

		<?php endwhile; ?>


	<?php else : ?>


	<?php endif; ?>
	

<br /><Br />
	<h2>Archives</h2>
				<?php wp_get_archives('type=monthly'); ?>
	




			<?php /* If this is the frontpage */ if ( is_home() || is_page() ) { ?>						




				

				
				
				
		
				
	<!--	
	
	
						<?php get_links_list(); ?>

	

				
							<li><h2>Categories</h2>
				<ul>
				<?php wp_list_cats('sort_column=name&optioncount=1&hierarchical=0'); ?>
				</ul>
			</li>


				
<li>
<a href="feed:<?php bloginfo('rss2_url'); ?>">Entries (RSS)</a>
		and <a href="feed:<?php bloginfo('comments_rss2_url'); ?>">Comments (RSS)</a>.</li>
				
				
				<li><h2>Meta</h2>
				<ul>
					<?php wp_register(); ?>
					<li><?php wp_loginout(); ?></li>
					<li><a href="http://validator.w3.org/check/referer" title="This page validates as XHTML 1.0 Transitional">Valid <abbr title="eXtensible HyperText Markup Language">XHTML</abbr></a></li>
					<li><a href="http://gmpg.org/xfn/"><abbr title="XHTML Friends Network">XFN</abbr></a></li>
					<li><a href="http://wordpress.org/" title="Powered by WordPress, state-of-the-art semantic personal publishing platform.">WordPress</a></li>
					<?php wp_meta(); ?>
				</ul>
				</li>
		-->
		
		
		<?php } ?>
			
	</div>

