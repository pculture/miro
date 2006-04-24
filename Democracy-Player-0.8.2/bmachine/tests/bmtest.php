<?php
if (! defined('SIMPLE_TEST')) {
  define('SIMPLE_TEST', 'simpletest/');
}
require_once(SIMPLE_TEST . 'unit_tester.php');
require_once(SIMPLE_TEST . 'web_tester.php');
require_once(SIMPLE_TEST . 'reporter.php');

class BMTestCase extends WebTestCase {

	function BMTestCase() {
		$this->WebTestCase();
	}
	
	function Login() {

	  $this->assertTrue(setup_data_directories(), "Couldn't setup data dirs");

		global $store;

		// make sure we have a unittest user
		$users = $store->getAllUsers();
		
		if ( !isset($users["unittest"]) ) {

			$user = array();
			$user["Created"] = time();
			$user["Email"] = "fake@fake.net";
			$user["Hash"] = hashpass("unittest", "unittest");
			$user["IsAdmin"] = 1;
			$user["IsPending"] = 0;
			$user["Name"] = "unittest";
			$user["Username"] = "unittest";

			$users["unittest"] = $user;
			
			$store->saveUser($user);
		}

		global $usercookie;
		global $hashcookie;

		$this->setCookie($usercookie, "unittest");
		$this->setCookie($hashcookie, hashpass("unittest", "unittest"));
	}
	
	function Logout() {

		global $usercookie;
		global $hashcookie;

		$this->setCookie($usercookie, "");
		$this->setCookie($hashcookie, "");	
	}
	
	function Find( $array, $key, $value ) {

		$got_it = false;

		foreach( $array as $f ) {
			if ( $f[$key] == $value ) {
				$got_it = true;
				break;
			}
		}
	
		return $got_it;	
	}

	function getContent() {
		return $this->_browser->getContentAsText();
	}
	
	function getResponseCode() {
		return $this->_browser->getResponseCode();
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
