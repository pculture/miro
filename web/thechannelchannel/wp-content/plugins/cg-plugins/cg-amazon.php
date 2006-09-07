<?php

//========================================
//
// CG-AMAZON
// Amazon live-product integration system
// (c)Copyright 2003-2005, David Chait.  All Rights Reserved
//
// DO NOT REDISTRIBUTE without prior authorization.
//
//========================================

$myAmaPath = dirname(__FILE__).'/';

//bring in core CG support files
require_once($myAmaPath."db_fns.php"); // for abstracting db access further.
require_once($myAmaPath."helper_fns.php"); // for other helpers.
require_once($myAmaPath."uni_fns.php");

// shouldn't need to do this... but it's the only point of WP integration needed, due to nice-URLs...
$siteurl = get_settings('siteurl');

//========================================
// HELPER FUNCTIONS
//========================================

//========================================
if (!function_exists('timer_stop')) // might not be on WP.
{
	$timer_last = 0;
	function timer_stop($show=0)
	{
    global $timer_last;
    $localtime = microtime();
    if ($timer_last>0)
    	$deltatime = $localtime - $timer_last;
    else
    	$deltatime = $localtime;
    $timer_last = $localtime;
    if ($show)
    	echo number_format($deltatime, 3);
    return($deltatime);
	}
}

//========================================
// these two functions will be extracted, as they can be user-overridden for custom visuals.
if (!function_exists('cga_block_start'))
{
$blockStartPrefix = '';
	function cga_block_start($pfx='')
	{
		global $tag_who;
		global $blockStartPrefix, $blockStartWrap;
		
		$output = '';
		$blockStartPrefix = $pfx;
		if ($blockStartPrefix)
			$blockStartPrefix .= '-';
		if (empty($blockStartPrefix))
			$output .= "<ul ";
		else
			$output .= "<div ";
		$output .= "class='".$blockStartPrefix.$tag_who."-block'>"; // start main output	
		return $output;
	}
}

if (!function_exists('cga_block_end'))
{
	function cga_block_end($showtime=false)
	{
		global $tag_who;
		global $showCacheTime;
		global $blockStartPrefix, $amazonWrapInfo;
		
		$output = '';
		if ($showCacheTime && $showtime)
		{
			if (empty($blockStartPrefix)) $output .= "<li class='timestamp-$tag_who'>"; // ul wrapped
			$output .= "<$amazonWrapInfo class='timestamp-$tag_who'>".get_last_timestamp()."</$amazonWrapInfo>";
			if (empty($blockStartPrefix)) $output .= '</li>'; // ul wrapped
		}
		if (empty($blockStartPrefix))
			$output .= "</ul>";
		else
			$output .= "</div>";
		return $output;
	}
}


//====================================
if (!isset($AmazonID)) $AmazonID = ''; // set this in your REFERENCING FILE if you have an ID you want to use.  It is blank here to initialize it.
//====================================
// READ LICENSE.HTM FOR LICENSING AGREEMENT
// A lot of variables and code in this file consitute the main functionality of CG-Amazon.
// By using this library, you agree that a random 20% of links will be tagged with the CG associates ID, to help
// support the development of the library.  In fact, you don't need an amazon ID at all if you want CG to get the
// benefit of all your click-throughs.  We'd appreciate it!
// Note that the random calc is based on PHPs random number generation, which is thus outside of our control.
// Also, as it is a random system, not an every-20th system, there can be cases where NONE (or all) of the links
// get overridden with our ID (again, assuming you set your own in cga-setup.php).
//====================================
// If you'd like an unrestriced license or corporate license to use the cg-amazon library, contact us at cgcode@chait.net.
//====================================

$AmazonCGID = 'chaitgear-20'; // this is the ChaitGear amazon associates ID.  DO NOT CHANGE.
if (!isset($AmazonCGAllSwap)) $AmazonCGAllSwap = false; // for internal use only.

//====================================
// DO NOT CHANGE THESE AT ALL!
//====================================
function get_creator_ID()
{
	return(get_assoc_ID());
}
//====================================
function has_assoc_ID()
{
	global $AmazonID;
	return(!empty($AmazonID));
}
//====================================
// This function returns the CG associates ID a random 20% of the time, per the usage agreement.
//====================================
function get_assoc_ID($tryToSwap=false, $which=0) // passing false (well, not passing true) will force the CG ID, say for initial queries.
{
	global $AmazonID, $AmazonCGID, $AmazonQueryMgr;
	global $AmazonCGAllSwap;
	
	$id = $AmazonQueryMgr->GetCreatorID(); // this had BETTER be 'chaitgear-20'...
	$overrideCreatorID = false;
	if (empty($id)) // !!!!TBD THIS SHOULD NEVER, EVER HAPPEN!!!!!
		$overrideCreatorID = true;
	else
	{
		if (has_assoc_ID($which) && $tryToSwap)
		{
			if ($AmazonCGAllSwap)
					$overrideCreatorID = true; // for overriding on CHAITGEAR with tracking IDs
			else
			{
		    	//srand((double) microtime() * 1000000);
				$randNum = rand(1,100); // exactly 100 chances
				if ($randNum >= 20) // we'll take anything in the first 20%.  the rest is the user's.
					$overrideCreatorID = true; // use the user's ID in the other 80%.
				// else, stick with the CG ID.
			}
		}
	}
	
	if ($overrideCreatorID)
	{
		if (!is_array($AmazonID))
		{
			if (!empty($AmazonID))
				return($AmazonID);
		}
		else
		{
			if ($which>0)
				if (!empty($AmazonID[$which]))
					return($AmazonID[$which]);
			// if we get here, want to use [0]
			if (!empty($AmazonID[0]))
				return($AmazonID[0]);		
		}
	}
	
	// fallback -- use OUR ID.
	return($id);
}
//====================================

function get_ama_image_size($image, $default='')
{
	global $defaultAmazonImage, $amaImageSizes, $AmazonDebug;

	if ($image===false) return('None');
	if ($default && in_array($default, $amaImageSizes, true))
		$imageSize = $default;
	else
		$imageSize = $defaultAmazonImage;
	if ($image===true) $image = $imageSize;
	if ($image)
	{
		if (in_array($image, $amaImageSizes, true))
		{
			if ($image===true && $AmazonDebug>0) dbglog("ARRRRRRGH: SHOULDN'T BE HITTING THIS, RIGHT???  image = $image, imageSize = $imageSize");
			$imageSize = $image;
		}
	}
	
	return($imageSize);
}
			
//========================================
// CG-AMAZON GLOBALS FOR MANAGING OUTPUT
//========================================
$tablecgamazon = $table_prefix."cg_amazon";
$amazonTime = time();

// test for override of locale!
if (!isset($amazonLocale)) $amazonLocale = 'us'; // default to USA.


if (!isset($amazonMinimumData)) $amazonMinimumData = false; // this was for switching to no-on-disk caching, just pull from DB.  NOT YET IMPLEMENTED.
if (!isset($amazonWrapperDiv)) $amazonWrapperDiv = true;
if (!isset($amazonWrapInfo)) $amazonWrapInfo = 'span';
if (!isset($amazonInfoBreak)) $amazonInfoBreak = ''; // this can be set to <br /> if needed...
if (!isset($amazonImageOnly)) $amazonImageOnly = false;
if (!isset($amazonImageFirst)) $amazonImageFirst = false;
if (!isset($amazonShowCreator)) $amazonShowCreator = false;
if (!isset($amazonShowBlogCat)) $amazonShowBlogCat = false;
if (!isset($forceExternalLinks)) $forceExternalLinks = true; // generates more clickthroughs this way...
if (!isset($amazonShowRelatedItems)) $amazonShowRelatedItems = true;
if (!isset($amaListMaxPerPage)) $amaListMaxPerPage = 10;
if (!isset($defaultAmazonImage)) $defaultAmazonImage = 'Small';
if (!isset($showPurchaseInfo)) $showPurchaseInfo = false;
if (!isset($amaTargetWindow)) $amaTargetWindow = 'NewWindow';
if (!isset($showExtrasInline)) $showExtrasInline = true;
if (!isset($amazonShowPrices)) $amazonShowPrices = false;
if (!isset($amazonClickForPrice)) $amazonClickForPrice = false;
if (!isset($showSupport)) $showSupport = true;
if (!isset($doMovieActors)) $doMovieActors = true;

if (!isset($showWishlistName)) $showWishlistName = false;
if (!isset($showWishlistCount)) $showWishlistCount = false;
if (!isset($showWishlistDates)) $showWishlistDates = false;
if (!isset($amazonLineBreak)) $amazonLineBreak = '';

if (strpos($_SERVER['REQUEST_URI'], "cgaindex.php")	 // try to stay in cgaindex?
||	strpos($_SERVER['REQUEST_URI'], "cga-admin.php")) // try to stay in cgaindex from cgaadmin
	$forceExternalLinks = false;

$amaImageSizes = array("None", "Small", "SmallMedium", "Medium", "Large", "Link",
						"SmallShadowed", "SmallMediumShadowed", "MediumShadowed", "LargeShadowed");
$amaNoProductsString = "No products found."; // so we can compare it...

$amazonDBData = Array();
$amazonAsins = Array();
$amazonGroups = Array();

$CurrentAmazonItem = null;

$showedProduct = 0;
$buyButtonShown = false;
$showedAds = false;
$autoAmazonAd = true;
$showAmazonAds = false; // default OFF.
$showAdsOnePost = false;
$theAmazonAds = Array();

