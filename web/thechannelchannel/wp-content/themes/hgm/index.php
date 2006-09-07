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
<!-- PROMO AREA -->
<div id="promo">
<h2>A "virtual livingroom" of news from Iraq</h2>
<a href="http://www.showusthewar.com/av/showusthewartrailerfin.mov" class="redlink" target="_blank">&raquo; WATCH THE VIDEO INTRO TO LEARN MORE</a>
<br>
<a href="http://www.showusthewar.com/av/showusthewartrailerfin.mov" class="redlink" target="_blank">
<img src="/wp-content/themes/hgm/images/home_trailerpromo.jpg" border="0" alt="Show Us the War Intro Video"></a>
<br />
<a href="mailto:?subject=Check out this video&body=Check out this video: http://www.showusthewar.com/av/showusthewartrailerfin.mov">&raquo; Send your friends the link to the video</a><br />
<a href="/?page_id=60">&raquo; Donate now so we can keep showing you the war</a><br />
<a href="http://www.showusthewar.com/signup.html">&raquo; Sign  up for alerts on news and videos</a><br />
</div>
<!-- END PROMO -->

<!-- WORLD NEWS -->
<div id="worldnews">
	<h2>INTERNATIONAL PERSPECTIVES</h2>	
	<h3>Views from the Middle East</h3>
	<a href="http://www.worldlinktv.org/mosaic/streamsArchive/">
	<img src="/wp-content/themes/hgm/images/mosaic_graphic.jpg" border="0" align="left"></a>
	<div class="broughtby">brought to you by</div>
	<a href="http://www.worldlinktv.org/mosaic/index.php3"><strong>Link TV's Mosaic</strong></a><br>
	<strong>Peabody Award winning coverage </strong>
	<br><a href="http://www.worldlinktv.org/mosaic/streamsArchive/"> watch the stream &raquo;</a>
	<br/><br/>
    <?php $feed_item = getSomeFeed("http://www.worldlinktv.org/cgi/database/mosaic_rss.xml",
                                   1, false, "mosaic", '', -1, -1, true, false, 2, true);
          if ($feed_item) {
    ?>
	<div id="mosaicfeed"><strong>Today: </strong><?= $feed_item ?></div>
    <?php } ?>
</div>
<!-- END WORLD NEWS -->
<br clear="all">
<!-- BEGIN FEATURE AREA-->
<div id="feature">
<DIV ID="home-feature-left"><div class="copy">
	<?php query_posts('category_name=homefeatureleft&showposts=1'); ?>

	<?php if (have_posts()) : ?>
		
		<?php while (have_posts()) : the_post(); ?>


<?php if ( in_category('28') ) { ?>

<h2><a href="<?php the_permalink() ?>" rel="bookmark" title="Permanent Link to <?php the_title(); ?>"><?php the_title(); ?></a></h2>
<p><?php the_excerpt_reloaded(25, '', 'none', false); ?></p>
<a href="<?php the_permalink() ?>" rel="bookmark" title="Permanent Link to <?php the_title(); ?>">full story &raquo;</a>
		
 <?php } else { ?>



 <?php } ?>

		<?php endwhile; ?>


	<?php else : ?>


	<?php endif; ?>
	</div>
</DIV>
<DIV ID="home-feature-graphic">
	<IMG SRC="/wp-content/themes/hgm/images/home_feature_graphic.jpg" WIDTH=199 HEIGHT=149 ALT="" />
</DIV>
<DIV ID="home-feature-right">
	<div id="featureitem">

<?php query_posts('category_name=featured&showposts=1'); ?>

	<?php if (have_posts()) : ?>
		
		<?php while (have_posts()) : the_post(); ?>


<?php if ( in_category('6') ) { ?>

<h2><a href="<?php the_permalink() ?>" rel="bookmark" title="Permanent Link to <?php the_title(); ?>"><?php the_title(); ?></a><span class="byline">
<?php echo c2c_get_custom('byline'); ?>
</span>
</h2><span class="featuretext" style="margin-top: 0px; padding-top: 0px;"><p><?php the_excerpt_reloaded(25, '', 'none', false); ?></p></span>
<a href="<?php the_permalink() ?>" rel="bookmark" title="Permanent Link to <?php the_title(); ?>">full story &raquo;</a>
		
 <?php } else { ?>



 <?php } ?>

		<?php endwhile; ?>


	<?php else : ?>


	<?php endif; ?>
	
		</div>
</DIV>
</div>

<br clear="all" />



	

</div><br clear="all"/>
<div id="soldiers">
	<div id="soldierleft">
	<P> In their own words...soldiers show us the war...<br /><br/>
	<a href="/?cat=14">more soldiers' stories &raquo;</a></p>
	</div>
	<div id="homearearight">
		<div id="featureitem">		
		<?php query_posts('cat=14&orderby=date&order=DESC'); ?>

			<?php if (have_posts()) : ?>
		
				<?php while (have_posts()) : the_post(); ?>
				<?php if ( in_category('32') ) { ?>	
				<span id="homethumb"><a href="<?php the_permalink() ?>" rel="bookmark" title="Permanent Link to <?php the_title(); ?>"><?php if(c2c_get_custom('thumbnail') != '') { ?><img src="<?php echo c2c_get_custom('thumbnail'); ?>" /></a><?php } ?></span>
				<h2><a href="<?php the_permalink() ?>" rel="bookmark" title="Permanent Link to <?php the_title(); ?>"><?php the_title(); ?></a><span class="byline"> 
				<?php echo c2c_get_custom('byline'); ?></span></h2><p><?php the_excerpt_reloaded(25, '', 'none', false); ?></p>
				
				 <a href="<?php the_permalink() ?>" rel="bookmark" title="Permanent Link to <?php the_title(); ?>">full story &raquo;</a>		
 			<?php break; } else { ?>
			<?php } ?>
		<?php endwhile; ?>

	<?php else : ?>

	<?php endif; ?>	
		</div>
	</div>

