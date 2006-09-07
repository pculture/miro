<?php

if (!isset($force_content_clears))
	$force_content_clears = true;
if (!isset($defaultImageFolder))
	$defaultImageFolder = "inline";
if (!isset($postImagesSubfolders))
	$postImagesSubfolders = true;
$searchForImages = true; // if not in default, and default != images, look in images.
if (!isset($alwaysInlineImages))
	$alwaysInlineImages = false;

if (!isset($inlineTargetWindow)) $inlineTargetWindow = 'NewWindow';
		
$inPathBase = dirname(__FILE__).'/';

// locate the wp path...
if (FALSE===strpos($inPathBase, 'wp-content')) // plugin
	$inPathPrefix = $inPathBase.'../'; // cgplugins->wp base dir.
else
	$inPathPrefix = $inPathBase.'../../../'; // cgplugins->plugins->wpcontent->wp base dir.
		
//if (!$AmazonQueryMgr)
//	@include_once("cga-config.php");

require_once($inPathBase.'helper_fns.php');


//========================================
function handle_linkto_inline($inlineNum, $onepost, $postID, $what, $dot, $title)
{ // what==postition, dot==alt style, title=base text
	global $inlineTargetWindow;
	if (!empty($dot)) $what .= '.'.$dot;
	$output = "<a href='$title' title='$what'";
	if ($inlineTargetWindow) $output .= " target='$inlineTargetWindow'";
	$output .= ">$what</a>";
	return($output);
}

//========================================
$query_URIs['google'] = 'http://www.google.com/search?hl=en&btnG=Google+Search&q=';
$query_URIs['yahoo'] = 'http://search.yahoo.com/search?p=';
$query_URIs['ask'] = 'http://web.ask.com/web?q=';
$query_URIs['wikipedia'] = 'http://en.wikipedia.org/wiki/';
$query_URIs['answers'] = 'http://www.answers.com/main/ntquery?s=';
$query_URIs['dictionary'] = 'http://dictionary.reference.com/search?q=';
$query_URIs['imdb'] = 'http://imdb.com/find?q=';
function handle_query_inline($inlineNum, $onepost, $postID, $what, $dot, $title)
{ // what==query site, title==keyword
	global $inlineTargetWindow, $query_URIs;
	if (!empty($dot)) $what .= '.'.$dot;
	if (isset($query_URIs[$what]))
		$uri = $query_URIs[$what].urlencode($title); // for now, just do URIs that slap keyword on end.
	$output = "<a href='$uri' title='$title @ $what'";
	if ($inlineTargetWindow) $output .= " target='$inlineTargetWindow'";
	$output .= ">$title</a>";
	return($output);
}

//========================================
function handle_floattext_inline($inlineNum, $onepost, $postID, $what, $dot, $title)
{ // what==postition, dot==alt style, title=base text
	$floatclass = 'floattext';
	$floatclass .= '-'.$what;
	if ($dot) $floatclass .= '-'.$dot;
	$output = "<span class='$floatclass'>$title</span>";
	return($output);
}

//========================================
function handle_permalink_inline($inlineNum, $onepost, $postID, $what, $dot, $title)
{ // what==ID, dot==alt link text, title=base text of link
	if (empty($title))
		$title = get_the_title($postID);
	if (empty($dot))
		$dot = $title;
	$output = "<a href='".get_permalink($what)."' title='$dot'>$title</a>";
	return($output);
}

//========================================
function handle_pagelink_inline($inlineNum, $onepost, $postID, $what, $dot, $title)
{ // what==pagenum
	global $pagetitles;

	$pagenum = intval($what);
	if ($pagenum<1) $pagenum = 1; // don't handle greater case for now...
	if (empty($pagetitles))
		$pagename = "Page $pagenum";
	else
		$pagename = $pagetitles[($pagenum-2)];
		
	if ('' == get_settings('permalink_structure')) {
		$output = '<a href="'.get_permalink().'&amp;page='.$pagenum.'"';
	} else {
		$output = '<a href="'.get_permalink().$pagenum.'/"';
	}
	$output .= ' title="'.safehtmlentities(get_the_title()).' Page '.$pagenum.'">'.$pagename.'</a>';
	return($output);
}


