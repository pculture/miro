<?php
/**
 * @package BMTest
 */


if (! defined('SIMPLE_TEST')) {
  define('SIMPLE_TEST', 'simpletest/');
}
require_once(SIMPLE_TEST . 'unit_tester.php');
require_once(SIMPLE_TEST . 'web_tester.php');
require_once(SIMPLE_TEST . 'reporter.php');

class TorrentTest extends BMTestCase {

  function TorrentTest() {
    $this->BMTestCase();
  }
	
  function TestPostTorrent() {
    global $store;
    
    $this->Login();
    
    // generate the hash
    $hash = $store->getAuthHash("unittest", hashpass("unittest", "unittest") );
    
    // now post our torrent to upload.php
    $url = get_base_url() . "upload.php";
    
    $post = array();
    $post["Username"] = "unittest";
    $post["Hash"] = $hash;
    
    $upload = array();
    $u1 = array();
    $u1["key"] = "Torrent";
    $u1["content"] = file_get_contents("tests/test.torrent");
    $u1["filename"] = "test.torrent";
    $u1["mimetype"] = "application/x-bittorrent";
    $upload[] = $u1;
    
    $this->post( $url, $post, $upload );
    
    $this->assertResponse("200", "TorrentTest/TestPostTorrent: didn't get 200 response");		
    
    global $torrents_dir;
    global $data_dir;
    
    $this->assertTrue( file_exists( $torrents_dir . '/test.torrent' ), "TorrentTest/TestPostTorrent: torrent wasn't in torrent folder" );
    $this->assertTrue( file_exists( $data_dir . '/' . $hash ), "TorrentTest/TestPostTorrent: torrent hash missing" );
    
    // test for spawning here?
    
    // toss the files so we can test again
    unlink_file($torrents_dir . '/test.torrent');
    unlink_file($data_dir . '/' . $hash);
	
  }
	
  function TestCreateTorrent() {
    
  }
  
  function TestSpawnTorrent() {
    
  }
	
  function TestPauseTorrent() {
    
  }

  function TestStopTorrent() {
    
  }
  
  function TestDeleteTorrent() {
    
  }
  
  function TestGetTorrentSize() {
    
  }
  
  function TestGetTorrentPeers() {
    
  }

}
?>