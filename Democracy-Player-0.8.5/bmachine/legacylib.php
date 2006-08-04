<?php
/**
 * Broadcast Machine legacy library
 *
 * provides support for older versions of PHP
 * Original version by: Greg Retkowski <greg-at-rage.net>
 * Licensed under the terms of the GNU GPL
 * @package BroadcastMachine
 */

// multibyte functions that we need for UTF stuff
if ( !function_exists("mb_substr") || !function_exists("mb_strtolower") ) {
  include_once("mb.php");
}


/**
 * writes data to the specified filename.  pretty basic function with some locking
 * and not much else in terms of error detection, etc.
 */
if ( ! function_exists("file_put_contents") ) {
  function file_put_contents($fname, $data) {
    $handle = fopen($fname, "wb+");
    flock( $handle, LOCK_EX );
    fwrite($handle, $data);
    fclose($handle);
  }
}


//
// mime-checking function
// (see http://us4.php.net/mime_content_type)
//
if (!function_exists('mime_content_type')) {
   function mime_content_type($f) {
       $f = escapeshellarg($f);
       return trim( `file -bi $f` );
   }
}

// Prevents PHP from crashing if zip functions aren't available
if (!function_exists('zip_open')) {
  function zip_open($file) {
    return false;
  }
}

// For versions of PHP older than 4.2.0
srand(time());


/*
 * Simple implementation of file_get_contents
 */
if (!function_exists('file_get_contents')) {

  function file_get_contents($file) {

    $string = '';

    $f = fopen($file,"rb");
    while ($r=fread($f,8192) ) {
      $string .= $r;
    }

    fclose($f);
    return($string);
  }

} // file_get_contents


if (! function_exists('sha1')) {

  if (function_exists('mhash')) {

    function sha1($str) {
      return bin2hex(mhash(MHASH_SHA1, $str));
    }

  } 
  else {

    /*
		SHA1 function from yggdrasil-cms -- Should be much faster than the
		other implementation we had.

		http://cvs.sourceforge.net/viewcvs.py/yggdrasil-cms/yggdrasil/include/sha1.inc.php?rev=1.5&view=markup

		Licensed under the GNU GPL

		Now, we check for the existence of mhash. If you're having CPU related
		performance issues on an older version of PHP without sha1, installing
		the mhash module should increase performance.
    */
    function _sha1_s($X, $n = 1) {
		return ($X << $n) | (($X & 0x80000000)?
			(($X>>1) & 0x07fffffff | 0x40000000)>>(31-$n):$X>>(32-$n));
    }


    function _sha1_step(&$H, $str) {
		$A = $H[0]; $B = $H[1]; $C = $H[2]; $D = $H[3]; $E = $H[4];
		$W = array_values(unpack('N16', $str));
		for ($i = 0; $i<16; ++$i) {
			$W[$i+16] = &$W[$i];
		}

      	$t = 0;
		do {		//  0 <= t < 20
			$s = $t & 0xf;
			if ($t>=16) {
				$W[$s] = _sha1_s($W[$s+13] ^ $W[$s+8] ^ $W[$s+ 2] ^ $W[$s]);
			}

			$TEMP = ($D ^ ($B & ($C ^ $D))) + 0x5A827999 +
		  _sha1_s($A, 5) + $E + $W[$s];

			$E = $D; $D = $C; $C = _sha1_s($B, 30); $B = $A; $A = $TEMP;

		} while (++$t<20);
     

		do {		// 20 <= t < 40

			$s = $t & 0xf;

			$W[$s] = _sha1_s($W[$s+13] ^ $W[$s+8] ^ $W[$s+ 2] ^ $W[$s]);
			$TEMP = ($B ^ $C ^ $D) + 0x6ED9EBA1 +
			_sha1_s($A, 5) + $E + $W[$s];
			$E = $D; $D = $C; $C = _sha1_s($B, 30); $B = $A; $A = $TEMP;
		} while (++$t<40);
     

		do {		// 40 <= t < 60
			$s = $t & 0xf;
			$W[$s] = _sha1_s($W[$s+13] ^ $W[$s+8] ^ $W[$s+ 2] ^ $W[$s]);

			$TEMP = (($B & $C) | ($D & ($B | $C))) + 0x8F1BBCDC +
			_sha1_s($A, 5) + $E + $W[$s];
			$E = $D; $D = $C; $C = _sha1_s($B, 30); $B = $A; $A = $TEMP;
		} while (++$t<60);
    
		do {		// 60 <= t < 80
			$s = $t & 0xf;
			$W[$s] = _sha1_s($W[$s+13] ^ $W[$s+8] ^ $W[$s+ 2] ^ $W[$s]);

			$TEMP = ($B ^ $C ^ $D) + 0xCA62C1D6 +
			_sha1_s($A, 5) + $E + $W[$s];
			$E = $D; $D = $C; $C = _sha1_s($B, 30); $B = $A; $A = $TEMP;
		} while (++$t<80);

		$H = array($H[0] + $A, $H[1] + $B, $H[2] + $C, $H[3] + $D, $H[4] + $E);
	}

	function sha1_raw($str) {
		$l = strlen($str);
		$str = str_pad("$str\x80\0\0\0\0", ($l&~63)+((($l&63)<56)?60:124), "\0") .  pack('N', $l<<3);
		$l = strlen($str);
		
		$H = array(0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476, 0xC3D2E1F0);
		for ($i = 0; $i<$l; $i += 64) {
			_sha1_step($H, substr($str, $i, 64));
		}

		return pack('N*', $H[0], $H[1], $H[2], $H[3], $H[4]);
	}

	function sha1($str) {
		return bin2hex(sha1_raw($str));
    }

  }

} // End sha1
?>