//========================================
$cachedInlines = '';
$cachedInlineCount = 0;

//========================================
function handle_image_inline($side, $onepost, $inlined, $postID, $what, $dot, $title)
{
	global $cachedInlines, $cachedInlineCount, $siteurl, $inPathPrefix;
	global $defaultImageFolder, $postImagesSubfolders, $searchForImages;
	global $doing_rss, $rss_no_inlines;
	
//echo "CACHING $what $dot $title<br/>";
	if ($title) dbg_log("IMAGE INLINE: $what $dot $title");

	$output = '';
	
	if (!$onepost)
	{
		if ($side=='left')
			$side = 'right';
		else
			$side = 'left';
	}
	
	$imgOptz = '';
	if ($doing_rss)
	{
		$imgOptz = 'align="left" border="0" hspace="10" vspace="0"';
		$inlined = false; // thumbnail.
	}
	
	$cleanTitle = htmlentities($title);

	$foundyet = false;
	if (!$inlined) 
		$filename = $what.'.thumb.'.$dot;
	else
		$filename = $what.'.'.$dot;
	
	$filepath = $defaultImageFolder.'/';
	if ($postImagesSubfolders) $filepath .= "post$postID/";
//	dbglog("looking in $inPathPrefix$filepath$filename");
	if (file_exists($inPathPrefix.$filepath.$filename))
	{
		$foundyet = true;
//		dbglog("FOUND $filename");
	}
	if (!$foundyet && $defaultImageFolder!='images')
	{
		$filepath = 'images/';
		$filename = $what.'.'.$dot; // since it'll be inlined, effectively.
//		dbglog("looking in $inPathPrefix$filepath$filename");
		if (file_exists($inPathPrefix.$filepath.$filename))
		{
			$foundyet = true;
//			dbglog("FOUND $filename");
			$inlined = true;
		}
	}

	if ($foundyet)
		if (!$onepost || $doing_rss)
			$output .= "<a href='".get_permalink($postID)."' title='Read Article'><div class='preview'>";

	if (!$doing_rss)
		$output .= "<div class='img$side'>"; // imgleft or imgright
		
	if (!$foundyet)
	{
		if (!$doing_rss)
		{
			if (strpos($_SERVER["SERVER_NAME"], 'chait'))
				$output .= "<img src='$siteurl/images/image-missing.gif' alt='Missing $filename' />";
			else
				$output .= "<em>Missing image $filename</em>";
		}
	}
	else
	{
//		if ($onepost) $output .= "<a href='$siteurl/my-inline/post$postID/$what.$dot' title='$title'>";	
		if ($onepost && !$inlined && !$doing_rss)
			$output .= "<a href='image.php?p=$postID&amp;file=$what.$dot&amp;title=$cleanTitle' title='$cleanTitle'>";
		
		$output .= "<img src='$siteurl/$filepath$filename' alt='$cleanTitle' $imgOptz/>";
		
		if ($onepost && !$inlined && !$doing_rss)
			$output .= "</a>";
	}
	
	if (!$doing_rss)
		$output .= "</div>";
	
	if ($foundyet)
		if (!$onepost || $doing_rss)
			$output .= "</div></a>";

	$output .= "\n";
	
	$cachedInlines[$cachedInlineCount++] = $output;
	
	return $output;
}

//========================================
function handle_imgright_inline($inlineNum, $onepost, $postID, $what, $dot, $title)
{
	global $alwaysInlineImages;
//	echo "$inlineNum, $onepost, $postID, $what, $dot, $title<BR/>";
//	if (!$onepost && $inlineNum>0) return '';
	$side = 'right';
	$inlined = false || $alwaysInlineImages;
	return handle_image_inline($side, $onepost, $inlined, $postID, $what, $dot, $title);
}

