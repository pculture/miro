<?php
if (! defined('SIMPLE_TEST')) {
  define('SIMPLE_TEST', 'simpletest/');
}
require_once(SIMPLE_TEST . 'unit_tester.php');
require_once(SIMPLE_TEST . 'web_tester.php');
require_once(SIMPLE_TEST . 'reporter.php');

class EncodingTest extends BMTestCase {

  function EncodingTest() {
		$this->BMTestCase();
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
		$result = $this->EncodeAndDecode("tests/utftext.txt", true);
    $this->assertTrue($result, "EncodingTest/TestUTFEncode: bdecoded text != original text");		
  }
/*
  function TestUTFChannel() {

    $this->assertTrue(setup_data_directories(false), "Couldn't setup data dirs");

		$utftitle = file_get_contents("tests/utftitle.txt");
		$utftext = file_get_contents("tests/utftext.txt");

		$publish_url = get_base_url() . "create_channel.php";
		
		$channel = array();
		$channel['post_title'] = "unit test " . rand(0, 10000) . ": " . $utftitle;
		$channel['post_description'] = $utftext;
		$channel['post_use_auto'] = 1;

		$this->Login();
		$this->post( $publish_url, $channel );

		$this->assertResponse("200", "EncodingTest/TestUTFChannel: didn't get 200 response");		

		global $store;
		$channels = $store->getAllChannels();
		
		$got_it = $this->Find($channels, "Name", encode($channel['post_title']) );
		$this->assertTrue( $got_it, "EncodingTest/TestUTFChannel: didn't find new channel - " . $channel['post_title']);
  }

  function TestUTFDonation() {
debug_message("TestUTFDonation");
    $this->assertTrue(setup_data_directories(false), "Couldn't setup data dirs");

		$utftitle = file_get_contents("tests/utftitle.txt");
		$utftext = file_get_contents("tests/utftext.txt");

		$publish_url = get_base_url() . "donation.php";
		
		$donation = array();
		$donation['donation_title'] = "unit test " . rand(0, 10000) . ": " . $utftitle;
		$donation['donation_text'] = $utftext;

		$this->Login();		
		$this->post( $publish_url, $donation );

		$this->assertResponse("200", "EncodingTest/TestUTFDonation: didn't get 200 response");		

		global $store;
		$donations = $store->getAllDonations();
		$got_it = $this->Find($donations, "title", encode($donation['donation_title']));
		$this->assertTrue( $got_it, "EncodingTest/TestUTFDonation: didn't find new donation" . $donation['donation_title']);
debug_message("TestUTFDonation - done");
  }
	
	function TestUTFFile() {

    $this->assertTrue(setup_data_directories(false), "Couldn't setup data dirs");

		$utftitle = file_get_contents("tests/utftitle.txt");
		$utftitle = $utftitle;

		$utftext = file_get_contents("tests/utftext.txt");
		$utftext = $utftext;
		
		$file = array();
		$file['post_file_url'] = "http://www.archive.org/download/AHTheManWhoKnewTooMuch1934/AHTheManWhoKnewTooMuch1934_256kb.mp4";
		$file['post_title'] = "unit test " . rand(0, 10000) . ": " . $utftitle;
		$file['post_desc'] = $utftext;
		$file['post_do_save'] = 1;

		$this->Login();
		$publish_url = get_base_url() . "publish.php";
		$this->post( $publish_url, $file );

		$this->assertResponse("200", "EncodingTest/TestUTFFile: didn't get 200 response");		

		global $store;
		$files = $store->getAllFiles();
		$got_it = $this->Find($files, "Title", encode($file['post_title']));
		$this->assertTrue( $got_it, "EncodingTest/TestUTFFile: didn't find new file - " . encode($file['post_title']) );
		
//		print_r($file);
	}

  function TestUTFSettings() {

    $this->assertTrue(setup_data_directories(false), "Couldn't setup data dirs");

		$utftitle = file_get_contents("tests/utftitle.txt");
		$utftext = file_get_contents("tests/utftext.txt");

		$publish_url = get_base_url() . "settings.php";
		
		global $settings;
		$tmp['title'] = $utftitle;
		$tmp['description'] = $utftext;

		$this->Login();		
		$this->post( $publish_url, $tmp );

		$this->assertResponse("200", "EncodingTest/TestUTFSettings: didn't get 200 response");		

		global $store;
		$store->layer->loadSettings();
		
		$this->assertTrue( encode($utftitle) == $settings['title'], "EncodingTest/TestUTFSettings: settings didn't match");
  }
*/
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
    $utf = file_get_contents("tests/utftext.txt");
    $utf = encode($utf);
    
    $this->assertTrue($utf == encode($utf), "EncodingTest/TestDoubleEncode: failed");
    
    //		print "<br><br>" . $utf . "<hr>" . encode($utf) . "<br><br>";
  }
}
?>