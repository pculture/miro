<?php
//============================================================
// original concept for stripped down XML reader was by Jaykul
// http://jaykul.huddledmasses.org/scripting/news_feed_parser.php
//
//============================================================
// CHAITGEAR CG-FeedRead implemented by David Chait (cgcode@chait.net)
// http://www.chait.net/wp-plugins/feedread.php and XMLParser.php
// while based on the basic concept of simplified XML parsing, FR was
// completely rewritten to base off the new CG XMLParser library.
//
// overall, the code has grown in functionality greatly this year.
// it pre-parses the XML page into an array structure, then walks the
// proper parts of the structure to extract important fields.
// it is pretty TRIVIAL to add fields to the output if you want them.
//
// 
// I should note, as people get confused: CG-FeedRead uses a caching system
// where it saves the output from the feed for a certain length of time.
// Right now, the caching system doesn't "know" when you change the call
// parameters, it only knows when it last grabbed an update from that feed.
// So, if you change parameters, the fastest way to get a result if you are
// just testing is to delete the cache files.  Alternately, for SHORT
// TESTING PERIODS, you can define the following before calling getSomeFeed:
// 
// $XML_CACHE_TIME = 60*60*3; // 60s x 60m x 3 hours
// 
// The default changes every now and then -- at one point it was 24 hours,
// then it was 7, ...  You can set it to whatever update frequency you want.
// So, again, FOR TESTING ONLY, you could set it to say 10 -- for updates
// after 10s since the last grab.  I caution this over and over as if you
// ping some sites EVERY 10s for more than a few minutes of testing, you
// may find yourself shut off or blacklisted.  But during testing of
// parameters, it is invaluable.
// 
//============================================================
// We ask if you find this useful to go to http://www.chait.net/index.php?type=14,
// grab one of the cool link graphics, and give us a link back!  Thanks!
//
//============================================================
// note that this file has NO particular dependence on WordPress
// and can really be used under any PHP website.
//
//============================================================

// UPDATE WITH RELEASES!
$feedReadVersion = "1.5.3";

if (!isset($XML_CACHE_TIME))
	$XML_CACHE_TIME = 6 * 60 * 60; // hr * min/h * secs/m  -- you can change this for faster updates of the caches.

if (!isset($feedReadEncoding)) // set in an earlier file if NOT using UTF-8
	$feedReadEncoding = '';
	
if (!isset($DebugFeed))
	$DebugFeed = 0;

if (!isset($feedTargetWindow)) $feedTargetWindow = 'NewWindow';
			
$FR_CACHE = "cache_feedread"; // the path to the cache folder.
$feedReadPath = dirname(__FILE__).'/';

require_once($feedReadPath."XMLParser.php");
$feedParser = null; // use a global...

require_once($feedReadPath."helper_fns.php");
require_once($feedReadPath."uni_fns.php");

// sort-by-date comparison function..
function time_cmp($a, $b)
{
	$result = $b['unixTime']-$a['unixTime']; // so b is ahead of a if it is greater.
	dbglog("CGFR: compare ".$a['unixTime'].", ".$b['unixTime']." ==  $result");
	//if ($a['unixTime']<=0) dbglog("Bad time for ".$a['itemTitle']." (".$a['siteTitle'].")");			
	return $result;
}

