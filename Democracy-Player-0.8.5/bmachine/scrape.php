<?php
include_once "include.php";

error_reporting(1);

/**
 * FBT2 - Flippy's BitTorrent Tracker v2 (GPL)
 * http://www.torrentz.com/fbt.html
 * flippy `at` ameritech `dot` net
 */

$time = intval((time() % 7680) / 60);

function getstat($file) {

  global $time;

  $handle = fopen($file, "rb+");
  flock($handle, LOCK_EX);
  $x = fread($handle, filesize($file));
  $no_peers = intval(strlen($x) / 7);

  for($j=0;$j<$no_peers;$j++) {

    $t_peer_seed = join('', unpack("C", substr($x, $j * 7, 1)));

    if($t_peer_seed >= 128) {
      $complete++;
      $t_time = $t_peer_seed - 128;
    }
    else {
      $incomplete++;
      $t_time = $t_peer_seed;
    }
    if($time - 40 <= $t_time && $time >= $t_time || $time + 88 < $t_time) {
      $new_data .= substr($x, $j * 7, 7);
    }
  }

  if($complete + $incomplete > 0) {
    $o .= '20:' . pack("H*", $file) . 'd8:completei' . (int)$complete . 'e10:incompletei' . (int)$incomplete . 'ee';
  }
  
  rewind($handle);
  ftruncate($handle, 0);
  fwrite($handle, $new_data);
  flock($handle, LOCK_UN);
  fclose($handle);
  return $o;
}


if($_GET['info_hash']) {

  echo 'd5:filesd';

  $info_hash = $_GET['info_hash'];

  if(strlen($info_hash) != 20) {
    $info_hash = stripcslashes($_GET['info_hash']);
  }

  if(strlen($info_hash) != 20) {
    er('Invalid info_hash');
  }

  $info_hash = bin2hex($info_hash);
  echo getstat($info_hash);
  die('ee');
}
else {

  global $data_dir;

  if(file_exists( $data_dir . '/scrape') && filemtime( $data_dir . '/scrape') > (time() - 60)) {
    readfile( $data_dir . '/scrape');
    die();
  }
  else {
    $o = 'd5:filesd';

    $handle = opendir($data_dir);
    while (false !== ($file = readdir($handle))) {
      if(strlen($file) == 40) {
	$o .= getstat( $data_dir . "/" . $file);
      }
    }

    closedir($handle);

    $o .= 'ee';

    $handle1 = fopen($data_dir . '/scrape', "wb");
    
    flock($handle1, LOCK_EX);
    fwrite($handle1, $o);
    flock($handle1, LOCK_UN);
    fclose($handle1);
    die($o);
  }
}

?>