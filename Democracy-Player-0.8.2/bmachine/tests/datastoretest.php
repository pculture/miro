<?php
if (! defined('SIMPLE_TEST')) {
  define('SIMPLE_TEST', 'simpletest/');
}
require_once(SIMPLE_TEST . 'unit_tester.php');
require_once(SIMPLE_TEST . 'web_tester.php');
require_once(SIMPLE_TEST . 'reporter.php');

class DataStoreTest extends BMTestCase {

  function DataStoreTest($email) {

		if ( $email != "" ) {
			$this->email = $email;
		}
		else {
			$this->email = "fake@fake.net";
		}
  }


  /**
   * test the global setup function
   */
  function TestSetup() {
    $this->assertTrue(setup_data_directories(), "Couldn't setup data dirs");

    global $data_dir;
    global $torrents_dir;

    $this->assertTrue(file_exists($data_dir));
    $this->assertTrue(file_exists($torrents_dir));
  }

  /**
   * test getting the type of datastore (we will need to test both mysql/flat at some point
   */
  function TestGetType() {

    $this->assertTrue(setup_data_directories(), "Couldn't setup data dirs");

    global $store;
    $v = $store->type();
    $this->assertTrue(isset($v), "DataStoreTest/TestGetType - no type");
  }

  /**
   * test the settings load/save functions
   */
  function TestSettings() {

    debug_message("DataStoreTest/TestSettings");
    $this->assertTrue(setup_data_directories(), "Couldn't setup data dirs");

    global $store;
    global $settings;

    $this->assertTrue( $store->layer->loadSettings() );
    $this->assertTrue( $settings, "DataStoreTest/TestSettings: Didn't load settings");
    $this->assertTrue( $store->layer->saveSettings($settings), "DataStoreTest/TestSettings: Can't Save Settings" );
  }


	/**
	 * test the users load/save functions
	 */
  function TestUsers() {

    debug_message("DataStoreTest/TestUsers");

    $this->assertTrue(setup_data_directories(false), "Couldn't setup data dirs");
    
    global $settings;
    global $store;

    $users = $store->getAllUsers();
    if ( isset($users["unittest"]) ) {
      $this->assertTrue($store->deleteUser("unittest"), "couldn't delete user");
	    $users = $store->getAllUsers();
      $this->assertTrue(!isset($users["unittest"]), "deleted user unittest, but they still exist");
    }
	
    $settings['AllowRegistration'] = true;
		$result = $store->addNewUser( "unittest",  "unittest", $this->email, true, false, $error );
    $this->assertTrue( $result, $error );

    $this->assertTrue( $store->deleteUser("unittest") );
    $users = $store->getAllUsers();
    $this->assertTrue(!isset($users["unittest"]));
  }

	/**
	 * test our login form
	 */
  function TestLogin() {

    debug_message("DataStoreTest/TestLogin");

    $this->assertTrue(setup_data_directories(false), "Couldn't setup data dirs");
    
    global $settings;
    global $store;

    $settings['AllowRegistration'] = true;
    $settings['RequireRegAuth'] = false;
    $result = $store->addNewUser( "unittest",  "unittest", $this->email, true, false, $error );
    $this->assertTrue($result, $error);

    $login_url = get_base_url() . "login.php";
    $this->get($login_url);

    $this->setField("username", "unittest");
    $this->setField("password", "unittest");
    $this->clickSubmit("Login >>");

    $this->get( get_base_url() . "admin.php" );
  }


	/**
	 * test our user-loading function
	 */
  function TestGetUsers() {

    debug_message("DataStoreTest/TestGetUsers");
    $this->assertTrue(setup_data_directories(false), "Couldn't setup data dirs");

    global $store;
    $this->assertTrue( is_array($store->getAllUsers())  );
  }
  

