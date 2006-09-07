	<div id="sidebar">
			






<div id="search">
				<?php include (TEMPLATEPATH . '/searchform.php'); ?>
</div>

<h2 class="leftside">Recent Features</h2> 
<div class="leftfeatures">
<?php 
$featured_posts = get_posts('numberposts=4&category=6');
foreach($featured_posts as $post) :
?>

<a href="<?php the_permalink() ?> &raquo;" rel="bookmark" title="Permanent Link to <?php the_title(); ?>"><?php the_title(); ?></a><P>

<?php endforeach; ?>

</div>

<P>&nbsp;</P>


<P>&nbsp;</P>
<h2 class="leftside">Independent Media Partners</h2> 

<div class="partners">
<span class="rotate" style="margin: 0px; padding: 0px;"><img src="/wp-content/themes/hgm/images/logo_rotate.gif" border="0"></span> 
	
<br><a href="http://www.alternet.org/">AlterNet</a>
<br><a href="http://www.chelseagreen.com/">Chelsea Green</a>
<br><a href="http://www.consortiumnews.com">The Consortium News</a>
<br><a href="http://www.freespeech.org/">Free Speech TV </a>
<br><a href="http://www.inthesetimes.com/">In These Times </a>
<br><a href="http://www.worldlinktv.org/">Link TV </a>
<br><a href="http://www.motherjones.com/">Mother Jones </a>
<br><a href="http://www.ploughshares.org/">Ploughshares Fund </a>
<!-- <br><a href="http://www.iwtnews.com/">The Real News</a> -->
<br><a href="http://www.revver.com/">Revver.com </a>
<br><a href="http://www.truthdig.com/">Truthdig</a>
<br><a href="http://www.washingtonmonthly.com/">The Washington Monthly</a>
<br><a href="http://www.theyoungturks.com/info/show">The Young Turks</a>
<div class="more">and dedicated independent media makers across the world</div>

</div>
 
<p>
		&nbsp;
	</p>
	<h2 class="leftside">
		Support Show Us the War
	</h2>
	<br>
	<span style="padding: 20px 4px 0px 14px;"><a href="http://www.showusthewar.com/av/showusthewartrailerfin.mov" target="_blank"><img src="/wp-content/themes/hgm/images/left_trailerbutton.gif" border="0"></a></span>
		<div class="leftfeatures">
		<a href="mailto:?subject=Show us the War&body=Check out this video: http://www.showusthewar.com/av/showusthewartrailerfin.mov" class="supportus">Send friends the video link &raquo;</a>
<br><a href="/?page_id=53" class="supportus">Add our banner to your site! &raquo;</a>
		<br><a href="/?page_id=60"  class="supportus">Donate so we can keep showing you the war &raquo;</a>
		<br>
			
	</div>
	<br />
<!-- How to participate -->
<h2 class="leftside">Your Turn - Show Us the War</h2>
	<div class="leftfeatures">
If you have content that you would like to present on Show Us the War, read the details on
<a href="/?page_id=13"  class="supportus">how to submit work &raquo;</a>
<P><!--
<a href="REAL%20LINK"  class="supportus">how to add show us the war content to your site or blog  &raquo;</a> -->

</div>	
	<br>
<!--COST OF WAR COUNTER  -->	
<div class="costofwar">
<!-- include cost of war javascript; this runs the counter -->
<script language="JavaScript" src="http://costofwar.com/costofwar.js"></script> 
<!-- the elements 'row' and 'alt' will be changed by the javascript to contain
     the correct numbers -->
	<div>
		<b>Cost of the War in Iraq</b>
	</div>
	<div id="raw">
		(JavaScript Error)
	</div>
	<div>
		<a href="http://costofwar.com" target="_top">To see more details, click here.</a>
	</div>
<!-- this line triggers the counter to start -->
<script language="JavaScript">
inc_totals_at_rate(1000);
</script> 
</div>
<!-- END COW -->
<!-- About us pages list -->

	<?php wp_list_pages('title_li=<h2 class=leftside>More about Show Us the War</h2>' ); ?>



<br /><Br />
	<h2 class="leftside"'>Archives</h2>
				<div class="leftfeatures"><?php wp_get_archives('type=monthly'); ?>
	
</div>



			<?php /* If this is the frontpage */ if ( is_home() || is_page() ) { ?>						


		
		<?php } ?>
			
	

</div>


