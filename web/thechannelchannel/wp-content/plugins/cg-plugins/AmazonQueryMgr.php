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

function reverse_strrchr($haystack, $needle)
{
   $pos = strrpos($haystack, $needle);
   if($pos === false) {
       return $haystack;
   }
   return substr($haystack, 0, $pos + 1);
}

// sort style string array.
$amaSort[0] = '';
$amaSort['default'] = '';
$amaSort['rank'] = '+salesrank';
$amaSort['title'] = '+titlerank';
$amaSort['price'] = '+pricerank';
// offer type string array
$amaOffer[0] = '';
$amaOffer['default'] = '';
$amaOffer['all'] = 'All';
$amaOffer['used'] = 'Used';
$amaOffer['collect'] = 'Collectible';
$amaOffer['refurb'] = 'Refurbished';

$AmazonQMax = 1000; // can't imagine we really want to be querying more than 1000 items at once!

//----------------------------------------------------------------------------
$amaMode['us'] = array();
$curMode = &$amaMode['us']; // for easier fill in.
$curMode['*'] = 				'Blended';		// searches top ten or so areas.
$curMode['apparel'] =			'Apparel';				// US ONLY
$curMode['baby'] =				'Baby';					// US ONLY
$curMode['beauty'] =			'Beauty';				// US ONLY
$curMode['books'] =				'Books';
$curMode['classical'] =			'Classical'; 	// Music blend
$curMode['digitalmusic'] =		'DigitalMusic';			// US ONLY
$curMode['dvd'] =				'DVD';			// Video blend
//$curMode['foreignbooks'] =		'ForeignBooks';			// not US|UK
$curMode['electronics'] =		'Electronics';			// not FR|CA
$curMode['gourmetfood'] =		'GourmetFood';			// US ONLY
$curMode['health'] =			'HealthPersonalCare';	// US|UK|DE only
$curMode['homegarden'] =		'HomeGarden';			// says UK|DE, wonder if its US|UK
$curMode['jewelry'] =			'Jewelry';				// US ONLY
$curMode['kitchen'] =			'Kitchen';				// not FR|CA
$curMode['magazines'] =			'Magazines';			// US|DE only
$curMode['misc'] =				'Miscellaneous';		// US ONLY
$curMode['music'] =				'Music';						// blend of classical+
$curMode['instruments'] =		'MusicalInstruments';	// US ONLY
$curMode['tracks'] =			'MusicTracks';			// not CA
$curMode['office'] =			'OfficeProducts';		// US ONLY
$curMode['outdoor'] =			'OutdoorLiving';		// US|UK|DE only
$curMode['petsupplies'] =		'PetSupplies';			// US only
$curMode['pc'] =				'PCHardware';			// US|DE only
$curMode['photo'] =				'Photo';				// US|DE only
$curMode['restaurants'] =		'Restaurants';			// US ONLY
$curMode['software'] =			'Software';
//$curMode['softwarevideogames']=	'SoftwareVideoGames';	// not US|JP
$curMode['sports'] =			'SportingGoods';		// US ONLY
$curMode['tools'] =				'Tools';				// US|DE only
$curMode['toys'] =				'Toys';					// US|UK|JP|DE only
$curMode['vhs'] =				'VHS';			// Video blend
$curMode['video'] =				'Video';				// not FR, blend of VHS+DVD
$curMode['videogames'] =		'VideoGames';
$curMode['wireless'] =			'Wireless';				// US ONLY
$curMode['wirelessaccessories']='WirelessAccessories';	// US ONLY

