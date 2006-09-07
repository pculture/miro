<?php 

// Original author:
//   nathan@ncyoung.com 
//
// modified by Ben Johnson (http://www.ben-johnson.org/blog or ben (at) ben-johnson.org) 
//   v 1.0 - added Google parsing (August 2003) 
//   v 1.1 - reformatted code, import DB settings from wp-config.php 
//
// further revised by David Chait for CHAITGEAR (www.chait.net)
//   v 1.5 - blacklist file, bot detection, multiple admin status output functions, revised query term parsing, updated search-output functionality
//	 v 1.5.1 - updated blacklists, updated bot detection and early-exit, updated flush function
//	 v 1.5.2 - further overhauled the search term code for more search sites.
//	 v 1.5.5 ... lots of minor and major improvements to performance and output.
//	v 1.5.6 added more fixes to getRecentSearches and query string parsing.
//	v 1.6  added bot tracking support, getRecentBots fn, direct-load history list
//  v 1.7 cleaned/revised to enable plugin-stub for wordpress.
//
//  Version numbers have since been reset and started over from 1.0. ;)
//
//============================================================
// PLEASE PLEASE PLEASE PLEASE PLEASE PLEASE PLEASE PLEASE
// We ask if you find this useful to go to http://www.chait.net/index.php?type=14,
// grab one of the cool link graphics and title text, and give us a link back!  Thanks!
// PLEASE PLEASE PLEASE PLEASE PLEASE PLEASE PLEASE PLEASE
//============================================================


if (isset($rlAbsPath)) return; // we're already loading...

$REQUESTED = $_SERVER['REQUEST_URI'];
if ($truncoff = strpos($REQUESTED, '&'))
	$REQUESTED = substr($REQUESTED, 0, $truncoff);
$rlAbsPath = dirname(__FILE__).'/';
// locate the wp path...
if (FALSE===strpos($rlAbsPath, 'wp-content')) // plugin
	$rlRootPath = $rlAbsPath.'../'; // cgplugins->wp base dir.
else
	$rlRootPath = $rlAbsPath.'../../../'; // cgplugins->plugins->wpcontent->wp base dir.

if (strpos($REQUESTED, "cg-referrer")
||	strpos($REQUESTED, "wp-admin/admin.php"))
{
	require_once($rlRootPath.'wp-config.php');
	if (strpos($REQUESTED, "wp-admin/admin.php"))
	{
		$title = __('CG-Referer Admin');
		$parent_file = 'admin.php';
		$this_file = "cg-referrer.php";
		require_once($rlRootPath.'wp-admin/admin-header.php');
	}
}

$siteurl = get_settings('siteurl');

if (!isset($user_level) && function_exists('get_currentuserinfo'))
	get_currentuserinfo(); // cache away in case hasn't been yet...

if (!isset($referTargetWindow)) $referTargetWindow = 'NewWindow';

// THEN we can bring in everything else...
require_once($rlAbsPath.'db_fns.php');
require_once($rlAbsPath.'bot_fns.php');
require_once($rlAbsPath.'helper_fns.php');
require_once($rlAbsPath.'cg-blacklist.php');

define("BOT_MARKER", '_BOT_');

$mailOnSpam = 1;

if (isset($_GET['remotedb']))
	$USE_REMOTE_DB = true;
	
//========================================================================

$referTable = $table_prefix."cg_referrer";

$dbgRef = false; // set to true to activate dbglog-ing

//===
//===
// borrowing from zedrdave...
function forbid_access($code=403)
{
	// this will nail bots, basically.
	sleep(5); // small tar pit
	header("HTTP/1.1 $code");
	header("Status: $code");
	if ($code==301)
		header('Location: ' . $HTTP_SERVER_VARS['HTTP_REFERER']);
	echo '<html>';
		if ($code==403) // try to auto-reload...
			echo '<head><meta http-equiv="refresh" content="0"></head>';
		echo '<body><h1>Auto-redirect in progress</h1>';
		echo '<p>If you see this and are not redirected immediately, please click this link to continue to the site: <a href="'.$_SERVER["REQUEST_URI"].'">http://' . $_SERVER["SERVER_NAME"] . $_SERVER["REQUEST_URI"] . '?cgr_redirect=1</a></p>';
	echo '</body>';
	echo '</html>';
	die();
}


//========================================================================
//========================================================================
function testForUniqueIP($userIP)
{
	global $referTable;
	global $dbgRef;
	global $uipResultTable;
	
	// query for date==today, userIP==currentuserIP.  if results, not unique...
	if (!isset($uipResultTable))
	{
	 	$queryStr = "
							 	SELECT *
								FROM $referTable
								WHERE DATE_FORMAT(NOW(), '%Y%m%d')=DATE_FORMAT(visitTime, '%Y%m%d')
								AND userIP='$userIP'
								ORDER BY visitTime DESC
								";
		$uipResultTable = db_getresults($queryStr, ARRAY_A, "testForUniqueIP");
	}
	if (empty($uipResultTable))
	{
		if ($dbgRef) dbglog("REFER: unique IP");
		return(true);
	}
	return(false);
}

//========================================================================
//========================================================================
function checkDupEntries($isLocal, $referingURL,$baseDomain,$visitURL,$userAgent,$userIP)
{
	global $referTable;
	global $dbgRef;
	global $uipResultTable;
	
	// query for date==today, userIP==currentuserIP.  if results, not unique...
	if (!isset($uipResultTable))
	{
	 	$queryStr = "
							 	SELECT *
								FROM $referTable
								WHERE DATE_FORMAT(NOW(), '%Y%m%d')=DATE_FORMAT(visitTime, '%Y%m%d')
								AND userIP='$userIP'
								ORDER BY visitTime DESC
								";
		$uipResultTable = db_getresults($queryStr, ARRAY_A, "checkDupEntries");
	}
	if (empty($uipResultTable))
		return(false);

	foreach($uipResultTable as $entry)
	{
		if (
				$baseDomain == $entry['baseDomain'] &&
				$userAgent == $entry['userAgent'] &&
				$userIP == $entry['userIP']
			)
		{
			$evURL = &$entry['visitURL'];
			$erURL = &$entry['referingURL'];
			if ($isLocal)
			{ // need to hack up the compared strings...
				$visitURL = substr($visitURL,0,strpos($visitURL,'&')); // allows post ?p=100, but not &page=3 nor other terms...
				$evURL = substr($evURL,0,strpos($evURL,'&'));
				$referingURL = substr($referingURL,0,strpos($referingURL,'&'));
				$erURL = substr($erURL,0,strpos($erURL,'&'));
			}
			if ($visitURL == $evURL && $referingURL == $erURL)
				return(true);
		}
	}
		
	return(false);
}


//========================================================================
//========================================================================
function clearDupEntries($clearCode=1)
{
	global $referTable;
	global $dbgRef;
	$serverName = $_SERVER['SERVER_NAME'];
	
	echo "Clearing dups...<br>";
	// NEW, use WHERE clause to only clear out REAL USERS.
	if ($clearCode>1)
		$where = "WHERE (referingURL NOT LIKE '%search%')
					AND (referingURL NOT LIKE '%query%')
					AND (baseDomain!='".BOT_MARKER."')
					AND (baseDomain NOT LIKE '[%')";
 	$queryStr = "SELECT count(userIP) as num, userIP FROM $referTable $where GROUP BY userIP ORDER BY num DESC limit 100";
	$sqr_IP = db_getresults($queryStr, ARRAY_A, "clearDupEntries");
	if (empty($sqr_IP))
		return;

	$counter = 0;
	$deleted = 0;
	foreach($sqr_IP as $ipEntry)
	{
		if ($ipEntry['num']<2) break; // WE'RE ALL DONE if we hit num==1 entries...
		
		$counter++;
		if ($counter%100==0) { echo "<br><span>$counter</span><br>"; flush(); }
		else echo "$counter.. ";
		
		$uip = $ipEntry['userIP'];
	 	$queryStr = "
							 	SELECT *, DATE_FORMAT(visitTime, '%y%m%d') as theDay
								FROM $referTable
								WHERE userIP='$uip'
								ORDER BY visitTime DESC
								";
		$sqr = db_getresults($queryStr, ARRAY_A, "clearDupEntries 2");
		$numEntries = count($sqr);
		if (empty($numEntries)) continue;

		//echo "Processing IP = $uip<br>";
		$noMatch = true;
		for ($i=0; $i<$numEntries-1; $i++)
		{
			$baseDomain = $sqr[$i]['baseDomain'];
			if ($baseDomain==BOT_MARKER)
			{
				if ($clearCode==1
				|| (FALSE===strpos($sqr[$i]['userAgent'], 'Java/1')
				&& FALSE===strpos($sqr[$i]['userAgent'], 'Lynx/2'))
					)
				continue; // ignore bots, except in clear-2 mode
			}
			$isLocal = findstr($serverName, $baseDomain);
			for ($j=$i+1; $j<$numEntries; $j++)
			{
				if (empty($sqr[$j]['_DUP_'])) // not tagged already.
				if ($sqr[$i]['visitID'] > $sqr[$j]['visitID']
				&&	$sqr[$i]['theDay'] == $sqr[$j]['theDay'])
				{
					if (
							$sqr[$i]['baseDomain']		== $sqr[$j]['baseDomain'] &&
							$sqr[$i]['userAgent']			== $sqr[$j]['userAgent']
							) // dup'd
					{
						$irURL = &$sqr[$i]['referingURL'];
						$jrURL = &$sqr[$j]['referingURL'];
						$ivURL = &$sqr[$i]['visitURL'];
						$jvURL = &$sqr[$j]['visitURL'];
						if ($isLocal)
						{ // need to adapt for local checks
							$irURL = substr($irURL,0,strpos($irURL,'&')); // allows post ?p=100, but not &page=3 nor other terms...
							$jrURL = substr($jrURL,0,strpos($jrURL,'&'));
							$ivURL = substr($ivURL,0,strpos($ivURL,'&'));
							$jvURL = substr($jvURL,0,strpos($jvURL,'&'));					
						}
						
						if ($irURL==$jrURL && $ivURL==$jvURL)
						{
							if ($noMatch)
							{
								echo "<br><span>DUPS for IP [$uip]</span><br>";
								$noMatch = false;
							}
							$sqr[$j]['_DUP_'] = true;
							$visit1 = $sqr[$i]['visitID'];
							$visit2 = $sqr[$j]['visitID'];
							
							$agent = $sqr[$j]['userAgent'];
					    $pos = strpos($agent, '(');
				  	  if (!$pos)
						    $pos = strpos($agent, 'http:');
						  if ($pos)
				    		$agent = substr($agent, 0, $pos);
					    $agent = safehtmlentities($agent); 
					    
							echo "&nbsp;&nbsp;&nbsp;&nbsp;$i:$j ".$sqr[$i]['theDay']." ($visit1,$visit2) ".$sqr[$i]['baseDomain'].' ('.$agent.') => '.$sqr[$i]['visitURL'].'<br>';
							if ($clearCode<10)
							{
								$result = db_runquery("DELETE FROM $referTable WHERE visitID='$visit2'", "cg-referrer clearadup");
								$deleted++;
							}
						}
					}
				}
			}
		}
		
		if (!$noMatch) echo "<hr><br>";
		flush();
	}
	
	return $deleted;
}

