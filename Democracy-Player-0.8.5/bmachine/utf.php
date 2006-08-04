<?php
/**
* @version $Id: core.php,v 1.5 2006/02/28 22:12:26 harryf Exp $
* @package utf8
* @subpackage strings
*/

/**
* Define UTF8_CORE as required
*/
if ( !defined('UTF8_CORE') ) {
    define('UTF8_CORE',TRUE);
}

global $UTF8_UPPER_TO_LOWER;
global $UTF8_LOWER_TO_UPPER;

//---------------------------------------------------------------
/**
* UTF-8 Case lookup table
* This lookuptable defines the upper case letters to their correspponding
* lower case letter in UTF-8
* @author Andreas Gohr <andi@splitbrain.org>
* @see utf8_strtoupper
* @package utf8
* @subpackage strings
* @see http://dev.splitbrain.org/view/darcs/dokuwiki/inc/utf8.php
*/
$UTF8_LOWER_TO_UPPER = array(
    0x0061=>0x0041, 0x03C6=>0x03A6, 0x0163=>0x0162, 0x00E5=>0x00C5, 0x0062=>0x0042,
    0x013A=>0x0139, 0x00E1=>0x00C1, 0x0142=>0x0141, 0x03CD=>0x038E, 0x0101=>0x0100,
    0x0491=>0x0490, 0x03B4=>0x0394, 0x015B=>0x015A, 0x0064=>0x0044, 0x03B3=>0x0393,
    0x00F4=>0x00D4, 0x044A=>0x042A, 0x0439=>0x0419, 0x0113=>0x0112, 0x043C=>0x041C,
    0x015F=>0x015E, 0x0144=>0x0143, 0x00EE=>0x00CE, 0x045E=>0x040E, 0x044F=>0x042F,
    0x03BA=>0x039A, 0x0155=>0x0154, 0x0069=>0x0049, 0x0073=>0x0053, 0x1E1F=>0x1E1E,
    0x0135=>0x0134, 0x0447=>0x0427, 0x03C0=>0x03A0, 0x0438=>0x0418, 0x00F3=>0x00D3,
    0x0440=>0x0420, 0x0454=>0x0404, 0x0435=>0x0415, 0x0449=>0x0429, 0x014B=>0x014A,
    0x0431=>0x0411, 0x0459=>0x0409, 0x1E03=>0x1E02, 0x00F6=>0x00D6, 0x00F9=>0x00D9,
    0x006E=>0x004E, 0x0451=>0x0401, 0x03C4=>0x03A4, 0x0443=>0x0423, 0x015D=>0x015C,
    0x0453=>0x0403, 0x03C8=>0x03A8, 0x0159=>0x0158, 0x0067=>0x0047, 0x00E4=>0x00C4,
    0x03AC=>0x0386, 0x03AE=>0x0389, 0x0167=>0x0166, 0x03BE=>0x039E, 0x0165=>0x0164,
    0x0117=>0x0116, 0x0109=>0x0108, 0x0076=>0x0056, 0x00FE=>0x00DE, 0x0157=>0x0156,
    0x00FA=>0x00DA, 0x1E61=>0x1E60, 0x1E83=>0x1E82, 0x00E2=>0x00C2, 0x0119=>0x0118,
    0x0146=>0x0145, 0x0070=>0x0050, 0x0151=>0x0150, 0x044E=>0x042E, 0x0129=>0x0128,
    0x03C7=>0x03A7, 0x013E=>0x013D, 0x0442=>0x0422, 0x007A=>0x005A, 0x0448=>0x0428,
    0x03C1=>0x03A1, 0x1E81=>0x1E80, 0x016D=>0x016C, 0x00F5=>0x00D5, 0x0075=>0x0055,
    0x0177=>0x0176, 0x00FC=>0x00DC, 0x1E57=>0x1E56, 0x03C3=>0x03A3, 0x043A=>0x041A,
    0x006D=>0x004D, 0x016B=>0x016A, 0x0171=>0x0170, 0x0444=>0x0424, 0x00EC=>0x00CC,
    0x0169=>0x0168, 0x03BF=>0x039F, 0x006B=>0x004B, 0x00F2=>0x00D2, 0x00E0=>0x00C0,
    0x0434=>0x0414, 0x03C9=>0x03A9, 0x1E6B=>0x1E6A, 0x00E3=>0x00C3, 0x044D=>0x042D,
    0x0436=>0x0416, 0x01A1=>0x01A0, 0x010D=>0x010C, 0x011D=>0x011C, 0x00F0=>0x00D0,
    0x013C=>0x013B, 0x045F=>0x040F, 0x045A=>0x040A, 0x00E8=>0x00C8, 0x03C5=>0x03A5,
    0x0066=>0x0046, 0x00FD=>0x00DD, 0x0063=>0x0043, 0x021B=>0x021A, 0x00EA=>0x00CA,
    0x03B9=>0x0399, 0x017A=>0x0179, 0x00EF=>0x00CF, 0x01B0=>0x01AF, 0x0065=>0x0045,
    0x03BB=>0x039B, 0x03B8=>0x0398, 0x03BC=>0x039C, 0x045C=>0x040C, 0x043F=>0x041F,
    0x044C=>0x042C, 0x00FE=>0x00DE, 0x00F0=>0x00D0, 0x1EF3=>0x1EF2, 0x0068=>0x0048,
    0x00EB=>0x00CB, 0x0111=>0x0110, 0x0433=>0x0413, 0x012F=>0x012E, 0x00E6=>0x00C6,
    0x0078=>0x0058, 0x0161=>0x0160, 0x016F=>0x016E, 0x03B1=>0x0391, 0x0457=>0x0407,
    0x0173=>0x0172, 0x00FF=>0x0178, 0x006F=>0x004F, 0x043B=>0x041B, 0x03B5=>0x0395,
    0x0445=>0x0425, 0x0121=>0x0120, 0x017E=>0x017D, 0x017C=>0x017B, 0x03B6=>0x0396,
    0x03B2=>0x0392, 0x03AD=>0x0388, 0x1E85=>0x1E84, 0x0175=>0x0174, 0x0071=>0x0051,
    0x0437=>0x0417, 0x1E0B=>0x1E0A, 0x0148=>0x0147, 0x0105=>0x0104, 0x0458=>0x0408,
    0x014D=>0x014C, 0x00ED=>0x00CD, 0x0079=>0x0059, 0x010B=>0x010A, 0x03CE=>0x038F,
    0x0072=>0x0052, 0x0430=>0x0410, 0x0455=>0x0405, 0x0452=>0x0402, 0x0127=>0x0126,
    0x0137=>0x0136, 0x012B=>0x012A, 0x03AF=>0x038A, 0x044B=>0x042B, 0x006C=>0x004C,
    0x03B7=>0x0397, 0x0125=>0x0124, 0x0219=>0x0218, 0x00FB=>0x00DB, 0x011F=>0x011E,
    0x043E=>0x041E, 0x1E41=>0x1E40, 0x03BD=>0x039D, 0x0107=>0x0106, 0x03CB=>0x03AB,
    0x0446=>0x0426, 0x00FE=>0x00DE, 0x00E7=>0x00C7, 0x03CA=>0x03AA, 0x0441=>0x0421,
    0x0432=>0x0412, 0x010F=>0x010E, 0x00F8=>0x00D8, 0x0077=>0x0057, 0x011B=>0x011A,
    0x0074=>0x0054, 0x006A=>0x004A, 0x045B=>0x040B, 0x0456=>0x0406, 0x0103=>0x0102,
    0x03BB=>0x039B, 0x00F1=>0x00D1, 0x043D=>0x041D, 0x03CC=>0x038C, 0x00E9=>0x00C9,
    0x00F0=>0x00D0, 0x0457=>0x0407, 0x0123=>0x0122,
);