//----------------------------------------------------------------------------
$amaMode['uk'] = array();
$curMode = &$amaMode['uk']; // for easier fill in.
$curMode['*'] = 				'Blended';		// searches top ten or so areas.
$curMode['books'] =				'Books';
$curMode['classical'] =			'Classical'; 	// Music blend
$curMode['dvd'] =				'DVD';			// Video blend
$curMode['electronics'] =		'Electronics';			// not FR|CA
$curMode['health'] =			'HealthPersonalCare';	// US|UK|DE only
$curMode['homegarden'] =		'HomeGarden';			// says UK|DE, wonder if its US|UK
$curMode['kitchen'] =			'Kitchen';				// not FR|CA
$curMode['music'] =				'Music';						// blend of classical+
$curMode['tracks'] =			'MusicTracks';			// not CA
$curMode['outdoor'] =			'OutdoorLiving';		// US|UK|DE only
$curMode['software'] =			'Software';
$curMode['softwarevideogames']=	'SoftwareVideoGames';	// not US|JP
$curMode['toys'] =				'Toys';					// US|UK|JP|DE only
$curMode['vhs'] =				'VHS';			// Video blend
$curMode['video'] =				'Video';				// not FR, blend of VHS+DVD
$curMode['videogames'] =		'VideoGames';

//----------------------------------------------------------------------------
$amaMode['de'] = array();
$curMode = &$amaMode['de']; // for easier fill in.
$curMode['*'] = 				'Blended';		// searches top ten or so areas.
$curMode['books'] =				'Books';
$curMode['classical'] =			'Classical'; 	// Music blend
$curMode['dvd'] =				'DVD';			// Video blend
$curMode['foreignbooks'] =		'ForeignBooks';			// not US|UK
$curMode['electronics'] =		'Electronics';			// not FR|CA
$curMode['health'] =			'HealthPersonalCare';	// US|UK|DE only
$curMode['homegarden'] =		'HomeGarden';			// says UK|DE, wonder if its US|UK
$curMode['kitchen'] =			'Kitchen';				// not FR|CA
$curMode['magazines'] =			'Magazines';			// US|DE only
$curMode['music'] =				'Music';						// blend of classical+
$curMode['tracks'] =			'MusicTracks';			// not CA
$curMode['outdoor'] =			'OutdoorLiving';		// US|UK|DE only
$curMode['pc'] =				'PCHardware';			// US|DE only
$curMode['photo'] =				'Photo';				// US|DE only
$curMode['software'] =			'Software';
$curMode['softwarevideogames']=	'SoftwareVideoGames';	// not US|JP
$curMode['tools'] =				'Tools';				// US|DE only
$curMode['toys'] =				'Toys';					// US|UK|JP|DE only
$curMode['vhs'] =				'VHS';			// Video blend
$curMode['video'] =				'Video';				// not FR, blend of VHS+DVD
$curMode['videogames'] =		'VideoGames';

//----------------------------------------------------------------------------
$amaMode['jp'] = array();
$curMode = &$amaMode['jp']; // for easier fill in.
$curMode['*'] = 				'Blended';		// searches top ten or so areas.
$curMode['books'] =				'Books';
$curMode['classical'] =			'Classical'; 	// Music blend
$curMode['dvd'] =				'DVD';			// Video blend
$curMode['foreignbooks'] =		'ForeignBooks';			// not US|UK
$curMode['electronics'] =		'Electronics';			// not FR|CA
$curMode['kitchen'] =			'Kitchen';				// not FR|CA
$curMode['music'] =				'Music';						// blend of classical+
$curMode['tracks'] =			'MusicTracks';			// not CA
$curMode['software'] =			'Software';
$curMode['toys'] =				'Toys';					// US|UK|JP|DE only
$curMode['vhs'] =				'VHS';			// Video blend
$curMode['video'] =				'Video';				// not FR, blend of VHS+DVD
$curMode['videogames'] =		'VideoGames';

$amaMode['ca'] = array();
$curMode = &$amaMode['ca']; // for easier fill in.
$curMode['*'] = 				'Blended';		// searches top ten or so areas.
$curMode['books'] =				'Books';
$curMode['classical'] =			'Classical'; 	// Music blend
$curMode['dvd'] =				'DVD';			// Video blend
$curMode['foreignbooks'] =		'ForeignBooks';			// not US|UK
$curMode['music'] =				'Music';						// blend of classical+
$curMode['tracks'] =			'MusicTracks';			// not CA
$curMode['software'] =			'Software';
$curMode['softwarevideogames']=	'SoftwareVideoGames';	// not US|JP
$curMode['vhs'] =				'VHS';			// Video blend
$curMode['video'] =				'Video';				// not FR, blend of VHS+DVD
$curMode['videogames'] =		'VideoGames';

