<?php

$REQUESTED = $_SERVER['REQUEST_URI'];
if ($truncoff = strpos($REQUESTED, '&'))
	$REQUESTED = substr($REQUESTED, 0, $truncoff);
$this_file = $REQUESTED; // this should hopefully work for 1.5 plugin system...
$admPath = dirname(__FILE__).'/';
require_once($admPath.'cga-config.php');
	
//$showAmaErrors = true;
//$AmazonDebug = 3;
if (!isset($dupsBumpToTop)) $dupsBumpToTop = true;

/* <CGAmazon Admin> */

//==================================================
//==================================================
function category_dropdown($selectedCat = '', $fieldname = 'item_catkey')
{
	global $amaCats;
	
	lookupAmaCats();
	
	echo "<select name='$fieldname' size='1'>\n";
	
	echo "<option value='0'";
		if (empty($selectedCat))
			echo " selected";
	echo ">0: None</option>\n";
		
	$i = 0;
	if (!empty($amaCats))
	foreach ($amaCats as $key => $acatname)
	{
		$catout = $acatname;
		if (empty($acatname)) continue;
		$i++; $j=$i;		
		echo "<option value='$key'";
		if ($acatname == $selectedCat)
			echo " selected";
		echo ">$j: $catout</option>\n";
	}
	
	echo "</select>\n";	
}


function catalog_dropdown($fieldname = 'find_cat')
{
	$catalogList = getAmazonCatList();
	
	echo "<select name='$fieldname' size='1'>\n";		
			
	$i = 0;
	if (!empty($catalogList))
	foreach ($catalogList as $catalog => $localname)
		{
			if (empty($catalog)) continue;
			$i++; $j=$i;
			echo "<option value='$catalog'";
			if ($i == 1)
				echo " selected";
			echo ">$catalog</option>\n";
		}
		echo "</select>\n";
}


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

$findvars = array('action', 'standalone', 'item_asin', 'item_note', 'item_catkey', 'item_catname',
									'find', 'find_what', 'find_cat', 'find_max', 'find_notexist',
									'page', 'sort', 'last_msg', 'create', 'resultname', 'redirect');

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


$standalone = 0;
if ($action=='create' || $action=='additem' || $action=='remove' || $action=='refresh' || $action=='time' || $action=='edited' || $action=='flushtimes') $standalone = 1;

// we assume the PLUGIN caused us to load, so we don't re-include cga-config
// try the WP1.2+ plugins path first.
$cgaaPathBase = dirname(__FILE__).'/';
/*
if (file_exists($cgaaPathBase.'../wp-content/plugins/cg-plugins/cga-config.php')) // use it
	require_once($cgaaPathBase.'../wp-content/plugins/cg-plugins/cga-config.php');
else // hope there's one at the top level...
	require_once($cgaaPathBase.'../cga-config.php');
*/
	
if ($page<1) $page=1; // reset page starting at 1, AFTER cga-config.

// some debug dump stuff...
/*
if ($AmazonDebug>2)
{
	ob_start();
	echo "HTTP_POST: ";
	print_r($_POST);	
	echo "<br>HTTP_GET: ";
	print_r($_GET);
	dbglog(ob_get_contents());
	ob_end_clean();
}
*/

//====================================
$btncount = 0;
function adminButton($sBtnText, $args, $onClick='') //, $pbef='', $paft='', $pargs=null, $pclass='', $pother='', $ptitle='')
{
	global $sort, $page; // things to try to maintain.
	global $this_file;
	global $btncount;
	$btncount++;
	$outlink ='';
		
	$outlink .= '<form name="adact-'.$btncount.'" action="'.$this_file.'" method="post">';
	foreach($args as $key => $value)
		$outlink .= '<input type="hidden" name="'.$key.'" value="'.$value.'" />';
	$outlink .= '<input type="submit" name="submit" value="'.$sBtnText.'" class="search" ';
	if ($onClick)
		$outlink .= 'onclick="'.$onClick.'" ';
	$outlink .= '/>';
	$outlink .= '</form>';
	return($outlink);
}

