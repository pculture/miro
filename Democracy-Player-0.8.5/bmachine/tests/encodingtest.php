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

class EncodingTest extends BMTestCase {

  var $textfiles = array();

  function EncodingTest() {
    $this->BMTestCase();
    $this->textfiles = array("frenchtext.txt", "utftext.txt", "utftitle.txt", "utf8demo.txt");
  }

  function EncodeAndDecode($file, $do_html = false, $do_strip = false ) {
    
    $data = array();
    $text = file_get_contents($file);
    
    if ( $do_strip == true ) {
      $text = encode($text);
    }
    else if ( $do_html == true ) {
      $text = html_encode_utf8($text);
    }
    $data["test text"] = $text;
    
    $encoded = bencode($data);
    
    $decoded = bdecode($encoded);
    $decoded = $decoded["test text"];
    
    return $decoded == $text;
  }
  
  function TestUTFEncode() {
    $this->assertTrue(setup_data_directories(false), "Couldn't setup data dirs");
    foreach( $this->textfiles as $file ) {
      $file = "tests/$file";
      $result = $this->EncodeAndDecode($file, true);
      $this->assertTrue($result, "EncodingTest/TestUTFEncode: bdecoded text != original text");
    }
  }

  function TestHTMLEncode() {
    $this->assertTrue(setup_data_directories(false), "Couldn't setup data dirs");
    $result = $this->EncodeAndDecode("tests/htmltext.txt");
    $this->assertTrue($result, "EncodingTest/TestHTMLEncode: bdecoded text != original text");		
  }
	
  function TestXSS() {
    $this->assertTrue(setup_data_directories(false), "Couldn't setup data dirs");
    $result = $this->EncodeAndDecode("tests/phptext.txt", false, true);
    $this->assertTrue($result, "EncodingTest/TestXSS: bdecoded text != original text");		
  }
	
  function TestDoubleEncode() {
    foreach( $this->textfiles as $file ) {
      $file = "tests/$file";
      $utf = file_get_contents($file);
      $utf = encode($utf);
      $this->assertTrue($utf == encode($utf), "EncodingTest/TestDoubleEncode: $file failed");
    }
  }
}
?>