/*
require_once("error-handler.php");

function mkdir_p($target)
{
if (is_dir($target)||empty($target)) return 1; // best case check first
if (file_exists($target) && !is_dir($target)) return 0;
if (mkdir_p(substr($target,0,strrpos($target,'/'))))
  return mkdir($target, 0755); // crawl back up & create dir tree
return 0;
}

function feedreadInstall()
{
	global $FR_CACHE;
	
	$frPathPrefix = dirname(__FILE__);
	// locate the wp path...
	if (FALSE===strpos($frPathPrefix, 'wp-content')) // plugin
		$backup = 1;
	else
		$backup = 3;

$old_umask = umask(0);
		
	for ($i=0; $i<$backup; $i++)
	{
		chmod($frPathPrefix, 0777);
		echo $frPathPrefix.'<br>';
		if (0==($pos = strrpos($frPathPrefix, '/')))
			$pos = strrpos($frPathPrefix, '\\');		
		$frPathPrefix = substr($frPathPrefix, 0, $pos);
	}
		
	$frPathPrefix .= '/'.$FR_CACHE;
		
	if (is_dir($frPathPrefix))
		echo("dir exists ($frPathPrefix)");
	if (file_exists($frPathPrefix) && !is_dir($frPathPrefix))
		echo("a file exists already as ($frPathPrefix) instead of a directory");
	$result = mkdir_p($frPathPrefix);
	if ($result)
		echo "we were able to create ($frPathPrefix)";
	else
		echo "we were NOT able to create ($frPathPrefix).  You'll need to do so manually.";
		
umask($old_umask);
}
*/

function getCachedFeed($cachedfile)
{
	global $feedParser;
	$output = '';
	if (file_exists($cachedfile))
		$output = file_get_contents($cachedfile);
	else
	if (isset($feedParser)) // then we failed to load
	{
		$output = $feedParser->setSourceFailed;
		dbglog("CGFR: $output...");
	}
	return ($output); // We're done.
}

function get_VALUE(&$data)
{
	global $XATTR,$XVALUE,$XTAG; // delimiters in the array breakdown...
	if (is_array($data) && $data[$XVALUE])
		$output = $data[$XVALUE];
	else
		$output = $data;
	return $output;
}

function get_CONTENT(&$data)
{
	global $XATTR,$XVALUE,$XTAG; // delimiters in the array breakdown...
	if (is_array($data))
	{
		if ($data[$XVALUE]) // then we're done...
			$output = $data[$XVALUE];
		else
		{
			foreach($data as $key => $elem)
			{
				if ($key==$XATTR) continue;
				$output = get_VALUE($elem);
				if (!empty($output)) break;
			}
		}
	}
	else
		$output = $data;
	return $output;
}


$hrefGrades = array('alternate' => 2);

function get_HREF(&$data)
{
	global $XATTR,$XVALUE,$XTAG; // delimiters in the array breakdown...
	global $hrefGrades;
	
//dbg_log('>>>> Picking through HREFs...');
	$output = '';	
	$grade = 0;
	if (isset($data['href']))
		$output = $data['href'];
	else // hopefully an array of links...
	{
		//if (is_array($data) // better be, assume it is...
		foreach($data as $posslinks)
		{
			if (strpos($posslinks['type'], 'html'))
			{
				$newGrade = 0;
				if (isset($hrefGrades[$posslinks['rel']]))
					$newGrade = $hrefGrades[$posslinks['rel']];
//dbg_log('>>>> HREF rel = '.$posslinks['rel'].', newgrade = '.$newGrade);
				if ($grade<=$newGrade)
				{
//dbg_log('>>>> using HREF '.$posslinks['rel'].', grade = '.$newGrade);
					$output = $posslinks['href'];
					$grade = $newGrade;
				}
				//$siteTitle = $posslinks['title']; // we could override here...
			}
		}
	}
	return $output;
}