if ($create)
{
	$action='';
	createCGATable();
}


//--------------------------------
switch($action)
{
	case 'create':
	{
		createCGATable();	
		?>
		<div class="wrap">
			<p>Table created.</p>
			<form name="createdone" action="<?php echo $REQUESTED; ?>" method="post">
				<input type="hidden" name="action" value="cancel" />
				<p><input type="submit" name="submit" value="Return" class="search" /></p>
			</form>
		</div>
		<?php
		//header("Location: $REQUESTED&resultname=TABLE_CREATED");
	}

	case 'find':
	{
		?>
		<div class="wrap">
			<form name="cancelfind" action="<?php echo $REQUESTED; ?>" method="post">
				<input type="hidden" name="action" value="cancel" />
				<p><input type="submit" name="submit" value="Cancel Search" class="search" /></p>
			</form>
		</div>
			
		<div class="wrap">
		
		<?php
			// do the find.
			$amaMaxFindItems = 10;
			if ($find_max)
				$amaMaxFindItems = $find_max;			
			if ($amaMaxFindItems > 50)
				$amaMaxFindItems = 50; // 30 should be more than enough!
			$find_max = $amaMaxFindItems; // so that we know the orig max...
			if ($find_notexist) $amaMaxFindItems *= 2; // double for the moment...
						
			$results = show_keyword_items(urldecode($find_what), $find_cat, 'NOCACHE', '', $amaMaxFindItems, 0, 'Small', false, true); // get the asins back.
			if (!is_array($results)) // oops
			{
				if ($AmaQueryError)
					echo $AmaQueryError;
				else
					echo $results;
				break;
			}
			else
			if (empty($results))
			{
				echo "No matches on '$find_what' in [$find_cat].";
				break;
			}			
		?>
			<form name="additemmulti" action="<?php echo $REQUESTED; ?>" method="post">
			<p><input type="submit" name="submit" value="Add Checked Items" class="search" /></p>
			<p>Pick Category:
			<?php category_dropdown(''); ?> &nbsp;&nbsp;<b>OR</b>&nbsp; Enter New Category: <input type="text" name="item_catname" value="" /> &nbsp;&nbsp;<i>(optional - can leave blank/None)</i>
			</p>
			<?php echo "<h2>Matching items for '$find_what' in [$find_cat]".($find_notexist?' (existing items hidden)':'')."</h2>"; ?>
			<input type="hidden" name="action" value="additem" />
			<table width="100%" cellpadding="3" cellspacing="3">
				<tr>
					<th scope='col'>Add</th>
					<th scope='col'>Pix</th>
					<th scope='col'>Name</th>
					<th scope='col'>Catalog</th>
					<th scope='col'>Asin</th>
				</tr>
				<?php
					// can't we pre-cache the blobs in memory??
					$result = query_amazon($results, 'NOCACHE', false);
					// now, we need query results one by one...
					$i = 0;
					$usedAsins = array();
					$iout = '';
					foreach ($results as $index=>$asin)
					{
						// first, eliminate duplicates we already processed!  just in case -- amazon can return dups?
						if (in_array($asin, $usedAsins)) continue;
						// then check our db for this item.
						$ouritem = db_getresults("SELECT * FROM $tablecgamazon WHERE ASIN='$asin'", OBJECT, "admin - CGA");
						if ($find_notexist && !empty($ouritem)) continue; //skip if already exists...
//					$result = query_amazon($asin, 'NOCACHE', false);
						$blob = get_amazon_asin_blob($asin);
						if (empty($blob)) continue;
						
						$usedAsins[] = $asin;
						
						$URL         = &$blob['Url'];
						$ProductName = &$blob['ProductName'];
						$Manuf		   = &$blob['_Creator']; // our hacked value.
						$Price       = &$blob['OurPrice'];
						$Image			 = &$blob["ImageUrlSmall"];
						$Cat      	 = &$blob['Catalog'];
						
						$linkb = "<a href='$siteurl/cgaindex.php?p=ASIN_$asin' title='See more on Amazon'>";
						$linke = '</a>';
						
						$i++;
						$bgcolor = ('#eee' == $bgcolor) ? 'none' : '#eee';
						$iout .= "<tr style='background-color: $bgcolor'>\n";
							$iout .= "<td align='center' width='5%'>";
							if (empty($ouritem))
								$iout .= "<input type='checkbox' name='item_asin[]' value='$asin' />";
							else
								$iout .= "&nbsp;-&nbsp";
							$iout .= "</td>\n";
							$iout .= "<td width='10%'>$linkb<img src='$Image' />$linke</td>\n";
							$iout .= "<td width='50%'>$linkb$ProductName ($Manuf)$linke</td>\n";
							$iout .= "<td>$Cat</td>\n";
							$iout .= "<td>$asin</td>\n";					
						$iout .= "</tr>\n";
						
						if ($i>=$find_max) break; // found enough.
					}
					
					if ($amazonEncoding && $amazonEncoding!='UTF-8')
						$iout = uni_decode($iout, $amazonEncoding);
					
					echo $iout;
				?>
				</table>
			</div>
		<?php

		break;
	}
	
//############################################################
//############################################################
	case 'flushtimes':
	{
		$items = db_getresults("SELECT ID FROM $tablecgamazon ORDER BY ID", OBJECT, "admin - flushtimes");
		$count = count($items);
		foreach($items as $prod)
		{
			// this works for <3600 products... good enough for now.
			$secs = intval($prod->ID % 60);
			$sectime = ($secs<10) ? "0".$secs : "".$secs;
			$mins = intval($prod->ID / 60);
			$mintime = ($mins<10) ? "0".$mins : "".$mins;
			$flushtime = "2004010203$mintime$sectime";
			db_runquery("UPDATE $tablecgamazon SET amTime='$flushtime' WHERE ID=$prod->ID", "admin - cga: time flushed");
			//			echo "ID=$prod->ID: $flushtime<br>";
		}

		?>
		<div class="wrap">
			<p>Flush completed.</p>
			<form name="flushdone" action="<?php echo $REQUESTED; ?>" method="post">
				<input type="hidden" name="action" value="cancel" />
				<p><input type="submit" name="submit" value="Return" class="search" /></p>
			</form>
		</div>
		<?php
		//header("Location: $REQUESTED&resultname=FLUSHEDTIMES");
	
		break;
	}
	
//############################################################
//############################################################
	case 'additem':
	{
		if ($user_level < 3)
			die ('Cheatin&#8217; uh?');

		if (!empty($item_catname))
			$catname = $item_catname;
		else
		{
			lookupAmaCats();
			if (empty($item_catkey))
				$catname="";
			else
				$catname = $amaCats[$item_catkey];
		}
		
		if (!is_array($item_asin))
			$item_asin = array($item_asin);

		// strip spaces, to fix copy-and-paste-from-amazon issues.
		$item_asin = str_replace(' ', '', $item_asin);
	
		$goterr = query_amazon($item_asin, '', false); // do the query regardless.. allows us to punt on errors.
		if ($goterr)
			$resultname = 'ERROR_QUERYING_AMAZON';
		else
		foreach($item_asin as $asin)
		{		
			$resultname = '';
			$item = db_getresults("SELECT ASIN FROM $tablecgamazon WHERE ASIN='$asin'", OBJECT, "admin - add cg item");
			if (empty($item))
			{ // wasn't already in database...
				$blob = get_amazon_asin_blob($asin);
				if (!empty($blob))
				{
					//			$Asin        = $blob['Asin']; // in case $productKey isn't Asin...
					$URL         = &$blob['Url'];
					$ProductName = safeAddSlashes($blob['ProductName']);
					$Manuf		   = safeAddSlashes($blob['_Creator']); // our hacked value.
					$Price       = &$blob['OurPrice'];
					$Image			 = &$blob["ImageUrlSmall"];
					$Cat      	 = safeAddSlashes($blob['Catalog']);
					
					db_runquery("
								INSERT INTO $tablecgamazon
									(ID, ASIN, amName, amCreator, amUrl, amImageUrlSmall, amCategory, wpCategory, metaNote)
								VALUES
									('0', '$asin', '$ProductName', '$Manuf', '$URL', '$Image', '$Cat', '$catname', '$item_note')
						", OBJECT, "admin - addcat");
						
					$resultname = 'ADDED';
				}		
				else
				{
					$resultname = 'QUERYERROR';
					//			require_once("../my-debuginfo.php");
					//			die("didn't get blob, $gotsum, $blob, $item_asin");
					//			db_runquery("UPDATE $tablecgamazon SET metaNote='$item_note', amUrl='Not Yet Found', WHERE ASIN='$item_asin'", "admin - cga: addnoquery");
				}
			}
			else
			{
				if ($dupsBumpToTop)
				{
					// for dups, update the timestamp to bring to top.
					db_runquery("UPDATE $tablecgamazon SET amTime=null WHERE ASIN='$asin'", "admin - cga: time updated");
				}
				$resultname = 'DUPLICATE';
			}
		}
		
		?>
		<div class="wrap">
			<p>Done.</p>
			<form name="adddone" action="<?php echo $REQUESTED; ?>" method="post">
				<input type="hidden" name="action" value="cancel" />
				<p><input type="submit" name="submit" value="Return" class="search" /></p>
			</form>
		</div>
		<?php
		/*
		if ($redirect)
		{
				//			if (strpos('?', $redirect) || strpos('&#63;', $redirect))
				header("Location: $redirect&resultname=$resultname");
				//			else
				//				header("Location: $redirect?resultname=$resultname");
		}
		else
		{
			header("Location: $REQUESTED&resultname=$resultname");
		}
		*/
		break;
	}

//############################################################
//############################################################
	case 'remove':
	{
		db_runquery("DELETE FROM $tablecgamazon WHERE ASIN='$item_asin'", OBJECT, "admin - cga: delete");
		?>
		<div class="wrap">
			<p>Deleted.</p>
			<form name="createdone" action="<?php echo $REQUESTED; ?>" method="post">
				<input type="hidden" name="action" value="cancel" />
				<p><input type="submit" name="submit" value="Return" class="search" /></p>
			</form>
		</div>
		<?php
	
		//header("Location: $REQUESTED&resultname=DELETED_$item_asin");
	
		break;
	}
	
//############################################################
//############################################################
	case 'edit':
	{
		$item = db_getrow("SELECT * FROM $tablecgamazon WHERE ASIN='$item_asin'", OBJECT, 0, "admin - edit cg item");
		$encItemName = $item->amName;
		if ($amazonEncoding && $amazonEncoding!='UTF-8')
			$encItemName = uni_decode($encItemName, $amazonEncoding);
		?>	
		<div class="wrap">
			<form name="cancelfind" action="<?php echo $REQUESTED; ?>" method="post">
				<input type="hidden" name="action" value="cancel" />
				<p><input type="submit" name="submit" value="Cancel Edit" class="search" /></p>
			</form>
		</div>
		<div class="wrap">
			<h2>Edit Product</h2>
			<form name="edititem" action="<?php echo $REQUESTED; ?>" method="post">
				<input type="hidden" name="action" value="edited" />
				<input type="hidden" name="item_asin" value="<?php echo $item_asin; ?>" />
				
				<p>Item <?php echo '['.$item_asin.']: <strong>'.$encItemName.'</strong>'; ?></p>
		
				<p>Pick Category:
				<?php category_dropdown($item->wpCategory); ?> &nbsp;&nbsp;<b>OR</b>&nbsp; Enter New Category: <input type="text" name="item_catname" value="" /> &nbsp;&nbsp;<i>(optional - can leave blank/None)</i>
				</p>
									
				<p>Meta Notation: (added to html output):<br />
				<textarea name="item_note" rows="3" cols="50" style="width: 97%;"><?php echo htmlentities($item->metaNote); ?></textarea></p>
				
				<p><input type="submit" name="submit" value="Submit Changes" class="search" /></p>
			</form>
		</div>
		
		<?php
		break;
	}

//############################################################
//############################################################
	case 'refresh':
	{		
		$gotsum = query_amazon($item_asin, '', false);
		$blob = get_amazon_asin_blob($item_asin);
		if (!empty($blob))
		{
			//			$Asin        = $blob['Asin']; // in case $productKey isn't Asin...
			$URL         = &$blob['Url'];
			$ProductName = safeAddSlashes($blob['ProductName']);
			$Manuf		   = safeAddSlashes($blob['_Creator']); // our hacked value.
			$Price       = &$blob['OurPrice'];
			$Image			 = &$blob["ImageUrlSmall"];
			$Cat      	 = safeAddSlashes($blob['Catalog']);
			
			db_runquery("UPDATE $tablecgamazon SET amTime=amTime, amName='$ProductName', amCreator='$Manuf', amUrl='$URL', amImageUrlSmall='$Image', amCategory='$Cat' WHERE ASIN='$item_asin'", "admin - cga: refreshed");
		}
		
		header("Location: $REQUESTED");
		
		break;
	}	

//############################################################
//############################################################
	case 'time':
	{
		db_runquery("UPDATE $tablecgamazon SET amTime=null WHERE ASIN='$item_asin'", "admin - cga: time updated");
		
		header("Location: $REQUESTED");
		
		break;
	}	
	
//############################################################
//############################################################
	case 'edited':
	{
		if ($user_level < 3)
			die ('Cheatin&#8217; uh?');

		if (!empty($item_catname))
			$catname = $item_catname;
		else
		{
			lookupAmaCats();
			if (empty($item_catkey))
				$catname="";
			else
				$catname = $amaCats[$item_catkey];
		}

		$gotsum = query_amazon($item_asin, '', false);
		$blob = get_amazon_asin_blob($item_asin);
		if (!empty($blob))
		{
			//			$Asin        = $blob['Asin']; // in case $productKey isn't Asin...
			$URL         = &$blob['Url'];
			$ProductName = safeAddSlashes($blob['ProductName']);
			$Manuf		   = safeAddSlashes($blob['_Creator']); // our hacked value.
			$Price       = &$blob['OurPrice'];
			$Image			 = &$blob["ImageUrlSmall"];
			$Cat      	 = safeAddSlashes($blob['Catalog']);
				
			db_runquery("UPDATE $tablecgamazon SET amTime=amTime, metaNote='$item_note', amName='$ProductName', amCreator='$creator', amUrl='$URL', amImageUrlSmall='$Image', amCategory='$Cat', wpCategory='$catname' WHERE ASIN='$item_asin'", "admin - cga: editedwithquery");
		}		
		else
			db_runquery("UPDATE $tablecgamazon SET amTime=amTime, metaNote='$item_note', wpCategory='$catname', amUrl='Not Yet Found' WHERE ASIN='$item_asin'", "admin - cga: editednoquery");
		
		header("Location: $REQUESTED");

		break;
	}
	
//############################################################
//############################################################
	default:
	{
		//		$standalone = 0;
		//		require_once ('admin-header.php');

		if ($user_level < 3)
		{
			die("You don't have adequate permissions ($user_ID, $user_name, $user_level) to edit this blog.<br />Ask for a promotion to your <a href='mailto:$admin_email'>blog admin</a>. :)");
		}
		?>
		
		<style type="text/css">
			.edit, .delete, .edit:hover, .delete:hover {
				font: bold 80% Arial, sans-serif;
				display: block;
				text-align: center;
				border-bottom: none;
				background-color: #aaaaee;
				/*border-left: 1px solid #8833aa;*/
			}
			
			.edit:hover {
				background-color: #ccc;
				color: #fff;
			}
			
			.delete:hover {
				background-color: #c00;
				color: #fff;
			}
			
			td span {
				color: #555588;
			}
			
			#amaresult {
				font: italic 110% Times, serif;
				padding: 6px;
				margin: 10px;
				background-color: #bbffee;
				width: 50%;
			}				
			
		</style>
			
		
		<?php					
			if ($resultname)
			{
				echo "<div id='amaresult'>Result = [$resultname]</div>";
			}

		echo '<div class="wrap">';
			
			$qnumitems = db_getrow("SELECT COUNT(*) as num FROM $tablecgamazon", OBJECT, 0, "admin - CGAmazon count");
			if (NULL===$qnumitems) // likely means table not exist, assume so.
			{
			?>
				<div class="wrap">
					<form name="createtable" action="<?php echo $REQUESTED; ?>" method="post">
						<input type="hidden" name="action" value="create" />
						<input type="submit" name="submit" value="Create CG-Amazon Table" class="search" />
					</form>
				</div>
			<?php
			}
			else
			{
				$numitems = $qnumitems->num;
				if ($numitems<=0)
				{
					echo "<p>No items in the table yet. &nbsp;\n";
				}
				else
				{
					$pageNav = "<p>$numitems Items. Sort by ".(empty($sort)?"age":$sort);
					if ($sort=="ID"||$sort=="metaNote") $pageNav.=" (descending)";
					else $pageNav.=" (ascending)";
					$pageNav .= ". &nbsp;\n";
					
					$totalpages = 1+intval((($numitems-1) / $amaListMaxPerPage));
					if ($page > $totalpages) $page=1; // reset if something goes wacky with page numbering!
					if ($totalpages>1)
					{
						
						$pageNav .= "$totalpages Pages: &nbsp;\n";
						if ($page>1) // show Prev
								$pageNav .= adminButton('<< Prev Page', array('page'=>($page-1),'sort'=>$sort))."\n";
						if ($page<$totalpages)
								$pageNav .= adminButton('Next Page >>', array('page'=>($page+1),'sort'=>$sort))."\n";
					}
					$pageNav .= "</p>";
					
					$i = 0;
					$j = $amaListMaxPerPage;
					if ($totalpages)
					{
						$i = intval($amaListMaxPerPage * ($page-1));
						if ($page==$totalpages)
							$j = $numitems % $amaListMaxPerPage;
						$subset = "$i,";
					}
					echo $pageNav;
					echo "<h2>Current Items (".($i+1)."-".($i+$j).")</h2>";
					echo '<table width="100%" cellpadding="3" cellspacing="3">';
						echo "<tr>\n";
							echo "<th scope='col'>".adminButton("ID", array('sort'=>'ID'))."</th>\n";
							echo "<th scope='col'>".adminButton("Asin", array('sort'=>'ASIN'))."</th>\n";
							echo "<th scope='col'>".adminButton("Name", array('sort'=>'amName'))."</th>\n";
							echo "<th scope='col'>".adminButton("AmazCat", array('sort'=>'amCategory'))."</th>\n";
							echo "<th scope='col'>".adminButton("BlogCat", array('sort'=>'wpCategory'))."</th>\n";
							echo "<th scope='col'>".adminButton("Note", array('sort'=>'metaNote'))."</th>\n";
		/*
							echo "<th scope='col'>#</th>\n";
							echo "<th scope='col'>Asin</th>\n";
							echo "<th scope='col'>Name</th>\n";
							echo "<th scope='col'>AmazCat</th>\n";
							echo "<th scope='col'>BlogCat</th>\n";
							echo "<th scope='col'>Note</th>\n";
		*/
							echo "<th colspan='4'>Action</th>\n";
						echo "</tr>\n";
					
						if (empty($sort))
	//						$order = "ID DESC"; // so newest is at top
							$order = "amTime DESC"; // so newest is at top
						else
						{
							if ($sort=='ID' || $sort=='metaNote' || $sort=='wpCategory') $sortdir=' DESC';
							$order = $sort.$sortdir.",ID DESC"; // just copy
						}
							
						$items = db_getresults("SELECT * FROM $tablecgamazon WHERE 1=1 ORDER BY $order LIMIT $subset$amaListMaxPerPage ", OBJECT, "admin - CGAmazon");
						
						$iout = '';
						
						foreach ($items as $item)
						{
							$i++;
							$bgcolor = ('#eee' == $bgcolor) ? 'none' : '#eee';
							$iout .= "<tr style='background-color: $bgcolor'>\n";
								$iout .= "<td>$item->ID</td>\n";
								$iout .= "<td><span>$item->ASIN</span></td>\n";
								$iout .= "<td>$item->amName <span>($item->amCreator)</span></td>\n";
								$iout .= "<td>$item->amCategory</td>\n";
								$iout .= "<td>$item->wpCategory</td>\n";
								$iout .= "<td>".(empty($item->metaNote)?'':'Y')."</td>\n";
								$iout .= "<td>".adminButton('&nbsp;Edit&nbsp;', array('action'=>'edit','item_asin'=>$item->ASIN))."</td>\n";
								$iout .= "<td>".adminButton('Time', array('action'=>'time','item_asin'=>$item->ASIN))."</td>\n";
								$iout .= "<td>".adminButton('&nbsp;@&nbsp;', array('action'=>'refresh','item_asin'=>$item->ASIN))."</td>\n";
								$clickcode = "return confirm('You are about to delete the product [". addslashes($item->amName) ."] (".$item->ASIN.").  OK to delete, Cancel to stop.')";
								$iout .= "<td>".adminButton('&nbsp;X&nbsp;', array('action'=>'remove','item_asin'=>$item->ASIN), $clickcode)."</td>\n";
							$iout .= "</tr>\n";
						}
						
						if ($amazonEncoding && $amazonEncoding!='UTF-8')
							$iout = uni_decode($iout, $amazonEncoding);

						echo $iout;
					echo "</table>";
				}
			?>
			</div>
			
			<div class="wrap">
				<!--<h2>Add New Items</h2>-->
				<h2>Search For Items:</h2>
				<form name="finditem" action="<?php echo $REQUESTED; ?>" method="post">
					<input type="hidden" name="action" value="find" />
					<p>Look for
						<input type="text" name="find_what" value="" />&nbsp;
						in
						<?php catalog_dropdown(); ?>
						<input type="submit" name="submit" value="&nbsp;Find&nbsp;" class="search" />
						&nbsp;&nbsp;&nbsp;Max Results: 
						<select name='find_max' size='1'>
							<option value='10' selected>10</option>
							<option value='20'>20</option>
							<option value='30'>30</option>
							<option value='40'>40</option>
							<option value='50'>50</option>
						</select>
						&nbsp;&nbsp;Hide existing: <input type="checkbox" name="find_notexist" value="1" class="checkbox" />
					</p>
				</form>
				<h2>Add Specific Item:</h2>
				<form name="additem" action="<?php echo $REQUESTED; ?>" method="post">
					<input type="hidden" name="action" value="additem" />
					
					<p>Amazon ASIN: <input type="text" name="item_asin" value="" />&nbsp;<input type="submit" name="submit" value="Add" class="search" /></p>
		
					<p>Pick Category:
					<?php category_dropdown(''); ?> &nbsp;&nbsp;<b>OR</b>&nbsp; Enter New Category: <input type="text" name="item_catname" value="" /> &nbsp;&nbsp;<i>(optional - can leave blank/None)</i>
					</p>
					
					<p>Meta Notation: (added to html output) <br />
					<textarea name="item_note" rows="3" cols="50" style="width: 97%;"></textarea></p>
				</form>
	
			<?php
		}
		
		echo '</div>'; // closes any case.

		break;
	}
}

//flush();

echo "<div class='wrap'>";
	if ($showAmaErrors && function_exists("myErrorOutput"))
		myErrorOutput();
echo "</div>";

/* </CGAmazon Admin> */
//include($rawWPPath.'wp-admin/admin-footer.php');

?>