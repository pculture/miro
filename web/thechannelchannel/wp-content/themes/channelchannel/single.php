<?php get_header(); ?>





  <?php if (have_posts()) : while (have_posts()) : the_post(); ?>
  <?php if (in_category('1')) { ?>


				
				
				
    <div class="video-large" id="post-<?php the_ID(); ?>">

	<h2><?php the_title(); ?></h2>

<p class="source"><?php echo c2c_get_custom('byline'); ?>
 <strong><?php the_time('F j, Y') ?></strong></p>
    
   <?php the_content('Read the rest of this entry &raquo;'); ?>



<object codebase="http://www.apple.com/qtactivex/qtplugin.cab" width="430" classid="clsid:02BF25D5-8C17-4B23-BC80-D3488ABDDC6B" height="330"><param name="src" value="<?php echo c2c_get_custom('video'); ?>" /><param name="controller" value="True" /><param name="cache" value="False" /><param name="autoplay" value="False" /><param name="kioskmode" value="False" /><param name="scale" value="tofit" /><embed src="<?php echo c2c_get_custom('video'); ?>" pluginspage="http://www.apple.com/quicktime/download/" scale="tofit" kioskmode="False" qtsrc="<?php echo c2c_get_custom('video'); ?>" cache="False" height="330" width="430" controller="True" type="video/quicktime" autoplay="False"></embed></object>

	    <p class="bar"><a href="#"><img src="/wp-content/themes/channelchannel/images/buttons/democracy.gif" alt="+ Democracy" width="85" height="16" /></a> <a href="#"><img src="/wp-content/themes/channelchannel/images/buttons/rss.gif" alt="RSS" width="16" height="16" /></a></p>


<!--
<p><strong>POST THIS VIDEO TO YOUR BLOG:</strong><br />
<textarea style="margin-left: 6px;" rows="10" cols="60" onclick="this.focus();this.select()" title="Right Click and Select Copy"><object codebase="http://www.apple.com/qtactivex/qtplugin.cab" width="480" classid="clsid:02BF25D5-8C17-4B23-BC80-D3488ABDDC6B" height="376"><param name="src" value="<?php echo c2c_get_custom('video'); ?>" /><param name="controller" value="True" /><param name="cache" value="False" /><param name="autoplay" value="False" /><param name="kioskmode" value="False" /><param name="scale" value="tofit" /><embed src="<?php echo c2c_get_custom('video'); ?>" pluginspage="http://www.apple.com/quicktime/download/" scale="tofit" kioskmode="False" qtsrc="<?php echo c2c_get_custom('video'); ?>" cache="False" height="376" width="480" controller="True" type="video/quicktime" autoplay="False"></embed></object></textarea>
-->

    
       <?php } ?>
       
       
       
       
 					
						<?php if (!('open' == $post-> comment_status) && ('open' == $post->ping_status)) {
							// Only Pings are Open ?>
							Responses are currently closed, but you can <a href="<?php trackback_url(true); ?> " rel="trackback">trackback</a> from your own site.
						
						<?php } elseif (('open' == $post-> comment_status) && !('open' == $post->ping_status)) {
							// Comments are open, Pings are not ?>
							You can skip to the end and leave a response. Pinging is currently not allowed.
			
						<?php } elseif (!('open' == $post-> comment_status) && !('open' == $post->ping_status)) {
							// Neither Comments, nor Pings are open ?>
							Both comments and pings are currently closed.			
						
						<?php } edit_post_link('Edit this entry.','',''); ?>
						
		
	<?php comments_template(); ?>
	
	<?php endwhile; else: ?>
	
		<p>Sorry, no posts matched your criteria.</p>
	
<?php endif; ?>
	

	
  	</div>
  
  
  
     
    
    
  </div>
  <hr />


<?php include (TEMPLATEPATH . '/sidebar.php'); ?>


</div>
</body>
</html>
