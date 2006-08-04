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
require_once('bmtest.php');

class XHTMLTest extends BMTestCase {

  function XHTMLTest() {
    $this->BMTestCase();
  }

  function TestPage($url = "") {
    if ( $url != "" ) {
      /*
      $this->get($url);
      $content = $this->getContent();
      
      $file = array();
      $file['fragment'] = $content;
      */

      $check_url = "http://validator.w3.org/check?url=$url";
      $this->get($check_url);
      //$this->post( $check_url, $file );
      
      /*return*/ $this->getContent();
    }
  }
	
  function TestIndex() {
    $output = $this->TestPage(get_base_url() . "index.php");
    $this->assertWantedPattern("/This Page Is Valid XHTML/", $output );
    //$this->assertWantedPattern("/This Page Is Valid XHTML/", "XHTMLText/TestIndex: index.php didn't pass!" );	
  }
	
  function TestLibrary() {
    $this->TestPage(get_base_url() . "library.php?i=1");
    $this->assertWantedPattern("/This Page Is Valid XHTML/", "XHTMLText/TestLibrary: library.php [1] didn't pass!" );	
  }
	
  function TestDetail() {
    
    $this->assertTrue(setup_data_directories(false), "Couldn't setup data dirs");
    
    global $store;
    $files = $store->getAllFiles();
    $channels = $store->getAllChannels();
    
		
    foreach( $files as $filehash => $file ) {
      $my_channel_id = -1;
      
      foreach ($channels as $channel) {
	foreach ($channel["Files"] as $list) {
	  if ($list[0] == $filehash) {
	    $my_channel_id = $channel["ID"];
	    break;
	  }
	}
      }
      
      if ( $my_channel_id != -1 ) {
	$url = get_base_url() . "detail.php?c=" . $my_channel_id . "&amp;i=" . $filehash;
	$this->TestPage($url);
	$this->assertWantedPattern("/This Page Is Valid/", "XHTMLText/TestDetail: $url didn't pass!" );	
	break;
      }
    }
  }
  
}
?>