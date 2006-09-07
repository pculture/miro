<?php

function amazon_track_view($asin)
{
	global $tablecgamazon, $user_level, $isaSearchbot;
	
	if ($isaSearchbot) return;
	if ($user_level > 4) return; // so primary admins don't increase counts!

	$uquery = "UPDATE $tablecgamazon SET amViewcount=amViewcount+1, amTime=amTime WHERE ASIN='$asin'";
	db_runquery($uquery);
}


function pop_amazon_list($max=6, $randomize=3, $showViewCount=false, $showInline=false)
{
	global $tablecgamazon;
	
	$output = '';

	if ($randomize>$max) $randomize = $max;
	$extrap = 0;
	if ($randomize) $extrap = 3 + 2 * (1 + $max - $randomize);
	$totalp = $max + $extrap;

	$rquery = "SELECT ASIN, amName, amViewcount FROM $tablecgamazon";
	$rquery .= " ORDER BY amViewcount DESC LIMIT $totalp";
	$results = db_getresults($rquery, OBJECT, "pop_amazon_list");

	$c = count($results); 	
	if ($c<=0) return '<ul><li>No products returned.</li></ul>';

	if ($c<=$max) $randomize = 0;
	
//	dbglog("total post count = $c");
	
	$usepost = array_fill(0, $c, false); // to initialize the array -- removes error notices...
	for ($i=0; $i<($max-$randomize); $i++)
		$usepost[$i] = true;
	$k = $i;
	if ($randomize)
	{
		for ($i=$k; $i<$max; $i++)
		{
			$apick = rand($k, $totalp-1);
			if ($usepost[$apick]) // already taken.  start from top and grab one.
			{
				for ($c=$k; $c<$max; $c++)
				{
					$apick = $c;
					if (!$usepost[$apick]) break;
				}
			}
			$usepost[$apick] = true;
		}
	}
	
	$output .= '<ul>';
	$i = 0;
	foreach ($results as $result)
	{
		if ($usepost[$i])
		{
			$asin = $result->ASIN;
			$name = stripslashes($result->amName);
			$viewcnt = $result->amViewcount;
			
			$output .= '<li>';
			if ($showViewCount && $showInline)
				$output .= '('.$viewcnt.') ';
			$output .= "<a href='cgaindex.php?p=ASIN_$asin'";
			if ($showViewCount)
			if ($showViewCount)
				$output .= ' title="Viewed '.$viewcnt.' times."';
			else
				$output .= ' title="'.$name.'"';
			$output .= '>'.$name.'</a>';
			$output .= '</li>';
		}
		$i++;
	}
	$output .= '</ul>';
	
	return($output);
}


function the_amazon_viewcount()
{
	global $product;
	if (empty($product)) return 0;
	return intval($product->amViewcount);
}

// check for direct inclusion...
if (strpos($_SERVER['REQUEST_URI'], "cgatracking.php"))
{
	$ctAbsPath = dirname(__FILE__).'/';
	
	if (file_exists($ctAbsPath.'../wp-config.php'))
		require_once($ctAbsPath.'../wp-config.php');
	else
		require_once($ctAbsPath.'../../../wp-config.php');
	
	require_once($ctAbsPath.'cga-config.php');
	
	$showStats = $_GET['stats'];
	$showStats = intval($showStats);

	if (!empty($showStats))
	if ($user_level>=2)
	{		
		echo '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">';
		echo '<html xmlns="http://www.w3.org/1999/xhtml">';
		//else if ($showStats)
			echo '<title>Showing popular products by pageload statistics</title>';
		echo '<meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1" />';
		echo '<style media="screen" type="text/css">';
		echo '	body {';
		echo '		font: 12px Georgia, "Times New Roman", Times, serif;';
		echo '		margin-left: 5%;';
		echo '		margin-right: 5%;';
		echo '	}';
		echo '	span {';
		echo '		font: bold 12px Arial, sans-serif;';
		echo '	}';
		echo '</style>';
		echo '</head><body><br>';
		
			$count = 100;
			if ($showStats)
				$count = $showStats;
			echo pop_amazon_list($count, 0, true, true);
			
		echo '</body>';
		echo '</html>';
	}
}
	
?>