$amaMode['fr'] = array();
$curMode = &$amaMode['fr']; // for easier fill in.
$curMode['*'] = 				'Blended';		// searches top ten or so areas.
$curMode['books'] =				'Books';
$curMode['classical'] =			'Classical'; 	// Music blend
$curMode['dvd'] =				'DVD';			// Video blend
$curMode['foreignbooks'] =		'ForeignBooks';			// not US|UK
$curMode['music'] =				'Music';						// blend of classical+
$curMode['tracks'] =			'MusicTracks';			// not CA
$curMode['software'] =			'Software';
$curMode['softwarevideogames']=	'SoftwareVideoGames';	// not US|JP
$curMode['vhs'] =				'VHS';			// Video blend
$curMode['videogames'] =		'VideoGames';


//...
$amaMode[0] = &$amaMode['us']; //just in case...

// bring in the CG xml parser code for processing REST queries into PHP arrays.
$myAmaQMPath = dirname(__FILE__).'/';
require_once($myAmaQMPath."XMLParser.php");

//===========================================
// define the main query manager class
//===========================================
class AmazonQueryMgr
{
	var $AmazonLocale = 'us';
//	var $AmazonServer = 'http://xml.amazon.com/onca/xml3';
	var $AmazonServer = 'http://webservices.amazon.com/onca/xml?Service=AWSECommerceService';
	// here's a fake bad path.
//	var $AmazonServer = 'http://davebytes.homeip.net/boo';

	var	$QueryMax = 50; // good default.  let people override if they must.
	var $AmazonQType = 'Large';
	var $AmazonSort = 'rank';
	var $AWSSubID = '09GE3K6JDGSKCKXKEJG2'; // >>DO NOT ALTER.<<
	var $AmazonAssocID = 'chaitgear-20';
	var $CreatorAssocID = array(	'us'=>'chaitgear-20', // the default assoc ID is the CG USA ID.  >>DO NOT CHANGE.<<
									'uk'=>'chaitgear-21', // now have a uk ID...
									'ca'=>'chaitgear07-20',
									'de'=>'',
									'jp'=>'',
									'fr'=>'',
								);
	
	var $DEAD = 'false'; // set to true if we detect during session that Amazon is misbehaving... need to put in db somewhere for multiple-users.

	//===========================================
	function SetLocale($locale='')
	{
		if ($locale)
		{
			if ($locale=='us')
			{
				$this->AmazonLocale = $locale; // no-op
				$this->AmazonServer = 'http://webservices.amazon.com/onca/xml?Service=AWSECommerceService';
			}
			else
			if ($locale=='jp')
			{
				$this->AmazonLocale = $locale;
				$this->AmazonServer = 'http://webservices.amazon.co.jp/onca/xml?Service=AWSECommerceService'; // uses JP server
			}
			else
			if ($locale=='uk')
			{
				$this->AmazonLocale = $locale;
				$this->AmazonServer = 'http://webservices.amazon.co.uk/onca/xml?Service=AWSECommerceService';  // UK server
			}
			else
			if ($locale=='de')
			{
				$this->AmazonLocale = $locale;
				$this->AmazonServer = 'http://webservices.amazon.de/onca/xml?Service=AWSECommerceService';  // DE server
			}
			else
			if ($locale=='fr')
			{
				$this->AmazonLocale = $locale;
				$this->AmazonServer = 'http://webservices.amazon.fr/onca/xml?Service=AWSECommerceService';  // FR server
			}
			else
			if ($locale=='ca')
			{
				$this->AmazonLocale = $locale;
				$this->AmazonServer = 'http://webservices.amazon.ca/onca/xml?Service=AWSECommerceService';  // CA server
			}
			else
			if (function_exists("dbglog"))
				dbglog("<br />[$locale] = <b>IMPROPER AMAZON LOCALE. DEFAULTING TO U.S.</b><br />");
		}
		
		// might do initial creation of a given
		// XMLParser to tie to the given AQM obj.
	}
	