//---------------------------------------------------------------
/**
* UTF-8 Case lookup table
* This lookuptable defines the lower case letters to their correspponding
* upper case letter in UTF-8
* @author Andreas Gohr <andi@splitbrain.org>
* @see http://dev.splitbrain.org/view/darcs/dokuwiki/inc/utf8.php
* @see utf8_strtolower
* @package utf8
* @subpackage strings
*/
$UTF8_UPPER_TO_LOWER = array(
    0x0041=>0x0061, 0x03A6=>0x03C6, 0x0162=>0x0163, 0x00C5=>0x00E5, 0x0042=>0x0062,
    0x0139=>0x013A, 0x00C1=>0x00E1, 0x0141=>0x0142, 0x038E=>0x03CD, 0x0100=>0x0101,
    0x0490=>0x0491, 0x0394=>0x03B4, 0x015A=>0x015B, 0x0044=>0x0064, 0x0393=>0x03B3,
    0x00D4=>0x00F4, 0x042A=>0x044A, 0x0419=>0x0439, 0x0112=>0x0113, 0x041C=>0x043C,
    0x015E=>0x015F, 0x0143=>0x0144, 0x00CE=>0x00EE, 0x040E=>0x045E, 0x042F=>0x044F,
    0x039A=>0x03BA, 0x0154=>0x0155, 0x0049=>0x0069, 0x0053=>0x0073, 0x1E1E=>0x1E1F,
    0x0134=>0x0135, 0x0427=>0x0447, 0x03A0=>0x03C0, 0x0418=>0x0438, 0x00D3=>0x00F3,
    0x0420=>0x0440, 0x0404=>0x0454, 0x0415=>0x0435, 0x0429=>0x0449, 0x014A=>0x014B,
    0x0411=>0x0431, 0x0409=>0x0459, 0x1E02=>0x1E03, 0x00D6=>0x00F6, 0x00D9=>0x00F9,
    0x004E=>0x006E, 0x0401=>0x0451, 0x03A4=>0x03C4, 0x0423=>0x0443, 0x015C=>0x015D,
    0x0403=>0x0453, 0x03A8=>0x03C8, 0x0158=>0x0159, 0x0047=>0x0067, 0x00C4=>0x00E4,
    0x0386=>0x03AC, 0x0389=>0x03AE, 0x0166=>0x0167, 0x039E=>0x03BE, 0x0164=>0x0165,
    0x0116=>0x0117, 0x0108=>0x0109, 0x0056=>0x0076, 0x00DE=>0x00FE, 0x0156=>0x0157,
    0x00DA=>0x00FA, 0x1E60=>0x1E61, 0x1E82=>0x1E83, 0x00C2=>0x00E2, 0x0118=>0x0119,
    0x0145=>0x0146, 0x0050=>0x0070, 0x0150=>0x0151, 0x042E=>0x044E, 0x0128=>0x0129,
    0x03A7=>0x03C7, 0x013D=>0x013E, 0x0422=>0x0442, 0x005A=>0x007A, 0x0428=>0x0448,
    0x03A1=>0x03C1, 0x1E80=>0x1E81, 0x016C=>0x016D, 0x00D5=>0x00F5, 0x0055=>0x0075,
    0x0176=>0x0177, 0x00DC=>0x00FC, 0x1E56=>0x1E57, 0x03A3=>0x03C3, 0x041A=>0x043A,
    0x004D=>0x006D, 0x016A=>0x016B, 0x0170=>0x0171, 0x0424=>0x0444, 0x00CC=>0x00EC,
    0x0168=>0x0169, 0x039F=>0x03BF, 0x004B=>0x006B, 0x00D2=>0x00F2, 0x00C0=>0x00E0,
    0x0414=>0x0434, 0x03A9=>0x03C9, 0x1E6A=>0x1E6B, 0x00C3=>0x00E3, 0x042D=>0x044D,
    0x0416=>0x0436, 0x01A0=>0x01A1, 0x010C=>0x010D, 0x011C=>0x011D, 0x00D0=>0x00F0,
    0x013B=>0x013C, 0x040F=>0x045F, 0x040A=>0x045A, 0x00C8=>0x00E8, 0x03A5=>0x03C5,
    0x0046=>0x0066, 0x00DD=>0x00FD, 0x0043=>0x0063, 0x021A=>0x021B, 0x00CA=>0x00EA,
    0x0399=>0x03B9, 0x0179=>0x017A, 0x00CF=>0x00EF, 0x01AF=>0x01B0, 0x0045=>0x0065,
    0x039B=>0x03BB, 0x0398=>0x03B8, 0x039C=>0x03BC, 0x040C=>0x045C, 0x041F=>0x043F,
    0x042C=>0x044C, 0x00DE=>0x00FE, 0x00D0=>0x00F0, 0x1EF2=>0x1EF3, 0x0048=>0x0068,
    0x00CB=>0x00EB, 0x0110=>0x0111, 0x0413=>0x0433, 0x012E=>0x012F, 0x00C6=>0x00E6,
    0x0058=>0x0078, 0x0160=>0x0161, 0x016E=>0x016F, 0x0391=>0x03B1, 0x0407=>0x0457,
    0x0172=>0x0173, 0x0178=>0x00FF, 0x004F=>0x006F, 0x041B=>0x043B, 0x0395=>0x03B5,
    0x0425=>0x0445, 0x0120=>0x0121, 0x017D=>0x017E, 0x017B=>0x017C, 0x0396=>0x03B6,
    0x0392=>0x03B2, 0x0388=>0x03AD, 0x1E84=>0x1E85, 0x0174=>0x0175, 0x0051=>0x0071,
    0x0417=>0x0437, 0x1E0A=>0x1E0B, 0x0147=>0x0148, 0x0104=>0x0105, 0x0408=>0x0458,
    0x014C=>0x014D, 0x00CD=>0x00ED, 0x0059=>0x0079, 0x010A=>0x010B, 0x038F=>0x03CE,
    0x0052=>0x0072, 0x0410=>0x0430, 0x0405=>0x0455, 0x0402=>0x0452, 0x0126=>0x0127,
    0x0136=>0x0137, 0x012A=>0x012B, 0x038A=>0x03AF, 0x042B=>0x044B, 0x004C=>0x006C,
    0x0397=>0x03B7, 0x0124=>0x0125, 0x0218=>0x0219, 0x00DB=>0x00FB, 0x011E=>0x011F,
    0x041E=>0x043E, 0x1E40=>0x1E41, 0x039D=>0x03BD, 0x0106=>0x0107, 0x03AB=>0x03CB,
    0x0426=>0x0446, 0x00DE=>0x00FE, 0x00C7=>0x00E7, 0x03AA=>0x03CA, 0x0421=>0x0441,
    0x0412=>0x0432, 0x010E=>0x010F, 0x00D8=>0x00F8, 0x0057=>0x0077, 0x011A=>0x011B,
    0x0054=>0x0074, 0x004A=>0x006A, 0x040B=>0x045B, 0x0406=>0x0456, 0x0102=>0x0103,
    0x039B=>0x03BB, 0x00D1=>0x00F1, 0x041D=>0x043D, 0x038C=>0x03CC, 0x00C9=>0x00E9,
    0x00D0=>0x00F0, 0x0407=>0x0457, 0x0122=>0x0123,
);