//========================================
function handle_imgleft_inline($inlineNum, $onepost, $postID, $what, $dot, $title)
{
	global $alwaysInlineImages;
//	if (!$onepost && $inlineNum>0) return '';
	$side = 'left';
	$inlined = false || $alwaysInlineImages;
	return handle_image_inline($side, $onepost, $inlined, $postID, $what, $dot, $title);
}

//========================================
function handle_img_inline($inlineNum, $onepost, $postID, $what, $dot, $title)
{
	global $alwaysInlineImages;
//	if (!$onepost && $inlineNum>0) return '';
	$side = 'big';
	$inlined = true || $alwaysInlineImages;
	return handle_image_inline($side, $onepost, $inlined, $postID, $what, $dot, $title);
}

//========================================
function handle_imgthumb_inline($inlineNum, $onepost, $postID, $what, $dot, $title)
{
	global $alwaysInlineImages;
//	if (!$onepost && $inlineNum>0) return '';
	$side = 'thumb';
	$inlined = false || $alwaysInlineImages;
	return handle_image_inline($side, $onepost, $inlined, $postID, $what, $dot, $title);
}

//========================================
function handle_imggallery_inline($inlineNum, $onepost, $postID, $what, $dot, $title)
{
	global $alwaysInlineImages;
//	if (!$onepost && $inlineNum>0) return '';
	$side = 'gallery';
	$inlined = false || $alwaysInlineImages;
	return handle_image_inline($side, $onepost, $inlined, $postID, $what, $dot, $title);
}

//========================================
function handle_floatclear_inline($inlineNum, $onepost, $postID, $what, $dot, $title)
{
	global $alwaysInlineImages;
	if (!$onepost) return '';
	
	if ($what=='both' || empty($what))
		return '<div class="float-clear"></div>';
	return '<div class="float-clear-'.$what.'"></div>';
}

//========================================
function handle_meta_inline($inlineNum, $onepost, $postID, $what, $dot, $title)
{
	if ($dot) $what .= '.'.$dot; // put it back together...	
		
	$metaval = get_post_meta($postID, $what, false);
	if (empty($metaval)) return null;
	
	if (is_array($metaval))
	{
		if ($title=='random')
			$metaval = $metaval[array_rand($metaval)];
		else // otherwise, return all entries together.
		if (count($metaval)==1)
			$metaval = $metaval[0];
		else
			$metaval = implode(', ', $metaval);
	}
	
	return '<span class="meta-inline">'.$metaval.'</span>';
}