$showCacheTime = true;
$lastQueryTime = 0;
$restrictRapidQueries = true; // once cached, not usually a problem.  but this attempts to apply the Amazon 1 request per second rule.

if (!isset($amazonPriceLead)) // then we set default(s)
{
	//$amazonPriceLead = "Priced at ";
	$amazonPriceLead = "Only ";
	//$amazonPriceLead = "";
}
if (empty($amazonCacheDir))
{
	$amazonCacheDir = "cache_amazon/"; // MUST have the slash as part of it!
}
$cacheExt = '.bin';
//$forceNoRecache = true;

if (!isset($extraProductFields)) $extraProductFields = '';
if (!isset($shouldTrackShown)) $shouldTrackShown = true;

$lastAmazonASIN = '';
$lastAmazonCategory = '';
$lastAmazonAccessories = '';

$trackedAsins = Array();

$amazonCacheWhat = Array();
$amazonCacheGroup = Array();
$amazonCacheImgsize = Array();
$amazonCachedCount = 0;
$maxProductsPerBlock = 3; // no more!  keeps site tighter..

$outdatedCache = Array();

$amazonBlob = Array();
$amaCats = null;

//========================================
//========================================
if (!isset($AmazonDebug)) $AmazonDebug = 1;
// 0 == nothing
// 1 == logging
// 2 == forced lookups
// 3 == internal-search logging
//========================================
//========================================
require_once($myAmaPath."AmazonQueryMgr.php");
$AmazonQueryMgr->SetLocale($amazonLocale);
$AmaQueryError = '';
//========================================
//========================================

//========================================
function getAmazonCatList()
{
	global $AmazonQueryMgr;
	return $AmazonQueryMgr->GetCatalogArray();
}


//========================================
function lookupAmaCats()
{
	global $tablecgamazon;
	global $amaCats;
	
	if (empty($amaCats)) // then try to get results
	{
		$qresults = db_getresults("SELECT DISTINCT wpCategory FROM $tablecgamazon ORDER BY wpCategory ASC", OBJECT, "lookupAmaCats");
		if ($qresults)
		{ // collapse results to single-index array entries
			$amaCats = array();
			foreach($qresults as $acat)
				$amaCats[] = $acat->wpCategory;
		}
	}
	
	return($amaCats);
}

//========================================
function lookupAmaAsins($custom='', $catalog='', $bytime=false)
{
	global $tablecgamazon, $AmazonDebug;
	global $amazonAsins;
	global $lastLookup;

	if (strpos($custom, ','))
		$custom = explode(',', $custom);

	$globalSet = '_global_';
	if (empty($custom) || is_array($custom))
	{
		$catname = $globalSet;
		if (empty($custom) && !empty($catalog))
			$catname = '_'.$catalog.'_'; // make catalog identifier.
	}
	else
		$catname = $custom;
		
	$catslist = $catname;
	if (is_array($custom))
		$catslist = implode('+',$custom); // build something to do uniqueness tests
			
	$whereclause = '';
	if (empty($amazonAsins[$catname]) || $lastLookup != $catslist) // then try to get results
	{
		$orderby = 'ID ASC';
		if ($bytime)
			$orderby = 'amTime DESC, '.$orderby;
			
		if ($setname || empty($catalog))
		{
			if ($AmazonDebug>0) dbglog("CGA: looking up asins in group [$catslist]");
			if (is_array($custom))
			{
				$whereclause = "WHERE wpCategory IN (";
				$setcount = 0;
				foreach($custom as $amset)
				{
					if ($setcount) $whereclause .= ',';
					$whereclause .= "'".$amset."'";
					$setcount++;
				}
				$whereclause .= ")";
			}
			else
			if ($catname != $globalSet)
				$whereclause = "WHERE wpCategory='$catname'";
		}
		else
		{
			if (!empty($catalog))
			{
				$whereclause = "WHERE amCategory='$catalog'";
				if ($AmazonDebug>0) dbglog("CGA: looking up asins in Catalog [$catalog]");
			}
			else
			{
				if ($AmazonDebug>0) dbglog("CGA: looking up asins in entire database");
			}
		}
		
		if ($AmazonDebug>1) dbglog("CGA: asinlookup using where clause: '$whereclause'");
		
		$qselect = "SELECT DISTINCT ASIN FROM $tablecgamazon $whereclause ORDER BY $orderby";
		$qresults = db_getresults($qselect, OBJECT, "lookupAmaAsins");
		if ($qresults)
		{ // collapse results to single-index array entries
			$amazonAsins[$catname] = array();
			foreach($qresults as $asin)
				$amazonAsins[$catname][] = $asin->ASIN;
		}
		// this won't cover every case, but should do decently...
		$lastLookup = $catslist;
	}
	
	if ($AmazonDebug>1 && !empty($amazonAsins[$catname]))
		dbglog("CGA: asins in group [$catname] = <br>".implode('<br>' , $amazonAsins[$catname]));
	return($amazonAsins[$catname]);
}

function asinIsInDB($asin)
{
	global $tablecgamazon;
	$qresults = db_getresults("SELECT DISTINCT ASIN FROM $tablecgamazon WHERE ASIN='$asin'", OBJECT, "asinIsInDB");
	if (empty($qresults))
		return false;
	return true;
}

function cache_dbdata($asinList)
{
	global $tablecgamazon, $AmazonDebug;
	global $amazonDBData;
	
	dbglog("dbdata: ".serialize($asinList));
	if ($AmazonDebug>1) dbglog("CGA: cache_DBData passed: ".serialize($asinList));
	if (empty($asinList)) return;
	
	$newList = array();
	foreach($asinList as $asin)
	{
		if (empty($amazonDBData[$asin]))
			$newList[] = "'".$asin."'";
	}
	
	if (empty($newList)) return;
	
	$asinList = implode(',',$newList);
	if ($AmazonDebug>1) dbglog("CGA: looking up dbdata for [$asinList]");
	
	$whereclause = "WHERE ASIN IN (".$asinList.")"; // and sizeof metaNote>0
	$qresults = db_getresults("SELECT DISTINCT ASIN, metaNote, wpCategory FROM $tablecgamazon $whereclause ORDER BY ID ASC", OBJECT, "cache_dbdata");
	if ($qresults)
	{
		foreach($qresults as $data)
		{
			//if (!empty($data->wpCategory))
			{
				$amazonDBData[$data->ASIN] = $data;
				if ($AmazonDebug>1) dbglog("CGA: cached dbdata for $data->ASIN");
			}
		}
	}
//	if ($AmazonDebug>1 && !empty($amazonAsins))
//		dbglog("CGA: asins in group [$setname] = ".implode(', ' , $amazonAsins[$setname]));
}

//========================================
// CG-AMAZON STATE TRACKING AND MGMT FNS
//========================================
function amazon_cachefile_outdated($group)
{
	global $outdatedCache;
	return $outdatedCache[$group];
}

//========================================
function set_cachefile_outdated($group)
{
	global $outdatedCache;
	$outdatedCache[$group] = true;
}

//========================================
// pre-check any cache failures now.
function amazon_cachefile_checkup()
{
/* TBD - how does this work within new caching system?
	global $amazonGroups, $amazonAsins, $defaultAmazonImage;
	amazon_stop_tracking_shown(); // so we don't fuck with display.  this doesn't clear list, just prevents further tracking.
	foreach($amazonGroups as $group)
	{
		if (amazon_cachefile_outdated($group))
		{
			dbg_log("<B>Amazon: trying to regen cache file for $group.</B>");
			query_amazon($amazonAsins[$group], $group, false, $defaultAmazonImage);
		}
	}				
	amazon_start_tracking_shown(); // okay to start again.
*/
}

//========================================
function cache_amazon_inline($what, $dot, $title)
{
	global $amazonCachedCount, $amazonCacheWhat, $amazonCacheGroup, $amazonCacheImgsize;
	// make sure it isn't already in the cache...
	for ($i=0; $i<$amazonCachedCount; $i++)
		if ($amazonCacheWhat[$i] == $what) return;
	$amazonCacheWhat[$amazonCachedCount] = $what;
	$amazonCacheGroup[$amazonCachedCount] = $dot;
	$amazonCacheImgsize[$amazonCachedCount] = $title;
	$amazonCachedCount++;
	
//	dbglog("caching inline [$amazonCachedCount]: $what, $dot, $title");
}

//========================================
function cg_amazon_flush_cache($imgsize)
{
	global $AmazonDebug;
	global $amazonCachedCount, $amazonCacheWhat, $amazonCacheGroup, $amazonCacheImgsize, $maxProductsPerBlock;
	
	if ($amazonCachedCount==0) return;

	if ($AmazonDebug)
	for ($i=0; $i<$amazonCachedCount; $i++)
		dbglog("flush inline: $amazonCacheWhat[$i]");
	
	$k = $maxProductsPerBlock;
	if ($k>$amazonCachedCount) $k = $amazonCachedCount;
	
	if ($k==1)
		$newLookup[0] = &$amazonCacheWhat[0];
	else
	{
		$rand_keys = safe_array_rand($amazonCacheWhat, $k);
		$k = count($rand_keys);
		for ($i=0; $i<$k; $i++)
		{
			$c = $rand_keys[$i];
			$newLookup[$i] = &$amazonCacheWhat[$c]; // ref op so we don't copy...
		}
	}
	
	$output = query_amazon($newLookup, '', true, $imgsize, false);
	
	$amazonCacheWhat = array();
	$amazonCachedCount = 0;
	echo $output;
}