//---------------------------------------------------------------
/**
* UTF-8 aware alternative to strtoupper
* Make a string uppercase
* Note: The concept of a characters "case" only exists is some alphabets
* such as Latin, Greek, Cyrillic, Armenian and archaic Georgian - it does
* not exist in the Chinese alphabet, for example. See Unicode Standard
* Annex #21: Case Mappings
* Note: requires utf8_to_unicode and utf8_from_unicode
* @author Andreas Gohr <andi@splitbrain.org>
* @param string
* @return mixed either string in lowercase or FALSE is UTF-8 invalid
* @see http://www.php.net/strtoupper
* @see utf8_to_unicode
* @see utf8_from_unicode
* @see http://www.unicode.org/reports/tr21/tr21-5.html
* @see http://dev.splitbrain.org/view/darcs/dokuwiki/inc/utf8.php
* @package utf8
* @subpackage strings
*/
function utf8_strtoupper($string){
    global $UTF8_LOWER_TO_UPPER;
    
    $uni = utf8_to_unicode($string);
    
    if ( !$uni ) {
        return FALSE;
    }
    
    $cnt = count($uni);
    for ($i=0; $i < $cnt; $i++){
        if( isset($UTF8_LOWER_TO_UPPER[$uni[$i]]) ) {
            $uni[$i] = $UTF8_LOWER_TO_UPPER[$uni[$i]];
        }
    }
    
    return utf8_from_unicode($uni);
}