	function TestDeleteChannel() {

    debug_message("DataStoreTest/TestDeleteChannel");
		global $store;
		
		$channels = $store->getAllChannels();
		
		foreach ( $channels as $c ) {
			if ( $c["Name"] == "unit test channel" ||
				$c["Name"] == "unit test - open to publishing" ||
				$c["Name"] == "unit test - require login to view" ) {

				$count = count( $store->getAllChannels() );

				$store->DeleteChannel($c['ID']);
				$this->assertTrue( count($store->getAllChannels()) + 1 == $count, "DataStoreTest/TestDeleteChannel: didnt delete channel: " . $c["Name"] );
			}
		}	
	}


	function TestDeleteFile() {

    debug_message("DataStoreTest/TestDeleteFile");
		global $store;	
		$files = $store->getAllFiles();
		
		foreach ($files as $filehash => $f) {
			if ( beginsWith($f["Title"], "unit test" ) ) {
				$count = count($store->getAllFiles());
				$store->DeleteFile($filehash);
				$this->assertTrue( count($store->getAllFiles()) + 1 == $count, "DataStoreTest/TestDeleteFile: didnt delete file" . $f["Title"] );
			}
		}
	
	}

  function TestGetAllDonations() {
		global $store;
    debug_message("DataStoreTest/TestGetAllDonations");
		$store->getAllDonations();
  }

  /*  function TestSaveDonations() {

		global $store;
    debug_message("DataStoreTest/TestSaveDonations");
		$donations = $store->getAllDonations();
	
		// we don't encode this because the user can enter in html if they want, but we will do
		// some formatting on display, and we'll make sure it's UTF-8 happy for now
		$donation_text = "random donation text " . rand(0, 10000);
		$donation_email = "email" . rand(0, 10000) . "@foo.net";
		$donation_title = "random donation title " . rand(0, 10000);
		$donationhash = md5( microtime() . rand() );
		
		$donations[$donationhash]["text"] = $donation_text;	
		$donations[$donationhash]["email"] = $donation_email;	
		$donations[$donationhash]["title"] = $donation_title;	

		$store->saveDonations($donations);

		$donations = 	$store->getAllDonations();
		$this->assertTrue( isset($donations[$donationhash]), "DataStoreTest/TestSaveDonations: save didn't work");

    debug_message("DataStoreTest/TestSaveDonations done");
  }
	*/

	function TestAddNewChannel() {
		global $store;

    $channel_id = $store->addNewChannel( "Junky Channel" );
		$channel = $store->getChannel($channel_id);

		$this->assertTrue( isset($channel), "DataStoreTest/TestAddNewChannel: couldn't load channel" );
		$this->assertTrue( $channel['ID'] == $channel_id && $channel["Name"] == "Junky Channel", 
			"DataStoreTest/TestAddNewChannel: didn't load channel data" );

	}
	
	function TestStoreChannel() {
		global $store;

    $channel_id = $store->addNewChannel( "Junky Channel: TestStoreChannel" );
		$channel = $store->getChannel($channel_id);
		$this->assertTrue( isset($channel), "DataStoreTest/TestStoreChannel: couldn't load channel" );
		
		$channel['Name'] = "TestStoreChannel" . rand(0, 10000);
		$store->saveChannel($channel);

		$channel2 = $store->getChannel($channel_id);

		$this->assertTrue( $channel["Name"] == $channel2["Name"], "DataStoreTest/TestStoreChannel: getChannel didn't return expected data" );	
		$this->assertTrue( $channel['ID'] == $channel2['ID'] && $channel2['ID'] == $channel_id, "DataStoreTest/TestStoreChannel: channel IDs don't match" );	

	}
	
	function TestStoreChannels() {
		global $store;

    $channel_id = $store->addNewChannel( "Junky Channel: TestStoreChannel" );
		$channels = $store->getAllChannels();
		
		$channel = $channels[$channel_id];
		$this->assertTrue( isset($channel), "DataStoreTest/TestStoreChannel: couldn't load channel" );
		
		$channel['Name'] = "TestStoreChannel" . rand(0, 10000);
//		$channels[$channel_id] = $channel;
		$store->saveChannel($channel);

		$channel2 = $store->getChannel($channel_id);

		$this->assertTrue( $channel["Name"] == $channel2["Name"], "DataStoreTest/TestStoreChannel: getChannel didn't return expected data" );	
	}