//========================================
function amazon_stop_tracking_shown()
{
	global $shouldTrackShown;
	$shouldTrackShown = false;
}

//========================================
function amazon_start_tracking_shown()
{
	global $shouldTrackShown;
	$shouldTrackShown = true;
}

//========================================
function track_as_shown($AsinList)
{
	global $trackedAsins, $shouldTrackShown;
	
	if (false==$shouldTrackShown) return;
	
	if (is_array($AsinList))
	{
		foreach($AsinList as $asin)
		{
			$trackedAsins[$asin] = true;
//			dbglog("showing amazon Asin = $AsinList");
		}
	}
	else
	{
		$trackedAsins[$AsinList] = true;
//		dbglog("showing amazon Asin = $AsinList");
	}
	
}

//========================================
function already_shown($AsinList)
{
	global $trackedAsins;
	if (is_array($AsinList))
	{
		foreach($AsinList as $asin)
		{
			if (isset($trackedAsins[$asin]) && $trackedAsins[$asin])
				return true;
		}
	}
	else
	{
		if (isset($trackedAsins[$AsinList]) && $trackedAsins[$AsinList])
			return true;
	}
		return false;
}

//========================================
function check_already_shown($AsinList)
{
	global $trackedAsins;
	if (is_array($AsinList))
	{
		$newNum = 0;
		$newArray = Array();
		foreach($AsinList as $asin)
		{
//			echo "checking $asin<br/>";
			if (!$trackedAsins[$asin])
			{
//				echo "= not found $asin<br/>";
				$newArray[$newNum] = $asin;
				$newNum++;
			}
			else
			{
//				echo "= already seen $asin<br/>";
			}
		}
		if ($newNum)
			return($newArray);
		else
			return null;
			
	}
	else
	{
		if ($trackedAsins[$AsinList])
			return null;
		else
			return($AsinList);
	}
}

//========================================
function get_annotation($Asin)
{
	global $amazonDBData;
	if (isset($amazonDBData[$Asin]))
		if (isset($amazonDBData[$Asin]->metaNote))
			return(stripslashes($amazonDBData[$Asin]->metaNote));
	return null;
}

//========================================
function get_wpCat($Asin)
{
	global $amazonDBData;
	if (isset($amazonDBData[$Asin]))
		if (isset($amazonDBData[$Asin]->wpCategory))
			return($amazonDBData[$Asin]->wpCategory);
	return null;
}

//========================================
function show_support($show = true)
{
	global $showSupport;
	
	if ($showSupport)
	{
		$suppStr = "<div class='support'>Support ".get_bloginfo('name')."</div>";
		if ($show)
			echo $suppStr;
		else
			return($suppStr);		
	}
}

//========================================
function show_amazon_disclaimers($before="<div class='disclaimer'>", $after="</div>")
{
	global $amazonShowPrices, $extraProductFields, $amazonMinimumData;
	
	//if ($showedProduct) // need better way to detect when to display this?
	{
		echo $before;
		echo "Disclaimer: All product data on this page belongs to Amazon.com or respective site(s). No guarantees are made as to accuracy of prices or product information.<br/>";
		if (!$amazonMinimumData && ($amazonShowPrices || $extraProductFields))
			echo "Prices listed are accurate as of the date/time indicated or otherwise within the last 24 hours.  Prices and product availability are subject to change.  Any price displayed on the Amazon website at the time of purchase will govern the sale of this product.";
		echo $after;
	}
}

//========================================
function show_amazon_ad($reallyShowAd=true)
{
	global $showedProduct, $showedAds, $showAmazonAds, $theAmazonAds;
	global $showAdsOnePost, $single;
	
	if (!$showAmazonAds) return(false);
	
	if (!$reallyShowAd)
	{
		//dbglog("show ads = $showAmazonAds, show single = $showAdsOnePost, single = $single");
		if (!$showAmazonAds || (!$showAdsOnePost && $single))
			return(false); // as if we showed it...
	}
	
	if ($showedAds) // show this once and only once...
		return(false);
	
	$numAds = count($theAmazonAds);
	if ($numAds==0)
		return(false);
		
	$showedAds = true;

	show_support();
	
	echo "<div class='shopat'>";
	$randNum = rand(0,$numAds-1);
	echo convert_chars($theAmazonAds[$randNum]);
	echo "</div>";
	
	return(true);
}

//========================================
function showed_amazon_product()
{
	global $showedProduct, $autoAmazonAd;
//	if ($showedProduct)
	if (!$autoAmazonAd || !show_amazon_ad(false))
		show_support();
	
	// for better page updates?
//	flush();
}


//========================================
$cacheTimestamp = null;
$cacheTimeRand = 0;
function check_needs_recache($name)
{
	global $cacheTimestamp, $cacheTimeRand, $CACHE_TIME, $amazonTime;
	global $amazonCacheDir, $myAmaPath,$cacheExt;
	global $AmazonDebug;
	$path = $myAmaPath . $amazonCacheDir . $name . $cacheExt;

//return(0); // NEVER RECACHES.
	
//	if ($cacheTimeRand==0)
		$cacheTimeRand = rand(1,600);
	
	$shouldRecache = 2;
	if ( file_exists ( $path ) )
	{
		//dbglog("CHECK AMAZON CACHE TIME.");
		$filemod = filemtime( $path );
		$cacheTimestamp = date('m/d/y g:ia', $filemod);
		//echo "\n\n\n<!-- ===== $filemod - ".time()."  [Updated ".($filemod - time())." seconds ago -->";
		$shouldRecache = 0;
		$deltaTime = $amazonTime - $filemod;
		if ($AmazonDebug>1) dbglog("CGA: Check cache ($path): [$deltaTime] > $CACHE_TIME - $cacheTimeRand");
		if ($AmazonDebug>2) // just force it.
			$shouldRecache = 3;
		else
		if ( $deltaTime > ($CACHE_TIME - $cacheTimeRand) ) // added 1-600s random so they don't all hit one pageload! ;)
		{
			$shouldRecache = 1;
		}
	}
	
	if ($shouldRecache>0)
	{
		if ($shouldRecache==3)
		{
			if ($AmazonDebug>0) dbglog("CGA: FORCED RECACHE OF $path");
		}
		else
		if ($shouldRecache==2)
		{
			if ($AmazonDebug>0) dbglog("CGA: MISSING CACHEFILE $path");
		}
		else
			if ($AmazonDebug>0) dbglog("CGA: cache out-of-date (needs requery): $name");
	}
	else
		if ($AmazonDebug>1) dbglog("CGA: cache still good for $path");
	
	return($shouldRecache);
}

//========================================
function get_last_timestamp()
{
	global $cacheTimestamp;
	if ($cacheTimestamp)
		return ($cacheTimestamp);
	else
		return '';
}

//========================================
function amazon_blob_loaded($name)
{
	global $amazonBlob;
	global $AmazonDebug;
	
	if (IsSet($amazonBlob[$name]) && !empty($amazonBlob[$name]))
		return(true);
	else
		return(false);
}


//========================================
function get_amazon_blob_creator(&$blob)
{
	global $AmazonDebug, $doMovieActors;
	
	if ($AmazonDebug>1) dbglog("Deciding on CREATOR...");
	if (empty($blob)) return null;
	
	$attrib = &$blob['ItemAttributes'];
	if (!empty($attrib['Manufacturer']))
		$creator = $attrib['Manufacturer'];
	// then, optionally override it in order...	
	if (!empty($attrib['Author']))
		$creator = $attrib['Author'];
	else
	if (!empty($attrib['Artist']))
		$creator = $attrib['Artist'];
	else
	if (!empty($attrib['Actor']) && $doMovieActors)
		$creator = $attrib['Actor'][0]; // !!!!TBD [0] is a hack to just use first 'top' actor...
	else
	if (!empty($attrib['Publisher']))
		$creator = $attrib['Publisher'];

	if (is_array($creator))
		$creator = implode(', ', $creator);

	if ($AmazonDebug>2) 
	{
		if (empty($creator))
		{
			dbglog($blob['ProductName']." has no good creator yet...");if (1)
			{
				dbglog("##########################");
				ob_start();
				print_r($blob['ItemAttributes']);
				$dbgit=ob_get_contents();
				ob_end_clean();
				dbglog(str_replace(array('(',')','['), array('<br/>(<br/>','<br/>)<br/>','<br/>['), $dbgit));
				return(null);
			}
		}
		else
			dbglog($blob['ProductName']." -- decided to use: ($creator)");
	}
	return $creator;
}

//========================================
function define_amazon_alt_images(&$blob)
{
	$newsmurl = str_replace('SCTHUMBZZZ', 'SDTHUMBZZZ', $blob["ImageUrlSmall"]);
	$blob['ImageUrlSmallMedium'] = $newsmurl;
	$blob['ImageUrlSmallShadowed'] = str_replace('_SCTHUMBZZZ', '_PC_SCTHUMBZZZ_', $blob['ImageUrlSmall']);
	$blob['ImageUrlSmallMediumShadowed'] = str_replace('_SCTHUMBZZZ', '_PC_SDTHUMBZZZ_', $blob['ImageUrlSmall']);
	$blob['ImageUrlMediumShadowed'] = str_replace('_SCMZZZZZZZ', '_PC_SCMZZZZZZZ_', $blob['ImageUrlMedium']);
	$blob['ImageUrlLargeShadowed'] = str_replace('_SCLZZZZZZZ', '_PC_SCLZZZZZZZ_', $blob['ImageUrlLarge']);
}