//--------------------------------------------------------------------
/**
* Takes an UTF-8 string and returns an array of ints representing the 
* Unicode characters. Astral planes are supported ie. the ints in the
* output can be > 0xFFFF. Occurrances of the BOM are ignored. Surrogates
* are not allowed.
* Returns false if the input string isn't a valid UTF-8 octet sequence
* and raises a PHP error at level E_USER_WARNING
* Note: this function has been modified slightly in this library to
* trigger errors on encountering bad bytes
* @author <hsivonen@iki.fi>
* @param string UTF-8 encoded string
* @return mixed array of unicode code points or FALSE if UTF-8 invalid
* @see utf8_from_unicode
* @see http://hsivonen.iki.fi/php-utf8/
* @package utf8
* @subpackage unicode
*/
function utf8_to_unicode($str) {
    $mState = 0;     // cached expected number of octets after the current octet
                     // until the beginning of the next UTF8 character sequence
    $mUcs4  = 0;     // cached Unicode character
    $mBytes = 1;     // cached expected number of octets in the current sequence
    
    $out = array();
    
    $len = strlen($str);
    
    for($i = 0; $i < $len; $i++) {
        
        $in = ord($str{$i});
        if ( $mState == 0) {
            
            // When mState is zero we expect either a US-ASCII character or a
            // multi-octet sequence.
            if (0 == (0x80 & ($in))) {
                // US-ASCII, pass straight through.
                $out[] = $in;
                $mBytes = 1;
                
            } else if (0xC0 == (0xE0 & ($in))) {
                // First octet of 2 octet sequence
                $mUcs4 = ($in);
                $mUcs4 = ($mUcs4 & 0x1F) << 6;
                $mState = 1;
                $mBytes = 2;
                
            } else if (0xE0 == (0xF0 & ($in))) {
                // First octet of 3 octet sequence
                $mUcs4 = ($in);
                $mUcs4 = ($mUcs4 & 0x0F) << 12;
                $mState = 2;
                $mBytes = 3;
                
            } else if (0xF0 == (0xF8 & ($in))) {
                // First octet of 4 octet sequence
                $mUcs4 = ($in);
                $mUcs4 = ($mUcs4 & 0x07) << 18;
                $mState = 3;
                $mBytes = 4;
                
            } else if (0xF8 == (0xFC & ($in))) {
                /* First octet of 5 octet sequence.
                *
                * This is illegal because the encoded codepoint must be either
                * (a) not the shortest form or
                * (b) outside the Unicode range of 0-0x10FFFF.
                * Rather than trying to resynchronize, we will carry on until the end
                * of the sequence and let the later error handling code catch it.
                */
                $mUcs4 = ($in);
                $mUcs4 = ($mUcs4 & 0x03) << 24;
                $mState = 4;
                $mBytes = 5;
                
            } else if (0xFC == (0xFE & ($in))) {
                // First octet of 6 octet sequence, see comments for 5 octet sequence.
                $mUcs4 = ($in);
                $mUcs4 = ($mUcs4 & 1) << 30;
                $mState = 5;
                $mBytes = 6;
                
            } else {
                /* Current octet is neither in the US-ASCII range nor a legal first
                 * octet of a multi-octet sequence.
                 */
                trigger_error(
                        'utf8_to_unicode: Illegal sequence identifier '.
                            'in UTF-8 at byte '.$i,
                        E_USER_WARNING
                    );
                return FALSE;
                
            }
        
        } else {
            
            // When mState is non-zero, we expect a continuation of the multi-octet
            // sequence
            if (0x80 == (0xC0 & ($in))) {
                
                // Legal continuation.
                $shift = ($mState - 1) * 6;
                $tmp = $in;
                $tmp = ($tmp & 0x0000003F) << $shift;
                $mUcs4 |= $tmp;
            
                /**
                * End of the multi-octet sequence. mUcs4 now contains the final
                * Unicode codepoint to be output
                */
                if (0 == --$mState) {
                    
                    /*
                    * Check for illegal sequences and codepoints.
                    */
                    // From Unicode 3.1, non-shortest form is illegal
                    if (((2 == $mBytes) && ($mUcs4 < 0x0080)) ||
                        ((3 == $mBytes) && ($mUcs4 < 0x0800)) ||
                        ((4 == $mBytes) && ($mUcs4 < 0x10000)) ||
                        (4 < $mBytes) ||
                        // From Unicode 3.2, surrogate characters are illegal
                        (($mUcs4 & 0xFFFFF800) == 0xD800) ||
                        // Codepoints outside the Unicode range are illegal
                        ($mUcs4 > 0x10FFFF)) {
                        
                        trigger_error(
                                'utf8_to_unicode: Illegal sequence or codepoint '.
                                    'in UTF-8 at byte '.$i,
                                E_USER_WARNING
                            );
                        
                        return FALSE;
                        
                    }
                    
                    if (0xFEFF != $mUcs4) {
                        // BOM is legal but we don't want to output it
                        $out[] = $mUcs4;
                    }
                    
                    //initialize UTF8 cache
                    $mState = 0;
                    $mUcs4  = 0;
                    $mBytes = 1;
                }
            
            } else {
                /**
                *((0xC0 & (*in) != 0x80) && (mState != 0))
                * Incomplete multi-octet sequence.
                */
                trigger_error(
                        'utf8_to_unicode: Incomplete multi-octet '.
                        '   sequence in UTF-8 at byte '.$i,
                        E_USER_WARNING
                    );
                
                return FALSE;
            }
        }
    }

    return $out;
}


