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

class PublishTest extends BMTestCase {

	function PublishTest() {
		$this->BMTestCase();
	}
  
  function TestDownloadHelpers() {

		$this->assertTrue(setup_data_directories(false), "Couldn't setup data dirs");

    $url = get_base_url() . "download.php?type=mac";
    $headers = bm_get_headers($url, true);
		$this->assertTrue($headers["content-disposition"] == "attachment; filename=BlogTorrent.zip", "PublishTest/TestUploadApps - bad mac uploader?");

    $url = get_base_url() . "download.php?type=exe";
    $headers = bm_get_headers($url, true);
		$this->assertTrue($headers["content-disposition"] == "attachment; filename=\"Broadcast_Machine_Upload.exe\"", "PublishTest/TestUploadApps - bad pc uploader?");
  }
  
	
	function TestPublishURL() {

		$this->assertTrue(setup_data_directories(false), "Couldn't setup data dirs");
			
		$file = array();
		$file['URL'] = "http://bitchell.dyndns.org/~colin/gijoepsa20.mpg";
		$file['Title'] = "URL unit test " . rand(0, 10000);
		$file['Description'] = "URL desc";
		$file['post_do_save'] = 1;

    $file['post_channels[]'] = 1;

    // donation

		global $store;
    $donations = $store->getAllDonations();
	
    // we don't encode this because the user can enter in html if they want, but we will do
    // some formatting on display, and we'll make sure it's UTF-8 happy for now
		$donation_text = "publishing donation text " . rand(0, 10000);
		$donation_email = "email" . rand(0, 10000) . "@foo.net";
		$donation_title = "random donation title " . rand(0, 10000);
		$donationhash = md5( microtime() . rand() );
		
		$donations[$donationhash]["text"] = $donation_text;	
		$donations[$donationhash]["email"] = $donation_email;	
		$donations[$donationhash]["title"] = $donation_title;	

		$store->saveDonations($donations);
		$donations = 	$store->getAllDonations();
		$this->assertTrue( isset($donations[$donationhash]), "PublishTest/TestPublishURL: save donation didn't work");
    $file['donation_id'] = $donationhash;
    

    // people/roles
    $file['People'] = "person1:role1\nperson2:role2\n";
    
    // keywords
    $file['Keywords'] = "kw1\nkw2\n";
	
		$this->Login();
		$publish_url = get_base_url() . "publish.php";

		$this->post( $publish_url, $file );
		$this->assertResponse("200", "PublishTest/TestPublishURL: didn't get 200 response");		
	
		$files = $store->getAllFiles();
		$got_it = $this->Find($files, "Title", encode($file['Title']));
		$this->assertTrue( $got_it, "PublishTest/TestPublishURL: didn't find new file");

    if ( $got_it ) {
      $this->assertTrue( $store->channelContainsFile($got_it, $store->getChannel(1) ), 
                         "PublishTest/TestPublishURL: file not in channel");

      $f = $store->getFile($got_it);
      $this->assertTrue( count($f['People']) == 2, 
                         "PublishTest/TestPublishURL: people not added?");

      $p = $f['People'][0];
      $this->assertTrue( $p[0] == "person1" && $p[1] == "role1",
                         "PublishTest/TestPublishURL: person data wrong");

      $this->assertTrue( count($f['Keywords']) == 2, 
                         "PublishTest/TestPublishURL: keywords not added?");

      $this->assertTrue( $f["Keywords"][0] == "kw1" && $f["Keywords"][1] == "kw2",
                         "PublishTest/TestPublishURL: keywords not what we expected?");

      $this->assertTrue( $f["donation_id"] == $donationhash,
                         "PublishTest/TestPublishURL: didn't get donationhash?");
    }

	}
	
  /**
   * publish a file:// url - this should give an error
   */
  function TestPublishFileURL() {

		$this->assertTrue(setup_data_directories(false), "Couldn't setup data dirs");
			
		$file = array();
		$file['URL'] = "file://funfiletest.mp3";
		$file['Title'] = "FILE unit test " . rand(0, 10000);
		$file['Description'] = "FILE desc";
		$file['post_do_save'] = 1;
	
		$this->Login();		
		$publish_url = get_base_url() . "publish.php";

		$this->post( $publish_url, $file );
		$this->assertResponse("200", "PublishTest/TestPublishFileURL: didn't get 200 response");		
    $this->assertWantedPattern("/Sorry, Broadcast Machine doesn't support/i", "PublishTest/TestPublishFileURLdidn't get error about publishing a file://");
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