//========================================
function load_amazon_blob($name)
{
	global $amazonBlob, $amazonCacheDir, $myAmaPath,$cacheExt;
	global $AmazonDebug;

	$path = $myAmaPath . $amazonCacheDir . $name . $cacheExt;
	$filedata = null;
	if (file_exists($path))
		$filedata = file_get_contents($path);
	if ($filedata)
	{
		if ($AmazonDebug>0) dbglog("CGA: Loading blob file $name...");
		$amazonBlob[$name] = unserialize(/*base64_decode*/($filedata));
		if (!amazon_blob_loaded($name))
		{
			if ($AmazonDebug>0) dbglog("CGA: bad datablob file $name...");
			unset($amazonBlob[$name]);
			return(false);
		}
		else
		{
			$blob = &$amazonBlob[$name];
			if (!isset($blob['_Creator'])) // hack in our own field... this would normally be pulled in direct from the db table, not the blob...
			{
				$blob['_Creator'] = get_amazon_blob_creator($blob);
				
				$Price = &$blob['OurPrice'];
				$MSRP  = &$blob['ListPrice'];
				if (!$MSRP)
					$MSRP = $Price; // which if no price either, makes both ZERO.
				if (!$Price)
				{
					if (!$MSRP)
						$MSRP      	 = &$blob['ThirdPartyNewPrice'];
					if (!$MSRP)
						$MSRP = 'n/a';
					$Price = &$MSRP;
				}
				if ($Price && $MSRP && ($Price!=$MSRP))
				{
					$pctoff = 0;
					if (ctype_digit($Price{1}) || ctype_digit($Price{0}))
						$pctoff = intval(100 * floatval(substr($Price, 1, strlen($Price))) / floatval(substr($MSRP, 1, strlen($MSRP))));
					if ($pctoff!=0 && $pctoff!=100)
					{
						$pctoff = 100-$pctoff;
						$pctnum = strval($pctoff);
						if (strlen($pctnum)==1) $pctnum = '0'.$pctnum;
						$pctnum = '_PE'.$pctnum.'_SC';
						$blob['_PercentOff'] = $pctoff;
						$blob['ImageUrlSmallOff'] = str_replace('_SC', $pctnum, $blob['ImageUrlSmall']);
						$blob['ImageUrlMediumOff'] = str_replace('_SC', $pctnum, $blob['ImageUrlMedium']);
						$blob['ImageUrlLargeOff'] = str_replace('_SC', $pctnum, $blob['ImageUrlLarge']);
					}
				}
				
				// add in the new smallmedium image size
				define_amazon_alt_images($blob);
			}
			return(true);
		}
	}
	
	if ($AmazonDebug>0) dbglog("CGA: no datablob file $name...");
	return(false);
}

//========================================
$amazonFailedBlobWrite = false;
function save_amazon_blob(&$blob, $name, $notToDisk=false)
{
	global $amazonBlob, $amazonCacheDir, $myAmaPath,$cacheExt;
	global $AmazonDebug;
	global $amazonFailedBlobWrite;
	
	$amazonBlob[$name] = $blob;
	// hack in our own field... this would normally be pulled in direct from the db table, not the blob...
//	$amazonBlob[$name]['_Creator'] = get_amazon_blob_creator($blob);

	if ($notToDisk) return;
	
	$path = $myAmaPath . $amazonCacheDir . $name . $cacheExt;
	
	if ($AmazonDebug>1) dbglog("CGA: trying to write blob file $path.");
	$cacheFile = @fopen($path,"w");
	if ($cacheFile==FALSE)
	{
		if (!$amazonFailedBlobWrite)
			echo "CG-Amazon failed to cache to disk -- couldn't write file to the cache_amazon directory.";
		$amazonFailedBlobWrite = true;
		dbglog("CGA: unable to write blob file to $path.");
	}
	else
	{
		if (flock($cacheFile, LOCK_EX)) {
			fwrite($cacheFile, /*base64_encode*/(serialize($blob)));
			flock($cacheFile, LOCK_UN);
		}
		fclose($cacheFile);
	}	
}

//========================================
function get_amazon_asin_blob($asin)
{
	global $amazonBlob;
	global $AmazonDebug;
	
	$name = 'Asin'.$asin;
	if (amazon_blob_loaded($name))
		return($amazonBlob[$name]);
		
	if (load_amazon_blob($name))
		return($amazonBlob[$name]);

	return null;		
}

//========================================
function ama_key_clean($keysearch)
{
	global $AmazonDebug;
	if ($AmazonDebug>1) dbglog("CGA cleaning keyword: $key");
	// strip parens from $laa... maybe strip the terms in the parens too...
	$keysearch = preg_replace("/[(][^)]*[)]/", '', $keysearch);
	$keysearch = preg_replace("/[\[][^)]*[\]]/", '', $keysearch);
	$keysearch = str_replace(array("`", "'", "\"", "\\"), '', $keysearch); // remove bad chars.
	$keysearch = str_replace(array(",", "-", ":", "\/", "&"), ' ', $keysearch); // remove bad chars.
	$keysearch = preg_replace('#\s{2,}#s', ' ', $keysearch); // smoosh multi spaces to a single space.
	$keysearch = strtolower($keysearch); // lowercase it!
	$keysearch = rtrim($keysearch); // remove trailing whitespace.
	return($keysearch);
}

//========================================
// for now, this will only grab the first <=10 items, the first 'page' of results.
function show_keyword_items($origKey, $amcat='', $cachename='', $where='', $count=3, $random=0, $image='Small', $show=true, $returnAsins=false, $alphaSort=false, $style='')
{
	global $forceExternalLinks, $amazonMinimumData, $amaNoProductsString;
	global $AmazonDebug;
	
	if ($AmazonDebug>1) dbglog("CGA Keyword: got input: <b>$keysearch</b>, count = $count, wants ".($returnAsins?'Asins':'Results'));
	$keysearch = $origKey;
	if (empty($keysearch))
	{
		$output = "No keywords given.";
		if ($returnAsins) // then we handle differently
			return($output);
	}
	else
	{
		if (is_array($keysearch))
		{
			foreach($keysearch as $key=>$word)
				$keysearch[$key] = ama_key_clean($word);
		}
		else
		{		
			$keysearch = ama_key_clean($keysearch);
			if ($AmazonDebug>1) dbglog("CGA Keyword: Cleaned = <b>$keysearch</b>");
		}
	
// hack to test bad strings
//		$keysearch .= "ANDA BUNCHA JUNK";

		if (!is_array($keysearch)) /// !!!!!TBD
		{
			$terms = explode(' ', $keysearch); // make into array of els.
			if ($alphaSort)
				sort($terms); // alpha.
			
			// do a manual implode, stripping 'bad' words on the fly.
			$searchfor = array('the', 'a', 'an', 'i', 'of');
			$keysearch = '';
			$i=0;
			foreach ($terms as $word)
			{
				$skip = false;
				foreach ($searchfor as $forword)
					if ($word == $forword)
					{
						$skip = true;
						break;
					}
				if ($skip) continue;
							
				if ($i) $keysearch .= ' '; // space between terms.
				$keysearch .= $word;
				$i++;
			}
			if ($AmazonDebug>1) dbglog("CGA Keyword: cleaned and alpha-sorted: <b>$keysearch</b>");
		}			
		
		if ($cachename == 'NOCACHE')
			$noCache = true;
		if ($cachename != 'NOCACHE')
		{
			if (is_array($keysearch))
			{
				$cachename = '';
				foreach($keysearch as $key=>$word)
				{
					if (!empty($cachename)) $cachename .= ' '; // space between clauses.
					$cachename .= $key.' '.$word;
				}
			}
			else
				$cachename = $keysearch;
			$cachename = stripslashes(strip_tags($cachename)); // strip everything else bad.
			$cachename = str_replace(array("\'"), ' ', $cachename); // remove bad chars.
			$cachename = preg_replace('#\s{2,}#s', ' ', $cachename); // smoosh multi spaces to a single space, again...
			$cachename = str_replace(" ", '_', $cachename); // convert spaces to underscores for nice filenames
			if ($AmazonDebug>1) dbglog("CGA Keyword: converted for caching: <b>$cachename</b>");
		}
		
		if (is_array($keysearch)) // spaces to %20
			foreach($keysearch as $key=>$word)
				$keysearch[$key] = str_replace(' ','%20',$word);
				
		if ($count<1) $count = 1;
		if ($count>50)
		{
			if ($AmazonDebug>1) dbglog("CGA Keyword: requested $count items, clamping to 50");
			$count=50; // just to clamp
		}
		
		$imageSize = get_ama_image_size($image);
		
		if ($where=='local') // don't go out to amazon for it...
		{
			$inCat = '';
//			if ($amcat) //!!!!TBD
//
			$asins = db_getresults("SELECT * FROM $tablecgamazon WHERE $incat MATCH (amName, amCreator) AGAINST ('$keysearch')", OBJECT, 0, "admin - fulltext search");
			die(serialize($asins));
		}
		else
			$output = query_amazon($keysearch, $cachename, !$returnAsins, $imageSize, !$amazonMinimumData,
																$random, !$returnAsins, 'Keywords', $count, $amcat,
																$style, false, false, false, true, !$forceExternalLinks,
																$returnAsins, '');
		if ($returnAsins) // then we handle differently
			return($output);
	}

	if ($show)
	{
		if ($output)
			echo $output;
		else
			echo $amaNoProductsString;
	}

	return($output);
}

