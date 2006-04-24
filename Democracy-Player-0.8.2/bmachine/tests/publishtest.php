<?php
if (! defined('SIMPLE_TEST')) {
  define('SIMPLE_TEST', 'simpletest/');
}
require_once(SIMPLE_TEST . 'unit_tester.php');
require_once(SIMPLE_TEST . 'web_tester.php');
require_once(SIMPLE_TEST . 'reporter.php');
require_once('bmtest.php');

class PublishTest extends BMTestCase {

	function PublishTest() {
		$this->BMTestCase();
	}
	
	function TestPublishURL() {

		$this->assertTrue(setup_data_directories(false), "Couldn't setup data dirs");
			
		$file = array();
		$file['URL'] = "http://lovelylittlegirls.com/z/fluvial-origine_des_femmes.mp3";
		$file['Title'] = "URL unit test " . rand(0, 10000);
		$file['Description'] = "URL desc";
		$file['post_do_save'] = 1;
	
		$this->Login();		
		$publish_url = get_base_url() . "publish.php";

		$this->post( $publish_url, $file );

    //print "CODE: " . $this->_browser->getResponseCode() . "<br>";
		$this->assertResponse("200", "PublishTest/TestPublishURL: didn't get 200 response");		
	
		global $store;
		$files = $store->getAllFiles();
		$got_it = $this->Find($files, "Title", encode($file['Title']));
		$this->assertTrue( $got_it, "PublishTest/TestPublishURL: didn't find new file");
	}



	function TestPublishURLWithSpaces() {

		$this->assertTrue(setup_data_directories(false), "Couldn't setup data dirs");
		
		if ( !file_exists("test file.mp3") ) {
			copy("tests/testfile.mp3", "test file.mp3");
		}
		$file = array();
		$file['URL'] = get_base_url() . "test file.mp3";
		$file['Title'] = "unit test - URL with a space" . rand(0, 10000);
		$file['Description'] = "unit test - URL with a space";
		$file['post_do_save'] = 1;
	
		$this->Login();		
		$publish_url = get_base_url() . "publish.php";
		$this->post( $publish_url, $file );
	
		$this->assertResponse("200", "PublishTest/TestPublishURLWithSpaces: didn't get 200 response");		
	
		global $store;
		$files = $store->getAllFiles();
		$got_it = $this->Find($files, "Title", encode($file['Title']));
		$this->assertTrue( $got_it, "PublishTest/TestPublishURLWithSpaces: didn't find new file");

	}

	function TestPublishBadURLHost() {

		$this->assertTrue(setup_data_directories(false), "Couldn't setup data dirs");
			
		$file = array();
		$file['URL'] = "http://www.junkjunknudsaasd.fake/download/AHTheManWhoKnewTooMuch1934/AHTheManWhoKnewTooMuch1934_256kb.mp4";
		$file['Title'] = "URL unit test " . rand(0, 10000);
		$file['Description'] = "URL desc";
		$file['post_do_save'] = 1;
	
		$this->Login();		
		$publish_url = get_base_url() . "publish.php";
		$this->post( $publish_url, $file );
	
		$this->assertResponse("200", "PublishTest/TestPublishBadURLHost: didn't get 200 response");		
	
		global $store;
		$files = $store->getAllFiles();
		$got_it = $this->Find($files, "Title", encode($file['Title']));
		$this->assertFalse( $got_it, "PublishTest/TestPublishBadURLHost: file was published but shouldn't be");
	}

	function TestPublishBadURL() {

		$this->assertTrue(setup_data_directories(false), "Couldn't setup data dirs");
			
		$file = array();
		$file['URL'] = get_base_url() . "file_that_does_not_exist.mp3";
		$file['Title'] = "URL unit test " . rand(0, 10000);
		$file['Description'] = "URL desc";
		$file['post_do_save'] = 1;
	
		$this->Login();		
		$publish_url = get_base_url() . "publish.php";
		$this->post( $publish_url, $file );
	
		$this->assertResponse("200", "PublishTest/TestPublishBadURL: didn't get 200 response");		
	
		global $store;
		$files = $store->getAllFiles();
		$got_it = $this->Find($files, "Title", encode($file['Title']));
		$this->assertFalse( $got_it, "PublishTest/TestPublishBadURL: file was published but shouldn't be");
	}


	function TestEdit() {
		// need to write a better version of this
	}

	function TestDelete() {

		$this->Logout();
		$this->Login();

		global $store;	
		$files = $store->getAllFiles();
		
		foreach ($files as $filehash => $f) {
			if ( beginsWith($f["Title"], "unit test" ) ) {

				$this->get(	get_base_url() . "delete.php?t=v&i=" . $filehash );

        global $store;

        //        clearstatcache();
        $files2 = $store->getAllFiles();
        $got_it = $this->Find($files2, "Title", $f['Title']);

				$this->assertTrue( !$got_it, "didnt delete file" . $f["Title"] );
			}
		}
	
	}
}


/*
 * Local variables:
 * tab-width: 2
 * c-basic-offset: 2
 * indent-tabs-mode: nil
 * End:
 */

?>