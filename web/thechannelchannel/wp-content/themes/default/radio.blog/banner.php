<?
$soundPath = 'sounds/';
$rbsExt = '.rbs';
$rbsPath = dirname(__FILE__).'/'.$soundPath;

include($soundPath."functions.php");
$tracks = getTracks($rbsPath,$rbsExt);

function getstr($str,$char) {
    $arrStr = explode($char,$str);
    $nbStr = count($arrStr);
    if ($nbStr > 1) $returnStr = $arrStr[$nbStr-2];
    if ($nbStr == 1)$returnStr = $arrStr[0];
    
    return $returnStr;
}

function clearString($string,$replace) {
    $allowedChar = 'abcdefghijklmnopqrstuvwxyz0123456789*"';

    $strlenght = strlen($string);
    for ($i=0; $i<$strlenght; $i++) {
        if (strpos($allowedChar, $string[$i]) === false) {
            $clear .= $replace;
        }
        else {
            $clear .= $string[$i];
        }
    }
    
    return $clear;
}

function getArtist($trackName) {
      $artist = getstr($trackName,'_');
      $artist = getstr($trackName,'-');
      $artist = trim($artist);
      
      return $artist;
}

$artists = array();
if (count($tracks) > 0) {
	foreach ($tracks as $trackName) {
	        $trackName = substr($trackName,0,strrpos($trackName,'.'));
	        $artistName = getArtist($trackName);
	        if (!in_array($artistName,$artists)) $artists[] = $artistName;
	}
}


?>
<script type="text/javascript" src="banner.js"></script>

<div id="banner">

<a href="javascript:void(window.open('http://www.radioblogclub.com/?ref='+document.URL));"><img src="radioblog_80_15.gif" width="80" height="15" alt="radio.blog.club" /></a>

<form action="none">
<div class="selectMask">
<select onchange="return submitThis(this);">
<option value="">Radio.blog Search:</option> 
<?
if (count($artists) > 0) {
	asort($artists);
	foreach ($artists as $artist) {
			echo '<option value="'.clearString(strtolower($artist),"_").'">'.ucfirst($artist)."</option>\n";
	}
}
?>
</select>
</div>
</form>

<noscript>
<div>
<?
if (count($artists) > 0) {
	asort($artists);
	foreach ($artists as $artist) {
			echo '<a href="http://www.radioblogclub.com/search/0/'.clearString(strtolower($artist),"_").'">'.ucfirst($artist).'</a> ';
	}
}
?>
</div>
</noscript>

</div>