function checkReferer($checkRefs, $ref, $baseDomain, $userAgent, $currentURL, $userIP)
{
	global $dbgRef;
	global $ignoreReferSites, $ignoreSpammerIPs, $ignoreAgents, $siteWhitelist;
	
	if ($dbgRef) dbglog("REFER: Checking referer: IP=$userIP, UA=$userAgent, ref=$ref");

	if ($checkRefs==true)
		$checkRefs = array('UA'=>1,'DASHES'=>1,'IP'=>1,'KW'=>1,'HTTP'=>1);
	
	// check blacklisted userAgents
	if ($checkRefs['UA'])
		if ($gotmatch = findstr($userAgent, $ignoreAgents))
			return array(true, 503, '[503]UA ');
	
	// check for 'blacklisted' IP addresses
	if ($checkRefs['IP'])
		if ($gotmatch = findstr($ref, $ignoreSpammerIPs) // check spammer IP list on the ref.
		|| $gotmatch = findstr($userIP, $ignoreSpammerIPs) )
			return array(true, 503, '[503]IP ');

	// okay, now good time to check site/domain whitelist...
	if (!empty($siteWhitelist))
		if ($gotmatch = findstr($baseDomain, $siteWhitelist))
			return(false);
	
	// check for 'bad' domain naming: three or more - characters for now.
	if ($checkRefs['DASHES'])
		if (($count = substr_count($baseDomain, '-')) >= 3)
			return array(true, 301, '[301]DASHES ');
			
	// check for 'blacklisted' referer sites EARLY.
	if ($checkRefs['KW'])
		if ($gotmatch = findstr($ref, $ignoreReferSites))
			return array(true, 301, '[301]KW ');

	// check for http injections EARLY. -- this IS WP specific at the moment.
	if ($checkRefs['HTTP'])
		if (strpos($currentURL, '=http:')) // look for HTTP injections
			return array(true, 410, '[410]HTTP ');

/*
	if (is_valid_IP_address($ref)) // we want domains not ip's!
	{
		$response = "Referer address sent was a dotted IP address.  Referral not tracked.\n";
		return $response;
	}
*/
	return array(false);
}

//========================================================================
//========================================================================
function logReferer($logUniqueIPs = false, $logInternal = false, $trackAllBots = false, $checkRefs = null, $puntSpam = true){ 
	global $referTable, $blogname;
	global $dbgRef;
	global $primaryAdminIP;
	global $siteurl;
	
	$currentURL = $_SERVER['REQUEST_URI']; 
	$serverName = $_SERVER['SERVER_NAME'];
	$fullCurrentURL = "http://" . $serverName . $currentURL; 
	$currentURL = str_replace($siteurl, '', $fullCurrentURL); // get the subpath...
	
	$userIP = $_SERVER["REMOTE_ADDR"];
	$userAgent = $_SERVER["HTTP_USER_AGENT"];
	$response = '';

	if ($userIP==$primaryAdminIP)
		return; // early exit
	
	$ref = getenv('HTTP_REFERER'); 
	$baseDomain = preg_replace("/http:\/\//i", "", $ref); 
	$baseDomain = preg_replace("/^www\./i", "", $baseDomain); 
	$baseDomain = preg_replace("/\/.*/i", "", $baseDomain); 
	$skipSlashdotters = (FALSE!==strpos($ref, 'slashdot.'));
	$waspost = '';
	if (!empty($_POST))
		$waspost = " [POST=".safehtmlentities(serialize($_POST))."]";

//	dbglog("IP = $userIP");
	
	if ($userIP == $baseDomain) // want domains not IPs!
	{
		$response = "Referer address sent was the same as your IP address.  Referral not tracked.\n";
		return $response; 
	}
	
	$is_a_bot = isa_bot($userAgent);
	if ($is_a_bot)
		$baseDomain .= ' [_BOT_]';
		
/* turning this off as it kills some bots/scanners we WANT to access the site.
	if (empty($userAgent)) // we don't allow this at all
	{
		$response = "<p>Please note that your user agent/browser identification is completely empty, which we must disallow as it is used for abusive bots, spiders, and other scanning.  Please connect with a browser with a known identification.</p>";
		dbg("referer ignored"); 
		die($response);
	}
*/
	if ($checkrefs && !empty($checkRefs))
	{
		$result = checkReferer($checkRefs, $ref, $baseDomain, $userAgent, $currentURL, $userIP);
		if (!empty($result) && $result[0]) // had a positive hit
		{
			if (strpos($baseDomain, "++++++++++")) $baseDomain = "XXXX:++++++++++++++++++++";
			$baseDomain = $result[2].$baseDomain; // prepend the status.
			$sql ="insert into $referTable (referingURL,baseDomain,visitURL,userAgent,userIP) values ('$ref$waspost','$baseDomain','$currentURL','$userAgent','$userIP')"; 
			db_runquery($sql, "logReferer");
 			if ($puntSpam)
	 			forbid_access($result[1]); // will now die in here.
	 		else
	 			return; // track and go back.
		}
	}
	
	if (!$skipSlashdotters) // for slashdot, skip uniqueness check for fast page processing...
	{
		if (!$ref)
		{
			dbg("no referer"); 
			
			$uniqueIP = false;
			if ($logUniqueIPs)
				$uniqueIP = testForUniqueIP($userIP);
			// if the return is commented out, we get almost full pageview tracking...
			if (!$uniqueIP)
			{
				if ($dbgRef) dbglog("REFER: No ref, not unique IP");
				return;
			}
		}
			
		// ignore site-internal references... -- doesn't catch basedomain yet, which is a bit down the page...
		if (!$logInternal)
		if ($gotmatch = findstr($ref, $serverName))
		{
			$uniqueIP = false;
			if ($logUniqueIPs)
				$uniqueIP = testForUniqueIP($userIP);
			if (!$uniqueIP)
			{
				if ($dbgRef) dbglog("REFER: Internal ref, not unique IP");
				return;
			}
		}
	}
	
	if ($ref != strip_tags($ref))
	{ 
		//then they have tried something funny, 
		//putting HTML or PHP into the HTTP_REFERER 
		dbg("bad char in referer"); 
		return $response;
	}

	if ($is_a_bot)
	{
		if ($trackAllBots)
		{
			$sql ="insert into $referTable (referingURL,baseDomain,visitURL,userAgent,userIP) values ('$ref$waspost','".BOT_MARKER."','$currentURL','$userAgent','$userIP')"; 
			db_runquery($sql, "logReferer");
		}
		return;
	}

	$gotmatch = findstr($serverName, $baseDomain); // our base domain referring into our server

	if (!$skipSlashdotters) // for slashdot, skip uniqueness check for fast page processing...
	if (!$logInternal) //if logging internally, skip dup check as we want all movement...	
	if (checkDupEntries($gotmatch, $ref, $baseDomain, $currentURL, $userAgent, $userIP))
	{
		if ($dbgRef) dbglog ("REFER: duplicate entry");
		return;
	}

	// ignore site-internal references... NOW we hit $baseDomain==basedomain
	if (!$skipSlashdotters) // for slashdot, skip uniqueness check for fast page processing...
	if (!$logInternal)
		if ($gotmatch) // our base domain referring into our server.
		{
			$uniqueIP = false;
			if ($logUniqueIPs)
				$uniqueIP = testForUniqueIP($userIP);
			if (!$uniqueIP)
			{
				if ($dbgRef) dbglog("REFER: Internal ref, not unique IP");
				return;
			}
		}
		
/* leaving this off, as 1. it didn't work, and 2. we can track unique visitors moving around site...
	// check for local server, so we don't spam ourselves.
	if (!empty($myLocalServer))
		if (stristr($ref, $myLocalServer))
			return $response;
*/		
	
	$sql ="insert into $referTable (referingURL,baseDomain,visitURL,userAgent,userIP) values ('$ref','$baseDomain','$currentURL','$userAgent','$userIP')"; 
	db_runquery($sql, "logReferer");
	
	return $response;
} 