//========================================
function handle_amazon_inline($inlineNum, $onepost, $postID, $what, $dot, $title)
{
	global $AmazonQueryMgr, $showExtrasInline, $wasReviewPost;
	global $cachedInlines, $cachedInlineCount;
	global $user_level;
	global $doing_rss, $rss_no_inlines;
	global $amazonImageOnly;

	if (!isset($AmazonQueryMgr)) return '<!--CG-Amazon not active-->'; // no amazon system.
	
	dbg_log("CGA INLINE: $what $dot $title");

	if (!$doing_rss && (!$onepost || ($onepost && !$wasReviewPost)))
	{ // cache any amazon inlines in post-list pages...
		if(0===strpos($what, '@')) // @ means user category listing...
			return '';
		cache_amazon_inline($what, $dot, $title);
		if (!$onepost && $inlineNum) return '';
	}
	
	$output = '';

	$amaWasImage = $amazonImageOnly;
	
	// ability to override title on single-entry amazon grab?
	
	$imgsize = 'Medium';
	if ($dot=='Link') // oh this is SUCH a freakin hack!!!
	{
		$imgsize = 'Link';
		$imgpos = $title;
	}
	else
	{
		$imgpos = 'float';
		if ($dot=='left'||$dot=='right')
			$imgpos .= "-$dot";
		elseif ($dot=='inline')
			$imgpos = $dot;
		elseif ($dot=='none')
			$imgpos = '';
			
		if ($onepost!=true)
			$imgsize = 'Small'; // default small if not in single post mode.
		
		if (strpos($title, '!')) // has a !
		{
			$title = trim($title, '!');
			$amazonImageOnly = true;
		}
		$imgsize = get_ama_image_size($title, $imgsize);
	}	
	
//		$searchData, $cacheName, $buildOutput=true, $imageSize='Small', $showtime=true,
//		$randomNum=0, $liteData=true, $searchType='Asin',
//		$searchMax=1000, $searchCat='', 
//		$divPrefix='', $button=false, $extraData=false,
//		$showSomeSupport=false, $showAnnotation=true, $cgaindexLinks=false,

	if (!$onepost)
	{
		if (0===strpos($what, '@'))
			return '';
			
		if (strpos($what,',')) // a list!
		{
			$list = explode(',', $what);
			$what = $list[0];
		}
		$output .= "<span class='preview'>";
		$output .= query_amazon($what, '', true, 'Preview',
														false, 0, true, 'Asin', 1, '',
														$imgpos, false, false, false, false, false);
		$output .= "</span>";
	}
	else
	{		
		if (0===strpos($what, '@'))
		{
			$what = ltrim($what, '@');
			$output .= show_amazon_items(100, 'time', true, $what, '', false, $imgpos);
		}
		else
		{
			$count = 1;
			if (strpos($what,',')) // a list!
			{
				$list = explode(',', $what);
				$what = $list;
				$count = count($what);
			}
			$internalRedirect = false; //($user_level>4); //false/*($imgsize=='Small')*/;
			$showExtras = $showExtrasInline;
			$output .= query_amazon($what, '', true, $imgsize,
															true, 0, true, 'Asin', $count, '',
															$imgpos, $showExtras && !$internalRedirect, $showExtras /*($imgsize!='Small')*/,
															$showExtras && ($imgsize!='Small'), false, $internalRedirect);
		}

	}
	
	$amazonImageOnly = $amaWasImage;
	$cachedInlines[$cachedInlineCount++] = $output;
	
	return $output;
}

//========================================
function get_cached_inline($which=0)
{
	global $cachedInlines, $cachedInlineCount;
//echo "CACHE RETRIEVE $cachedInlines[$which] <br/>";
	return($cachedInlines[$which]);
}

//========================================
function flush_cached_inlines()
{
	global $cachedInlines, $cachedInlineCount;
	$cachedInlineCount = 0;
}

//========================================
// now build the array entries for the function handlers...
//$inlineHandler = Array();
$inlineHandler['imgright'] = 'handle_imgright_inline';
$inlineHandler['imgleft'] = 'handle_imgleft_inline';
$inlineHandler['img'] = 'handle_img_inline';
$inlineHandler['imgthumb'] = 'handle_imgthumb_inline';
$inlineHandler['imggallery'] = 'handle_imggallery_inline';
$inlineHandler['amazon'] = 'handle_amazon_inline';
$inlineHandler['permalink'] = 'handle_permalink_inline';
$inlineHandler['pagelink'] = 'handle_pagelink_inline';
$inlineHandler['floattext'] = 'handle_floattext_inline';
$inlineHandler['linkto'] = 'handle_linkto_inline';
$inlineHandler['query'] = 'handle_query_inline';
$inlineHandler['floatclear'] = 'handle_floatclear_inline';
$inlineHandler['meta'] = 'handle_meta_inline';

//========================================
if (!isset($debug_pullins)) $debug_pullins = false;
//$debug_pullins = true; // !!!!!!TEMPORARY

function content_inlines($text)
{
	global $single;
	global $id;
	global $debug_pullins;
	global $force_content_clears;
	if ($debug_pullins) dbg_log("Processing CG-Inlines");
	// since most people would want spans:
	return(doInlineConversion($text, $id, false, true).($force_content_clears?"<div class='float-clear'></div>":""));
}

