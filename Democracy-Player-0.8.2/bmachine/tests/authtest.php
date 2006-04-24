<?php
if (! defined('SIMPLE_TEST')) {
  define('SIMPLE_TEST', 'simpletest/');
}
require_once(SIMPLE_TEST . 'unit_tester.php');
require_once(SIMPLE_TEST . 'web_tester.php');
require_once(SIMPLE_TEST . 'reporter.php');

class AuthTest extends BMTestCase {

	var $_rand_channel = '';
	var $_rand_file = '';

	function AuthTest() {
		$this->BMTestCase();
		$_rand_channel = "unitchannel" . rand(0, 100);
		$_rand_file = "unitfile" . rand(0, 100);
	}
	
	function Login() {
	
		$this->assertTrue(setup_data_directories(false), "Couldn't setup data dirs");

		global $settings;
		global $store;

		$this->Logout();
		
		if ( isset($_SESSION['user']['Username']) ) {
			global $store;
			$users = $store->getAllUsers();
		}	

		$settings['AllowRegistration'] = true;
		$settings['RequireRegAuth'] = false;
		$users = $store->getAllUsers();
		if ( !isset($users["unittest"]) ) {
			$this->assertTrue( $store->addNewUser( "unittest",  "unittest", "fake@fake.net", true, false, $error ), $error );
		}
		$login_url = get_base_url() . "login.php";
		$this->get($login_url);
		
		$this->setField("username", "unittest");
		$this->setField("password", "unittest");
		$this->clickSubmit("Login >>");
		
		$this->get( get_base_url() . "admin.php" );

		$this->assertTrue($this->getUrl() == get_base_url() . "admin.php" );
	}
	
	function Logout() {
		$this->get( get_base_url() . "login.php?logout=1" );
	}

	function TestSetChannelAuth() {

		$this->assertTrue(setup_data_directories(false), "Couldn't setup data dirs");

		$publish_url = get_base_url() . "create_channel.php";
		
		$channel = array();
		$channel['post_title'] = $this->_rand_channel;
		$channel['post_description'] = "unit test - must be logged in to view a file";
		$channel['post_open'] = "1";
		$channel['post_publisher'] = "unit tests, inc.";

		$this->Login();		
		$this->post( $publish_url, $channel );

		$this->assertResponse("200", "ChannelTest/TestCreateOpenPublishPage: didn't get 200 response");		

		global $store;
		$channels = $store->getAllChannels();
		$got_it = $this->Find($channels, "Name", $channel['post_title']);
		$this->assertTrue( $got_it, "ChannelTest/TestCreateOpenPublishPage: didn't create channel" . $channel["post_title"] );
	}

}
?>