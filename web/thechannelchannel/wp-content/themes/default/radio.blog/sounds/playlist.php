<?
$rbsExt = '.rbs';
$rbsPath = dirname(__FILE__);
include("functions.php");
$tracks = getTracks($rbsPath,$rbsExt);

$webPath = webPath();


header ("Content-type: text/xml");
echo "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n";
echo "<tracks>\n";
if (count($tracks) > 0) {
    krsort($tracks);
	#asort($tracks); // REMOVE THE # TO SORT YOUR PLAYLIST ALPHABETICALLY
	foreach ($tracks as $trackMod => $track) {
        $trackName = substr($track,0,strrpos($track,'.'));
		echo "<track trackMod=\"".$trackMod."\" title=\"".$trackName."\" path=\"".$webPath.$track."\"/>\n";
	}
}

echo "</tracks>";
?>