//========================================
// for now, this will only grab the first <=100 items.
function show_wishlist_items($listID='', $count=1, $image=true, $show=true, $style='')
{
	global $forceExternalLinks, $amazonMinimumData;
	global $AmazonDebug;
	global $myAmazonWishlist, $amaNoProductsString;
	
	if (empty($listID))
		$listID = $myAmazonWishlist;

	if (empty($listID))
	{
		$output = "Empty wishlist given.";
	}
	else
	{	
		if ($count<1) $count = 1;
		if ($count>100) $count=100;
		
		$imageSize = get_ama_image_size($image);
		
		//$external = false; // wishlist MUST force external...
		$external = !$forceExternalLinks;
		$output = query_amazon($listID, '', true, $imageSize, !$amazonMinimumData,
																$count, true, 'Wishlist', $AmazonQMax, '',
																$style, false, true, false, true,
																$external);
	}

	if ($show)
	{
		if ($output)
			echo $output;
		else
			echo $amaNoProductsString;
	}

	return($output);
}

//========================================
function show_amazon_items($count=1, $mode='rand', $image=true, $wpCat='', $amCat='', $show=true, $style='')
{
	global $forceExternalLinks, $amazonMinimumData, $amaNoProductsString;
	global $AmazonDebug;
	
	$output = null;
	if ($count<1) $count = 1;
	$someAsins = lookupAmaAsins($wpCat, $amCat, $mode=='rand'?false:true);
	if ($count>count($someAsins)) $count = count($someAsins);

	if (!empty($someAsins))
	{
		if ($mode=='rand')
		{
			$rand_keys = safe_array_rand($someAsins, $count);
			$count = count($rand_keys);
			if ($count==1) // just a direct index...
			{
				$randAsins[0] = &$someAsins[$rand_keys]; // ref op so we don't copy...
			}
			else
			for ($i=0; $i<$count; $i++)
			{
				$c = $rand_keys[$i];
				$randAsins[$i] = &$someAsins[$c]; // ref op so we don't copy...
			}
		}
		else
		{ // not random.  recent additions...
			for ($i=0; $i<$count; $i++)
				$randAsins[$i] = &$someAsins[$i]; // ref op so we don't copy...
		}
		
		// since the lookup came from the DB, if we're in 'minimal mode', we can use a simpler function
		if (0 && $amazonMinimumData)
		{
			$output = query_database($randAsins, $image);
		}
		else
		{
			$imageSize = get_ama_image_size($image);
		
			$output = query_amazon($randAsins, '', true, $imageSize, !$amazonMinimumData,
																	0, true, 'Asin', $AmazonQMax, $amCat,
																	$style, false, true, false, true, !$forceExternalLinks);
		}
	}	
	
	if ($show)
	{
		if ($output)
			echo $output;
		else
			echo $amaNoProductsString;
	}

	return($output);
}

//========================================
function query_database($asinList, $showImages)
{
}

