<?
/* CG-WhatTunes.php
	System to grab information from tracktunes.php and do lookups through CG-Amazon
	Copyright (c)2004 by David Chait, CHAITGEAR - www.chait.net, All Rights Reserved.
*/

$myPassword = ''; // set this if you want to lightly restrict access to add/set commands.

$showWhatTunes = false;

if (strpos($_SERVER['REQUEST_URI'], "cga-update.php"))
{
	$cguPathPrefix = dirname(__FILE__).'/';
	// locate the wp path...
	if (FALSE===strpos($cguPathPrefix, 'wp-content')) // plugin
		$cguRootPath = $cguPathPrefix.'../'; // cgplugins->wp base dir.
	else
		$cguRootPath = $cguPathPrefix.'../../../'; // cgplugins->plugins->wpcontent->wp base dir.
		
	include_once($cguRootPath.'wp-config.php');
//	@include_once($wtPathPrefix.'/my-setup.php');
	if (!isset($AmazonQueryMgr))
	{
		if (file_exists($cguPathPrefix."cga-config.php"))
			include_once($cguPathPrefix."cga-config.php");
	}
}

$findvars = array('doup');

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

// this functions walks through most amazon data, and tries to
// update as many things as it can that are out-of-date on disk.
function updateDatabase()
{
	if ($nuCache)
	{
		if (is_array($searchData) && $randomNum && $randomNum < count($searchData))
		{ // build random-order set.
			$checkItemCount = count($searchData);
			$maxCheckItems = $randomNum+3; // +3 gives it a little flexibility if bad files around...
			$rand_check = array_rand($searchData, $checkItemCount);
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
			if ($shouldRecache==0)
			{
				if ($currNumItems >= $maxCheckItems) continue; // skip this one
				if (!$noCache && !load_amazon_blob($tmpName))
					$shouldRecache = 2;
			}
			if ($shouldRecache>0)
				$searchItems[] = $checkIt;
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

if ($doup==1)
{
	updateDatabase();
}

?>