//========================================================================
//========================================================================
function rl_DailyStats($short = 2)
{
	global $referTable;
	$fullLookup = 0;
	if ($short > 9)
	{
		$fullLookup = 1;
		$short = intval($short / 10);
	}
	if ($fullLookup)
		$countQ = "*";
	else
		$countQ = "DISTINCT userIP";
	
	$lastthree = array(0, 0, 0);
	
	// blank this out if you don't want to restrict the number of weeks back to show...
	$where = "WHERE TO_DAYS(NOW()) - TO_DAYS(visitTime) < (7*4*2)+(TO_DAYS(NOW())%7)";
	/* this is the optimized, total-unique-IPs-EVER lookup.  but we'd rather accumulate the per-day totals... */
/*
	if ($short==3)
	{
 		$queryStr = "SELECT count(DISTINCT userIP) as thecount";
		$queryStr .= " FROM $referTable";
		$sqr = db_getresults($queryStr, ARRAY_A, "rl_DailyStats");
	}
	else
*/
	{
	 	$queryStr = "
	 							SELECT DATE_FORMAT(visitTime, '%y%m%d') as thedate,
	 							  count($countQ) as thecount
								FROM $referTable
								$where
								AND baseDomain!='".BOT_MARKER."'
								AND baseDomain NOT LIKE '[%'
								GROUP BY TO_DAYS(visitTime)
								";
		$sqr = db_getresults($queryStr, ARRAY_A, "rl_DailyStats");
	}
	if (empty($sqr))
		echo "No stats available.";
	else
	{
		if ($short<=2) echo "<div id='stats'><span><i>Unique IPs, per-day, weekly sum:</i></span><br />";
		if ($short==1) echo "<br />";
		$i = 0;
		$count = 0;
		$sumtotal = 0;
		foreach($sqr as $result_row)
		{
			$i++;
      $date = $result_row['thedate'];
      $c =  $result_row['thecount'];
      
   		$sumtotal = $sumtotal + $c;
   		
			if ($short<=2)
      {
	      if ($short==1)
					echo "<i>$date</i>&nbsp;&nbsp;&nbsp;&nbsp;<b>$c</b><br />";
				
	      if ($i % 7 == 0) // looping
	      {
		      // output last chunk of data
		      $wksum = $sumtotal + array_sum($lastthree);
		      array_shift($lastthree);
		      $lastthree[2] = $sumtotal;
		      if ($short==1)
		      {
			      echo "<span><i>======> $sumtotal</i></span><br />";
			      echo "<span>[$wksum]</span><br /><br />";
		      }
		      else
		      if ($short==2)
		      {
		        if ($count>0) echo " :: ";
		        echo "$sumtotal";
	       	}
	       	
	       	// reset counter if supposed to...
	       	if ($short<=2) $sumtotal = 0;
	        $count++;
	        $i = 0;
	    	}
  		}
 		}
		
		if ($i % 7 != 0) // didn't just finish a row
		{
      $wksum = $sumtotal + array_sum($lastthree);
      if ($short==1)
      {
	      echo "<span><i>======> $sumtotal</i></span><br />";
	      echo "<span>[$wksum]</span><br /><br />";
      }
      else
			if ($short==2)
			{
				echo " :: $sumtotal"; // the missing number
				echo " ($i)";
			}
		}
		
		if ($short<=2) echo "<br /></div><br />";
		if ($short==3) printf("%08d", $sumtotal);
	}
//	echo "<br />";
}


//========================================================================
//========================================================================
function rl_DailyUnique()
{
	global $referTable;
		
	$where = "TO_DAYS(NOW()) - TO_DAYS(visitTime) = 0";

 	$queryStr = "
 							SELECT count(distinct(userIP)) as uniqueIPs
							FROM $referTable
							WHERE $where
								AND baseDomain!='".BOT_MARKER."'
								AND baseDomain NOT LIKE '[%'
							";
//								GROUP BY TO_DAYS(visitTime)
	$sqr = db_getresults($queryStr, ARRAY_A, "rl_DailyUnique");
	if (empty($sqr))
		return "0";
	else
		return $sqr[0]['uniqueIPs'];
}

//========================================================================
//========================================================================
function rl_MonthlyUnique()
{
	global $referTable;
		
	$where = "TO_DAYS(NOW()) - TO_DAYS(visitTime) <= 30 AND TO_DAYS(NOW()) - TO_DAYS(visitTime) >= 0";

 	$queryStr = "
 							SELECT count(distinct(userIP)) as uniqueIPs
							FROM $referTable
							WHERE $where
								AND baseDomain!='".BOT_MARKER."'
								AND baseDomain NOT LIKE '[%'
							";
//								GROUP BY TO_DAYS(visitTime)
	$sqr = db_getresults($queryStr, ARRAY_A, "rl_MonthlyUnique");
	if (empty($sqr))
		return "0";
	else
		return $sqr[0]['uniqueIPs'];
}

//========================================================================
//========================================================================
function rl_TotalUnique()
{
	global $referTable;
 	$queryStr = "
 							SELECT count(distinct(userIP)) as uniqueIPs
							FROM $referTable
								WHERE baseDomain!='".BOT_MARKER."'
								AND baseDomain NOT LIKE '[%'
							";
	$sqr = db_getresults($queryStr, ARRAY_A, "rl_TotalUnique");
	if (empty($sqr))
		return "0";
	else
		return $sqr[0]['uniqueIPs'];
}


//========================================================================
//========================================================================
function refererList ($howMany=5, $visitURL="", $makeLinks=1, $between="<br/>", $spanQueries=false, $showTime=false, $showAll=false)
{ 
	global $siteurl;
	global $referTable, $ignoreReferSites, $ignoreSpammerIPs, $showIPs, $showAsTable;
	global $referTargetWindow;
	global $user_level, $REQUESTED;

	$i=0; 

	$ret = Array(); 
	$last = Array();

	//if no visitURL, will show links to current page. 
	//if url given, will show links to that page. 
	//if url="global" will show links to all pages 
	
	if (!$visitURL)
		$visitURL = $_SERVER['REQUEST_URI']; 
	$ran = intval($howMany * 3); // figure half our hits are searches.  at some time, flag searches when ADDING to the table...

	$selwhat = "*, DATE_FORMAT(visitTime, '%y%m%d %H:%i:%s') as theTime"; // these are the only things we care about
	$selwhere = '';
	if (!$showAll)
		$selwhere = "WHERE baseDomain!='".BOT_MARKER."'
								AND baseDomain NOT LIKE '[%'";
	if ($visitURL == "global")
		$query = "			SELECT $selwhat FROM $referTable
							$selwhere
							ORDER BY visitID desc
							LIMIT $ran";
	else
		$query = "			SELECT $selwhat FROM $referTable
							WHERE visitURL = '$visitURL'
							$selwhere
							ORDER BY visitID desc
							LIMIT $ran";
    
	$sqr_recentReferer = db_getresults($query, ARRAY_A, "refererList");
			
 	$query_term = '';
 	$qpre = '';
 	$qpost = '';
	
	if (!empty($sqr_recentReferer))
	foreach($sqr_recentReferer as $result_row)
	{
		$id = $result_row['visitID']; 
		$fullUrl = $result_row['referingURL']; 
		$domain = $result_row['baseDomain'];
		$userIP = $result_row['userIP'];
		$theTime = $result_row['theTime'];
		$userAgent = $result_row['userAgent'];
		
		$visitURL = $result_row['visitURL'];
		$visitURL = str_replace($siteurl, '', $visitURL);
		$visitURL = str_replace('&', ' - ', $visitURL);
		$visitOutput = '<small>'.safehtmlentities(convert_to_ascii($visitURL)).'</small>';
		$visitCell = '<td>'.$visitOutput.'</td>';
		
		if (!$showAll)
		{
			if (!$domain) continue; 
			if (!$fullUrl) continue; 
			
			if ($last[$domain]) continue; 
		
			// check for 'blacklisted' referer sites, in case something wasn't flushed...
			if (findstr($domain, $ignoreReferSites)) continue;
			
			if ($userIP == $domain) // want domains not IPs!
			{
				$response = "domain is same as user IP\n";
				continue;
			}
				
			if (is_valid_IP_address($domain)) // we want domains not ip's!
			{
				$response = "domain is a dotted ip\n";
				continue;
			}
		}
		else
		if ($showAsTable)
		{
			$tdclass = '';
			if (0===strpos($domain, BOT_MARKER))
				$tdclass = 'class="ref-bot"';
			else
			if (0===strpos($domain, '['))
				$tdclass = 'class="ref-bad"';
		}
			
		$temp = '';
		if ($i>0) $temp = $between;
		else // first one...
		if ($showAsTable) // headers
		{
			$hdr = '';
			if ($user_level>4) $hdr .= '<th width="10%">ID</th>';
			if ($showTime) $hdr .= '<th width="10%">time</th>';
			if (1) $hdr .= '<th width="10%">IP</th>';
			$hdr .= '<th width="40%">domain</th>';
			if ($spanQueries) $hdr .= '<th width="20%">req</th>';
			if ($showIPs) $hdr .= '<th>UA</th>';
			array_push($ret,$hdr);
			
		}
					
		if ($showAsTable)
			if ($user_level>4)
			{
				if (strpos($REQUESTED, "wp-admin/admin.php"))
					$temp .= '<td class="ref-id"><a href="'.$REQUESTED.'&entry='.$id.'">'.$id.'</a></td>';
				else
					$temp .= '<td></td>';
			}
			
		if ($showTime)
		{
			if ($showAsTable)
				$temp .= '<td>'.$theTime.'</td>';
			else
				$temp .= $theTime . ' > ';
		}
		
		$last[$domain] = 1;
   	
		//echo "<br/>$visitURL<br/>";
		if ($spanQueries)// && $domain)
		{ // reset each time through.
			$query_term = '';
			$qpre = '';
			$qpost = '';
			if (strpos($visitURL,'s=')) // internal search...
				$query_term = findQueryTerms($visitURL);
			else
				$query_term = findQueryTerms($fullUrl);
			if (!$query_term)
			{
				$qpre = '<span>';
				$qpost = '</span>';
			}
		}		
		if (1)
		{
			if ($showAsTable)
				$temp .= '<td>'.$userIP.'</td>';
			else
				$temp .= '['.$userIP.'] ';
		}	
   	
		if (empty($domain))
		{
			if ($showAsTable)
				$temp .= '<td '.$tdclass.'>local</td>'.$visitCell;
			else
				$temp .= $qpre.' local '.$qpost;
		}
		else
		{
			$currout = '';
			if ($makeLinks)
			{
				$cleanFullUrl = safehtmlentities($fullUrl); 
				$currout .= '<a href="'.$cleanFullUrl.'"';
				if ($referTargetWindow) $currout .= ' target="'.$referTargetWindow.'"';
				$currout .= '>';
			}
			if ($spanQueries)
				$currout .= $qpre.$domain.$qpost;
			else
				$currout .= $domain;
			if ($makeLinks)
				$currout .= '</a>'; 
			if ($showAsTable)
			{
				$temp .= '<td '.$tdclass.'>'.$currout.'</td>';
				if ($query_term)
					$temp .= '<td><span>'.safehtmlentities(convert_to_ascii($query_term)).'</span>'."<br/>".$visitOutput.'</td>';
				else
					$temp .= $visitCell;
			}
			else
			if ($query_term)
				$temp .= $currout . ' ' . $query_term;
			else
				$temp .= $currout;
		}
		
		if ($showIPs)
		{
			if ($showAsTable)
				$temp .= '<td>'.substr($userAgent,0,64).'</td>';
			else
				$temp .= '['.$userIP.'] ';
		}
	
		if ($specialpost)
			$temp .= $specialpost;
		array_push($ret,$temp); 

		if (++$i > $howMany)
			break; 
	} 

	if ($i==0)
		$ret[0] = "No referers";
	
	return $ret; 
} 