//--------------------------------------------------------------------
/**
* Takes an array of ints representing the Unicode characters and returns 
* a UTF-8 string. Astral planes are supported ie. the ints in the
* input can be > 0xFFFF. Occurrances of the BOM are ignored. Surrogates
* are not allowed.
* Returns false if the input array contains ints that represent 
* surrogates or are outside the Unicode range
* and raises a PHP error at level E_USER_WARNING
* Note: this function has been modified slightly in this library to use
* output buffering to concatenate the UTF-8 string (faster) as well as
* reference the array by it's keys
* @param array of unicode code points representing a string
* @return mixed UTF-8 string or FALSE if array contains invalid code points
* @author <hsivonen@iki.fi>
* @see utf8_to_unicode
* @see http://hsivonen.iki.fi/php-utf8/
* @package utf8
* @subpackage unicode
*/
function utf8_from_unicode($arr) {
    ob_start();
    
    foreach (array_keys($arr) as $k) {
        
        # ASCII range (including control chars)
        if ( ($arr[$k] >= 0) && ($arr[$k] <= 0x007f) ) {
            
            echo chr($arr[$k]);
        
        # 2 byte sequence
        } else if ($arr[$k] <= 0x07ff) {
            
            echo chr(0xc0 | ($arr[$k] >> 6));
            echo chr(0x80 | ($arr[$k] & 0x003f));
        
        # Byte order mark (skip)
        } else if($arr[$k] == 0xFEFF) {
            
            // nop -- zap the BOM
        
        # Test for illegal surrogates
        } else if ($arr[$k] >= 0xD800 && $arr[$k] <= 0xDFFF) {
            
            // found a surrogate
            trigger_error(
                'utf8_from_unicode: Illegal surrogate '.
                    'at index: '.$k.', value: '.$arr[$k],
                E_USER_WARNING
                );
            
            return FALSE;
        
        # 3 byte sequence
        } else if ($arr[$k] <= 0xffff) {
            
            echo chr(0xe0 | ($arr[$k] >> 12));
            echo chr(0x80 | (($arr[$k] >> 6) & 0x003f));
            echo chr(0x80 | ($arr[$k] & 0x003f));
        
        # 4 byte sequence
        } else if ($arr[$k] <= 0x10ffff) {
            
            echo chr(0xf0 | ($arr[$k] >> 18));
            echo chr(0x80 | (($arr[$k] >> 12) & 0x3f));
            echo chr(0x80 | (($arr[$k] >> 6) & 0x3f));
            echo chr(0x80 | ($arr[$k] & 0x3f));
            
        } else {
            
            trigger_error(
                'utf8_from_unicode: Codepoint out of Unicode range '.
                    'at index: '.$k.', value: '.$arr[$k],
                E_USER_WARNING
                );
            
            // out of range
            return FALSE;
        }
    }
    
    $result = ob_get_contents();
    ob_end_clean();
    return $result;
}