	function TestDeleteUser() {

    $this->assertTrue(setup_data_directories(false), "Couldn't setup data dirs");
    
    global $settings;
    global $store;

    $users = $store->getAllUsers();

    if ( isset($users["unittest"]) ) {
      $this->assertTrue($store->deleteUser("unittest"), "DataStoreTest/TestDeleteUser: couldn't delete pre-existing user");
	    $users = $store->getAllUsers();
      $this->assertTrue(!isset($users["unittest"]), "DataStoreTest/TestDeleteUser: deleted user, but they still exist");
    }
	
    $settings['AllowRegistration'] = true;
    $this->assertTrue( $store->addNewUser( "unittest",  "unittest", $this->email, true, false, $error ), $error);

    $this->assertTrue( $store->deleteUser("unittest"), "DataStoreTest/TestDeleteUser: couldn't delete user" );
		$users = $store->getAllUsers();
		$this->assertTrue(!isset($users["unittest"]), "DataStoreTest/TestDeleteUser: deleted user, but they still exist (2)");
	}

/*
	function TestAddNewUser() {
		global $store;
		$username = "unittest" . rand(0, 10000);
		$password = $username;
		$email = "$username@foo.net";
		
		$this->assertTrue( $store->addNewUser($username, $password, $email, true, false, $error), "DataStoreTest/TestAddNewUser: couldn't add user: $error" );
	
	}*/
	
	function TestAuthUser() {
    global $store;
		global $settings;
		
		$oldsetting = $settings['RequireRegAuth'];

		$settings['RequireRegAuth'] = true;
		$_SESSION['user'] = '';

		$username = "unittest" . rand(0, 10000);
		$password = $username;
		$email = "$username@foo.net";
		
		$this->assertTrue( $store->addNewUser($username, $password, $email, true, false, $error), "DataStoreTest/TestAuthUser: couldn't add user" );

    $hashlink = $store->userHash( $username, $password, $email );
    $this->assertTrue( $store->authNewUser( $hashlink, $username), "DataStoreTest/TestAuthUser: couldn't auth user" );	

	}


	function TestUpdateUser() {
		global $store;

		$username = "unittest" . rand(0, 10000);
		$password = $username;
		$email = "$username@foo.net";
		
		$this->assertTrue( $store->addNewUser($username, $password, $email,true, false, $error), "DataStoreTest/TestUpdateUser: couldn't add user" );

		$newemail = "new$username@foo.net";
		$newhash = "newhash";
		
    $hashlink = $store->userHash( $username, $password, $email );
    $this->assertTrue( $store->authNewUser( $hashlink, $username), "DataStoreTest/TestUpdateUser: couldn't auth user" );	

		$store->updateUser( $username, $newhash, $newemail, false, false, false);
		
		$newuser = $store->getUser($username);
		$this->assertTrue(isset($newuser), "DataStoreTest/TestUpdateUser: user missing?");	
		$this->assertTrue(isset($newuser['Email']) && $newuser['Email'] == $newemail, "DataStoreTest/TestUpdateUser: email didn't update");
		$this->assertTrue(isset($newuser['Email']) && $newuser['Hash'] == $newhash, "DataStoreTest/TestUpdateUser: hash didn't update");		
	}

	function PublishTorrent() {
		global $torrents_dir;
		if ( !file_exists( $torrents_dir . "/test.torrent" ) ) {
			copy("tests/test.torrent", $torrent_dir . "/test.torrent");
		}
		$file['Title'] = "torrent test " . rand(0, 10000);
		$file['Description'] = "torrent test description";
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