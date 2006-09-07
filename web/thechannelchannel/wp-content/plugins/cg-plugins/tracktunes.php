<?
/* tracktunes.php
Enhanced by David Chait for CHAITGEAR @ http://www.chait.net
- table-based listing, with playtime
- added 'security' to the inclusion/use of the file
- added passwording control
- use of $_GET superglobal
- proper initialization/testing of vars to eliminate undefined-var notices
- proper check for file before operations
- proper quoting of constants as string operators.
- new setHistory method
- new getlastartistalbum method
- tracks cache filename as a global
*/

$myPassword = ''; // set this if you want to lightly restrict access to add/set commands.

/*
// Original tracks.php information:
###########################################################################
Copyright (C) 2004 by Harper Reed
web: http://www.nata2.org
email: nata2info at nata2.org
###########################################################################

LICENSE

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License (GPL)
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

To read the license please visit http://www.gnu.org/copyleft/gpl.html

###########################################################################
*/

$tracksFilename = 'tracktunes.txt';
$myAbsPath = dirname(__FILE__).'/';
$tracksFilename = $myAbsPath.$tracksFilename;

//============================================================
if (!function_exists('safeunhtmlentities'))
{
	function safeunhtmlentities ($string)
	{
	  $trans_tbl = get_html_translation_table (HTML_ENTITIES);
	  $trans_tbl = array_flip ($trans_tbl);
	  $ret = strtr ($string, $trans_tbl);
	  return preg_replace('/&#(\d+);/me',  "chr('\\1')",  $ret);
	}
}

//a simple truncate function to make sure the track length is not out of
//control
function truncate ($string,$maxlength)
{
	if (strlen($string)<=$maxlength)
		return $string;
	else
		return substr($string,0,($maxlength-1))."...";
}

// this writes the posted info to the data file
function addHistory($track, $artist,$genre, $album)
{
	global $tracksFilename, $trackTunesDirectCall;
  $handle = fopen ($tracksFilename, "a+");
  $time = mktime();
  $line= "$track\t$album\t$artist\t$genre\t$time";
  fwrite($handle, $line ."\n");
  fclose($handle);
  if ($trackTunesDirectCall)
	  echo "Added:<br/>$track<br/>$album<br/>$artist<br/>$genre<br/>$time<br/>";
}

// this writes the posted info to the data file
function setHistory($track, $artist, $genre, $album)
{
	global $tracksFilename, $trackTunesDirectCall;
  $handle = fopen ($tracksFilename, "w+");
  $time = mktime();
  $line= "$track\t$album\t$artist\t$genre\t$time";
  fwrite($handle, $line ."\n");
  fclose($handle);
  if ($trackTunesDirectCall)
	  echo "Added:<br/>$track<br/>$album<br/>$artist<br/>$genre<br/>$time<br/>";
}

// this gets the data from the file
function gettracks($howMany=5)
{
	global $tracksFilename;
	if (file_exists($tracksFilename))
	{
    $handle = fopen ($tracksFilename, "rb");
    $contents = fread ($handle, filesize ($tracksFilename));
    $tracks = preg_split('/\n/', $contents);
    array_pop($tracks);
    $tracks = array_reverse($tracks);
    $i=0;
    foreach ($tracks as $song)
    {
      $i++;
      if ($i>$howMany) break;
      
      $song = preg_split('/\t/', $song);
      $track['title'] = $song[0];
      $track['album'] = $song[1];
      $track['artist'] = $song[2];
      $track['genre'] = $song[3];
      $track['playtime'] = $song[4];
      $songs[] = $track;
    }
    return $songs;
  }
  else
  	return null;
}

//----------
function getNowPlaying()
{
	$songs = gettracks(1);
	if ($songs) return($songs[0]);
 	return null;
}

//the function that displays the track info
function dispTracks($trunc = false, $howMany=5, $asTable=false)
{
	global $tracksFilename;
	$tracks = gettracks($howMany);
	if ($tracks !="")
	{
		$lastArtist = '';
		$lastAlbum = '';
		if ($asTable)
			echo '<table><tr class="rhead"><th width="120">Date</th><th>Song</th><th>Artist</th><th>Album</th>'."\n";
		$c=0;
		foreach ($tracks as $song)
		{
			$c++;
			$playdate = date('r'/*"F j, Y, g:i a"*/, $song['playtime']);
			$playtitle = $song['title'];
			$playartist = $song['artist'];
			$playalbum = $song['album'];
			if ($trunc)
			{
				$playtitle = truncate($playtitle,30);
				$playartist = truncate($playartist,30);
				$playalbum = truncate($playalbum,30);
			}
			
			if ($asTable)
			{
				echo '<tr class="'.(($c%2)?'rodd':'reven').'">';
				echo "<td>$playdate</td>";
				echo "<td>$playtitle</td>";
				if ($playartist==$lastArtist)
					echo "<td> </td>";
				else
					echo "<td>$playartist</td>";
				if ($playalbum==$lastAlbum)
					echo "<td> </td>";
				else
					echo "<td>$playalbum</td>";
				echo '</tr>';
			}
			else
			{
				//echo $playdate .' : ';
//				echo "<a href='#' title='".$song['title']." - ".$song['album']." - ".$song['artist']."\n".$song['genre']." - ".$playdate."'>";
				echo $playtitle;
				if ($playartist) echo " by ".$playartist;
				if ($playalbum) echo " on ".$playalbum;
//				echo "</a>";
			}
			echo "\n";
			
			$lastArtist = $playartist;
			$lastAlbum = $playalbum;
		}
		if ($asTable)
			echo '</table><br/>'."\n";
	}
	else
    	echo "The $tracksFilename file is empty or doesn't exist.";
}

// this makes inclusion of the file not automatically do anything...
if (strpos($_SERVER['REQUEST_URI'], "tracktunes.php"))
{
	$trackTunesDirectCall = true;
	
	// much-streamlined http-var grabber
	if (empty($_POST)) // itunes bloggers use GET
		$grabvars = array('add','set','pw','t','a','g','al');
	else
		$grabvars = array('Playing','pw','Title1','Artist1','Genre1','Album1');
	for ($i=0; $i<count($grabvars); $i += 1)
	{
		$getvar = $grabvars[$i];
		if (isset($$getvar)) continue;
		if (isset($_POST[$getvar]))
			$$getvar = stripslashes(safeunhtmlentities($_POST[$getvar]));
		else
		if (isset($_GET[$getvar]))
			$$getvar = stripslashes(safeunhtmlentities($_GET[$getvar]));
		else
			$$getvar = '';
		// SANITY CHECK INCOMING DATA!
		if ($$getvar) // check for bad content
			if (FALSE!==strpos($$getvar, 'http:')) // NO URIs AT ALL IN THESE COMMANDS!
				$$getvar = '';
	}
	
	$passOK = true;
	if ($myPassword)
	{
		$passOK = false;
		if ($myPassword!=$pw)
			die("Incorrect password ($pw).  Exiting.");
		else
			$passOK = true;
	}
	
	if ($set == 1)
		setHistory($t,$a,$g,$al);
	else
	if ($add == 1)
		addHistory($t,$a,$g,$al);
	else
	if (isset($Playing)) // WinAmp NowPlaying...
		addHistory($Title1, $Artist1, $Genre1, $Album1);
	else // if no param, just raw display for now
		//echo getlastartistalbum();
		dispTracks();
}

?>