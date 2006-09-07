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
       <?php } elseif (in_category('10')) { ?>
       <!-- on the web -->

       <h2><?php the_title(); ?></h2>
       <b><?php the_time('F j, Y') ?></b>

       <p><?php the_content(); ?></p>
       


       <!-- /on the web -->
       <?php } else { ?>
       <!-- anything else -->

       <h2><?php the_title(); ?></h2>
       <b><?php the_time('F j, Y') ?></b>

       <p><?php the_content(); ?></p>
       


       <!-- /anything else -->
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
						
					</small>
				</p>
	
			</div>
		</div>
		
	<?php comments_template(); ?>
	
	<?php endwhile; else: ?>
	
		<p>Sorry, no posts matched your criteria.</p>
	
<?php endif; ?>
	

	
	
	</div>


<!--END MAIN BODY -->
			</td>
		<td class="rightcolumn">
			<img src="/wp-content/themes/hgm/images/spacer.gif" width="82" height="1023" alt=""></td>
	</tr>


<pclass="footer"><?php get_footer(); ?></p>