//========================================================================
//========================================================================
function topRefererList ($howMany=5,$visitURL="",$makeLinks=true,$between="<br/>",$spanQueries=false)
{ 
	global $referTable, $showIPs, $showAsTable;
	global $referTargetWindow;
	
	$i=1; 
	$ret = Array(); 
	$last = null;
	
	//see refererList() for notes. 
	
	if (!$visitURL)
		$visitURL = $_SERVER['REQUEST_URI']; 

	$selwhat = "Count(baseDomain) as totalHits, baseDomain, referingURL"; // these are the only things we care about
	if (!$showAll)
		$selwhere = "WHERE baseDomain!='".BOT_MARKER."'
								AND baseDomain NOT LIKE '[%'";
	if ($visitURL != "global")
	{
		if (empty($selwhere)) $selwhere = "WHERE";
		$selwhere .= " visitURL = '$visitURL'";
	}
	
	$query = "select $selwhat from $referTable $selwhere group by baseDomain order by totalHits desc limit $howMany"; 

	$sqr_recentReferer = db_getresults($query, ARRAY_A, "topRefererList");

 	$query_term = '';
 	$qpre = '';
 	$qpost = '';
	
	if (!empty($sqr_recentReferer))
	{
		if ($showAsTable) // headers
		{
			$hdr = '';
			$hdr .= '<th width="10%">hits</th>';
			$hdr .= '<th width=50%>domain</th>';
			array_push($ret,$hdr);
		}

		foreach($sqr_recentReferer as $result_row)
		{
			$domain = $result_row['baseDomain']; 
			
			if (!$domain) continue; 
			if ($last[$domain]) continue;
				
			if ($showAsTable)
			{
				$tdclass = '';
				if (0===strpos($domain, BOT_MARKER))
					$tdclass = 'class="ref-bot"';
				else
				if (0===strpos($domain, '[40'))
					$tdclass = 'class="ref-bad"';
			}
			
			$temp = "";
			if ($i>1) $temp = $between;
			
			$count = $result_row['totalHits']; 
			
			if ($makeLinks || $spanQueries)
			{
				$cleanLatestUrl = $domain;
				if ($spanQueries)
				{
					//		    $query = "select referingURL from $referTable where baseDomain = '$domain' order by visitID desc";
					$latestUrl = $result_row['referingURL'];
					$cleanLatestUrl = htmlspecialchars($latestUrl); 
							   	
					// reset each time through.
					$query_term = '';
					$qpre = '';
					$qpost = '';
					$query_term = findQueryTerms($latestUrl);
					if (!$query_term)
					{
					$qpre = '<span>';
					$qpost = '</span>';
					}
				}		
			}
			
			if ($showAsTable)
				$temp .= '<td width=10%>'.$qpre.$count.$qpost.'</td>';
			
			$currout = '';
			if ($makeLinks)
			{
				//$currout .= '<a href="'.$cleanLatestUrl.'" target="_blank">';
				$currout .= '<a href="http://'.$domain.'"';
				if ($referTargetWindow) $currout .= ' target="'.$referTargetWindow.'"';
					$currout .= '>';
			}
			if ($spanQueries)
				$currout .= $qpre.$domain.$qpost;
			else
				$currout .= $domain;
			if ($makeLinks)
				$currout .= '</a>'; 
			
			if ($showAsTable)
				$temp .= '<td '.$tdclass.' width=50%>'.$currout.'</td>';
			else
				$temp .= $currout . ' (' . $count . ')';
			
			array_push($ret,$temp); 
			
			if ($i++ > $howMany)
				break; 
		}
	}
    
	if (count($ret)==0)
		$ret[0] = "No referers";
	
	return $ret; 
} 


//==============================================================================
// original Google parsing / display functions by Ben Johnson
// modified heavily by David Chait for alternate search sites and query strings.
//==============================================================================


//========================================================================
// simplified helper function for trimming search referURLs.
function trimSearchURL($URL, $Pos, $end='&')
{
	if ($Pos) 
	{
		//$nMax = strlen($URL); 
		$nEndPos = strpos($URL,$end,$Pos); 
		
		//echo "Pos = $Pos, end = $nEndPos, Max = $nMax<br />";
		if ($nEndPos === false) 
		{ 
			// $Arg is on the end of the URL 
			$URL = substr($URL,$Pos); 
		} 
		else 
		{ 
			// $Arg is in the URL 
			$URL = substr($URL,$Pos,$nEndPos-$Pos); 
		} 
	} 
	return $URL; 
}


//========================================================================
/* Helper function - based on php.net sample code, removes the argument named $arg from $URL */ 
function removeArgFromURL($URL, $Arg) 
{ 
	$Pos = strpos($URL, "$Arg"); 
	if ($Pos) 
	{ 
		if ($URL[$Pos+strlen($Arg)] == "=") 
		{ 
			// If Pos+strlen+1 is pointing to a '=' increase Pos by strlen+1 so we lose the = 
			$Pos += strlen($Arg)+1; 
		} 
		return trimSearchURL($URL, $Pos);
	} 
	return $URL; 
} 

//========================================================================
// This decodes quoted-printable parameters (ie =2c) 
function qp_Decode($string) { 
	return preg_replace("/=([0-9A-F]{2})/e", "chr(hexdec('\\1'))", $string); 
} 

//========================================================================
// This decodes URL-encoded parameters (ie %2c) 
function url_Decode($string) { 
return preg_replace("/%([0-9A-Fa-f]{2})/e", "chr(hexdec('\\1'))", $string); 
} 


//========================================================================
$engineName = '';
//========================================================================

