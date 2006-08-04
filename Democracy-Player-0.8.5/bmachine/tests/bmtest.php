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

class BMTestCase extends WebTestCase {

  var $channel_id;
  var $id;

	function BMTestCase() {
		$this->WebTestCase();
	}

  function ClearOldData() {
    global $store;
    $store->unlockAll();
    exec("rm -rf data");
  }

  function BackupData($name) {
    exec("tar cvf tests/backups/$name.tar.gz data thumbnails text publish torrents");
  }

  function RestoreDataPoint($name) {
    $this->ClearOldData();
    exec("tar xvf tests/backups/$name.tar.gz -C . ");
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
    $_SESSION['user'] = $users["unittest"];
	}
	
	function Logout() {

		global $usercookie;
		global $hashcookie;

		$this->setCookie($usercookie, "");
		$this->setCookie($hashcookie, "");	
	}
	
	function Find( $array, $key, $value ) {

		$got_it = false;

		foreach( $array as $id => $f ) {
			if ( $f[$key] == $value || $id == $value ) {
        if ( isset($f["ID"]) ) {
          return $f["ID"];
        }
        else if ( isset($f["id"]) ) {
          return $f["id"];
        }
        else if ( isset($id) ) {
          return $id;
        }

			}
		}
	
		return false;
	}

	function getContent() {
		return $this->_browser->getContentAsText();
	}
	
	function getResponseCode() {
		return $this->_browser->getResponseCode();
	}


  function BuildTestData() {

    //setup_data_directories(false);

    $this->Login();

    global $store;
    $channel_id = $store->addNewChannel( "Junky Channel" );
    $this->assertTrue( $channel_id > 0 , "didn't create channel");
    $store->unlockAll();

    $file = array();

    $file['URL'] = "http://blogfiles.wfmu.org/KF/2006/05/laughing_yogi.mpeg";
    $file['Title'] = "File & Junk Test";
    $encodedtext = file_get_contents("tests/utf8demo.txt"); // file_get_contents("tests/frenchtext.txt") . 
    $file['Description'] = "URL desc & general notes\n" . $encodedtext;
    $file['donation_id'] = 1;
    $file['People'] = array(
			    0 => "colin:did stuff & had fun",
			    1 => "colin2:did other stuff & slept a lot",
          2 => "Uppercase:not allowed in rss"
    );
    $file['Keywords'] = array(
			      0 => 'kw1',
			      1 => 'kw2');
    
    $file['post_channels'] = array($channel_id);
    set_file_defaults($file);

    global $errorstr;
    $this->assertTrue( publish_file($file) == true, "didn't publish file: $errorstr");

    $this->id = $file["ID"];
    $this->channel_id = $channel_id;
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
