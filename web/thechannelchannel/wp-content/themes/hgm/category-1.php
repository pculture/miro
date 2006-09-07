<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
<meta http-equiv="Cache-control" content="no-cache" />
<meta http-equiv="pragma" content="no-cache" />
<meta name="robots" content="index,follow" />
<meta name="description" content="" />
<meta name="keywords" content="" />
<meta name="author" content="" />
<meta name="copyright" content="" />
<link rel="stylesheet" type="text/css" href="/wp-content/themes/channelchannel/stylesheets/common.css" media="screen, print, projection, handheld" />
<link rel="stylesheet" type="text/css" href="/wp-content/themes/channelchannel/stylesheets/screen.css" media="screen, projection" />
<link rel="stylesheet" type="text/css" href="/wp-content/themes/channelchannel/stylesheets/print.css" media="print" />
<link rel="stylesheet" type="text/css" href="/wp-content/themes/channelchannel/stylesheets/handheld.css" media="handheld" />
<!--[if lte IE 6]>
 <link rel="stylesheet" type="text/css" href="/wp-content/themes/channelchannel/stylesheets/ie.css" media="screen, projection" />
<![endif]-->
<!--[if IE 7.0]>
 <link rel="stylesheet" type="text/css" href="/wp-content/themes/channelchannel/stylesheets/ie7.css" media="screen, projection" />
<![endif]-->
<title>The Channel Channel - One minute previews of Internet TV Channels</title>
</head>
<body>
<div id="wrapper">
  <div id="header">
    <h1><a href="#">The Channel Channel<span> </span></a></h1>
    <p id="slogan"><strong>One minute previews of Internet TV Channels<span> </span></strong></p>
    <p id="to-content"><a href="#content-start">Skip navigation</a></p>
    <ul id="nav">
      <li><a href="index.html" id="featured" class="current">Featured<span> </span></a></li>
      <li><a href="video.html" id="all">All<span> </span></a></li>
    </ul>
  </div>
  <a name="content-start"></a>
  <div id="content">
    
    
    
    <!-- BEGIN MAIN BODY AREA-->

		<?php if (have_posts()) : ?>

		 <?php $post = $posts[0]; // Hack. Set $post so that the_date() works. ?>
<?php /* If this is a category archive */ if (is_category()) { ?>				
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
  <div id="sidebar">
    <p class="download"><a href="#"><img src="/wp-content/themes/channelchannel/images/buttons/get-dem.gif" alt="Download Democracy For Mac OSX" width="191" height="75" /></a> <br />
      <a href="#">For Windows</a> | <a href="#">For Linux</a> </p>
	<div class="whats-this">
    <h3><img src="/wp-content/themes/channelchannel/images/text/whats-this.gif" alt="What's This?" width="109" height="16" /></h3>
    <p> Watch previews of internet TV channels.  Subscribe to the best, forget the rest.</p>
	</div>
    <p class="rss-feed"><a href="#"><img src="/wp-content/themes/channelchannel/images/text/rss-feed.gif" alt="Why not grab our RSS feed?" width="182" height="20" /></a></p>
    <p><a href="#"><img src="/wp-content/themes/channelchannel/images/buttons/submit-channel.gif" alt="Submit your channel" width="192" height="45" /></a></p>
  </div>
</div>
</body>
</html>