//--------------------------------------------------------------------
/**
* Unicode aware replacement for strlen(). Returns the number
* of characters in the string (not the number of bytes), replacing
* multibyte characters with a single byte equivalent
* utf8_decode() converts characters that are not in ISO-8859-1
* to '?', which, for the purpose of counting, is alright - It's
* much faster than iconv_strlen
* Note: this function does not count bad UTF-8 bytes in the string
* - these are simply ignored
* @author <chernyshevsky at hotmail dot com>
* @link   http://www.php.net/manual/en/function.strlen.php
* @link   http://www.php.net/manual/en/function.utf8-decode.php
* @param string UTF-8 string
* @return int number of UTF-8 characters in string
* @package utf8
* @subpackage strings
*/
function utf8_strlen($str){
    return strlen(utf8_decode($str));
}


//--------------------------------------------------------------------
/**
* UTF-8 aware alternative to strpos
* Find position of first occurrence of a string
* Note: This will get alot slower if offset is used
* Note: requires utf8_strlen amd utf8_substr to be loaded
* @param string haystack
* @param string needle (you should validate this with utf8_is_valid)
* @param integer offset in characters (from left)
* @return mixed integer position or FALSE on failure
* @see http://www.php.net/strpos
* @see utf8_strlen
* @see utf8_substr
* @package utf8
* @subpackage strings
*/
function utf8_strpos($str, $needle, $offset = NULL) {
    
    if ( is_null($offset) ) {
    
        $ar = explode($needle, $str);
        if ( count($ar) > 1 ) {
            return utf8_strlen($ar[0]);
        }
        return FALSE;
        
    } else {
        
        if ( !is_int($offset) ) {
            trigger_error('utf8_strpos: Offset must be an integer',E_USER_ERROR);
            return FALSE;
        }
        
        $str = utf8_substr($str, $offset);
        
        if ( FALSE !== ( $pos = utf8_strpos($str, $needle) ) ) {
            return $pos + $offset;
        }
        
        return FALSE;
    }
    
}