//============================================================
function getSomeFeed($InUrl, $maxItemsPerFeed=5, $showDetails=false, $cacheName='', $filterCat='',
										$tLimit = -1, $dLimit = -1, $noHTML = true,  // no HTML by default, ==2 might allow safe tags
										$showTime = false, $feedStyle = false, $noTitle = false,
										$showTimeGMT = false, $titleImages = false, $multiSiteTitle=true,
										$makeRSS=false, $rssName="CG-FeedRead Multifeed", $rssLink="http://www.chait.net/") 
{
	//Globals
	global $XML_CACHE_TIME, $FR_CACHE;
	global $XATTR,$XVALUE,$XTAG; // delimiters in the array breakdown...
	global $DebugFeed;
	global $feedTargetWindow;
	global $feedParser;
	global $feedReadEncoding;
	
	$stylePosts='li'; // list sidebar style
	if ($feedStyle===true || $feedStyle===1)
		$stylePosts='wp'; // wordpress post-page styles
	else
	if ($feedStyle==2)
		$stylePosts='br'; // simple br-separated list
		
	$feedCount = 1;
	if (is_array($InUrl))
	{
		$feedCount = count($InUrl);
		dbglog("CGFR: MultiFeed ($feedCount) processing...");
	}

	if ($XML_CACHE_TIME < 5) // require 5s minimum...
		$XML_CACHE_TIME = 5; // secs
			
	if (is_array($maxItemsPerFeed)) // first number is total, second is per-feed.
	{
		$maxTotal = $maxItemsPerFeed[0];
		$maxItemsPerFeed = $maxItemsPerFeed[1];
	}
	else
	{
		$maxTotal = $maxItemsPerFeed;
	}
		
	if ($maxTotal<0 || $maxTotal>36) // arbitrary cutoff...
		$maxTotal = 36; // you need more than 3 dozen items????
	if ($maxItemsPerFeed<0 || $maxItemsPerFeed>100) // arbitrary cutoff...
		$maxItemsPerFeed = 100;
	if ($maxItemsPerFeed>$maxTotal)
		$maxItemsPerFeed = $maxTotal;
	
	if ($stylePosts=='wp')
		$ending = "_WP.html";
	else
		$ending = ".html";
		
	$links = true;
	$reCache = true;
	$doCache = true;
	
	$cacheDir = $FR_CACHE;
	$cachePath = dirname(__FILE__) . '/' . $cacheDir . '/' . $cacheName;
	
	if (empty($InUrl))
		return "CGFR: RSS/XML url string was empty. Please check arguments.";
		
	if (empty($cacheName)) // Don't bother caching.
		$doCache = false;
	else
	{
		$isThere = file_exists ( $cachePath.$ending );
		if ($isThere)
		{
			$filemod = filemtime( $cachePath.$ending );
			//echo "\n\n\n<!-- ===== $filemod - ".time()."  [Updated ".($filemod - time())." seconds ago -->";
			if( (time() - $filemod + rand(0,100) ) < $XML_CACHE_TIME ) // added 0-100s random so they don't all hit one pageload! ;)
				$reCache = false;
		}     
	}
	
	// <!-- ===== START ===== RSS FEED OUTPUT ===== --/>
	$output = '';
	$rssout = '';
	$lf = "\n";
	//$reCache = true;

	//----------
	// if $reCache is false at this point, either was to start, or failed reading URL.
	// spit out from cache.
	if ( !$reCache ) // we're pulling from cachefile...
		return(getCachedFeed($cachePath.$ending));
		
	// master variable.
	$feed = array();

	for ($c = 0; $c<$feedCount; $c++)
	{
		// per-feed parsing setup.
		$currFeed = null;		
		$siteTitle = ""; $siteLink = ""; $siteDescription = "";
		
		if (is_array($InUrl))
			$url = $InUrl[$c];
		else
			$url = $InUrl;
			
		dbglog("CGFR: Recaching $cacheName ($url)...");
		$feedParser = new XMLParser();
		$ret = $feedParser->setSource($url, 'url');
		if (!$ret)
		{
			dbglog("CGFR: ERROR trying to read feed $cacheName ($url)!");
			if (empty($cacheName)) // just return immediate for error case.
				return "CGFR: Unable to open feed [$url], and no cache."; 
			else
				return(getCachedFeed($cachePath.$ending));
			// !!!!TBD we could continue processing, but if mixing feeds, that'd be weird.
		}
		
		// if we get here, we've gotten to a URL, cache it.
		$tree = $feedParser->getTree();
		if ($DebugFeed>1)
		{
			$rawarray = print_r($tree, TRUE);
			//dbg_log("Feed tree = ".$rawarray);
	
			if (0)
				die($rawarray);
			else
			{
				$fp = fopen($cachePath."RAW.PHP",'w');
				fwrite($fp, $rawarray, strlen($rawarray));
				fclose($fp);
			}
	//			die();
		}
		
		$itemTag = 'item';
		if (IsSet($tree["rdf:RDF"])) // rdf 1.0 feed
		{
			$feedType = "RDF";
			$currFeed = &$tree["rdf:RDF"];
			$siteTitle = $currFeed['channel']['title'];
			$siteLink = $currFeed['channel']['link'];
			$siteDescription = $currFeed['channel']['description'];
			$siteImage = '';
			$siteImageTitle = '';
		}
		else
		if (IsSet($tree["rss"])) // some kind of rss feed
		{
			$feedType = "RSS";
			$currFeed = &$tree['rss']['channel'];
			$siteTitle = $currFeed['title'];
			$siteLink = $currFeed['link'];
			$siteDescription = $currFeed['description'];
			$siteImage = $currFeed['image']['url'];
			$siteImageTitle = $currFeed['image']['title'];
		}
		else
		if (IsSet($tree["feed"])) // a generic feed, likely to assume Atom
		{
			$feedType = "ATOM";
			$currFeed = &$tree['feed'];
			$siteTitle = get_VALUE($currFeed['title']);
			$siteLink = get_HREF($currFeed['link']);
			$siteDescription = get_VALUE($currFeed['tagline']);
			$siteImage = '';
			$siteImageTitle = '';
			
			$itemTag = 'entry';
		}
		else
		{
			$errout = "CGFR: Feed contains invalid format.";
			dbglog($errout." [$url]");
		
			if (1)
				foreach($tree as $leafname => $leaf)
					$errout .= $leafname;
			if ($feedCount==1) return $errout . "<!-- CHAITGEAR CG-Feedread $feedReadVersion: error showing feed: $url -->"; // we're done...
		}	  
	  
		if ($DebugFeed>1) dbglog("CGFR: type = $feedType");
		$notice = $lf.'<!-- CG-Feedread '.$feedReadVersion.' from CHAITGEAR, http://www.chait.net'.$lf."SHOWING FEED: $url -->".$lf;
		$output .= $notice;
		if ($makeRSS) $rssout .= $notice;
			  
		$siteLink = safehtmlentities($siteLink, ENT_QUOTES);
		if (empty($siteTitle)) $siteTitle = $siteLink;
		if (empty($siteDescription)) $siteDescription = $siteTitle;
	
		// try to detect unicode:
		if ($feedParser->uni && !uni_detect($siteTitle) && !uni_detect($siteDescription))
			$feedParser->uni = false; // force turn it off.
		if ($DebugFeed && $feedParser->uni) dbglog("CGFR: feed was multibyte...");
	
		// grrr.  people putting html into the site description should be...			
		if ($feedParser->uni)					
			$siteDescription = uni2str(uni_strip_tags(str2uni($siteDescription)));
		$siteDescription = strip_tags($siteDescription);
				
	//	$output .= "Parsing Feed = $siteTitle : $siteDescription @ $siteLink";
				
		$items = &$currFeed[$itemTag];
		if (!is_array($items) || !isset($items[0])) // not an array, or single item collapsed so no [0] element...
		{
			dbglog("CGFR: dealing with singlular-entry case...");
			$items = array(0 => $items); // in case a single entry...
		}
	
		if ($DebugFeed>1) dbglog("itemtag = $itemTag, count = ".count($items));
	
		$i=0;
		foreach($items as $index=>$item)
		{
			if ($i>=$maxItemsPerFeed)
				break; // done
			if ($DebugFeed>2) dbglog("item $index:<br/>".$item['title']);
			$itemTitle = get_VALUE($item['title']);
	//			if (empty($itemTitle))
	//				$itemTitle = $siteTitle;
	
	/*
			if ($DebugFeed>2) dbglog("$index str title: ".str_replace('_',' ',$itemTitle));
			if ($DebugFeed>2) dbglog("$index clean title: ".cleanBadChars($itemTitle));
			if ($DebugFeed>2) dbglog("$index strip title: ".strip_tags($itemTitle));
			if ($DebugFeed>2) dbglog("$index special title: ".htmlspecialchars($itemTitle));
			if ($DebugFeed>2) dbglog("$index html title: ".htmlentities($itemTitle));
			if ($DebugFeed>2) dbglog("$index safe title: ".safehtmlentities($itemTitle));
	*/
			$itemAuthor = get_VALUE($item['author']);
			
			$itemTime = get_VALUE($item['pubDate']); // s:7:"pubDate";s:31:"Wed, 30 Jun 2004 04:54:55 +0000"
			if (!empty($itemTime)) // raw convert.
			{
				$unixTime = strtotime($itemTime);
				if ($unixTime==-1) // badly formed?
				{
					$timeFields = preg_split("/(\d{2}:\d{2}:\d{2}\s\D{3})/", $itemTime, -1, PREG_SPLIT_DELIM_CAPTURE);
					$itemTime = $timeFields[0].' '.$timeFields[2].' '.$timeFields[1];
					$unixTime = strtotime($itemTime);
					//dbglog("Rewritten time = $itemTime ($unixTime)");
				}
				//dbglog("Time for $itemTitle in pubDate = $itemTime ($unixTime)");
			}
			else 
			{ // try alternate formats
				$itemTime = get_VALUE($item['dc:date']); // s:25:"2004-07-14T10:45:00-08:00"
				if (empty($itemTime))
					$itemTime = get_VALUE($item['modified']); // atom style //"2004-07-17T19:57:08Z" Z can be offset
				if (!empty($itemTime)) // parse it.
				{ // 1YYYY 2MM 3DD 4HH 5MM 6SS 7+|- 8Z|HH 9MM
					$result = preg_match("/(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})([+|-]*)([Z|\d{2}]+)/", $itemTime, $timeFields);
	//					if ($DebugFeed>2) dbglog($itemTime. " = " .serialize($timeFields));
					$dat['year']=intval($timeFields[1]);
					$dat['month']=intval($timeFields[2]);
					$dat['day']=intval($timeFields[3]);
					$dat['hour']=intval($timeFields[4]);
					$dat['min']=intval($timeFields[5]);
					$dat['sec']=intval($timeFields[6]);
					// need to add adj off of GMT when there is one...
					if ($timeFields[7] && $showTimeGMT) // emtpy if Zulu == [8]
					{
						if ($timeFields[7]=='-') // GMT - n, so ADD to get back to Zulu.
						{
							$dat['hour'] += intval($timeFields[8]);
							$dat['min'] += intval($timeFields[9]);
						}
						else // GMT + n, so SUB to get to Zulu.
						{
							$dat['hour'] -= intval($timeFields[8]);
							$dat['min'] -= intval($timeFields[9]);
						}
					}	
					$unixTime = mktime($dat['hour'], $dat['min'], $dat['sec'], $dat['month'], $dat['day'], $dat['year']);
	//					if ($DebugFeed>2) dbglog("time fields = [$unixTime] ".serialize($dat));
				}
			}
			
			$itemTime = date("n/j/Y g:ia", $unixTime);
			
			$itemCat = get_VALUE($item['category']);
			if (empty($itemCat))
				$itemCat = get_VALUE($item['dc:subject']); // atom, rss2
			
			if ($feedType=='ATOM')
				$itemLink = get_HREF($item['link']);
			else
				$itemLink = get_VALUE($item['link']);
			if (empty($itemLink))
				$itemLink = get_VALUE($item['guid']);

			$itemDescription = null;
			if ($feedType=='ATOM')
				$itemDescription = get_CONTENT($item['content']);
			if (empty($itemDescription))
				$itemDescription = get_CONTENT($item['content:encoded']);
			if (empty($itemDescription))
				$itemDescription = get_CONTENT($item['description']);
			if (empty($itemDescription))
				$itemDescription = get_VALUE($item['summary']);
			if (empty($itemDescription))
			{
				$itemDescription = $siteDescription;
				dbglog("CGFR: no feed item description = ".serialize($item));
			}
								
			if (!empty($filterCat))
			{
				if (empty($itemCat)) // then compare against the url
				{
					if (false==findstr($itemLink, $filterCat)) continue;
				}
				else
				{
					if (false==findstr($itemCat, $filterCat))	continue;
				}
			}
			
			$i++; // we found one.
							
			$itemCat = safehtmlentities($itemCat, ENT_QUOTES);
			$itemLink = safehtmlentities($itemLink, ENT_QUOTES);
			$linkTitle = '';
			if ($feedType=='ATOM')
				$linkTitle = get_VALUE($item['summary']);
			
			if ($feedParser->uni)
			{
				if (!$showDetails)
					$itemDescription = str2uni($itemDescription, 64);
				else
				if ($dLimit>0)
					$itemDescription = uni_snippet(str2uni($itemDescription, $dLimit+8), $dLimit);
				else
					$itemDescription = str2uni($itemDescription);
				$stripDescript = uni_strip_tags($itemDescription);
				$snippedTitle = uni2str(uni_snippet($stripDescript, 40));
				$snippedTitle = strip_tags($snippedTitle);
	//						dbglog(serialize($snippedTitle));
				$stripDescript = strip_tags(uni2str($stripDescript));
	//						dbglog(serialize($stripDescript));
			}
			else
			{
				$itemDescription = cleanBadChars($itemDescription); // just in case...
				$stripDescript = strip_tags($itemDescription);
				if ($showDetails && $dLimit>0) $itemDescription = snippet($itemDescription, $dLimit);
				$snippedTitle = snippet($stripDescript, 40);
				$snippedTitle = strip_tags($snippedTitle);
			}
	
			if ($feedParser->uni)
			{
				if ($tLimit>0)	$itemTitle = str2uni($itemTitle, $tLimit+8);
				else						$itemTitle = str2uni($itemTitle);
				$itemTitle = uni_strip_tags($itemTitle, ENT_QUOTES);
				if (empty($itemTitle) || empty($linkTitle))
				{
					if (empty($itemTitle))		$itemTitle = $snippedTitle;
					if (empty($linkTitle))		$linkTitle = $snippedTitle;
				}
				else
				if (!empty($linkTitle)) $linkTitle = uni2str(uni_snippet(str2uni($linkTitle, 80), 64));
				
				if ($tLimit>0) $itemTitle = uni_snippet($itemTitle, $tLimit);
				$itemTitle = uni2str($itemTitle);
			}
			else
			{
				if (empty($itemTitle) || empty($linkTitle))
				{
					if (empty($itemTitle))		$itemTitle = $snippedTitle;
					if (empty($linkTitle))		$linkTitle = $snippedTitle;
				}
				else
				if (!empty($linkTitle)) $linkTitle = snippet($linkTitle, 64);
				if ($tLimit>0) $itemTitle = snippet($itemTitle, $tLimit);
			}
			
			$itemTitle = strip_tags($itemTitle, ENT_QUOTES);
			$itemTitle = safehtmlentities($itemTitle, ENT_QUOTES);
			$linkTitle = strip_tags($linkTitle, ENT_QUOTES);
			$linkTitle = safehtmlentities($linkTitle, ENT_QUOTES);
			
			if ($showDetails) 
			{
				if ($feedParser->uni)
				{
					if ($noHTML)
						$stripDescript = $stripDescript;
					else
						$itemDescription = uni2str($itemDescription);
				}
									
				if ($noHTML) // use the tag-stripped version, AND convert quotes...
					$itemDescription = safehtmlentities($stripDescript, ENT_QUOTES);
			}
			
	
/*		if ($DebugFeed>2)
			{
				$chars = ''; $tmp = str2uni($linkTitle);
				foreach($tmp as $achr) $chars .= '['.$achr.'='.chr($achr).'] ';
				dbglog("CGFR: link = ".$chars);
			} */
		
			// hold onto the item.
			$curItem = &$feed[]; // $feed is our master caching array.
			$curItem['itemTitle'] = $itemTitle;
			$curItem['linkTitle'] = $linkTitle;
			$curItem['itemLink'] = $itemLink;
			$curItem['itemTime'] = $itemTime;
			$curItem['unixTime'] = $unixTime;
			$curItem['itemDescription'] = $itemDescription;
			$curItem['itemAuthor'] = $itemAuthor;
	
			$curItem['siteTitle'] = $siteTitle;
			$curItem['siteLink'] = $siteLink;
			$curItem['siteDescription'] = $siteDescription;
			$curItem['siteImage'] = $siteImage;
			$curItem['siteImageTitle'] = $siteImageTitle;
		} // foreach items as item
	} // foreach c per feed
			
	// now, if multifeed, do proper sorting.
	if (count($feed)>1 && $feedCount>1) // && count($feed)>$maxTotal
	{		
		usort($feed, "time_cmp");
//		for($i=0; $i<count($feed); $i++)
//			dbglog('   >>>   '.$feed[$i]['unixTime'].' :: '.$feed[$i]['itemTime'].' :: '.$feed[$i]['itemTitle']);
	}

	if ($makeRSS) // prep the feed...
	{
		// make sure the xml line is line ONE.
		// and insert the current contents after the generator line.
		$rssout = '<?xml version="1.0"?>
			<!-- generator="CG-FeedRead/1.5" -->
			'.$rssout.'
			<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
				<channel>
					<title>'.$rssName.'</title>
					<link>'.$rssLink.'</link>
					<description>'.$rssName.'</description>
					<language>en</language>
					<copyright>Copyright 2005</copyright>
					<pubDate>'.gmdate('r').'</pubDate>
					<generator>http://www.chait.net/index.php?p=238</generator>';
		$rssftr = '
				</channel>
			</rss>';
	}
	
	// Okay, NOW we can actually work
	$i=0;
	while ($i<$maxTotal && $i<count($feed))
	{
		$curItem = &$feed[$i]; // $feed is our master caching array.
		$i++;
		if ($i==1) //start of feed output
		{		
			if (!$noTitle && $feedCount==1) // we shouldn't do this for multifeed.
			{
				if ($titleImages && !empty($siteImage))
					$output .= "<div class='feedTitleGraphic'>".$lf;
				else
					$output .= "<div class='feedDescription'>".$lf;
					
				if (1) //$stylePosts=='wp')
					$output .= '<h2>'.$lf;
					
				if ($links)
				{
					$output .= '<a href="'.$siteLink.'" title="'.$siteDescription.'"';
					if ($feedTargetWindow) $output .= " target='".$feedTargetWindow."'";
					$output .= '>';
				}
				if ($titleImages && !empty($siteImage))
					$output .= '<img src="'.$siteImage.'" alt="'.$siteDescription.'" />';
				else
					$output .= $siteTitle;
				if ($links)
					$output .= "</a>";
				
				if (1) //$stylePosts=='wp')
					$output .= '</h2>'.$lf;
					
				$output .= "</div>".$lf;
				
			}
			if ($stylePosts=='wp')
				$output .= '<div class="cgfeed">'.$lf;
			else
			if ($stylePosts=='br')
				$output .= '<div class="cgfeed">'.$lf;
			else //if ($stylePosts=='li')
				$output .= '<ul class="cgfeed">'.$lf;
		}

	// wrapper the entire item
		//$output .= "<!--FEEDITEM #$i-->".$lf;
		if ($stylePosts=='wp')
			$output .= '<div class="post">'.$lf;
		else
		if ($stylePosts=='br')
		{}
		else
			$output .= "<li class='feedItem'>".$lf;
			
	// wrapper the title
		if ($stylePosts=='wp')
			$output .= "<h3 class='storytitle'>".$lf;
		else
		if ($stylePosts=='br')
		{}
		else
			$output .= "<span class='feedItemTitle'>";
		
		if ($links)
		{
			$output .= '<a href="'.$curItem['itemLink'].'" title="'.$curItem['linkTitle'].'"';
			if ($feedTargetWindow) $output .= " target='".$feedTargetWindow."'";
			$output .= '>';
		}
		if ($feedCount>1 && $multiSiteTitle)
		{
			$tmpTitle = $curItem['siteImageTitle'];
			if (empty($tmpTitle)) $tmpTitle = $curItem['siteTitle'];
			$output .= "[$tmpTitle] ";
		}
		$output .= $curItem['itemTitle'];
		if ($links)
			$output .= "</a>";

	// close each item title...		
		if ($stylePosts=='wp')
			$output .= "</h3>".$lf;
		else
		if ($stylePosts=='br')
		{} // $output .= "<br/>".$lf;
		else
			$output .= "</span>";
		
		if ($showDetails)
		{
			if ($stylePosts=='wp')
				$output .= "<div class='storycontent'>".$curItem['itemDescription']."</div>".$lf;
			else
				$output .= "<p class='feedItemDescription'>".$curItem['itemDescription']."</p>".$lf;
		}
		
		if ($showTime && !empty($curItem['itemTime']))
			$output .= "<div class='meta'>".$curItem['itemTime']."</div>".$lf;
		
	// close each item
		if ($stylePosts=='wp')
			$output .= '</div>'.$lf;
		else
		if ($stylePosts=='br')
		{}//	$output .= '</div>'.$lf;
		else
			$output .= "</li>".$lf;
			
		if ($makeRSS)
		{
			$rssout .= '
				<item>
					<title>'.$curItem["itemTitle"].'</title>
					<link>'.$curItem["itemLink"].'</link>
					<pubDate>'.$curItem["itemTime"].'</pubDate>
					<author>'.$curItem["itemAuthor"].'</author>
		<!--	<category></category>-->
					<guid isPermaLink="false">'.$i.'@'.$curItem["siteLink"].'</guid>
					<description>
						<![CDATA['.$curItem["itemDescription"].']]>
					</description>
				</item>
				';
		}		
	}
		
	if ($i) // we had something in output.
	{
		if ($stylePosts=='wp')
			$output .= '</div>'.$lf;
		else
		if ($stylePosts=='br')
			$output .= '</div>'.$lf;
		else
			$output .= "</ul>".$lf;
		$output .= "<!-- end feed -->".$lf;
	}
	
	if ($feedReadEncoding && $feedReadEncoding!='UTF-8')
		$output = uni_decode($output, $feedReadEncoding);
	
	// cache the full cached PHP array for later reference			
	$cacheFileDat = fopen($cachePath.".DAT","w");
	flock($cacheFileDat, LOCK_EX);
//	fwrite($cacheFileDat, /*base64_encode*/(serialize($tree)));
	fwrite($cacheFileDat, /*base64_encode*/(serialize($feed)));
	flock($cacheFileDat, LOCK_UN);
	fclose($cacheFileDat);

	if ($makeRSS)
	{
		$rssout .= $rssftr;
		$cacheFile = fopen($cachePath.'.xml',"w");
		if ($cacheFile)
		{
			if (flock($cacheFile, LOCK_EX))
			{
				fwrite($cacheFile, $rssout);
				flock($cacheFile, LOCK_UN);
			}
		}
		else
			echo "CG-Feedread failed to create RSS cache -- couldn't write to the $FR_CACHE directory.";
		fclose($cacheFile);
	}
		
	if (!$DebugFeed && $doCache)
	{
		$cacheFile = fopen($cachePath.$ending,"w");
		if ($cacheFile)
		{
			if (flock($cacheFile, LOCK_EX))
			{
				fwrite($cacheFile, $output);
				flock($cacheFile, LOCK_UN);
			}
		}
		else
			echo "CG-Feedread failed to save feed to disk -- couldn't write to the $FR_CACHE directory.";

		fclose($cacheFile);
	}
	else
		dbglog("CGFR: HTML caching disabled, debug=$DebugFeed, doCache=$doCache");
		
	return $output;
	// <!-- ===== END ===== RSS FEED OUTPUT ===== --/>   
}

?>