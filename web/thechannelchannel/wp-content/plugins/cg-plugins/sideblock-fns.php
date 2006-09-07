<?php

function start_block($name, $codename, $innertag='', $style='')
{
	global $currBlockInnerTag;
	
//	$styletag = '';
	$styletag = '-flat';
	if (!empty($style)) $styletag = "-$style";
	
	$le = "\n";
	$output = '';

	// debug info.
//	echo "... $name ... $codename ... $innertag ... $column ...".$le;
	
	$currBlockInnerTag = $innertag;
		
	$output .= "<div class='sidewrap$styletag' id='$codename'>".$le;
																	$output .= "\t\t\t\t";
	$output .= "<div class='sideblock$styletag' id='b-$codename'>".$le;
																	$output .= "\t\t\t\t\t";
	$output .= "<div class='boxhead$styletag'>".$le;
																	$output .= "\t\t\t\t\t\t";
	$output .= "<span id='t-$codename'>$name</span>".$le;
																	$output .= "\t\t\t\t\t";
	$output .= "</div>".$le;
																	$output .= "\t\t\t\t\t";
	$output .= "<div class='boxbody$styletag'>".$le;
	if (!empty($currBlockInnerTag))
	{
																	$output .= "\t\t\t\t\t\t";
		$output .= "<".$currBlockInnerTag.">".$le;
	}
	
	// if we wanted to do this via a passed-in include or callback, it'd go here. ;)
	
	echo $output;
}


function end_block()
{
	global $currBlockInnerTag;

	$le = "\n";
	$output = '';
																	$output .="\t\t\t";
	
	if (!empty($currBlockInnerTag))
	{
		$output .= "</".$currBlockInnerTag.">".$le;
	}

																	$output .= "\t";
	$output .= "</div>".$le;
																	$output .= "\t\t\t\t";
	$output .= "</div>".$le;

	$output .= '<div class="float-clear"></div>'; // ensuring our block encloses all floats

																	$output .= "\t\t\t\t";
	$output .= "</div>".$le;
	
	echo $output;
}

?>
