<?php get_header(); ?>







<?php include("nav.php") ?>


<div id="inner_content">


				
  <?php if (have_posts()) : while (have_posts()) : the_post(); ?>
	
	
<div class="post" id="post-<?php the_ID(); ?>">

	<!--
		<div class="navigation">
			<div class="alignleft"><?php previous_post_link('&laquo; %link') ?></div>
			<div class="alignright"><?php next_post_link('%link &raquo;') ?></div>
		</div>

         -->

				
				
  <?php if (in_category('1')) { ?>
  <!--  VIDEO  -->
				
				
				
				
<div class="embedded_video">

								<h2><?php the_title(); ?></h2>


				<object codebase="http://www.apple.com/qtactivex/qtplugin.cab" width="480" classid="clsid:02BF25D5-8C17-4B23-BC80-D3488ABDDC6B" height="376"><param name="src" value="<?php echo c2c_get_custom('video'); ?>" /><param name="controller" value="True" /><param name="cache" value="False" /><param name="autoplay" value="False" /><param name="kioskmode" value="False" /><param name="scale" value="tofit" /><embed src="<?php echo c2c_get_custom('video'); ?>" pluginspage="http://www.apple.com/quicktime/download/" scale="tofit" kioskmode="False" qtsrc="<?php echo c2c_get_custom('video'); ?>" cache="False" height="376" width="480" controller="True" type="video/quicktime" autoplay="False"></embed></object>

</div>
				
				
				
				
				
		<div class="byline">
		<?php echo c2c_get_custom('byline'); ?>
		</div>
		
		
				<div class="entry">
			
		<?php the_content('Read the rest of this entry &raquo;'); ?>
				</div>
				
				<div class="date_details">	
				<?php the_time('F j, Y') ?> at <?php the_time('h:mA') ?>
				</div>
				

<p><strong>POST THIS VIDEO TO YOUR BLOG:</strong><br />
<textarea style="margin-left: 6px;" rows="10" cols="60" onclick="this.focus();this.select()" title="Right Click and Select Copy"><object codebase="http://www.apple.com/qtactivex/qtplugin.cab" width="480" classid="clsid:02BF25D5-8C17-4B23-BC80-D3488ABDDC6B" height="376"><param name="src" value="<?php echo c2c_get_custom('video'); ?>" /><param name="controller" value="True" /><param name="cache" value="False" /><param name="autoplay" value="False" /><param name="kioskmode" value="False" /><param name="scale" value="tofit" /><embed src="<?php echo c2c_get_custom('video'); ?>" pluginspage="http://www.apple.com/quicktime/download/" scale="tofit" kioskmode="False" qtsrc="<?php echo c2c_get_custom('video'); ?>" cache="False" height="376" width="480" controller="True" type="video/quicktime" autoplay="False"></embed></object></textarea>

<br />


       <!-- /VIDEO -->
       <?php } elseif (in_category('3')) { ?>
       <!-- EXCLUSIVE ARTICLES -->

       <h2><?php the_title(); ?></h2>
       <b><?php the_time('F j, Y') ?></b>

       <p><?php the_content(); ?></p>
       
       <!-- /EXCLUSIVE ARTICLES -->
       <?php } elseif (in_category('4')) { ?>
       <!-- PHOTOS AND VIDEO -->

       <h2><?php the_title(); ?></h2>
       <img src="<?php echo c2c_get_custom('photolink'); ?>">
       <p><?php the_content(); ?></p>

       <!-- /PHOTOS AND VIDEO -->
       <?php } ?>
 
<!--	
		<div class="post" id="post-<?php the_ID(); ?>">
			<h2><a href="<?php echo get_permalink() ?>" rel="bookmark" title="Permanent Link: <?php the_title(); ?>"><?php the_title(); ?></a></h2>
	
			<div class="entrytext">
				<?php the_content('<p class="serif">Read the rest of this entry &raquo;</p>'); ?>
	
				<?php link_pages('<p><strong>Pages:</strong> ', '</p>', 'number'); ?>
	
				<p class="postmetadata alt">
					<small>
						This entry was posted
						<?php /* This is commented, because it requires a little adjusting sometimes.
							You'll need to download this plugin, and follow the instructions:
							http://binarybonsai.com/archives/2004/08/17/time-since-plugin/ */
							/* $entry_datetime = abs(strtotime($post->post_date) - (60*120)); echo time_since($entry_datetime); echo ' ago'; */ ?> 
						on <?php the_time('l, F jS, Y') ?> at <?php the_time() ?>
						and is filed under <?php the_category(', ') ?>.
						You can follow any responses to this entry through the <?php comments_rss_link('RSS 2.0'); ?> feed. 
	
	
	
						<?php if (('open' == $post-> comment_status) && ('open' == $post->ping_status)) {
							// Both Comments and Pings are open ?>
							You can <a href="#respond">leave a response</a>, or <a href="<?php trackback_url(true); ?>" rel="trackback">trackback</a> from your own site.


	-->

						
						<?php } elseif (!('open' == $post-> comment_status) && ('open' == $post->ping_status)) {
							// Only Pings are Open ?>
							Responses are currently closed, but you can <a href="<?php trackback_url(true); ?> " rel="trackback">trackback</a> from your own site.
						
						<?php } elseif (('open' == $post-> comment_status) && !('open' == $post->ping_status)) {
							// Comments are open, Pings are not ?>
							You can skip to the end and leave a response. Pinging is currently not allowed.
			
						<?php } elseif (!('open' == $post-> comment_status) && !('open' == $post->ping_status)) {
							// Neither Comments, nor Pings are open ?>
							Both comments and pings are currently closed.			
						
						<?php } edit_post_link('Edit this entry.','',''); ?>
						
					</small>
				</p>
	
			</div>
		</div>
		
	<?php comments_template(); ?>
	
	<?php endwhile; else: ?>
	
		<p>Sorry, no posts matched your criteria.</p>
	
<?php endif; ?>
	

	
	
	</div>


<?php get_sidebar(); ?>

<?php get_footer(); ?>
