<?php
/**
 * @package BMTest
 */


if (! defined('SIMPLE_TEST')) {
	define('SIMPLE_TEST', 'simpletest/');
}
require_once(SIMPLE_TEST . 'unit_tester.php');
require_once(SIMPLE_TEST . 'reporter.php');
require_once('bmtest.php');

class IncludeTest extends BMTestCase {

  function IncludeTest() {
  }

  /**
   * test version_number function
   */
  function TestGetVersionNumber() {
    $v = version_number();
    $this->assertTrue($v);
  }
  
  /**
   * test our get_version function
   */
  function TestGetVersionString() {
    $v = get_version();
    $this->assertTrue($v != "", "IncludeTest: couldn't get version string");
  }
  
  /**
   * test get_base_url
   */
  function TestGetBaseURL() {
    $url = get_base_url();
    $this->assertTrue($url != "", "IncludeTest: couldn't get base URL");
  }
  
  /**
   * test bencode and bdecode functions
   */
  function TestEncode() {
    $data = array();
    $e1 = array(
		"val1" => 1,
		"val2" => "value"
		);
    $e2 = array(
		"val1" => 2,
		"val2" => "other"
		);
    
    $data["element1"] = $e1;
    $data["element2"] = $e2;
    
    $result = bencode($data);
    $this->assertTrue($result != "");
    
    $decoded = bdecode($result);
    
    $out1 = $decoded["element1"];
    $out2 = $decoded["element2"];
    
    $this->assertTrue($out1["val1"] == 1 && $out1["val2"] == "value", "IncludeTest/TestEncode: bencode failed (1)");
    $this->assertTrue($out2["val1"] == 2 && $out2["val2"] == "other", "IncludeTest/TestEncode: bencode failed (1)");
  }
  
  function TestSiteTitle() {
    $result = site_title();
    $this->assertTrue(isset($result), "IncludeTest: couldn't get site title");
  }
  
  function TestSiteDescription() {
    $result = site_description();
    $this->assertTrue(isset($result), "IncludeTest: couldn't get site description");
  }
  
  function TestDelete() {
    $tmpfile = "data/tmpfile";
    touch($tmpfile);
    $this->assertTrue(unlink_file($tmpfile), "IncludeTest/TestDelete: couldn't delete tmpfile");
  }
  
  
  function TestURLMatch() {
    $url1 = "http://localhost/torrents/file1.mp3";
    
    $this->assertTrue( !is_local_file($url1), "IncludeTest/TestURLMatch: file doesn't exist but is_local_file says it does");
    
    global $torrents_dir;		
    $handle = opendir($torrents_dir);
    
    while (false != ($file = readdir($handle))) {
      if (($file != '.') && ($file != '..')) {
	$url1 = "http://junkydomain.com/$torrents_dir/$file";
	$this->assertTrue( is_local_file($url1), "IncludeTest/TestURLMatch: file exists but is_local_file says it doesn't");
	
	if ( endsWith( $url1, ".torrent" ) ) {
	  $this->assertTrue( is_local_torrent($url1), "IncludeTest/TestURLMatch: file is a torrent but is_local_torrent fails");					
	}
	else {
	  $this->assertTrue( !is_local_torrent($url1), "IncludeTest/TestURLMatch: file isn't a torrent but is_local_torrent suceeds");
	}
	
      }
    }
    
    closedir($handle);	
  }
 
  function TestGetHeaders() {
    ini_set('allow_url_fopen', 0);
    $headers = bm_get_headers("http://getdemocracy.com/");
    $this->assertTrue( isset($headers) && count($headers) > 0, "IncludeTest/TestGetHeaders - failed with allow_url_fopen off");

    ini_set('allow_url_fopen', 1);
    $headers = bm_get_headers("http://getdemocracy.com/");
    $this->assertTrue( isset($headers) && count($headers) > 0, "IncludeTest/TestGetHeaders - failed with allow_url_fopen on");


    // try disabling file-access:
    // https://develop.participatoryculture.org/projects/democracy/ticket/1901#preview

  }
 
  function TestPrependHTTP() {
    $urls = array(
		  "http://www.yahoo.com/image.jpg",
		  "ftp://www.yahoo.com/image.jpg",
		  "gopher://www.yahoo.com/image.gif",
		  "https://www.yahoo.com/image.png"
		  );
    foreach($urls as $url) {
      $this->assertTrue( prependHTTP($url) == $url, "$url was prepended when it shouldn't have" );
    }

    $url = "www.yahoo.com/image.jpg";
    $this->assertTrue( prependHTTP($url) == "http://$url", "$url wasn't prepended when it should have" );
  }

  function TestFolderCreation() {

    $this->assertTrue( perms_for("0777") == 0777 );
    $this->assertTrue( perms_for("0644") == 0644 );
    $this->assertTrue( perms_for(0777) == 0777 );
    $this->assertTrue( perms_for(0644) == 0644 );

    if ( file_exists("/tmp/testmake") ) {
      rmdir("/tmp/testmake");
    }
    make_folder("/tmp/testmake");
    $this->assertTrue( substr(sprintf('%o', fileperms('/tmp/testmake')), -4) == FOLDER_PERM_LEVEL );
  }

}
?>