//--------------------------------------------------------------------
/**
* UTF-8 aware alternative to strrpos
* Find position of last occurrence of a char in a string
* Note: This will get alot slower if offset is used
* Note: requires utf8_substr and utf8_strlen to be loaded
* @param string haystack
* @param string needle (you should validate this with utf8_is_valid)
* @param integer (optional) offset (from left)
* @return mixed integer position or FALSE on failure
* @see http://www.php.net/strrpos
* @see utf8_substr
* @see utf8_strlen
* @package utf8
* @subpackage strings
*/
function utf8_strrpos($str, $needle, $offset = NULL) {
    
    if ( is_null($offset) ) {
    
        $ar = explode($needle, $str);
        
        if ( count($ar) > 1 ) {
            // Pop off the end of the string where the last match was made
            array_pop($ar);
            $str = join($needle,$ar);
            return utf8_strlen($str);
        }
        return FALSE;
        
    } else {
        
        if ( !is_int($offset) ) {
            trigger_error('utf8_strrpos expects parameter 3 to be long',E_USER_WARNING);
            return FALSE;
        }
        
        $str = utf8_substr($str, $offset);
        
        if ( FALSE !== ( $pos = utf8_strrpos($str, $needle) ) ) {
            return $pos + $offset;
        }
        
        return FALSE;
    }
    
}