//========================================================================
//========================================================================
function findQueryTerms($fullUrl, $visitUrl)
{
	global $engineName;
	$arg = '';
	$ending = '&';
	
	// adding in detection of search engine.
	if (FALSE!==strpos($fullUrl,"google."))
	{
		$engineName = 'Google';
		$arg = "q=";
		if (FALSE!==strpos($fullUrl,"as_epq=")) // weird secondary form...
		    $arg = "as_epq=";
		else
		if (FALSE!==strpos($fullUrl,"as_q=")) // weird secondary form...
		    $arg = "as_q=";
	}
	else
	if (FALSE!==strpos($fullUrl,"yahoo."))
	{
		$engineName = 'Yahoo';
		$arg = "p=";
		if (FALSE!==strpos($fullUrl,"va=")) // weird secondary form...
		    $arg = "va=";
	}
	else
	if (FALSE!==strpos($fullUrl,"a9."))
	{
		$engineName = 'A9';
		$arg = "a9.com?";
	}
	else
	if (FALSE!==strpos($fullUrl,"looksmart."))
	{
		$engineName = 'looksmart';
		$arg = "key=";
	}
	else
	if (FALSE!==strpos($fullUrl,"mysearch."))
	{
		$engineName = 'mysearch';
		$arg = "searchfor=";
	}
	else
	if (FALSE!==strpos($fullUrl,"iwon."))
	{
		$engineName = 'iwon';
		$arg = "searchfor=";
	}
	else
	if (FALSE!==strpos($fullUrl,"aol."))
	{
		$engineName = 'AOL';
		if (FALSE!==strpos($fullUrl,"encquery"))
			return 'unknown'; // can't parse their encoded queries...
		$arg = "query=";
	}
	else
	if (FALSE!==strpos($fullUrl,"msn."))
	{
		$engineName = 'MSN';
		$arg = "q=";
		if (FALSE!==strpos($fullUrl,"q=&"))
		    $arg = "q=&q=";
	}
	else
	if (FALSE!==strpos($fullUrl,"hotbot."))
	{
		$engineName = 'hotbot';
		$arg = "MT=";
	}
	else
	if (FALSE!==strpos($fullUrl,"netscape."))
	{
		$engineName = 'netscape';
		$arg = "query=";
	}
	else
	if (FALSE!==strpos($fullUrl,"hotbot."))
	{
		$engineName = 'hotbot';
		$arg = "query=";
	}
	else
	if (FALSE!==strpos($fullUrl,"dogpile."))
	{
		$engineName = 'dogpile';
		$arg = "search/web/";
		$ending = '/'; // special handling
	}
	else
	if (FALSE!==strpos($fullUrl,"metacrawler."))
	{
		$engineName = 'metacrawler';
		$arg = "search/web/";
		$ending = '/'; // special handling
	}
	else
	if (FALSE!==strpos($fullUrl,"excite."))
	{
		$engineName = 'excite';
		$arg = "search/web/";
		$ending = '/'; // special handling
	}
	else
	if (FALSE!==strpos($fullUrl,"kazazz."))
	{
		$engineName = 'kazazz';
		$arg = "query=";
	}
	else
	if (FALSE!==strpos($fullUrl,"mywebsearch."))
	{
		$engineName = 'mywebsearch';
		$arg = "searchfor=";
	}
	else
	if (FALSE!==strpos($fullUrl,"infospace."))
	{
		$engineName = 'infospace';
		$arg = "qkw=";
	}
	else
	if (FALSE!==strpos($fullUrl,"websearch."))
	{
		$engineName = 'websearch';
		$arg = "qkw=";
	}
	else
	if (FALSE!==strpos($fullUrl,"copernic."))
	{
		$engineName = 'copernic';
		$arg = "qkw=";
	}
	else
	if (FALSE!==strpos($fullUrl,"cometsystems."))
	{
		$engineName = 'cometsystems';
		$arg = "qry=";
	}
	else
	if (FALSE!==strpos($fullUrl,"steadysearch."))
	{
		$engineName = 'steadysearch';
		$arg = "w=";
	}
	else
	if (FALSE!==strpos($fullUrl,"viewpoint."))
	{
		$engineName = 'viewpoint';
		$arg = "k=";
	}
	else
	if (FALSE!==strpos($fullUrl,"fresheye."))
	{
		$engineName = 'fresheye';
		$arg = "kw=";
	}
	// SECOND TO LAST..
	else // look for our server, internal searches...
	if (FALSE!==strpos($fullUrl,$_SERVER['HTTP_HOST']))
	{
		$engineName = 'localhost';
		$arg = 's=';
		// do the lookup on our visiturl...
		$fullUrl = $visitUrl;
	}
	
	if (strpos($fullUrl,"q=cache:")) // if cached, try just the first + sign...
	{
		$arg = "+";
	}
	
	if (!empty($arg)) // first lookup...
		$Pos = strpos($fullUrl, $arg);	

	if (empty($Pos)) // nobody found... try some alt tags
	{
		if (empty($engineName))
			$engineName = 'unknown';
		$arg = "&q=";
		$Pos = strpos($fullUrl, $arg);
		if (empty($Pos))
		{
			$arg = "q=";
			$Pos = strpos($fullUrl, $arg);
		}
		if (empty($Pos))
		{
			$arg = "query=";
			$Pos = strpos($fullUrl, $arg);
		}
		if (empty($Pos))
		{
			$arg = "string=";
			$Pos = strpos($fullUrl, $arg);
		}
		if (empty($Pos))
		{
			$arg = "s=";
			$Pos = strpos($fullUrl, $arg);
		}
	}
	
	if (empty($Pos))
		return null;
		  
	//echo "Base = $fullUrl<br />";
	$trimmedSearch = trimSearchURL($fullUrl, $Pos+strlen($arg), $ending);
	//echo "  trimmed = $trimmedSearch<br />";
	/* not sure why this old code was here... but queries I'm seeing don't use it...
	$Pos = strpos($trimmedSearch,':'); // just in case something fell through...
	if (!empty($Pos)) // aaaaagh!
	{ // find the last colon...
		$Pos = strrpos($trimmedSearch, ':');
		$trimmedSearch = substr($trimmedSearch, $Pos+1);
	}
	*/
	
	$trimmedSearch = qp_Decode(url_Decode($trimmedSearch));
	$removeChars = array('\'', '+', '"', ',');
	$trimmedSearch = str_replace($removeChars, ' ', $trimmedSearch);
		return $trimmedSearch;
}

//========================================================================
// List-building function - by default returns last 5 queries.
//========================================================================
function getRecentSearches($howMany=5, $doOutput=false, $matchString='', $showEngineName = false, $showFullURL = false, $showAsTable=false,
														$befBlock = '<ul>', $aftBlock = '</ul>', 
														$befItem = '<li>', $aftItem = '</li>'
												)
{ 
	global $referTable, $engineName;
	global $referTargetWindow;
	
	$makeLinks = true;
	
	$ret = Array(); 
	$last = Array();
	$output = '';
	$ran = intval($howMany * 3); // figure half our hits are searches.  at some time, flag searches when ADDING to the table...

	$match = '';
	if (!empty($matchString))
	{
		if (strpos($matchString, ','))
		{
			$terms = explode(',', $matchString);
			$match = "AND ";
			$match .= '(';
			$c = 0;
			foreach($terms as $term)
			{
				$c++;
				if ($c>1) $match .= ' OR ';
				$match .= "referingURL LIKE '%$term%'";
			}
			$match .= ')';
		}
		else
			$match = "AND referingURL LIKE '%$matchString%'";
	}
	
	$sqquery = "
				SELECT referingURL, DATE_FORMAT(visitTime, '%y%m%d %H:%i:%s') as theTime, visitURL
				FROM $referTable
				WHERE (referingURL LIKE '%search%'
					OR referingURL LIKE '%query%'
					OR referingURL LIKE '%q=%'
					OR visitURL LIKE '%?s=%')
				$match
				AND baseDomain!='".BOT_MARKER."'
				AND baseDomain NOT LIKE '[%'
				ORDER BY visitID DESC LIMIT $ran"; // limit 200 to give us a range...

	$sqr = db_getresults($sqquery, ARRAY_A, "getRecentSearches");

	if ($showAsTable)
	{
		$befBlock = '';
		$aftBlock = '';
		$befItemOdd = '<tr class="ref-odd">';
		$befItemEven = '<tr class="ref-even">';
		$aftItem = '</tr>';
		// headers
		$hdr = '';
		$hdr .= '<th width=15%>time</th>';
		$hdr .= '<th width=70%>query</th>';
		$hdr .= '<th>engine</th>';
		$output .= $hdr;
//		$tds = '<td style="border-top: 1px solid #5555bb">';
		$tds = '<td>';
	}
	else
		$output .= $befBlock . "\n";
	
	$i=0; 
	if (!empty($sqr))
	foreach($sqr as $result_row)
	{
	    $fromUrl = $result_row['referingURL']; 
	    $visitUrl = $result_row['visitURL']; 
		$theTime = $result_row['theTime'];
         
	    $query_term = findQueryTerms($fromUrl, $visitUrl);

	    if (!$query_term) continue; 
	    if ($last[$query_term]) continue;
	    
	    $last[$query_term] = 1; 
    
		if ($makeLinks)
		{
			if ($engineName=='localhost') // then we should use visitUrl, no?
				$cleanFromUrl = safehtmlentities($visitUrl); 
			else
				$cleanFromUrl = safehtmlentities($fromUrl); 
		}
		
	    $query_term = safehtmlentities(convert_to_ascii($query_term));
    
	    $i++;
		$output .= (($i%2)?$befItemOdd:$befItemEven);
		
		if ($showAsTable)
		{ // !!!! NOT CURRENTLY SHOWING FULL URL IN TABLE MODE !!!!
			$output .= "<td>$theTime</td>";
			$output .= "<td><span>$query_term</span>";
			if (1)
				$output .= '<br/><small>' . safehtmlentities($visitUrl) . '</small>';
			$output .= '</td>';
				
			$output .= '<td>';
				if ($makeLinks)
				{
					$output .= '<span><a href="'.$cleanFromUrl.'"';
					if ($referTargetWindow) $output .= ' target="'.$referTargetWindow.'"';
					$output .= '>';
				}
				$output .= "$engineName";
				if ($makeLinks)
					$output .= '</a></span>';			
			$output .= "</td>\n";
		}
		else
		{
//			$output .= "$theTime: ";		
			$output .= "$query_term <br/>";		
			if ($showEngineName)
			{
				$output .= '<br /><i>... from <b>';
				if ($makeLinks)
				{
					$output .= '<a href="'.$cleanFromUrl.'"';
					if ($referTargetWindow) $output .= ' target="'.$referTargetWindow.'"';
					$output .= '>';
				}
				$output .= $engineName;
				if ($makeLinks)
					$output .= '</a>';			
				$output .= '</b></i>';
			}
			if ($showFullURL)
				$output .= '<br />' . $fromUrl;
			if (1)
				$output .= '<br/><small>' . safehtmlentities($visitUrl) . '</small>';
		}
			
		$output .= $aftItem . "\n";
		
    	if ($i > $howMany)
			break; 
	}
  
	if ($i==0)
	{
		$output = $befItem; // NOTE: assigning as no results, blow table.
		$output .= "No searches.\n";
		$output .= $aftItem . "\n";
	}
	
	$output .= $aftBlock . "\n";
	
	if ($doOutput)
		echo $output;
	
	return $output; 
} 

