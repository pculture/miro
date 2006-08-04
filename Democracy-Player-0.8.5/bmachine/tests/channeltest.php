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

class ChannelTest extends BMTestCase {
	
	function TestCreateOpenPublishPage() {

		$this->assertTrue(setup_data_directories(false), "Couldn't setup data dirs");

		$publish_url = get_base_url() . "create_channel.php";
		
		$channel = array();
		$channel['Name'] = "unit test - open to publishing" . rand(0, 10000);
		$channel['Description'] = "unit test - anyone can post to channel";
		$channel['OpenPublish'] = "on";
		$channel['Publisher'] = "unit tests, inc.";

		$this->Login();		
		$this->post( $publish_url, $channel );

		$this->assertResponse("200", "ChannelTest/TestCreateOpenPublishPage: didn't get 200 response");		

		global $store;
		$channels = $store->getAllChannels();
		$got_it = $this->Find($channels, "Name", $channel['Name']);
		$this->assertTrue( $got_it, "ChannelTest/TestCreateOpenPublishPage: didn't create channel" . $channel["Name"] );
	}

	function TestCreatePage() {

		$this->assertTrue(setup_data_directories(false), "Couldn't setup data dirs");

		$publish_url = get_base_url() . "create_channel.php";
		
		$channel = array();
		$channel['Name'] = "unit test channel" . rand(0, 10000);
		$channel['Description'] = "unit test channel - description";
		$channel['OpenPublish'] = "on";
		$channel['Publisher'] = "unit tests, inc.";

		$this->Login();		
		$this->post( $publish_url, $channel );

		$this->assertResponse("200", "ChannelTest/TestCreatePage: didn't get 200 response");		

		global $store;
		$channels = $store->getAllChannels();
		$got_it = $this->Find($channels, "Name", $channel['Name']);
		$this->assertTrue( $got_it, "ChannelTest/TestCreatePage: didn't create channel" . $channel["Name"] );
	}


	function TestCreateRequireLoginPage() {

		$this->assertTrue(setup_data_directories(false), "Couldn't setup data dirs");

		$publish_url = get_base_url() . "create_channel.php";
		
		$channel = array();
		$channel['Name'] = "unit test - require login to view" . rand(0, 10000);
		$channel['Description'] = "unit test - must be logged in to view a file";
		$channel['RequireLogin'] = "on";
		$channel['Publisher'] = "unit tests, inc.";

		$this->Login();		
		$this->post( $publish_url, $channel );

		$this->assertResponse("200", "ChannelTest/TestCreateOpenPublishPage: didn't get 200 response");		

		global $store;
		$channels = $store->getAllChannels();
		$got_it = $this->Find($channels, "Name", $channel['Name']);
		$this->assertTrue( $got_it, "ChannelTest/TestCreateRequireLoginPage: didn't create channel" . $channel["Name"] );
	}

	function TestDelete() {

		$this->assertTrue(setup_data_directories(false), "Couldn't setup data dirs");
		$this->Login();

		global $store;	
		$channels = $store->getAllChannels();
		
		foreach ( $channels as $c ) {
			if ( $c["Name"] == "unit test channel" ||
				$c["Name"] == "unit test - open to publishing" ||
				$c["Name"] == "unit test - require login to view" ) {


				$this->get(	get_base_url() . "delete.php?t=c&i=" . $c["ID"] );

        $tmp = $store->getAllChannels();
        $got_it = $this->Find($tmp, "Name", $c['Name']);
        $this->assertTrue( $got_it, "ChannelTest/TestDelete: didn't delete channel" . $c["Name"] );

			}
		}
	
	}

  function TestAddSection() {
    
  }

  function TestDeleteSection() {

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