	function GetCreatorID()
	{
		$loc = $this->AmazonLocale;
		$id = $this->CreatorAssocID[$loc];
		if (empty($id))
			$id = $this->AmazonAssocID;
		return($id);
	}

	function GetCatalogArray()
	{
		global $amaMode;
		return $amaMode[$this->AmazonLocale];
	}

	//===========================================
	// ability to set query params, as we may switch
	// between IDs, lite & heavy, on the fly during
	// ONE site page's processing...
	function SetQueryParams($assocID='', $type='', $max = 50) // default to 50, people can increase if needed.
	{
		global $AmazonQMax;
		if ($assocID) $this->AmazonAssocID = $assocID;
		if ($type) $this->AmazonQType = $type;
		if ($max==0) $max = 50; // 0 means use default!
		if ($max<0 || $max>$AmazonQMax) $max = $AmazonQMax;
		$this->QueryMax = $max;
	}
	

	//===========================================
	// setup XML/REST query url, and make request
	// of the Amazon WS servers via our XMLParser
	// class.
	function RESTQuery($searchType, $searchIndex, $searchTerms, $searchMode = '')
	{
		global $XATTR,$XVALUE,$XTAG;
		global $amaSort, $amaOffer, $amaMode;
		global $AmazonDebug;
		
		$parser = null;
		
		$catalogs = $this->GetCatalogArray();
		$searchIndex = $catalogs[$searchIndex];
		
//		if ($searchType!='Asin')
//			die ("Query: $searchType, ".serialize($searchTerms));

		// start with the base REST URL for AWS4, with our sub ID.  Assoc ID is optional, but makes rewrites easier.
		$urlhead = $this->AmazonServer;
		$urlhead .= '&SubscriptionId='.$this->AWSSubID;
		$urlhead .= '&AssociateTag='.$this->GetCreatorID();
		$urlmid = '&ResponseGroup='.$this->AmazonQType;

		// defaults:
		$detailBranchName = 'Items';
		$detailRoot = 'ItemLookupResponse';
		$detail = 'Item';
		
		if ($searchType=='Wishlist')
		{
			$detailRoot = 'ListLookupResponse';
			$detailBranchName = 'Lists';
			$detail = 'ListItem';
			
			$urltail = '&Operation=ListLookup';
			$urltail .= '&ListType=WishList';
			
			// overriding default start for urlmid:
			$urlmid = '&ResponseGroup=ListFull,Small,ItemAttributes,OfferSummary,SalesRank,Images';
			$urlmid .= '&ListId='.$searchTerms;
//			$urlmid .= '&ProductGroup='.$something;
			$urlmid .= '&Sort='.'LastUpdated'; //DateAdded,LastUpdated,Price
		}
		else
		if ($searchType=='Asin')
		{
			$urltail = '&Operation=ItemLookup';
			
			$urlmid .= '&ItemId='.$searchTerms;
		}
		else
		if ($searchType=='Similar')
		{
			$detailRoot = 'SimilarityLookupResponse';

			$urltail = '&Operation=SimilarityLookup';
			
			$urlmid .= '&ItemId='.$searchTerms;
		}
		else
		{
			$detailRoot = 'ItemSearchResponse';
			
			$urltail = '&Operation=ItemSearch';
			$urltail .= '&SearchIndex='.$searchIndex; // what group to search...
			
			//$urlmid .= '&'.$searchMode.'='.$searchTerms;
			// until I allow other types, Keyword is the default...
			if (is_array($searchTerms))
			{
				foreach($searchTerms as $key=>$word)
					$urlmid .= '&'.$key.'='.htmlentities(urlencode($word));
	    	}
	    	else
	    		$urlmid .= '&'.$searchType.'='.$searchTerms;
	    		
			if ($searchIndex!='Blended')
				$urlmid .= '&Sort=salesrank'; // default...
		}
		
/*
		if ($searchMode) // category...
			$urltail .= '&mode='.($amaMode[$this->AmazonLocale][$searchMode]);
		// add in the general terms
		if ($searchType=='SellerSearch') // hardcode for now
			$urltail .= '&offerstatus=open';
		else
		{
			$urltail .= '&sort='.$amaSort[$this->AmazonSort];
		//$urltail .= '&offer='.$amaOffer['default'];
		//if ($this->AmazonLocale != 'us')
			$urltail .= '&locale='.$this->AmazonLocale;
		}
*/
		
//		$url .= '&type=lite'; // force lite temporarily...
				
		$hLen = strlen($urlhead);
		$mLen = strlen($urlmid);
		$tLen = strlen($urltail);
		// we assume if the URL is great than say 1000 characters that we should trim it.
		if ($hLen+$mLen+$tLen > 1000)
		{
			$targetLen = 1010-($hLen+$tLen); // how long can $mLen be safely?
			while ($mLen > $targetLen)
			{
				$pos = strrpos($urlmid, ','); // comma sep'd?
				if ($pos === false)
					$pos = strrpos($urlmid, '+'); // plus sep'd?
				if ($pos === false)
					$pos = $targetLen-1; // SLAM IT?!?!?!?!
				$mLen = $pos;
			}
			$urlmid = substr($urlmid, 0, $mLen);
		}
		$url = $urlhead.$urlmid.$urltail;
//		if ($AmazonDebug>1) dbl_log("url = $url");

		if ($AmazonDebug>1) dbglog("AQM: query = ".$url);
		
//		die($url);

		$foundData = array();
		$pagenum = 1; // always start on page 1
		// we start off the loop knowing that the result array has nothing in it...
		while (count($foundData) < $this->QueryMax)
		{
			$xml = $url;
			if ($pagenum>1) // since only if we're querying past page 1 do we need this...
			{
				if ($detail=='ListItem')
					$xml .= '&ProductPage='.$pagenum;
				else
					$xml .= '&ItemPage='.$pagenum;
			}
			
			$parser = new XMLParser();
			if ($AmazonDebug>1) dbglog("XMLPARSER pre-setSource");
			$wasset = $parser->setSource($xml, 'url');
			if ($AmazonDebug>1) dbglog("XMLPARSER post-setSource");
			if ($parser->setSourceFailed) return($parser->setSourceFailed);
			// if (!$wasset) return null; // failed to open
			
			$resultSet = $parser->getTree($detailRoot, $detailBranchName);
			//if ($AmazonDebug>1)	dbglog("AQM: REST Result: ".serialize($Result));
			//die("Result set was: ".serialize($resultSet));

			if ($resultSet == null)
				break; // we're done.  didn't find the tree/nodes we asked for.	
						
			$resultCount = count($resultSet);
			$totalPages = $resultSet['TotalPages'];
			$totalResults = $resultSet['TotalResults'];
			// resultCount should be 2, since the response info is in it...
			if ($resultSet['Request']['IsValid']==false
//			||	isset($resultSet['Request']['Errors']
				)
			{
				if (isset($resultSet['Request']['Errors']['Message']))
					$amaerror = $resultSet['Request']['Errors']['Message'];
				else
				if (isset($resultSet['Request']['Errors']['Error']['Message']))
					$amaerror = $resultSet['Request']['Errors']['Error']['Message'];
				else
				if (isset($resultSet['Errors']['Message']))
					$amaerror = $resultSet['Errors']['Message'];
					
				if ($amaerror)
					$dbgit = "Trying to look-up product, the following error occurred:<br/><i>$amaerror</i>";
				else
				if ($resultSet['Request']['IsValid']==false)
				{
					ob_start();
					print_r($resultSet);
					$dbgit=ob_get_contents();
					ob_end_clean();
					$dbgit = "Amazon had bad request/response we don't know how to handle:<br/>".$dbgit;
					dbglog(str_replace('[','<br/>[', $dbgit));
				}

				// return back so we cleanly exit up..
				return($dbgit);
//				die("<br/>... fini.");
			}
			else // seems like a possibly okay result set...
			{
				// did we get an error anyway?
				if (isset($resultSet['Request']['Errors']))
				{
					ob_start();
					print_r($resultSet['Request']);
					$dbgit=ob_get_contents();
					ob_end_clean();
					$dbgit = "Amazon query succeeded, but noted an error condition:<br/>".$dbgit;
					dbglog(str_replace('[','<br/>[', $dbgit));
				}
				//dbglog(serialize($resultSet['Request']));
				//$resultSet = &$resultSet['Item'];
			}
		  

			{ // otherwise, result array with ordinal keys.
				if ($detail=='ListItem')
				{
					$resultSet = $resultSet['List'];
				}				
				
				if (!isset($resultSet[$detail][0]))
					$foundData[] = $resultSet[$detail];
				else				
				foreach ($resultSet[$detail] as $anItem)
				{
					if (count($foundData) >= $this->QueryMax)
						break;
					$foundData[] = $anItem;
				}
			}
			
			// reset result count...
			$resultCount = count($foundData);
			if ($AmazonDebug>1)
			{
				dbglog("AQM: got $resultCount results back, page=$pagenum."); //, url=".str_replace('&',' ',$xml));
				if ($resultCount > $this->QueryMax) // oops?
					dbglog("AQM: full results too big (asked for $this->QueryMax, got $resultCount)"); //: ".serialize($resultSet));
			}
		  
			// if we get less than ten items, we can assume no more 'pages' to query.
			if ($resultCount < 10)
				break; // we're done.
						
			// else, if we got here, increment page counter, and loop to query again for more results.			  
			$pagenum++;
			if ($detail=='ListItem')
			{
				if ($resultSet['TotalPages']<$pagenum) // we're done...
					break;
				/* other fields:
				[ListURL] => http://www.amazon.com/gp/registry/Z8UC4ZGXPZU6
				[ListType] => WishList
				[TotalItems] => 17
				[TotalPages] => 2
				[DateCreated] => 2001-07-26
				[CustomerName] => My Name
				*/
			}
		}

		// DONE WITH THE QUERY.
		//if ($AmazonDebug>1) dbglog("AQM: XML = $xml");				
		
		// HANDLE ANY TWEAKING OF THE FOUND DATA
		if ($searchType=='Wishlist')
		{
			$wishlistID = $searchTerms; // should only be one...
			
			// first, extract the ListItems Items
			$wishlistItem = '';

			$newData = array();
			foreach($foundData as $key => $item) // ListItems...
			{
				// $resultSet['ListName'] might be a ListMania name for listmania list...
				// !?!?!? what about wedding lists? !!!!!!!
				
				//dbglog("iterate $key => ".$item['Item']['ASIN']);
				$asin = $item['Item']['ASIN'];
				$wishlistItem = $item['ListItemId'];
				/* other fields:
				[ListItemId] => I3R8YQTQVBXIMA
				[DateAdded] => 2004-12-06
				[QuantityDesired] => 1
				[QuantityReceived] => 0
				*/
				$blob = &$item['Item']; // pull Item up from ListItem enclosure
				$blob['_WishDate'] = $item['DateAdded'];
				$blob['_WishGot'] = $item['QuantityReceived'];
				$blob['_WishWant'] = $item['QuantityDesired'];
				// how the frack do I encode the wishlist referencing into the link???
				//$blob['DetailPageURL'] = str_replace('chaitgear-20', 'chaitgear-20'.urlencode(urlencode('&coliid='.$wishlistItem.'&colid='.$wishlistID)), $blob['DetailPageURL']);
				$newData[] = &$blob;
			}
			
			// okay, we're done, return the new data.
//			$foundData = ''; // houseclean early.
			$foundData = null;
			$foundData = &$newData;
		}
		
		// 'promote' the URL attributes up a level for each returned item
		if (empty($foundData) || count($foundData)==0)
			$foundData = ''; // send empty back, NOT null.
		else
		foreach($foundData as $key => $item)
		{
			$blob = &$foundData[$key];
						
			// promote the url AND stick in the ref=nosim thing at the same time...
			//str_replace($this->AmazonAssocID, 'ref=nosim/'.$this->AmazonAssocID, $blob[DetailPageURL']);
			
			// fake up the field names we expect... we'll rewrite this all LATER!
			$blob['Asin'] = $blob['ASIN'];
			$blob['ProductName'] = $blob['ItemAttributes']['Title'];
			$blob['Catalog'] = $blob['ItemAttributes']['ProductGroup'];
			$blob['AverageRating'] = $blob['CustomerReviews']['AverageRating'];
			$blob['ImageUrlSmall'] = $blob['SmallImage']['URL'];
			$blob['ImageUrlMedium'] = $blob['MediumImage']['URL'];
			$blob['ImageUrlLarge'] = $blob['LargeImage']['URL'];
			
			// no REF for these -- we modify!!!
			$blob['Url'] = $blob['DetailPageURL'];
			$blob['ListPrice'] = $blob['ItemAttributes']['ListPrice']['FormattedPrice'];
			$blob['OurPrice'] = $blob['OfferSummary']['LowestNewPrice'];
			if (is_array($blob['OurPrice']))
				$blob['OurPrice'] = $blob['OurPrice']['FormattedPrice'];
//			$blob['ListPrice'] = $blob['ItemAttributes']['ListPrice']['Amount'] / 100.0;
//			$blob['OurPrice'] = $blob['OfferSummary']['LowestNewPrice']['Amount'] / 100.0;
			
			// add in our custom CG _Creator field...
			$creator = get_amazon_blob_creator($blob);
			if ($creator)
				$blob['_Creator'] = $creator;
			
			// special case for US until I understand internation price punctuations...
			if ($this->AmazonLocale=='us') // remove the fricking commas!
			{
				$blob['OurPrice'] = str_replace(',','',$blob['OurPrice']);
				$blob['ListPrice'] = str_replace(',','',$blob['ListPrice']);
				$blob['UsedPrice'] = str_replace(',','',$blob['UsedPrice']);
				$blob['ThirdPartyNewPrice'] = str_replace(',','',$blob['ThirdPartyNewPrice']);
			}
			
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
			if ($Price && $MSRP && ($Price!=$MSRP) && $MSRP!='n/a')
			{
				$pctoff = 0;
				// testing for second, then first, character to be a number (first might be $ or something...)
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
	
		return $foundData;
	}

	//===========================================
	
	function RunQuery($searchType, $searchItems, $searchCat='')
	{
		global $AmazonDebug;
		
		if ($AmazonDebug>0) dbglog("AQM: Amazon REST Query ($searchType, $this->QueryMax)");
		
		if ($searchType=='Asin')
		{
			if (is_array($searchItems))
				$totalCount = count($searchItems);
			else
				$totalCount = 1;
			//echo serialize($ASIN)."\n<br>";
			//echo $Count."\n<br>";
						
			// currently always 10 at a time.
			//$pageSize = 30;
			//if ($this->AmazonQType!='lite')
				$pageSize = 10;
	    
			if ($totalCount>$pageSize) // then need to loop
			{
				$loopi = floor(($totalCount+9)/$pageSize);
				$tmpRet = array();
				for ($i=0; $i<$loopi; $i++)
				{
					$c = $pageSize;
					if ($i >= $loopi-1)
						$c = $totalCount % $pageSize;
					$tmpAsins = '';
					$koffset = $pageSize*$i;
					if ($AmazonDebug>1) dbglog("multiple page request. LOOP = $loopi, request num=$i, size=$c");
					for ($k=0; $k<$c; $k++)
					{
						if ($k>0) $tmpAsins .= ',';
						$tmpAsins .= htmlentities($searchItems[$k+$koffset]);
					}
					// we need to override the Max result count...
					$this->QueryMax = $c;
					$Ret = $this->RESTQuery($searchType, '*', $tmpAsins);
					if (empty($Ret)) break;
						foreach($Ret as $key=>$item)
							$tmpRet[] = $item; // extra copy sucks, but oh well.
				}      
				$results = &$tmpRet;
		    }
		    else // can do in one shot
		    {
			    if (is_array($searchItems))
			      $searchItems = implode(',', $searchItems);
		    	// we need to override the Max result count...
		    	$this->QueryMax = $totalCount;
			    $results = $this->RESTQuery($searchType, '*', $searchItems);
		    }
		    return $results;
		}
		else
		if ($searchType=='Similar')
		{
		    if (is_array($searchItems))
		    	$searchItems = $searchItems[0]; // grab first entry.
			if ($AmazonDebug>0) dbglog("AQM: SIMILARITY QUERY ($searchItems)");
		    return $this->RESTQuery($searchType, '*', htmlentities($searchItems), htmlentities($searchCat));
	    //if ($AmazonDebug>0) dbglog("CGA: Similar search requested $searchMax, found ".count($QueryResults).".");
		}
		else
		if ($searchType=='Upc')
		{
		    // all AWS documentation says only single UPC per query unlike ASIN query.
		    if (is_array($searchItems))
		    	$searchItems = $searchItems[0]; // grab first entry.
		  	// we need to override the Max result count...
		  	$this->QueryMax = 1;
		    return $this->RESTQuery($searchType, 'books', htmlentities($searchItems), htmlentities($searchCat));
		}
		else
		if ($searchType=='Keywords')
		{
		    if (is_array($searchItems) && isset($searchItems[0]))
	    		$searchItems = htmlentities(urlencode($searchItems[0])); // grab first entry only.
			if ($AmazonDebug>0) dbglog("AQM: $searchType Search = ".urldecode(serialize($searchItems)));
	  		return $this->RESTQuery($searchType, htmlentities($searchCat), $searchItems);
		}
		else
		if ($searchType=='Author'
		||	$searchType=='Actor'
		||	$searchType=='Artist'
		||	$searchType=='Title' // TBD
		||	$searchType=='Power' // TBD
		||	$searchType=='Brand' // TBD
		||	$searchType=='BrowseNode' // TBD
		||	$searchType=='Manufacturer' // TBD
			)
		{
			// I believe these are ALL single-term searches
	    	if (is_array($searchItems))
	    		$searchItems = $searchItems[0]; // grab first entry only.
	    	$searchItems = urlencode($searchItems);
			if ($AmazonDebug>0) dbglog("AQM: $searchType Search = ".urldecode($searchItems));
	  		return $this->RESTQuery($searchType, htmlentities($searchCat), htmlentities($searchItems));
		}
		else
		if ($searchType=='Wishlist')
		{
	    	if (is_array($searchItems))
	    		$searchItems = $searchItems[0]; // grab first entry only.
			if ($AmazonDebug>0) dbglog("AQM: $searchType Search = ".urldecode($searchItems));
	  		return $this->RESTQuery($searchType, '*', htmlentities($searchItems), htmlentities($searchCat));
		}
		else
		if ($searchType=='Seller')
		{
	    	if (is_array($searchItems))
	    		$searchItems = $searchItems[0]; // grab first entry only.
			if ($AmazonDebug>0) dbglog("AQM: $searchType Search = ".urldecode($searchItems));
	  		return $this->RESTQuery($searchType, '*', htmlentities($searchItems), htmlentities($searchCat),
	  													'SellerSearch', 'SellerSearchDetails'); //, 'ListingProductInfo');
		}

		echo "BAD searchType SPECIFIED: $searchType.  UNKNOWN.<br />";		
		return null;
	}
	
	// end of class defn.
}

$AmazonQueryMgr = new AmazonQueryMgr();

?>