function getRecentBots($howMany=5, $doOutput=false, $matchString='', $stripSite=false, $showAsTable=false,
														$befBlock = '<ul>', $aftBlock = '</ul>', 
														$befItem = '<li>', $aftItem = '</li>'
												)
{ 
	global $referTable, $engineName, $ignoreFakeBots;
	global $user_level, $REQUESTED;
	
	$ret = Array(); 
	$last = Array();
	$output = '';
	
	if ($ignoreFakeBots)
	$andterm = "AND userAgent NOT LIKE '%Lynx%'
					AND userAgent NOT LIKE '%Java%'";
//					OR baseDomain LIKE '[%')
	
	$match = '';
	if (!empty($matchString))
	{
		if (intval($matchString)) //searching for [403] errors?
			$match = "AND baseDomain LIKE '%$matchString%'";
		else
			$match = "AND userAgent LIKE '%$matchString%'";
	}
	
	$sqquery = "
				SELECT *, DATE_FORMAT(visitTime, '%y%m%d %H:%i:%s') as theTime
				FROM $referTable
	  					WHERE (baseDomain='".BOT_MARKER."')
				$andterm
	  					$match
				ORDER BY visitID DESC LIMIT $howMany";
	
	$sqr = db_getresults($sqquery, ARRAY_A, "getRecentBots");

	if ($showAsTable)
	{
		$befBlock = '';
		$aftBlock = '';
		$befItemOdd = '<tr class="ref-odd">';
		$befItemEven = '<tr class="ref-even">';
		$aftItem = '</tr>';
		// headers
		$hdr = '';
		if ($user_level>4)
			$hdr .= '<th width=10%>ID</th>';
		$hdr .= '<th width=10%>time</th>';
		$hdr .= '<th width=10%>IP</th>';
		$hdr .= '<th>ref</th>';
		$hdr .= '<th>agent</th>';
		$hdr .= '<th>url</th>';
		$output .= $hdr;
//		$tds = '<td style="border-top: 1px solid #5555bb">';
		$tds = '<td>';
	}
	
	$output .= $befBlock . "\n";
	
	$i=0; 
	if (!empty($sqr))
	foreach($sqr as $result_row)
	{
		$id = $result_row['visitID'];
	    $fullUrl = $result_row['visitURL']; 
		$agent = $result_row['userAgent'];
		$ip = $result_row['userIP'];
		$theTime = $result_row['theTime'];
		$baseDomain = $result_row['baseDomain'];
         
    	$fullUrl = safehtmlentities($fullUrl);
    
		if ($stripSite)
		{
			$pos = strpos($agent, '(');
			if (!$pos)
				$pos = strpos($agent, 'http:');
			if ($pos)
				$agent = substr($agent, 0, $pos);
		}
		$agent = safehtmlentities($agent); 

		$i++;
		$output .= (($i%2)?$befItemOdd:$befItemEven);
		if ($showAsTable)
		{
			if ($user_level>4)
			{
				if (strpos($REQUESTED, "wp-admin/admin.php"))
					$output .= '<td class="ref-id"><a href="'.$REQUESTED.'&entry='.$id.'">'.$id.'</a></td>';
				else
					$output .= '<td></td>';
			}
			
			$output .= "<td>$theTime</td><td>$ip</td>";
			if (strpos($baseDomain, ']'))
				$output .= "<td><span>$baseDomain</span></td><td>$agent</td><td>$fullUrl</td>\n";
			else
				$output .= "<td></td><td><span>$agent</span></td><td>$fullUrl</td>\n";
		}
		else
			$output .= "$theTime [$ip] $agent ($fullUrl) <br/>";
		$output .= $aftItem . "\n";
		
	    if ($i > $howMany)
			break; 
	}
	
	if ($i==0)
	{
		$output .= $befItem;
		$output .= "No bots.\n";
		$output .= $aftItem . "\n";
	}
  	
	$output .= $aftBlock . "\n";
  
  if ($doOutput)
  	echo $output;
  	
  return $output; 
} 


function getRecentBlocked($howMany=5, $doOutput=false, $matchString='', $showAsTable=false,
														$befBlock = '<ul>', $aftBlock = '</ul>', 
														$befItem = '<li>', $aftItem = '</li>'
												)
{ 
	global $referTable, $engineName;
	global $user_level, $REQUESTED;
	
	$ret = Array(); 
	$last = Array();
	$output = '';
	
	$match = '';
	if (!empty($matchString))
	{
		$match = "AND baseDomain LIKE '%$matchString%'";
	}
	
	$sqquery = "
				SELECT *, DATE_FORMAT(visitTime, '%y%m%d %H:%i:%s') as theTime
				FROM $referTable
  					WHERE (baseDomain LIKE '%[%')
	  					$match
				ORDER BY visitID DESC LIMIT $howMany";
	
	$sqr = db_getresults($sqquery, ARRAY_A, "getRecentBlocked");
	
	if ($showAsTable)
	{
		$befBlock = '';
		$aftBlock = '';
		$befItemOdd = '<tr class="ref-odd">';
		$befItemEven = '<tr class="ref-even">';
		$aftItem = '</tr>';
		// headers
		$hdr = '';
		$hdr .= '<th width=15%>time</th>';
		$hdr .= '<th width=10%>IP</th>';
		$hdr .= '<th>base</th>';
		$hdr .= '<th>agent</th>';
		$hdr .= '<th>url</th>';
		$output .= $hdr;
//		$tds = '<td style="border-top: 1px solid #5555bb">';
		$tds = '<td>';
	}
	
	$output .= $befBlock . "\n";
	
	$i=0; 
	if (!empty($sqr))
	foreach($sqr as $result_row)
	{
		$id = $result_row['visitID'];
    	$fullUrl = $result_row['visitURL']; 
		$agent = $result_row['userAgent'];
		$ip = $result_row['userIP'];
		$theTime = $result_row['theTime'];
		$baseDomain = $result_row['baseDomain'];
         
		$fullUrl = safehtmlentities($fullUrl);
		
		if (1) //$stripSite)
		{
			$pos = strpos($agent, '(');
			if (!$pos)
				$pos = strpos($agent, 'http:');
			if ($pos)
				$agent = substr($agent, 0, $pos);
		}
	    $agent = safehtmlentities($agent); 
      
		$i++;
		$output .= (($i%2)?$befItemOdd:$befItemEven);
		if ($showAsTable)
		{
			if ($user_level>4)
			{
				if (strpos($REQUESTED, "wp-admin/admin.php"))
					$output .= '<td class="ref-id"><a href="'.$REQUESTED.'&entry='.$id.'">'.$id.'</a></td>';
				else
					$output .= '<td></td>';
			}
			$output .= "<td>$theTime</td><td>$ip</td>";
			if (strpos($baseDomain, ']'))
				$output .= "<td><span>$baseDomain</span></td><td>$agent</td><td>$fullUrl</td>\n";
			else
				$output .= "<td></td><td><span>$agent</span></td><td>$fullUrl</td>\n";
		}
		else
			$output .= "$theTime [$ip] $agent ($fullUrl) <br/>";
		$output .= $aftItem . "\n";
		
    	if ($i > $howMany)
			break; 
	}
	
	if ($i==0)
	{
		$output .= $befItem;
		$output .= "No blocked.\n";
		$output .= $aftItem . "\n";
	}
  	
	$output .= $aftBlock . "\n";
  
  if ($doOutput)
  	echo $output;
  	
  return $output; 
} 


//========================================================================
//========================================================================
function dbg($string){ 
    //print $string . "<BR>\n"; 
} 


//========================================================================
//========================================================================
function install_referer_table()
{
	global $referTable;
	echo "Creating table...<BR />"; 
	$success = db_runquery(" 
					        create table `$referTable` ( 
					            visitID int(11) auto_increment, 
					            primary key (visitID), 
					            visitTime timestamp, 
					            visitURL varchar(255), 
					            referingURL varchar(255), 
					            baseDomain varchar(100),
					            userAgent varchar(255),
					            userIP varchar(32)
											)
									");
	if (false===$success)
		echo "<span>Failed to create table -- see above error message.  (This usually means it already exists in the database, but check the error message for more details.)</span>"; 
	else
		echo "<span>Created CG-Referer history table.</span>"; 
}


//========================================================================
// these are the file-direct output fns.
//========================================================================
/*
	    foreach($_SERVER as $key=>$value)
	        echo $key . " = " . $value . "<br>";
	    echo "<br><br><br>";
*/

//========================================
//========================================
if (!isset($cgr_uniqueOncePerDay))
	$cgr_uniqueOncePerDay = false; // false means track multiple visits by same IP.  set true to only track one visit per day.
if (!isset($cgr_trackInternalMovement))
	$cgr_trackInternalMovement = true;  // true means track people moving around within your site.
if (!isset($cgr_doBlacklistChecks))
	$cgr_doBlacklistChecks = false; // set this to true to enable the various blacklists, or an array of blacklist-tests to perform.
if (!isset($cgr_puntBlacklisted))
	$cgr_puntBlacklisted = false; // set this to true to not just tag blacklisted refs, but punt them immediately.

function referrer_track()
{
	global $cgr_uniqueOncePerDay, $cgr_trackInternalMovement, $cgr_doBlacklistChecks, $cgr_puntBlacklisted;
	global $onTestServer, $onNewServer, $user_level;
	
	if (!strpos($_SERVER['REQUEST_URI'], "cg-referrer")) 
	{
		if (!isset($user_level) && function_exists('get_currentuserinfo'))
			get_currentuserinfo(); // cache away in case hasn't been yet...
	//	if (!$onCriticalFallback)
		if (!$onTestServer && !$onNewServer && $user_level<4)
			$referrerResponse = logReferer($cgr_uniqueOncePerDay, $cgr_trackInternalMovement, true, $cgr_doBlacklistChecks, $cgr_puntBlacklisted); // catch all unique IPs per day...
		if ($user_level<4)
			return; // early exit...
	}
}

// test for not in admin...
if (!strpos($REQUESTED, "wp-admin/admin.php"))
{
	// well, check for direct-include...
	if (!strpos($REQUESTED, "cg-referrer"))
	{
		if (function_exists('referrer_track'))
			add_action('plugins_loaded', 'referrer_track');
		return; // we're done here if not in admin pages...
	}
	
	// if direct-include, we need to make sure we have user_level
	if (!isset($user_level) && function_exists('get_currentuserinfo'))
		get_currentuserinfo(); // cache away in case hasn't been yet...
	if ($user_level<4) die("You need a higher access level.");
}
	
// else, admin functions...
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

$findvars = array(
	'action', 'standalone', 'page', 'create', 'resultname',	'purge_days'
	);

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
	// SANITY CHECK INCOMING DATA!
	if ($$avar) // check for bad content
		if (FALSE!==strpos($$avar, 'http:')) // NO URIs AT ALL IN THESE COMMANDS!
			$$avar = '';
}