function doInlineConversion($input, $id=0, $justCache=false, $onepost=true)
{
	global $doing_rss, $rss_no_inlines;
	global $debug_pullins;
	global $contentFeature, $inlineHandler; // new CDN support.

	$output = null;
		
	//$piRegex = '/<!--((\w+):(\w+).([^:]*)[:]?([^-]*))-->/i'; 
	//$piRegex = '/<!--((\w+):(\w+)[\.]?([^:]*)[:]?([^-]*))-->/i';  // original version
	//$piRegex = '/<!--((\w+)[:]{1}?(\w+)[\.]?([^:]*)[:]?([^>|^<]*?))[^<]{1}->/i'; // newer version, catches cases of other comments interfering...
	
	//{commentstart}{pullin-type}:{pullin-arg1}[.{pullin-arg2}]:{pullin-arg3}{commentend}
	
	$firstRegex = '/<!--([^<]+)-->/i'; // newer version, catches cases of other comments interfering...
	$secondRegex = '/(\w+):([\w|\s|\'|-|\,]+)[\.]?([^:]*)[:]?(.*)/i';  // more complex catch

	if ($debug_pullins) $timedelta = timer_stop(0);
		$pullins = preg_split($firstRegex, $input, -1, PREG_SPLIT_DELIM_CAPTURE);
		$k = count($pullins);
	if ($debug_pullins)
	{
		dbg_log("PULLIN COUNT: " . count($pullins));
		dbg_log("PULLINS: " . serialize($pullins));
		$timedelta = timer_stop(0) - $timedelta;
	}

	if ($k<1) return(null);
	if ($k==1) return($input); // untouched
	// are there further special cases to be handled here???	
			
	if ($debug_pullins)
	{
		dbg_log(" Total regex time = ".number_format($timedelta,3));
		
		dbg_log("PULLINS COUNT: " . (($k-1) / 2));
		$i=0;
		if (count($pullins)>1)
			foreach($pullins as $pull)
			{
				if ($i%2)
					dbg_log("pull $i = $pull");
				$i++;
			}
	}
	
	if ($debug_pullins) dbg_log("Doing inline conversion for $id...");
	
	if (!$justCache) $output = ''; // we're 'rewriting' the output...

	for ($i=0; $i<$k; $i++)
	{
		// quick loop on even slots which are original body content
		if ($i % 2 == 0)
		{
 			if (!$justCache) $output .= $pullins[$i];
 			continue;
		}
			
		// find the sub-tags of the pullin
		$tags = null;
		$locColon = strpos($pullins[$i], ':');
		if ($locColon)
			$tags = preg_split($secondRegex, $pullins[$i], -1, PREG_SPLIT_DELIM_CAPTURE);
			
//		if (!$doing_rss || !$rss_no_inlines) // pull these out in rss feeds?
		if (count($tags)>1) // actually, a full set of tags is 6: [blank][who][what][dot][title][blank]
		{
			if ($debug_pullins)
			{
				$tagstream = '';
				foreach($tags as $tag)
					$tagstream .= "[$tag]";
				if ($debug_pullins) dbg_log("PULLIN: found tagset = $tagstream");
			}
			// ignore $tags[0] and $tags[5]
			$tag_who = $tags[1];
			$tag_what = $tags[2];
			$tag_dot = $tags[3];
			$tag_title = $tags[4];
			$func = $inlineHandler[$tag_who]; 
			if (!empty($func) && function_exists($func))
			{
				if ($debug_pullins) dbg_log("PULLIN: function call [$func]");
				$pullCount = intval($i / 2);
				$result = call_user_func($func, $pullCount, $onepost, $id, $tag_what, $tag_dot, $tag_title);
				if (!$justCache) $output .= $result; // justFirst simply caches inlines...
				continue; // to skip over the fall-through handling below...
			} // if handlerexisted
		} // if second regex had hits
		
		// fall-through: if not handled for some reason, push the comment back into the output.
		$output .= "<!--$pullins[$i]-->";
	} // forloop over firstRegex pullins

	//dbg_log("PULLINS RETURNING: " . $output);
	return($output);	
}

?>