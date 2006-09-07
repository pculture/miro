<?php 

//========================================
//
// CG-AMAZON
// Amazon live-product integration system
// (c)Copyright 2003-2004, David Chait.  All Rights Reserved
//
// DO NOT REDISTRIBUTE without prior authorization.
//
//========================================

//$DebugXML = 3;
//$AmazonDebug = 3;
//$showAmaErrors = true;
//$amazonShowRelatedItems = false;
//$forceExternalLinks = false;
	
if (!isset($user_level))
{
	if (!function_exists('get_currentuserinfo'))
		require (ABSPATH . WPINC . '/pluggable-functions.php');
		
	if (function_exists('get_currentuserinfo'))
		get_currentuserinfo(); // cache away in case hasn't been yet...
}

$cgacAbsPath = dirname(__FILE__);
$rawOffset = strpos($cgacAbsPath, 'wp-content');
if ($rawOffset===FALSE)
	$rawOffset = strpos($cgacAbsPath, 'cg-plugins');
$rawWPPath = substr($cgacAbsPath, 0, $rawOffset); 
	
//---------------------------------------
//---------------------------------------
// DONT CHANGE THESE LINES
if (file_exists($rawWPPath.'my-setup.php'))
{
	$onCG = true;
	include_once($rawWPPath.'my-setup.php'); //CGA runs a limited set of CG main files, so test what we've got
}
if (!$onCG || empty($myplugins)) // if we didn't get plugins directory, we do all needed vars now
{
	if (FALSE===strpos($cgacAbsPath, 'wp-content')) // not a plugin
		$myplugins = 'cg-plugins/'; // just down one level
	else
		$myplugins = 'wp-content/plugins/cg-plugins/'; // in the plugins subdir

	$siteurl = get_settings('siteurl');
	
	$wpstyle = true; // tells us that we should try to match default WP style approach.
	// setup for CG-Error plugin, not yet integrated...
	$ignoreNoticeErrors = true;
	$normalErrorHandler = true;
	if (!function_exists('myErrorOutput'))
		@include_once($cgacAbsPath.'/'.'error-handler.php');
// DONT CHANGE THESE LINES
//---------------------------------------
//---------------------------------------
	
// Now, THIS stuff you can change... :)

//----------
// controls over general CG-Amazon functionality...

	// setup our error tracking level
	//$AmazonDebug = 1;
	
	//---------------------------------------
	// Here are some of the CG-Amazon control settings you can change:
	// Uncomment any you want to try to test out on your site.
	
	// set this if you have an Associates ID you want to use
	//$AmazonID = '';
	
	// set this to change locales.  NOTE: if you set a NON-US locale, you MUST GIVE A LINK TO CHAITGEAR, as I get no link-tagging at all.
	//$amazonLocale = 'us'; // or 'jp', 'uk', 'de'.  NON-US is barely tested, feedback to cgcode@chait.net appreciated!
	
	// IF >NOT< USING WordPress, AND NOT USING UTF-8 FOR YOUR SITE, SET THIS TO YOUR ENCODING!
	//$amazonEncoding = ""; 

	// set this to be your amazon wishlist ID/'Asin', so you don't need to pass
	// it into the show_wishlist function all the time...
	//$myAmazonWishlist = '';
	
	// set these to true to show wishlist item details
	//$showWishlistCount = true;
	//$showWishlistDates = true;
	//$showWishlistName = true; // not yet implemented
	
	// we wrap each generated block of products in a div, for better CSS control.
	// set to false to leave it raw, unwrappered.
	//$amazonWrapperDiv = false; 
	
	// how should we wrapper each 'line' of a given product's information?
	// li or span, though other HTML tags may work as well -- default is span, but set to li to style like default WP stylings.
	// if 'li', we wrapper each individual product in its own 'ul' automatically.
	//$amazonWrapInfo = 'li';
	$amazonWrapInfo = 'span';
	
	// how should we end each 'line' of a given product's information?
	// can be set to <br /> or anything else as needed.
	//$amazonInfoBreak = '<br />';
	
	// name of target window for external links.  set to '' to turn off target tag completely.
	//$amaTargetWindow = 'NewWindow';

	// default size of images -- normally 'Small', but can be 'SmallMedium', 'Medium', or 'Large', or tack 'Shadowed' onto any of the four.
	// $defaultAmazonImage = 'SmallMediumShadowed';

	// when showing product images, what order do you want them?
	// show image first, before product name? CHAITGEAR uses false, so product name first.  most blogs seem to like image-first.
	$amazonImageFirst = true;

	// set this true to show ONLY the product image, NO other fields.  this basically infers minimumData too...
	//$amazonImageOnly = true;

	// should we show the manufacturer/artist/author names in addition to product name?
	// set to true to show the 'creator' of the product
	//$amazonShowCreator = true;
	
	// should we show the BlogCat DB field for an item in parens after the name of the item?
	//$amazonShowBlogCat = true;
	
	// to show product prices.
	// requires (automatic) daily cache updates, versus weekly/monthly update timing.
	//$amazonShowPrices = true;
	
	// leading text before the price.  otherwise nothing.
	//$amazonPriceLead = 'Only '; // if you want extra text preceding the price.
	
	// array of extra product data fields you want shown.  requires daily updates.
	// array should be sets of two strings, in succession.
	// first string is a product data field name, second string is what you want
	// prefixed before the field value is output.
	// example:
	//$extraProductFields = array("ListPrice", "MSRP ", "SalesRank", "Ranked #");
	
	// set this to true to turn on 'Support <mysite>' lines, false to keep them off.
	$showSupport = false;
		
	// set this to false to basically just show the product link, no extra data.
	//$showExtrasInline = false;
	
	// to show minimal data, no extra fields/pricing, no timestamps.
	//$amazonMinimumData = true;
	
//----------
// controls over use and display of cgaindex.php:
	
	// set this to false to use cgaindex.php internal listing file.
	//$forceExternalLinks = false; // defaults true as generates more clickthroughs...

	// set this true to show pricing/msrp, etc. info in cgaindex.php
	$showPurchaseInfo = true;
	
	// set this to false to NOT show related items in side menu in cgaindex.php
	//$amazonShowRelatedItems = false;

	// default for cga-admin and cgaindex is to list 8 items per page.  set this to change the default.
	//$amaListMaxPerPage = 16;

	// default size for cgaIndex single-item pix.
	$amaBigPix = 'Medium'; // large doesn't always exist, and doesn't always fit tight template layouts.
	
//---------------------------------------
//---------------------------------------
// DONT CHANGE THESE LINES
}
else
{ // default CG settings...
	$showSupport = false;
	$showPurchaseInfo = true;
	$amazonShowPrices = true;
	$amazonClickForPrice = true;
//	$amazonPriceLead = 'Price: ';
	$amazonPriceLead = 'Click for Price';

	//$extraProductFields = array("ListPrice", "MSRP ", "SalesRank", "Ranked #");
//	$AmazonDebug = 3;

	// override with new tracking IDs
	// array: first for normal links, second for single-item-w/extrainfo, third for cgaindex.
	$AmazonID = array('surpass1-20','surpass2-20','surpass3-20');
	
	if ($user_level>4) // admins click through to cgaindex
		$forceExternalLinks = false;
}

require_once($cgacAbsPath.'/'."cg-amazon.php");
// DONT CHANGE THESE LINES
//---------------------------------------
//---------------------------------------

function output_ama_errors()
{
	global $showAmaErrors, $user_level;
	if (($showAmaErrors || $showDebugging) && $user_level>4 && function_exists('myErrorOutput'))
	{
		echo '<div id="debug" style="clear:both; text-align:left">';
			myErrorOutput();
		echo '</div>';
	}
}

if (!$onCG)
if ($user_level>4)
	add_action('wp_footer', 'output_ama_errors');

?>