//========================================
// THE MAIN INTERFACE FUNC FOR CG-AMAZON
//========================================
function query_amazon(
						$searchData, $cacheName, $buildOutput=true, $imageSize='Small', $showtime=true,
						$randomNum=0, $heavyData=true, $searchType='Asin',
						$searchMax=50, $searchCat='',
						$divPrefix='', $button=false, $extraData=false,
						$showSomeSupport=false, $showAnnotation=true, $cgaindexLinks=false,
						$returnAsins = false, $noProductsOut='' )
{
	global $CACHE_TIME, $amazonCacheDir, $myAmaPath, $siteurl;
	global $AmazonDebug;
	global $AmazonQueryMgr; // the main search object.  create it once!
	global $AmaQueryError;
	global $CurrentAmazonItem, $amazonImageOnly, $amazonImageFirst, $amazonMinimumData, $amazonLocale;
	global $amazonWrapperDiv, $amazonWrapInfo, $amazonInfoBreak;
	global $showedProduct, $extraProductFields, $amazonShowCreator, $amazonShowBlogCat, $amazonShowPrices, $amazonClickForPrice, $amazonPriceLead, $buyButtonShown, $amaTargetWindow;
	global $lastAmazonASIN, $showCacheTime, $lastQueryTime, $forceNoRecache;
	global $lastAmazonCategory, $lastAmazonAccessories;
	global $restrictRapidQueries, $forceExternalLinks;
	global $showWishlistCount,$showWishlistDates,$showWishlistName;
	global $amazonLineBreak;
	global $amazonEncoding;
	
	global $amazonTime, $amazonBlob, $cacheExt;
	global $tag_who, $myplugins, $myAmaPath;

	if (!file_exists($myAmaPath . $amazonCacheDir))
	{
		echo "CRITICAL FAILURE: Amazon cache directory [$myAmaPath$amazonCacheDir] doesn't exist!";
		return(null);
	}
	
	$justPreview = false;
	if ($imageSize=='Preview')
	{
		$justPreview = true;
		$imageSize = 'Small';
		// turn off everything, just in case...
		$showAnnotation = false;
		$button = false;
		$extraData = false;
		$cgaindexLinks = false;
		$showTime = false;
	}
	
	$noCache = false;
	if ($cacheName=='NOCACHE') // hack to disable caching...
		$noCache = true;
		
	if ($searchMax==0)
		$searchMax = 50; // default to something 'nominal'
		
	if ($AmazonDebug>1) dbglog("CGA: $searchType $searchMax $searchData ".($heavyData?'heavy':'lite'));

//	if ($AmazonDebug>0) dbglog("CGA: showing prices = $amazonShowPrices");
	
	$amazonCacheTimeMin = 24 * 60 * 60; // hr * min/h * secs/m
	if ($amazonMinimumData && !$amazonShowPrices) // then can cache longer
		$amazonCacheTimeMin *= 7;  // could do up to 30 or something, let's start with 7
	else
	if (!$amazonShowPrices || $amazonClickForPrice)
//		$amazonCacheTimeMin = 60*60*24 * 120; // 120d for now, to fix code... 
		$amazonCacheTimeMin = 60*60*rand((7*24),(11*24));  // 7-11 day spread by hours
	if ($CACHE_TIME < 60 || $CACHE_TIME > $amazonCacheTimeMin) // require 60s minimum
		$CACHE_TIME = $amazonCacheTimeMin; 
		
	// these MUST remain in THIS ORDER!
	if (empty($imageSize)) $imageSize='Small';
	if ($imageSize=='None') $imageSize='';
	
	$showedProduct++; // increment counter...
	$output = ''; // clear string to start.
	$Results = Array(); $QueryResults = Array();
	$tag_who = "amazon"; // for generality.
	$searchOn = $searchType; // so we can change the search type on the fly...

	$doLookup = true;
	$doMatch = false;
	$PrintAll      = false;
	$qwhy = '';
	$cachePath = '';

//	if (is_array($extraProductFields)) // then extra data to output...
//		$heavyData = true; // we need extra response data.

	if (is_array($searchData))
		$single = false;
	else
		$single = true;
	$searchString = $single; // keep the fact that we have string vs array...
		
	if ($searchType == "Similar") // only works with Asins...
	{
		$single = false; // since we're looking for multiple results...
		$searchOn = 'Asin';
	}
	else
	if ($searchType != "Asin"
	&&	$searchType != "Upc") // only works with Asins...
	{
		$single = false; // since we're looking for multiple results...
	}
	
	if ($single)
	{
		if ($searchType=='Asin') // then track
			$lastAmazonASIN = $searchData;
		$randomNum = 0; // don't touch random stuff if single lookup determined.
	}
	
	if ($searchType=='Asin'
	||	$searchType=='Upc')
		$doMatch = true; // we have a list, only show those items, even if cache has more stored...
	
	$nuCache = ($searchType=='Asin'||$searchType=='Upc');
	
	$noCacheGiven = empty($cacheName);
	if ($noCacheGiven)
	{
		if ($single || $searchType=='Similar' || $searchType=='Wishlist')
			$cacheName = $searchType.$searchData;
		else
		{
			if ($searchString)
				$cacheName = $searchType.md5($searchData);
			else
				$cacheName = $searchType."_unkcache1";
		}
	}
	else
		if (!$nuCache)
			$cacheName = $searchType.'_'.$amazonLocale.$searchCat.'_'.$cacheName;
				
	$cachePath = $myAmaPath . $amazonCacheDir . $cacheName . $cacheExt;
		
	if ($AmazonDebug>0) dbglog("CGA: query type = $searchType, data = ".serialize($searchData).", cache = $cacheName");
	//$output .= "CHECK CACHE.\n";
	//$amazonTime = time();

	$cachedItems = array();
			
	if ($nuCache)
	{
		if (is_array($searchData) && $randomNum && $randomNum < count($searchData))
		{ // build random-order set.
			$checkItemCount = count($searchData);
			$maxCheckItems = $randomNum+3; // +3 gives it a little flexibility if bad files around...
			$rand_check = safe_array_rand($searchData, $checkItemCount);
			$checkItemCount = count($rand_check);
			$checkItems = array();
			for ($i=0; $i<$checkItemCount; $i++)
				$checkItems[$i] = &$searchData[$rand_check[$i]];
		}
		else
		{
			if (is_array($searchData))
				$checkItems = &$searchData;
			else
				$checkItems[0] = $searchData;
			$maxCheckItems = count($checkItems);
		}
	
		$searchItems = array();
		$currNumItems = 0;
		foreach($checkItems as $checkIt)
		{
			$tmpName = $searchType.$checkIt;
			$shouldRecache = check_needs_recache($tmpName);
			if ($shouldRecache<2) // I think we ALWAYS should load the blob if we can... || ($justPreview && $shouldRecache<2)) // when previewing, out of date files are okay, just try to force load them anyway...
			{
				if ($currNumItems >= $maxCheckItems) continue; // skip this one
				if (!$noCache && !load_amazon_blob($tmpName))
					$shouldRecache = 2;
			}
			if ($justPreview && $shouldRecache<2)
			{
				if ($AmazonDebug>0) dbglog("CGA: preview img $tmpName");
				$shouldRecache = 0; // don't recache for preview images!!!
			}
			if ($shouldRecache>0)
				$searchItems[] = $checkIt; // even if blob loaded, try to query.
			else
			{
				$currNumItems++; // we only count items we'll be pulling off disk -- or I should say HAVE pulled off disk already in load_amazon_blob...
				$cachedItems[] = $tmpName;
			}
		}
		
		$doLookup = false;
		if (!empty($searchItems))
		{
			$doLookup = true;
			$qwhy = "CGA: nucache needs to find new items";
		}
	}
	else // old cache method
	{
		$doLookup = true;
		if (is_array($searchData))
			$checkItems = &$searchData;
		else
			$checkItems[0] = $searchData;
		$searchItems = &$checkItems;
		if ($AmazonDebug>0) dbglog("CGA: searching ".serialize($searchData));
	
		if ($AmazonDebug>0) dbglog("CGA: cache check = ".($single?"single ":"multi ").($noCacheGiven?"nocache":"cached"));
		if ( !$noCache && file_exists ( $cachePath ) )
		{
			//dbglog("CHECK AMAZON CACHE TIME.");
			$filemod = filemtime( $cachePath );
			$cacheTimestamp = date('m/d/y g:ia', $filemod);
			//echo "\n\n\n<!-- ===== $filemod - ".time()."  [Updated ".($filemod - time())." seconds ago -->";
			$shouldRecache = ( ( $amazonTime - $filemod + rand(0,600) ) > $CACHE_TIME ); // added 0-600s random so they don't all hit one pageload! ;)
			if ($AmazonDebug>0) dbglog("CGA: ".($shouldRecache?"Need to recache":"Cache okay for")." $cacheName$cacheExt");
			
			if ($shouldRecache) // Then cachefile was outdated.
			{
				set_cachefile_outdated($cacheName);
				
				// are we trying to recache a single entry of a bigger cache file?
				if ($single && !$noCacheGiven) // then we shouldn't recache right now...
					$shouldRecache = false;
				if ($AmazonDebug>1) dbglog("CGA: ".$shouldRecache?"LOOKUP-STILL":"SINGLE-SO-GETCACHE");
					
				if ($shouldRecache && $restrictRapidQueries) // welll... only recache if haven't hit query too recently.
				{
					$shouldRecache = ( $amazonTime - $lastQueryTime > 1 ); // decent since we have per-query overhead anyway.
					if (!$shouldRecache)
						dbglog("CGA: wanted to query ($cacheName$cacheExt), but TOO SOON (under 1s == ".($amazonTime - $lastQueryTime)." since prev query...)");
				}
			}
				
			if ( !$shouldRecache || $forceNoRecache )
				$doLookup = false;
			else
			{
				$qwhy = "cache file $cacheName$cacheExt OUTDATED";
			}
		
			// for the moment, always preload the results from cache if we can.
			// this is in case of failure of the ping to amazon...
			
			//if (!$doLookup)
			{ /* try to grab from file */
		//			dbglog("TRY TO READ CACHE.");
				$filedata = file_get_contents($cachePath);
				$Results = unserialize(/*base64_decode*/($filedata));
				
				if ($AmazonDebug>2) // to temp force lookups
				{
					$doLookup = true;
					$qwhy = "debugmode forced";
				}
				else
				if ($searchType=='Similar' || $searchType=='Wishlist') // then we eat error cases like a null file...
				{
					if (empty($Results))
						$Results = Array(); // REALLY CLEAR IT!
					if ($AmazonDebug>0) dbglog("Similarity cachefile was ".(empty($Results)?"EMPTY":"not empty"));
				}
				else
				if (empty($Results))
				{
					$doLookup = true;
					$qwhy = "cache file $cachePath was empty";
					//$output .= "UNSERIALIZE FAILED.\n";
				}
				else // got something in the file.  see if our element is there, otherwise need to go fetch.
				{
					if ($single == false)
					{
						$doLookup = $shouldRecache; // assume we match whatever was supposed to be in the file...
					}
					else // look to find the single entry in the cache file.
					{
						$doLookup = true;
						$qwhy = "cache file $cachePath didn't contain item ($searchOn) $searchData";
		//					dbglog("TRYING TO FIND $searchData IN $cachePath.");
						$k = count($Results);
						for ($i=0; $i<$k; $i++)
						{
							$ResultRow = $Results[$i];
							$result    = $ResultRow[$searchOn];
		//						dbglog(".. result = $result ($searchOn)");
							if ($result == $searchData) // match!
							{
		//							echo "Result MATCHED<BR/>";
								$doLookup = $shouldRecache;
								break;
							}
						}
					}
				}
			}
		}
		else
		{
			if ($noCache)
				$qwhy = "NOCACHE specified.";
			else
				$qwhy = "cache file $cacheName$cacheExt DOES NOT EXIST.";
			set_cachefile_outdated($cacheName);
			//dbglog("Missing CACHE: $cachePath for ".($single?"single ($searchData)":"multi")." query.");
		}
	}
	
	$doWriteCache = false;
	if ($doLookup)
	{
		if ($AmazonDebug>0) dbglog("CGA: needed to run Query = $qwhy.");
		//$output .= "REQ SEARCH.\n";
		$lastQueryTime = time(); // store IMMEDIATE time value...
		
		/* Set up search mode */
		$answerSize = 'Medium'; /* setting this to heavy gets us much more data, but takes longer too! */
//		if ($AmazonDebug<2) // to have debug always lite lookups
			if ($heavyData)
				$answerSize = 'Large';
		
		if ($AmazonDebug>0)
		{
			dbglog("CGA: query size = $answerSize, max = $searchMax");
		}
		
		$AmazonQueryMgr->SetQueryParams('', $answerSize, $searchMax);

		if ($AmazonDebug>0) $querytimer = timer_stop(0); // to make sure it is reset...
		$QueryResults = $AmazonQueryMgr->RunQuery($searchType, $searchItems, $searchCat);
		if ($AmazonDebug>0) dbglog("CGA: Query time = ".number_format(timer_stop(0)-$querytimer,3));
		
		$AmaQueryError = '';

		if ($searchType=='Seller') //skip to directly returning results for now.
			return($QueryResults);
		
//		dbglog("Query results = ".serialize($NewResults));
		if ($QueryResults && !is_array($QueryResults))
		{ // must be an error message...
			$AmaQueryError = $QueryResults;
			dbglog("<b>CGA: Query failure in CG-Amazon:<br/></b><i>$AmaQueryError</i>");
			$QueryResults = null;
		}
		
		if ($QueryResults==null || count($QueryResults)==0) // means no error, search just had no result.
		{// then dbglog, but save out THEN we return null back... so that callers can nix empty blocks.
			$QueryResults = Array(); // blank it out...
			if ($AmazonDebug>0) dbglog("CGA: query on $searchType found no items.");
			
			if ($nuCache) // eeek.  try to just chuck the searchitems onto the cacheditems array.
			{
				if (!empty($searchItems))
				{
					if (is_array($searchItems))
					{
						foreach($searchItems as $oldItem)
							$cachedItems[] = $oldItem;
					}
					else
						$cachedItems[] = $searchItems;
				}
				// else we continue...
			}
			else // old cache method, so if results empty, we're screwed.
			{
				if (empty($Results))
				{
					if ($AmaQueryError && $AmazonDebug>1) // otherwise, EAT IT.
						return ($AmaQueryError);
					else
						return($noProductsOut);
				}
				if ($AmazonDebug>0) dbglog("CGA: NO RESULTS from query.  Using last-cached results.");
			}
		}
		else
		{
			// comment this out if you don't want to write to the cache, for testing purposes...
			$doWriteCache = true;
			$Results = &$QueryResults;
		}
	}
	
	if (1 || $nuCache) // handle results tweaking
	{
		// write out new result items...
		if ($doWriteCache)
		{
			if ($searchType=='Asin' || $searchType=='Upc')
			{
//				if ($AmazonDebug>1) //!empty($Results))
//						dbglog("results = $Results");
//				echo "results = $Results";
				if (!empty($Results))
				foreach($Results as $keyname => $saveItem)
				{
					$saveID = $saveItem['Asin'];
					if ($saveID)
					{
						$tmpName = $searchType.$saveID;
						save_amazon_blob($Results[$keyname], $tmpName, $noCache); // pass Results so that the blob gets modified inline
					}
				}
			}
			else // until we deal with Similarity searches by opening the original cache...
//			if ($searchType=='Similar' || $searchType=='Wishlist')
//			if ($searchType=='Keyword') // try using the cachename...
			{
				// try just using the cachename already set up for us.
				save_amazon_blob($Results, $cacheName, $noCache);
			}
			// NOT HANDLING KEYWORD RESULTS YET!!! TBD!!! TODO!!!
		}
		
		$cr = count($Results);
		if ($AmazonDebug>1) dbglog("CGA: nucache : found $cr new products");
		
		// tack on cached items
		$ci = count($cachedItems);
		if ($AmazonDebug>1) dbglog("CGA: nucache : had $ci cached products");
		if ($ci)
			foreach($cachedItems as $gotIt)
				if (amazon_blob_loaded($gotIt))
				{
					if ($AmazonDebug>0) dbglog("CGA: nucache : adding on $gotIt to result list");
					$Results[] = &$amazonBlob[$gotIt];
				}

		$cfr = count($Results);
		if ($AmazonDebug>0) dbglog("CGA: nucache : ($cr+$ci) = $cfr products total");
		
		$doWriteCache = false; // we already did... ;)
	}

	$k = count($Results);
	if ($k==0)
	{
		if ($AmazonDebug>0) dbglog("CGA: there were no results at all.");
		if ($AmazonDebug>1) // otherwise, EAT IT.
			return $AmaQueryError; // output nothing, except possible error string...
		else
			return $noProductsOut;
	}
	
	if ($k>$searchMax) // !!! SHOULD POST AN ERROR
	{
		// double sanity-check!!!
		if ($searchMax<1)
			$searchMax = 50; // default to something 'nominal'
		//echo "requested max=$searchMax, got $k results!<br/>";
		$k = $searchMax;
	}
	if ($AmazonDebug>1) dbglog("CGA: output count = $k");

	$le = "\n"; // inside a post, this causes <br> generation... "\n"; // line ending...
	if ($amazonImageOnly) $le = ''; // blank.
	if ($single)
	{
		$le = "";
		if ($searchOn=='Asin' && $k)
		{
			$ResultRow   = $Results[0];
			$lastAmazonCategory = $ResultRow['Catalog'];
			$lastAmazonAccessories = $ResultRow['Accessories'];
		}
	}
		
	if ($buildOutput || $returnAsins) // then go through building up toward $output...
	{
		// reduce the working set to what we want to show...
		$newResults = Array();
		$newResultCount = 0;
		for ($i=0; $i<$k; $i++)
		{
			$ResultRow   = $Results[$i];
			$Asin        = $ResultRow['Asin']; // in case $productKey isn't Asin...
			// store primary key...
			$productKey      = $ResultRow[$searchType];
			if ($AmazonDebug>1) dbglog("CGA: result #$i ASIN = $Asin");
			
			if (($k > 1) && ($single)) // looking for one specific ASIN
				if ($productKey != $searchData) // no match, continue
					continue;
			
			if (already_shown($Asin))
				if (!$single)
					continue;
				
	/* // this code would allow passing a smaller sub-result set to pull from a cache... sorta dangerous in hindsight.
			if ($doMatch) // try and find key in $searchData
			{
				$foundMatch = false;
				if (is_array($searchData)) // always show singles?
				{
					foreach($searchData as $searchKey)
						if ($searchKey==$productKey)
						{
							$foundMatch = true;
							break;
						}
					if (!$foundMatch) continue;
				}
			}
	*/
			
			$newResults[$newResultCount] = $ResultRow;
			$newResultCount++;
		}
		
		if ($randomNum > $newResultCount)
		{
			if ($AmazonDebug>1) dbglog("CGA: Asked for random ".$randomNum." but only ".$newResultCount." to pick from...");
			$randomNum = 0; // just output what we've got
		}
			
		if ($randomNum)
		{
			//dbglog("Trying a random set of ".$randomNum);
			$rand_keys = safe_array_rand($newResults, $randomNum);
			$k = count($rand_keys); // changes the loop iterator to only loop for num of random entries
		}
		else
			$k = $newResultCount;
			
		// go through and process what asins we're actually dealing with, and go lookup any stored DB data.
		$showingAsins = array();
		for ($i=0; $i<$k; $i++)
		{
			if ($AmazonDebug>1) dbglog("CGA: processing showingAsins[$i]");
			if ($randomNum)
				$c = $rand_keys[$i];
			else
				$c = $i;
			$ResultRow   = &$newResults[$c]; // ref op so we don't copy...
			$Asin        = $ResultRow['Asin']; // in case $productKey isn't Asin...
			$showingAsins[] = $Asin;
		}	
		if ($showAnnotation || $amazonShowBlogCat)
			cache_DBData($showingAsins);
		
		// THIS IS AN EARLY EXIT!  NOTHING ELSE GETS EXECUTED PAST THIS IF HIT!
		if ($returnAsins)
			return($showingAsins); // so we get them in order.
				
		for ($i=0; $i<$k; $i++)
		{
			if ($randomNum)
				$c = $rand_keys[$i];
			else
				$c = $i;
				
			$CurrentAmazonItem = &$newResults[$c]; // ref op so we don't copy...
			// store primary key...
			$productKey      = &$CurrentAmazonItem[$searchType];
			
			$Asin        = &$CurrentAmazonItem['Asin']; // in case $productKey isn't Asin...
			$URL         = &$CurrentAmazonItem['Url'];
			$ProductName = &$CurrentAmazonItem['ProductName'];
			$ProductName = safehtmlentities($ProductName, ENT_QUOTES);
			$Creator     = &$CurrentAmazonItem['_Creator'];
			$Price       = &$CurrentAmazonItem['OurPrice'];
			$MSRP 			 = &$CurrentAmazonItem['ListPrice'];
			if (!$MSRP)
				$MSRP = $Price; // which if no price either, makes both ZERO.
			if (!$Price)
			{
				if (!$MSRP)
					$MSRP      	 = &$CurrentAmazonItem['ThirdPartyNewPrice'];
				if (!$MSRP)
					$MSRP = 'n/a';
				$Price = &$MSRP;
			}

			if ($AmazonDebug>1 && empty($Creator)) dbglog("CREATOR WAS EMPTY");
			
			// this will do the random replacement rules to insert/replace associate ID.
			$prodURL = $URL;
			if (has_assoc_ID())
			{
				$searchFor = $AmazonQueryMgr->AmazonAssocID; // should give us whatever was used in the search...
				$replaceWith = get_assoc_ID(true, $single?1:0);
				if ($searchFor==$replaceWith) // if the same, ignore.
				{
					$searchFor = null;
					$replaceWith = null;
				}
				if ($searchFor)
					$prodURL = str_replace($searchFor, $replaceWith, $URL);
			}
			
			if ($imageSize!='Link')
			{		
				if ($output=='') // not yet begun!
				{
					if ($amazonWrapperDiv) $output .= "<div class='".$tag_who."-item-wrap'>".$le;
					$output .= cga_block_start($divPrefix);
					if ($showSomeSupport && $imageSize && ($imageSize != 'Small')) $output .= show_support(false);
				}
				
				if (empty($divPrefix))
					$output .= "<li>".$le;
					
				if ($amazonWrapInfo=='li')
					$output .= "<ul class='$tag_who-item'>".$le;
	/*
				else
				if ($amazonWrapInfo=='span')
					$output .= "<div class='$tag_who-item'>".$le;
	*/		
			}
			
			if ($justPreview)
			{
				// nada
			}
			else
			if ($cgaindexLinks) // && !$forceExternalLinks) // this disables some admin features...
			{
				$output .= "<a href='$siteurl/cgaindex.php?p=ASIN_$Asin' title='More about $ProductName'>".$le;
			}
			else
			{
				$output .= "<a href='$prodURL' title='$ProductName @ ".strtoupper($tag_who.($amazonLocale=='us'?'':".$amazonLocale"))."'";
				if ($amaTargetWindow)
					$output .= " target='$amaTargetWindow'";
				$output .= '>'.$le;
			}
		
			if ($imageSize=='Link')
			{
				$output .= $ProductName.'</a>'.$le;
			}
			else
			{
				$Image = '';
				$urlSize = "ImageUrlSmall";
				if ($imageSize)
				{
					$urlSize = "ImageUrl$imageSize";
					$Image		 = &$CurrentAmazonItem[$urlSize];
					if (empty($Image))
					{ // put it back to small!
						$urlSize = "ImageUrlSmall";
						$Image		 = &$CurrentAmazonItem[$urlSize];
					}
				}
				if ($amazonShowPrices && !$justPreview && !$amazonImageOnly && !empty($CurrentAmazonItem[$urlSize.'Off']))
					$Image = &$CurrentAmazonItem[$urlSize.'Off'];
				
				$CurrentAmazonItem["ImageUrl"] = &$CurrentAmazonItem[$urlSize];
				if (!$justPreview && !$amazonImageOnly)
					if (!$amazonImageFirst)
						$output .= "<$amazonWrapInfo class='t-$tag_who'>$ProductName</$amazonWrapInfo>".$amazonInfoBreak.$le;
				if ($imageSize && $Image)
				{
					$output .= "<$amazonWrapInfo class='b-$tag_who'>".$le;
					$output .= "<img src='$Image' alt='$ProductName' />".$le;
					$output .= "</$amazonWrapInfo>".$amazonInfoBreak.$le;
				}
				if (!$justPreview && !$amazonImageOnly)
					if ($amazonImageFirst)
						$output .= "<$amazonWrapInfo class='t-$tag_who'>$ProductName</$amazonWrapInfo>".$amazonInfoBreak.$le;
	
				if (!$justPreview && !$amazonImageOnly)
				{
					if ($amazonShowCreator)
					{
						$befCreator='[';
						$aftCreator=']';
						$output .= "<$amazonWrapInfo class='t-$tag_who'>$befCreator$Creator$aftCreator</$amazonWrapInfo>".$amazonInfoBreak.$le;
					}
					
					if ($amazonShowBlogCat)
					{
						$aCat = get_wpCat($Asin);
						if (!empty($aCat))
						{
							$befCat='(';
							$aftCat=')';
							$output .= "<$amazonWrapInfo class='t-$tag_who'>$befCat$aCat$aftCat</$amazonWrapInfo>".$amazonInfoBreak.$le;
						}
					}
	
					if ($cgaindexLinks && $imageSize!='Small') // output something when internal linking and big pix...
					{
						if (!$amazonImageFirst) // the only other switch I can think to use!
							$output .= "<$amazonWrapInfo class='t-$tag_who'>See More Details...</$amazonWrapInfo>".$amazonInfoBreak.$le;
					}
				}
				
				if (!$justPreview && !$amazonImageOnly)
				if (!$amazonMinimumData)
				{
					if ($CurrentAmazonItem['_WishWant'])
					{
						if ($showWishlistCount)
						{
							$output .= "<$amazonWrapInfo class='t-$tag_who-price'>";
							$wishneed = $CurrentAmazonItem['_WishWant']-$CurrentAmazonItem['_WishGot'];
							if ($CurrentAmazonItem['_WishGot'])
								$output .= "Got ".intval($CurrentAmazonItem['_WishGot'])." of ";
							else
								$output .= "Need ";
							$output .= intval($CurrentAmazonItem['_WishWant']);
							$output .= "</$amazonWrapInfo>".$amazonInfoBreak.$le;
						}
						if ($showWishlistDates)
						if ($CurrentAmazonItem['_WishDate'])
							$output .= "<$amazonWrapInfo class='t-$tag_who-price'>Added on ".$CurrentAmazonItem['_WishDate']."</$amazonWrapInfo>".$amazonInfoBreak.$le;
					}
									
					$doExtraData = ($extraData && !empty($extraProductFields));
					if ($Price && ($amazonShowPrices /*|| $doExtraData*/ /* || $button */ )) // lots of reasons to want to show price...
					{
						if ($amazonClickForPrice) // don't actually show price
							$output .= "<$amazonWrapInfo class='t-$tag_who-price'>$amazonPriceLead</$amazonWrapInfo>".$amazonInfoBreak.$le;
						else
							$output .= "<$amazonWrapInfo class='t-$tag_who-price'>$amazonPriceLead".$Price."</$amazonWrapInfo>".$amazonInfoBreak.$le;
					}
			
					if ($doExtraData)// then more to output...
					{
						if (is_array($extraProductFields))
							for($ef=0; $ef<count($extraProductFields); $ef+=2)
							{
								$extraField = $extraProductFields[$ef];
								$extraTitle = $extraProductFields[$ef+1];
								$info = $CurrentAmazonItem["$extraField"];
								if (empty($info)) $info = $CurrentAmazonItem['ItemAttributes']["$extraField"];
								if (is_array($info)) $info = implode($info, ', ');
								if (!empty($info))
								{
									$output .= "<$amazonWrapInfo class='x-$tag_who'>"; // for now, all extra fields are the same class, for simpler css.
									$output .= "$extraTitle$info</$amazonWrapInfo>".$amazonInfoBreak.$le;
								}
							}
					}
				}
	
				if (!$justPreview && !$amazonImageOnly && !empty($divPrefix))
				if ($button && !$buyButtonShown)
				{
					$buyButtonShown = true; // only show once per page...
					$output .= "<$amazonWrapInfo><img src='".$myplugins."moreinfo-$tag_who.gif' alt='' /></$amazonWrapInfo>".$amazonInfoBreak.$le;
	//				$output .= "<$amazonWrapInfo><img src='$siteurl/images/buy-button-$tag_who.gif' alt='' /></$amazonWrapInfo>".$amazonInfoBreak.$le;
				}
				
				if (!$justPreview)
					$output .= "</a>".$le;
				
				// still within the list item, but outside the link (as we might have our own links.)... add any annotation data.
				if ($showAnnotation)
				{
					$note = get_annotation($Asin);
					if (!empty($note))
					{
						if (function_exists('doInlineConversion'))
							$note = doInlineConversion($note);
						$output .= "<$amazonWrapInfo class='note-$tag_who'>";
						$output .= "$note</$amazonWrapInfo>".$amazonInfoBreak.$le;
					}
				}
				
				if ($amazonWrapInfo=='li')
					$output .= "</ul>".$le;
	/*
				else
				if ($amazonWrapInfo=='span')
					$output .= "</div>".$le;
	*/
				if (empty($divPrefix))
					$output .= "</li>".$le;
			}	
			
			if (!$justPreview)
				track_as_shown($Asin);
		}
	}

	if ($imageSize!='Link' && $output != '')
	{
//		echo "fields = ".($amazonMinimumData?'a':'').($amazonShowPrices?'p':'').($doExtraData?'x':'');
//		if ($amazonImageOnly || $justPreview)
			$showtime = false; // immediate override.
//		else
		if (/*!$amazonMinimumData ||*/ $amazonShowPrices || $doExtraData) // then MUST SHOW TIME!
			$showtime = true; // immediate override.
		$output .= cga_block_end($showtime);
		if ($amazonWrapperDiv) $output .= "</div>".$le;
	
		// ALWAYS add an EXPLICIT newline at end, for proper paragraph break parsing by wp/textile
		$output .= "\n";
	}

	// this caches the raw array data.
	if ($doLookup && $doWriteCache && !$noCache)
	{
		//$output .= "WRITING CACHE.\n";
		if ($AmazonDebug>2)
		{
//			$doWriteCache = false;  // a forced override for testing.
			$cachePath = $myAmaPath . $amazonCacheDir . "DEBUG" . $cacheExt;
		}
		else
		if ($single && $cacheName != $searchType.$searchData) // need to make it so at this point...
			$cachePath = $myAmaPath . $amazonCacheDir . $searchType.$searchData . $cacheExt;
		if ($AmazonDebug>0) dbglog("CGA: trying to write cachefile $cachePath.");
		$cacheFile = fopen($cachePath,"w");
		if ($cacheFile==FALSE)
		{
			echo "CG-Amazon failed to cache to disk -- couldn't write file to the cache_amazon directory.";
		}
		else
		{
			if (flock($cacheFile, LOCK_EX)) {
				fwrite($cacheFile, /*base64_encode*/(serialize($Results)));
				flock($cacheFile, LOCK_UN);
			}
			fclose($cacheFile);
		}
	}

	if ($amazonEncoding && $amazonEncoding!='UTF-8')
		$output = uni_decode($output, $amazonEncoding);
	
	return $output;
}