//--------------------------------------------------------------------
/**
* UTF-8 aware alternative to substr
* Return part of a string given character offset (and optionally length)
* Note: supports use of negative offsets and lengths but will be slower
* when doing so
* @param string
* @param integer number of UTF-8 characters offset (from left)
* @param integer (optional) length in UTF-8 characters from offset
* @return mixed string or FALSE if failure
* @package utf8
* @subpackage strings
*/
function utf8_substr($str, $offset, $length = NULL) {
    
    if ( $offset >= 0 && $length >= 0 ) {
    
        if ( $length === NULL ) {
            $length = '*';
        } else {
            if ( !preg_match('/^[0-9]+$/', $length) ) {
                trigger_error('utf8_substr expects parameter 3 to be long', E_USER_WARNING);
                return FALSE;
            }
            
            $strlen = strlen(utf8_decode($str));
            if ( $offset > $strlen ) {
                return '';
            }
            
            if ( ( $offset + $length ) > $strlen ) {
               $length = '*';
            } else {
                $length = '{'.$length.'}';
            }
        }
        
        if ( !preg_match('/^[0-9]+$/', $offset) ) {
            trigger_error('utf8_substr expects parameter 2 to be long', E_USER_WARNING);
            return FALSE;
        }
        
        $pattern = '/^.{'.$offset.'}(.'.$length.')/us';
        
        preg_match($pattern, $str, $matches);
        
        if ( isset($matches[1]) ) {
            return $matches[1];
        }
        
        return FALSE;
    
    } else {
        
        // Handle negatives using different, slower technique
        // From: http://www.php.net/manual/en/function.substr.php#44838
        preg_match_all('/./u', $str, $ar);
        if( $length !== NULL ) {
            return join('',array_slice($ar[0],$offset,$length));
        } else {
            return join('',array_slice($ar[0],$offset));
        }
    }
}

//---------------------------------------------------------------
/**
* UTF-8 aware alternative to strtolower
* Make a string lowercase
* Note: The concept of a characters "case" only exists is some alphabets
* such as Latin, Greek, Cyrillic, Armenian and archaic Georgian - it does
* not exist in the Chinese alphabet, for example. See Unicode Standard
* Annex #21: Case Mappings
* Note: requires utf8_to_unicode and utf8_from_unicode
* @author Andreas Gohr <andi@splitbrain.org>
* @param string
* @return mixed either string in lowercase or FALSE is UTF-8 invalid
* @see http://www.php.net/strtolower
* @see utf8_to_unicode
* @see utf8_from_unicode
* @see http://www.unicode.org/reports/tr21/tr21-5.html
* @see http://dev.splitbrain.org/view/darcs/dokuwiki/inc/utf8.php
* @package utf8
* @subpackage strings
*/
function utf8_strtolower($string){
    global $UTF8_UPPER_TO_LOWER;
    
    $uni = utf8_to_unicode($string);
    if ( !$uni ) {
        return FALSE;
    }
    
    $cnt = count($uni);
    for ($i=0; $i < $cnt; $i++){
        if ( isset($UTF8_UPPER_TO_LOWER[$uni[$i]]) ) {
            $uni[$i] = $UTF8_UPPER_TO_LOWER[$uni[$i]];
        }
    }

    return utf8_from_unicode($uni);
}
