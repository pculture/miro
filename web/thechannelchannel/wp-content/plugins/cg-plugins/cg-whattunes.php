<?
/* CG-WhatTunes.php
	System to grab information from tracktunes.php and do lookups through CG-Amazon
	Copyright (c)2004 by David Chait, CHAITGEAR - www.chait.net, All Rights Reserved.
*/

$REQUESTED = $_SERVER['REQUEST_URI'];
if ($truncoff = strpos($REQUESTED, '&'))
	$REQUESTED = substr($REQUESTED, 0, $truncoff);

$myPassword = ''; // set this if you want to lightly restrict access to add/set commands.

$wtPathPrefix = dirname(__FILE__).'/';

// locate the wp path...
if (FALSE===strpos($wtPathPrefix, 'wp-content')) // plugin
	$wtRootPath = $wtPathPrefix.'../'; // cgplugins->wp base dir.
else
	$wtRootPath = $wtPathPrefix.'../../../'; // cgplugins->plugins->wpcontent->wp base dir.
	
include_once($wtRootPath.'wp-config.php');
//	@include_once($wtPathPrefix.'/my-setup.php');
if (!isset($AmazonQueryMgr))
{
	if (file_exists($wtPathPrefix."cga-config.php"))
		include_once($wtPathPrefix."cga-config.php");
}

include_once($wtPathPrefix."tracktunes.php");

function getWhatsPlaying($showAmazon = true, $showTitle = false, $titleBefore = true,
														$preTitle = '<ul class="amazon-block">', $postTitle = '</ul>', $titleWrap = true,
														$imageSize = '')
{
	global $amazonImageFirst, $amazonShowCreator, $amazonWrapInfo;
	global $forceExternalLinks;
	//global $AmazonQueryMgr, $AmazonDebug;
	//dbglog("CGWT: looking up last album.");
	
	$output = '';
	$lf = "\n";
	$np = getNowPlaying();
	if ($np)
	{
		$laa = $np['artist'];
		if ($laa)
			if ($np['album'])
				$laa .= ' - ';
		$laa .= $np['album'];	
		dbglog("CGWT: last album: ".($laa?$laa:'[blank]'));
		
		if ($showTitle)
		{
			$titleout = $preTitle.$lf;
			if ($amazonWrapInfo!='li') $titleout .= '<li>'.$lf;
			
			if ($titleWrap) $titleout .= "<$amazonWrapInfo class='t-amazon'>".$lf;
			$titleout .= $np['title'].$lf;
			if ($titleWrap) $titleout .= "</$amazonWrapInfo>".$lf;
			
			if ($amazonWrapInfo!='li') $titleout .= '</li>'.$lf;
			$titleout .= $postTitle.$lf;
		}
		
		$qresults = '';
		if ($laa && $amazonWrapInfo)
		{
			$keysearch = array();
				
			$was_amazonImageFirst = $amazonImageFirst;
			$was_amazonShowCreator = $amazonShowCreator;
			
			$amazonImageFirst = true;
			$amazonShowCreator = true;
			
			$maxResults = 1; // one is fine..
			if ($np['album'])
				$keysearch['Title'] = $np['album'];
			if ($np['artist'])
				$keysearch['Keywords'] = $np['artist'];
			$qresults = show_keyword_items($keysearch, 'music', '', '', $maxResults, 0, $imageSize, false, false, false, (strpos($preTitle,'float')?'float':''));
			if (empty($qresults)) // irk.  try just the album name?
			{
				if (isset($keysearch['Keywords']))
					unset($keysearch['Keywords']);
				$qresults = show_keyword_items($keysearch, 'music', '', '', $maxResults, 0, $imageSize, false, false, false, (strpos($preTitle,'float')?'float':''));
				dbglog("Second query returned:<br>".serialize($qresults));
			}
			$amazonImageFirst = $was_amazonImageFirst;
			$amazonShowCreator = $was_amazonShowCreator;
		}
		
		if ($showTitle && $titleBefore) $output .= $titleout;
		if (empty($qresults))
		{
			$output .= $preTitle.$lf;
			if ($amazonWrapInfo!='li') $output .= '<li>'.$lf;
			if ($titleWrap) $output .= "<$amazonWrapInfo class='t-amazon'>".$lf;
			$output .= $np['artist'].$lf;
			if ($titleWrap) $output .= "</$amazonWrapInfo>".$lf;
			if ($amazonWrapInfo!='li') $output .= '</li>'.$lf;
			$output .= $postTitle.$lf;
			
			$output .= $preTitle.$lf;
			if ($amazonWrapInfo!='li') $output .= '<li>'.$lf;
			if ($titleWrap) $output .= "<$amazonWrapInfo class='t-amazon'>".$lf;
			$output .= $np['album'].$lf;
			if ($titleWrap) $output .= "</$amazonWrapInfo>".$lf;
			if ($amazonWrapInfo!='li') $output .= '</li>'.$lf;
			$output .= $postTitle.$lf;
		}
		else
		{
//				showed_amazon_product();
//$output .= "######################<br/>\n";
			$output .=  $qresults;
		}
		if ($showTitle && !$titleBefore) $output .= $titleout;
	}
	
	return $output;
}

//if ($showWhatTunes)
	//echo getWhatsPlaying();

if ( strstr($REQUESTED, 'cg-plugins/cg-whattunes.php') ) // under cg plugins
{
	$forceExternalLinks = false; // try to not pop out to amazon...
	
	//==================================================
	//==================================================
	if (!function_exists('add_magic_quotes'))
	{
		function add_magic_quotes($array)
		{
			foreach ($array as $k => $v) {
				if (is_array($v)) {
					$array[$k] = add_magic_quotes($v);
				} else {
					$array[$k] = addslashes($v);
				}
			}
			return $array;
		} 
	}
	
	if (!get_magic_quotes_gpc())
	{
		$_GET    = add_magic_quotes($_GET);
		$_POST   = add_magic_quotes($_POST);
		$_COOKIE = add_magic_quotes($_COOKIE);
	}
	
	$findvars = array('action', 'options');
	
	for ($i=0; $i<count($findvars); $i += 1)
	{
		$avar = $findvars[$i];
		if (isset($$avar)) continue;
		if (!empty($_POST[$avar]))
			$$avar = $_POST[$avar];
		elseif (!empty($_GET[$avar]))
			$$avar = $_GET[$avar];
		else
			$$avar = '';
	}
	
//	if ($action=='create')
	{ // admin display page, using the 'zeitgeist' div to float current track to the right, like dashboard info.
		?>
			<style>
				tr.rodd { background: #fefefe; }
				tr.reven { background: #eeefee; }
				tr.rhead { background: #aabbdd; }
				#zeitgeist ul {list-style: none;}
				#zeitgeist .amazon-item-wrap span {display:block;}
				<!-- @import url(<?php echo $siteurl;?>/cg-amazon.css); -->
			</style>
			<div class="wrap">
				<div id="zeitgeist">
					<h2><?php _e('Latest Track'); ?></h2>
					<?php echo getWhatsPlaying(true, true, true, '<ul class="amazon-item-wrap">', '</ul>', true, 'Medium'); ?>
				</div>
				<h2>CG-WhatTunes</h2>
				<p>Last 20 songs played:</p>
				<?php dispTracks(false, 20, true); ?>
		</div>
		<?php
	}
}
?>