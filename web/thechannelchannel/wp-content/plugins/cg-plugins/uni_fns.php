<?php
//============================================================
// Unicode handler functions
// (c)2004 David Chait
//============================================================

function uni_detect(&$string)
{
	// for testing...
//	return(true);

	$len = strlen($string); // raw originating bytes.
	$i = 0;
	while ($i < $len)
	{	
		$val = ord($string{$i});
		++$i;
		if ($val > 127)
			return(true);
	}
	return(false);
}

//============================================================
//============================================================
// UTF-8 encoding bit-packing layout:
// 1 byte      7 bits   0bbbbbbb
// 2 byte     11 bits   110bbbbb 10bbbbbb
// 3 byte     16 bits   1110bbbb 10bbbbbb 10bbbbbb
// 4 byte     21 bits   11110bbb 10bbbbbb 10bbbbbb 10bbbbbb
// note that this means that UTF8 strings can't have single-byte chars >127
//============================================================

$uniMask[1] = (1<<(5)) - 1;
$uniMask[2] = (1<<(4)) - 1;
$uniMask[3] = (1<<(3)) - 1;

function str2uni(&$string, $termlen=0)
{
	global $DebugFeed;
	global $uniMask;
	
	$uni = array();
	$len = strlen($string); // raw originating bytes.
	$i = 0;
	$c = 0;
//	echo "STR2UNI ($termlen): ".$string."\n<br>";
	while ($i < $len)
	{	
		$val = ord($string{$i});
		++$i;
		if ($val < 128)
		{
			$uni[] = $val; // short circuit the decode process...
		}
		else
		{
			// how many extra bytes?
			if ($val>>5 == 6) // 110bbbbb
				$uniLen = 1;
			else
			if ($val>>4 == 14) // 1110bbbb
				$uniLen = 2;
			else // assume 11110bbb
				$uniLen = 3;
				
			//$j=0;
			$uniVal = ($val & $uniMask[$uniLen]);
			// $j++;
			for ($j=1; $j<=$uniLen; $j++)
			{
				$uniVal <<= 6; // make room for 6 bits of new data...
				$val = ord($string{$i++});
				$uniVal += ($val & 63);
			}
			
			$uni[] = $uniVal;
		}
		$c++;
		if ($termlen && $c >= $termlen)
			break;
	}
	
//	echo "UNI: ".uni2str($uni)."\n<br>";
	return $uni;
}

$uniBytePre[2] = 3 << 6; // 11 => 11000000
$uniBytePre[3] = 7 << 5; // 111 => 11100000
$uniBytePre[4] = 15 << 4; // 1111 => 11110000
$bits11 = (1<<(11+1));
$bits16 = (1<<(16+1));

function uni2str(&$uni)
{
	global $uniBytePre, $bits11, $bits16;
	$string = '';
	$c = count($uni);
	$i = 0;
	$uniChars[0] = ''; $uniChars[1] = ''; $uniChars[2] = ''; $uniChars[3] = '';
	while ($i < $c)
	{
		$uniVal = $uni[$i];
		++$i;
		if ($uniVal < 128)  // 1<<(7+1) == 7 bits
			$string .= chr($uniVal);
		else
		{
			$string .= '&#' . $uniVal . ';';
/*
			if ($uniVal < $bits11) // == 11 bits
				$uniLen = 2;
			else if ($uniVal < $bits16) // == 16 bits
				$uniLen = 3;
			else //if ($uniVal < (1<<(16+1))) // == 16 bits
				$uniLen = 4;
			for ($j=$uniLen; $j>0; $j--)
			{
				$uniChars[$j-1] = $uniVal & 63;
				$uniVal = $uniVal >> 6;
			}

			for ($j=0; $j<$uniLen; $j++)
			{			
				if ($j==0)
					$string .= chr($uniBytePre[$uniLen] + $uniChars[$j]);
				else
					$string .= chr(128 + $uniChars[$j]);
			}
*/
		}
	}
	return $string;
}

function uni_strip_tags(&$uni)
{
	return($uni); // !!!!TBD
}

function uni_snippet(&$uni, $length, $tail="&#8230;")
{
	if ($length<4)
		$length = 4;
	$uniLen = count($uni);
	if ($length > $uniLen)
		return($uni);

//	if (1) { echo("SNIPPET TO: $length \n<br>"); flush(); 	}

	while($length>4)
	{
		$uniVal = $uni[--$length];
//		if (1) { echo("$length: ".chr($uniVal)." == ".$uniVal."\n<br>"); flush(); 	}
		if ($uniVal < 128)
		{
			if (chr($uniVal) == ' '
			||	chr($uniVal) == ','
			||	chr($uniVal) == '.'
			||	chr($uniVal) == '-'
			||	chr($uniVal) == "\t"
			||	chr($uniVal) == "\n"
			||	chr($uniVal) == "\r"
				)
				break;
		}
	}
	
	$uniOut = array();
	for ($i=0; $i<$length; $i++)
		$uniOut[] = $uni[$i];
	for ($i=0; $i<strlen($tail); $i++)
		$uniOut[] = ord($tail[$i]);
		
	return $uniOut;
}

function uni_decode(&$string, $encoding)
{
	if (function_exists('iconv') && $encoding!='ISO-8859-1')
	{
		$string = iconv('UTF-8', $encoding, $string);
	}
	else if (function_exists('utf8_decode')) // backup, or primary for 8859-1
	{ // this will try to just decode to iso-8859-1
		$string = utf8_decode($string);
		// if we have replaceable conversion modules for this encoding, run them now...
		/// !!!!TBD
	}
	else
	{
		// should output an error, somewhere, somehow!
	}
	
	return($string);
}

?>