//====================================
function pageLink($ptext, $pbef='', $paft='', $pargs=null, $pclass='', $pother='', $ptitle='')
{
	global $sort, $page; // things to try to maintain.
	global $this_file;
	$outlink ='';
	
	if ($pbef)
		$outlink .= $pbef;
		
	$outlink .= "<a href='$this_file";
	
	if (is_array($pargs))
		$pargs = implode('&amp;', $pargs);
		
	if (FALSE===strpos($pargs,"sort=") && FALSE===strpos($pargs,"action=")) // if we didn't pass in a sort or action, then we can add page and sort -- otherwise, drop both.
	{
		if ($page>1 && FALSE===strpos($pargs,"page="))
		{
			if ($pargs) $pargs .= '&amp;';
			$pargs .= "page=$page";
		}
		if ($sort)
		{
			if ($pargs) $pargs .= '&amp;';
			$pargs .= "sort=$sort";
		}
	}	
	
	if (strpos($this_file, '?')) // already a ? in url
		$linkArgs = '&amp;';
	else
		$linkArgs = '?';
	if ($pargs)
		$outlink .= "$linkArgs$pargs";
	$outlink .= "'"; // close quotes
	
	if ($pother)
		$outlink .= " $pother";
		
	if ($pclass)
		$outlink .= " class='$pclass'";

	if ($ptitle)
		$outlink .= " title='$ptitle'";

	$outlink .= ">$ptext</a>";
	
	if ($paft)
		$outlink .= $paft;
	
//	$outlink .= "\n";
	return($outlink);
}

function createCGATable()
{
	global $tablecgamazon;
	$query = "
			CREATE TABLE `$tablecgamazon` (
		  `ID` int(11) unsigned NOT NULL auto_increment,
		  `amTime` timestamp,
		  `ASIN` varchar(10) NOT NULL default '',
		  `amName` varchar(255) default NULL,
		  `amCreator` varchar(255) default NULL,
		  `amViewcount` int(10) unsigned NOT NULL default '0',
		  `amUrl` varchar(255) default NULL,
		  `amImageUrlSmall` varchar(255) default NULL,
		  `amCategory` varchar(128) default NULL,
		  `wpCategory` varchar(128) default NULL,
		  `metaNote` varchar(255) default NULL,
		  `amData` mediumtext,
		  PRIMARY KEY  (`ID`),
		  KEY `ASIN` (`ASIN`)
		) TYPE=MyISAM;";
	$results = db_runquery($query);
	return $results;
}

?>