// test database...
$qnumitems = db_getrow("SELECT COUNT(*) as num FROM $referTable", OBJECT, 0, "admin - referrer count");
if (!empty($qnumitems)) 
{
	$qnumitems = $qnumitems->num; // just grab the count.
}
else // likely means table not exist, test error...
if (db_lasterror()) // was error, table doesn't exist??
{
?>
	<div class="wrap">
		<form name="createtable" action="<?php echo $REQUESTED; ?>" method="post">
			<p>Cannot locate any existing CG-Referrer data.</p>
			<input type="hidden" name="action" value="create" />
			<input type="submit" name="submit" value="Create CG-Referrer Table" class="search" />
		</form>
	</div>
<?php
}

	$flushBlacklist = $_GET['flush'];
//	$purgeEntries = $_GET['purge'];
//	$purgeEntries = intval($purgeEntries);
	$tagEntries = $_GET['tag'];
	if (!$tagEntries)
		$tagEntries = ($action=='tag');
	$flushBots = $_GET['flushbots'];
	$showBots = $_GET['bots'];
	$showBlocked = $_GET['blocked'];
	$createTable = $action=='create';
	$clearDups = $_GET['cleardups'];
	if (isset($_GET['stats']))
	{
		$showStats = $_GET['stats'];
		$showStats = intval($showStats);
	}
	if (isset($_GET['searches']))
	{
		$showSearches = $_GET['searches'];
		$showSearches = intval($showSearches);
	}
	$showMatches = $_GET['match']; // this needs to be wrapped for safety.
	$showTop = intval($_GET['top']);
	$showRecent = intval($_GET['recent']);
	$showIPs = intval($_GET['showips']);
	$showEntry = intval($_GET['entry']);
	$showAsTable = true; // for now, force on table layout;

	$homepanel = !($action || $createTable || $flushBlacklist || $purgeEntries || $tagEntries || $clearDups || $showStats || $showBots || $showBlocked || $showEntry || $showSearches || $showTop || $showRecent || $flushBots) && (strpos($REQUESTED, "wp-admin/admin.php"));
		
	if ($user_level>=2)
	if ($homepanel || $action || $createTable || $flushBlacklist || $purgeEntries || $tagEntries || $clearDups || $showStats || $showBots || $showBlocked || $showEntry || $showSearches || $showTop || $showRecent || $flushBots)
	{	
		if ($createTable)
			$firstTitle = 'Creating CG-Referrer Primary DB Table';
		else if ($flushBlacklist)
			$firstTitle = 'Flushing Referers Using Blacklist';
		else if ($flushBots)
			$firstTitle = 'Flushing Bots';
		else if ($purgeEntries)
			$firstTitle = 'Purging Referer Table Entries';
		else if ($tagEntries)
			$firstTitle = 'Tagging Referer Table Entries';
		else if ($clearDups)
			$firstTitle = 'Clearing duplicate entries';
		else if ($showStats)
			$firstTitle = 'Showing current referrer list statistics';
		else if ($showBots)
			$firstTitle = 'Showing recent bot activity';
		else if ($showBlocked)
			$firstTitle = 'Showing recent blocked access';
		else if ($showEntry)
			$firstTitle = "Showing entry [$showEntry]";
		else if ($showTop)
				$firstTitle = 'Showing top referrers';
		else if ($showRecent)
				$firstTitle = 'Showing most recent referrers';
		else if ($showSearches)
			$firstTitle = 'Showing referrer list Search Referral history';
		else //if ($homepanel)
			$firstTitle = 'CG-Referrer Home Panel';	
		if (!strpos($REQUESTED, "wp-admin/admin.php"))
		{
			echo '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">';
			echo '<html xmlns="http://www.w3.org/1999/xhtml">';
			echo '<title>'.$firstTitle.'</title>';
			echo '<meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1" />';
			echo '<style media="screen" type="text/css">';
			echo '	body {';
			echo '		font: 9px Georgia, "Times New Roman", Times, serif;';
			echo '		margin-left: 5%;';
			echo '		margin-right: 5%;';
			echo '	}';
			echo '	span {';
			echo '		font: bold 12px Arial, sans-serif;';
			echo '	}';
			echo '</style>';
			echo '</head>';
		}
		else
		{
			?>
				<style type="text/css">
					.ref-odd {
						background: #fefefe;
					}
					.ref-even {
						background: #eeefee;
					}
					th {
						background: #aabbdd;
					}
					.ref-bad, .ref-bad a {
						background: #FFBBBB;
						color: #774444;
						text-decoration: none;
						border:none;
					}
					.ref-bot, .ref-bot a  {
						background: #BBEEBB;
						color: #447744;
						text-decoration: none;
						border:none;
					}
					.ref-id, .ref-id a  {
						background: #bbccee;
						color: #331111;
						text-decoration: none;
						border:none;
						text-align: center;
					}
					.ref-bad a:hover, .ref-bot a:hover, .ref-id a:hover {
						border-bottom: 1px solid black;
					}
					td span {
						font-weight: bold;
					}
					.ref-bot span, .ref-bad span {
						font-weight: normal;
					}
				</style>
			<?php
		}
		echo '<body><br />';

//		print_r($_GET);
//		print_r($_POST);
			    
		echo '<div class="wrap">';
//		echo "<div id='mydate'>".date("D M jS @ g:iA")."</div>";

		// to fit into old scheme quickly:
		if ($action=='purge')
		{
			$purgeEntries = $purge_days;
			?>
			<form name="donepurge" action="<?php echo $REQUESTED; ?>" method="post">
				<input type="hidden" name="action" value="purgerequest" />
				<p><input type="submit" name="cancel" value="Done" class="search" /></p>
			</form>
			<h2>Purging Referrer Database (<?php echo $purgeEntries-1; ?> days back):</h2>
			<?php
		}
		else
		if ($tagEntries)
		{
			?>
			<form name="donetag" action="<?php echo $REQUESTED; ?>" method="post">
				<input type="hidden" name="action" value="" />
				<p><input type="submit" name="cancel" value="Done" class="search" /></p>
			</form>
			<h2>Tagging Referrer Database:</h2>
			<?php
			flush(); // just to help things along...
		}
		
		if ($homepanel)
		{
			echo "<h2>$firstTitle</h2>";
			echo "<table>";
				echo "<tr><th colspan=2>Unique IPs Tracked</th></tr>";

				$unqcount = rl_DailyUnique();
				echo '<tr class="ref-odd">';
					echo '<td width="100"><em>Today</em></td>';
					echo '<td width="100">';
					printf("%08d", $unqcount);
					echo '</td>';
				echo '</tr>';
				
				$unqcount = rl_MonthlyUnique();
				echo '<tr class="ref-even"><td><em>Last 30 days</em></td>';
					echo '<td width="100">';
					printf("%08d", $unqcount);
					echo '</td>';
				echo '</tr>';
			echo "</table>";
		}
		else
		if ($action=='purgerequest')
		{
			?>
				<form name="cancelpurge" action="<?php echo $REQUESTED; ?>" method="post">
					<input type="hidden" name="action" value="cancel" />
					<p><input type="submit" name="cancel" value="Cancel" class="search" /></p>
				</form>
				<h2>Purge Referrer Database:</h2>
				<form name="purgedb" action="<?php echo $REQUESTED; ?>" method="post">
					<input type="hidden" name="action" value="purge" />
					<p>The Database currently contains <?php echo $qnumitems; ?> total records.</p>
					<?php if ($qnumitems>0) { ?>
					<p>Clear:
						<select name='purge_days' size='1'>
							<option value='1'>All</option>
							<option value='8'>Older Than 1 Week</option>
							<option value='31' selected>Older Than 1 Month</option>
							<option value='91'>Older Than 3 Months</option>
							<option value='181'>Older Than 6 Months</option>
						</select>
						<input type="submit" name="submit" value="&nbsp;PURGE&nbsp;" class="search" />
					</p>
					<?php } ?>
				</form>
			<?php
		}
		else
 		if ($createTable)
		{ 
			install_referer_table();
		} 
		else
		if ($showEntry)
		{
			echo "<h2>$firstTitle</h2>";
			$query = "SELECT * FROM $referTable WHERE visitID='$showEntry'";
			$result = db_getresults($query, ARRAY_A, "get specific entry");
			if (empty($result)) break;
			
			echo '<table>';
			echo '<tr><th width="100">field</th><th width="360">value</th></tr>'."\n";
			if (1)
			{ // reset each time through.
				$query_term = '';
				$qpre = '';
				$qpost = '';
				if (strpos($result[0]['visitURL'],'s=')) // internal search...
					$query_term = findQueryTerms($result[0]['visitURL']);
				else
					$query_term = findQueryTerms($result[0]['referingURL']);
				if ($query_term)
				{
					$qpre = '<span>';
					$qpost = '</span>';
				}
			}		
			foreach($result[0] as $field => $value)
			{
				echo '<tr><td align="center"><i>'.$field.'</i></td>';
				if ($field=='baseDomain' && strpos($value, '[')===0)
					echo '<td class="ref-bad">';
				else
				if ($field=='referingURL' && $query_term)
					echo '<td>'.$qpre.$query_term.$qpost."\n";
				else
					echo '<td>';
				echo htmlentities($value).'</td></tr>'."\n";
			}
			echo '</table>';
		}
		else
		if ($showSearches)
		{
			echo "<h2>Showing $showSearches most recent queries</h2>";
			$out = getRecentSearches($showSearches, false, $showMatches, true, false, $showAsTable);
			if ($showAsTable) echo "<table>$out</table>";
		}
		else
		if ($showBots)
		{
			echo "<h2>$firstTitle</h2>";
			$ignoreFakeBots = ($showBots+1) % 2; // odd == show all...
			$out = getRecentBots($showBots, false, $showMatches, true, $showAsTable);
			if ($showAsTable) echo "<table>$out</table>";
		}
		else
		if ($showBlocked)
		{
			echo "<h2>$firstTitle</h2>";
			$out = getRecentBlocked($showBlocked, false, $showMatches, $showAsTable);
			if ($showAsTable) echo "<table>$out</table>";
		}
		else
		if ($showStats)
		{
			echo "<h2>$firstTitle</h2>";
			echo "<div class='pagefooter'>";
			$unqcount = rl_MonthlyUnique();
			$unqpre = "0000";
			if ($unqcount>1000)
			{
				if ($unqcount<10000)
					$unqpre = "000";
				else if ($unqcount<100000)
					$unqpre = "00";
				else if ($unqcount<1000000)
					$unqpre = "0";
				else
					$unqpre = "";
			}
			echo "30 Day Unique<br /><b>[$unqpre$unqcount]</b>";	
/*
			echo "<hr><br />";
			$unqcount = rl_TotalUnique();
			$unqpre = "0000";
			if ($unqcount>1000)
			{
				if ($unqcount<10000)
					$unqpre = "000";
				else if ($unqcount<100000)
					$unqpre = "00";
				else if ($unqcount<1000000)
					$unqpre = "0";
				else
					$unqpre = "";
			}
			echo "Total Unique<br /><b>[$unqpre$unqcount]</b>";
*/
			echo "</div><br />";
			
			rl_DailyStats($showStats);
		}
		else if ($showTop||$showRecent)
		{
			if ($showTop)
			{
				$out = "<h2>Showing top $showTop referring domains</h2>";
				$rlist = topRefererList ($showTop, "global", true, "", true);
			}
			else
			{
				$out = "<h2>Showing $showRecent most recent entries</h2>";
				$rlist = refererList ($showRecent, "global", true, "", true, true, true);
			}
			$i = 0;
			foreach($rlist as $aref)
			{
				if ($showAsTable)
				{
					$out .= '<tr class="'.(($i%2)?'ref-odd':'ref-even').'"';
					$out .= ">$aref</tr>\n";
				}
				else
					$out .= "<li>$aref</li>\n";
				$i++;
			}
			if ($showAsTable)
				echo "<table>$out</table>";
			else
				echo "<ul>$out</ul>";
		}
		else
		{
			$count = 0;
			$order = "DESC";
			$what = '*';
			if ($purgeEntries>0)
			{
				if ($purgeEntries==1) $purgeEntries=1; // 1 day...
				$maxDays = $purgeEntries-1; // seems like a good cutoff.
				$modWhere .= "WHERE TO_DAYS(NOW()) - TO_DAYS(visitTime) >= $maxDays AND TO_DAYS(NOW()) - TO_DAYS(visitTime) < 10000";
				$order = "ASC";
				$what = 'visitID';
			}
			else
			if ($flushBots)
			{
				$modWhere .= "WHERE (baseDomain='".BOT_MARKER."')";
				$order = "ASC";
				$what = 'visitID';
			}
			else
			if ($tagEntries)
			{
				$modWhere .= "WHERE (baseDomain !='".BOT_MARKER."') AND baseDomain NOT LIKE '%[%'";
			}
			
			$query = "SELECT count(visitID) as num FROM $referTable $modWhere";			
			$maxrowsresult = db_getrow($query, OBJECT, 0, "get CG-Referrer row count");
			$maxrows = $maxrowsresult->num;
			echo "STARTING RAW QUERY on $maxrows records...<br />";
			$perloop = 100;
			
			if ($clearDups)
			{
				$count = clearDupEntries($clearDups);
			}
			else
			for ($j=0; $j<$maxrows; $j+=$perloop)
			{
				echo "<span>$j...</span><br/>"; flush();
									
				$limit = "LIMIT $j,$perloop";
				if ($purgeEntries || $flushBots)
					$limit = "LIMIT $perloop";
				$query = "SELECT $what FROM $referTable $modWhere ORDER BY visitID $order $limit";
				$sqr_ref = db_getresults($query, ARRAY_A, "flushing bad referrals");
				if (empty($sqr_ref)) break;
				
				echo "Processing ".count($sqr_ref)." records...<br />";
				
				$i = $j;
				if ($purgeEntries || $flushBots)
				{
					$visitIDList = '';
					foreach($sqr_ref as $result_row)
					{
						if (!empty($visitIDList)) $visitIDList .= ',';
						$visitIDList .= $result_row['visitID'];
						$count++;
					}
					$result = db_runquery("DELETE FROM $referTable WHERE visitID IN (".$visitIDList.")", "CG-Referrer flush-purge");
				}
				else
				foreach($sqr_ref as $result_row)
				{
					$i++; // just to have a counter around...
					
					$visitUrl = $result_row['visitURL'];  // this could be empty, no referral, for unique IP tracking
					$fullUrl = $result_row['referingURL'];  // this could be empty, no referral, for unique IP tracking
					$domain = $result_row['baseDomain'];  // this could be empty, no referral, for unique IP tracking
					$userIP =  $result_row['userIP'];
					$userAgent =  $result_row['userAgent'];
					$num = $result_row['visitID'];
		
					$ignoreDomain = '';
					$emptyAgent = '';
					$ignoreAgent = '';
					$botAgent = isa_bot($userAgent);

					if ($tagEntries)
					{
						global $cgr_doBlacklistChecks; // just in case...
						$check = $cgr_doBlacklistChecks;
						$tagit = true;
						if ($check==false)
						{
							$check = true; // do all
							$tagit = false; // don't WRITE TO DB!
						}
						$result = checkReferer($cgr_doBlacklistChecks, $fullUrl, $domain, $userAgent, $visitUrl, $userIP);
						if (!empty($result) && $result[0]) //tag it!
						{
							echo "<span>Entry $num = $baseDomain, $result[2]...".($tagit?' TAGGED.':'')."</span> <br>";
							$baseDomain = $result[2].$domain;
							if ($tagit)
								$qresult = db_runquery("UPDATE $referTable SET baseDomain='$baseDomain' where visitID=$num", "tagReferer");
						}
						else
						if ($botAgent)
						{
							echo "(bot [$userAgent] needed tagging...) <br>";
							$result = db_runquery("UPDATE $referTable SET baseDomain='".BOT_MARKER."' where visitID=$num", "logReferer");
						}
						flush();
					}
					else
					if ($action='purge' || $flushBlacklist || $ignoreDomain || $ignoreIP || $emptyAgent || $ignoreAgent || $botAgent || $clearDups || $flushBots)
					{	
						if (!empty($domain)) // we don't worry about empty domains - they show up for a reason -- ie., unique IP tracking
							$ignoreDomain = findstr($domain, $ignoreReferSites);
						if (!$ignoreDomain)
						{
							$ignoreIP = findstr($userIP, $ignoreSpammerIPs);
							if ($ignoreIP)
							{
								$emptyAgent = empty($userAgent); // we punt empty agents.
								if (!$emptyAgent)
									$ignoreAgent = findstr($userAgent, $ignoreAgents);
							}
						}
						
						if ($botAgent)
						{
							if ($domain!=BOT_MARKER) // set it...
							{
								echo "(bot [$userAgent] needed tagging...) <br>";
								$result = db_runquery("UPDATE $referTable SET baseDomain='".BOT_MARKER."' where visitID=$num", "logReferer");
							}
						}
						else
						{
							echo "<span>";
							if ($action='purge' || $flushBlacklist==1) // don't flush, just show, if > 1...
							{
								if ($i==$j+1) // then print ONE LINE
									echo "...trying to delete #$num ";
							}
							else
							{
								echo "found #$num ";
								
								if ($clearDups)
									echo "[DUPLICATE] <br>";
								else
								if ($ignoreDomain)
									echo "[IGNORE DOMAIN] <br>";
								else
								if ($ignoreIP)
									echo "[IGNORE IP] <br>";
								else
								if ($emptyAgent)
									echo "[EMPTY AGENT] <br>";
								else
								if ($ignoreAgent)
									echo "[IGNORE AGENT] <br>";
								else
									echo "[UNKNOWN ENTRY] <br>";
							}
							
							echo "</span>";
							if ($action!='purge')
								echo "$visitTime [$userIP] $domain :: $fullUrl ($userAgent)...";
							flush();
							if ($action='purge' || $flushBlacklist==1) // don't flush, just show, if > 1...
							{
								$result = db_runquery("DELETE FROM $referTable WHERE visitID=$num", "CG-Referrer flush blacklist");
								if ($i==$j+1) // then print ONE LINE
									echo " done <br />";
							}
							else
								echo " done <br />";
							$count++;
						}
					}
				}	
			}
			
			echo "<span>Processed $count total records.</span><br />";
		}
		
		echo '</div>';
		echo '</body>';
		if (!strpos($REQUESTED, "wp-admin/admin.php"))
			echo '</html>';	
	}
	
?>