</div>
<br clear="all" />
<div id="ontheground">
<div id="groundleft">
	<P> Filmmakers, Iraqis and journalists show us the war..<br /><br/>
	<a href="/?cat=8">more from on the ground &raquo;</a></p>
	</div>
	<div id="homearearight">
		<div id="featureitem">		
		<?php query_posts('cat=8&orderby=date&order=DESC'); ?>

			<?php if (have_posts()) : ?>
		
				<?php while (have_posts()) : the_post(); ?>
				<?php if ( in_category('32') ) { ?>	
				<span id="homethumb"><a href="<?php the_permalink() ?>" rel="bookmark" title="Permanent Link to <?php the_title(); ?>"><?php if(c2c_get_custom('thumbnail') != '') { ?><img src="<?php echo c2c_get_custom('thumbnail'); ?>" /></a><?php } ?></a></span>
				<h2><a href="<?php the_permalink() ?>" rel="bookmark" title="Permanent Link to <?php the_title(); ?>"><?php the_title(); ?></a><span class="byline"> 
				<?php echo c2c_get_custom('byline'); ?></span></h2>
				<p><?php the_excerpt_reloaded(25, '', 'none', false); ?></p>
				 <a href="<?php the_permalink() ?>" rel="bookmark" title="Permanent Link to <?php the_title(); ?>">full story &raquo;</a>		
 			<?php break; } else { ?>
			<?php } ?>
		<?php endwhile; ?>

	<?php else : ?>

	<?php endif; ?>	
		</div>
	</div>
</div>
<br clear="all" />
<div id="onourminds">
<div id="mindsleft">
	<P>Journalists, analysts, policy and opinion makers show us what they think about the war...<br /><br />
	<a href="/?cat=9">more from on our minds &raquo;</a></p>
	</div>
	<div id="homearearight">
		<div id="featureitem">		
		<?php query_posts('cat=9&orderby=date&order=DESC'); ?>

			<?php if (have_posts()) : ?>
		
				<?php while (have_posts()) : the_post(); ?>
				<?php if ( in_category('32') ) { ?>	
				<span id="homethumb"><a href="<?php the_permalink() ?>" rel="bookmark" title="Permanent Link to <?php the_title(); ?>"><?php if(c2c_get_custom('thumbnail') != '') { ?><img src="<?php echo c2c_get_custom('thumbnail'); ?>" /></a><?php } ?></a></span>
				<h2><a href="<?php the_permalink() ?>" rel="bookmark" title="Permanent Link to <?php the_title(); ?>"><?php the_title(); ?></a><span class="byline"> 
				<?php echo c2c_get_custom('byline'); ?></span></h2>
				<p><?php the_excerpt_reloaded(25, '', 'none', false); ?></p>
				 <a href="<?php the_permalink() ?>" rel="bookmark" title="Permanent Link to <?php the_title(); ?>">full story &raquo;</a>		
 			<?php break; } else { ?>
			<?php } ?>
		<?php endwhile; ?>

	<?php else : ?>

	<?php endif; ?>	
		</div>
	</div>
</div>
<br clear="all" />
<div id="ontheweb">
<div id="webleft">
	<P>Podcasts, blogs, news, first person accounts...show us the war 
<br /><br />
	<a href="/?cat=10">more from on the web &raquo;</a></p>
	</div>
	<div id="homearearight">
		<div id="featureitem">		
		<?php query_posts('cat=10&showposts=1&orderby=date&order=DESC'); ?>

			<?php if (have_posts()) : ?>
		
				<?php while (have_posts()) : the_post(); ?>
				<?php if ( in_category('32') ) { ?>	
				<span id="homethumb"><a href="<?php the_permalink() ?>" rel="bookmark" title="Permanent Link to <?php the_title(); ?>"><?php if(c2c_get_custom('thumbnail') != '') { ?><img src="<?php echo c2c_get_custom('thumbnail'); ?>" /></a><?php } ?></a> </span>
				<h2><a href="<?php the_permalink() ?>" rel="bookmark" title="Permanent Link to <?php the_title(); ?>"><?php the_title(); ?></a><span class="byline"> 
				<?php echo c2c_get_custom('byline'); ?></span></h2>
				<p><?php the_excerpt_reloaded(25, '', 'none', false); ?></p>
				 <a href="<?php the_permalink() ?>" rel="bookmark" title="Permanent Link to <?php the_title(); ?>">full story &raquo;</a>		
 			<?php break; } else { ?>
			<?php } ?>
		<?php endwhile; ?>

	<?php else : ?>

	<?php endif; ?>	
		</div>
	</div>
</div>
<br clear="all" />
<!--END MAIN BODY -->
			</td>
		<td class="rightcolumn">
			<img src="/wp-content/themes/hgm/images/spacer.gif" width="82" height="1023" alt=""></td>
	</tr>


<pclass="footer"><?php get_footer(); ?></p>
