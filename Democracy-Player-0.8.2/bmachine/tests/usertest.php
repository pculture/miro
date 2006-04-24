<?php
if (! defined('SIMPLE_TEST')) {
  define('SIMPLE_TEST', 'simpletest/');
}
require_once(SIMPLE_TEST . 'unit_tester.php');
require_once(SIMPLE_TEST . 'web_tester.php');
require_once(SIMPLE_TEST . 'reporter.php');

class UserTest extends BMTestCase {

	function UserTest() {
		$this->BMTestCase();
	}

	function TestAddUserAsAdmin() {
		global $store;
		
		$this->Login();
		
		$username = "usertest" . rand(0, 10000);
		$password = $username;
		$email = "$username@fake.net";

		$result = $store->addNewUser($username, $password, $email, false, false, $error);
		$this->assertTrue($result, "UserTest/TestAddUser: couldn't add user - $error");
	}

	function TestAuthUser() {

		global $store;
		
		$this->Login();
		
		$username = "usertest" . rand(0, 10000);
		$password = $username;
		$email = "$username@fake.net";

		$result = $store->addNewUser($username, $password, $email, false, false, $error);
		$this->assertTrue($result, "UserTest/TestAuthUser: couldn't add user - $error");

    $hashlink = $store->userHash( $username, $password, $email );
		$result = $store->authNewUser($hashlink, $username);
		global $errstr;
		$this->assertTrue($result, "UserTest/TestAuthUser: couldn't auth user - $errstr");
	
		$users = $store->getAllUsers();
		$this->assertTrue(isset($users[$username]), "UserTest/TestAuthUserAsUser: user $username wasn't authed");
	}

	function TestAddUserAsUser() {
		global $store;
		
		$this->Logout();
		
		$username = "usertest" . rand(0, 10000);
		$password = $username;
		$email = "$username@fake.net";

		$result = $store->addNewUser($username, $password, $email, false, false, $error);
		$this->assertTrue($result, "UserTest/TestAddUserAsUser: couldn't add user - $error");
	}

	function TestAuthUserAsUser() {
		global $store;
		
		$this->Logout();
		
		$username = "usertest" . rand(0, 10000);
		$password = $username;
		$email = "$username@fake.net";

		$result = $store->addNewUser($username, $password, $email, false, false, $error);
    //		print "try and add $username - $email<br>";
		$this->assertTrue($result, "UserTest/TestAuthUserAsUser: couldn't add user - $error");

    $hashlink = $store->userHash( $username, $password, $email );
		$result = $store->authNewUser($hashlink, $username);
		global $errstr;
		$this->assertTrue($result, "UserTest/TestAuthUserAsUser: couldn't auth user - $errstr");
		
		$users = $store->getAllUsers();
		$this->assertTrue(isset($users[$username]), "UserTest/TestAuthUserAsUser: user $username wasn't authed");
	}

	function TestUserPasswordChange() {

		global $store;

		$username = "usertest" . rand(0, 10000);
		$password = $username;
		$email = "$username@fake.net";

		$result = $store->addNewUser($username, $password, $email, false, false, $error);
		$this->assertTrue($result, "UserTest/TestAuthUserAsUser: couldn't add user - $error");

    $hashlink = $store->userHash( $username, $password, $email );
//		$hashlink = sha1( $username . $password . $email );		
		$result = $store->authNewUser($hashlink, $username);
		global $errstr;
		$this->assertTrue($result, "UserTest/TestAuthUserAsUser: couldn't auth user - $errstr");

		$newpass = "usertest" . rand(0,10000);
    $hashlink = $store->userHash( $username, $newpass, $email );
//		$hashlink = sha1( $username . $newpass . $email );		
		$store->updateUser($username, $hashlink, $email, false, false);
	
	}

  /*
	function TestUsernameChange() {

		global $store;

		$username = "usertest" . rand(0, 10000);
		$password = $username;
		$email = "$username@fake.net";

		$result = $store->addNewUser($username, $password, $email, false, false, $error);
		$this->assertTrue($result, "UserTest/TestAuthUserAsUser: couldn't add user - $error");

    $hashlink = $store->userHash( $username, $password, $email );
		$result = $store->authNewUser($hashlink, $username);
		global $errstr;
		$this->assertTrue($result, "UserTest/TestAuthUserAsUser: couldn't auth user - $errstr");

		$newuser = "usertest" . rand(101, 200);
		$store->renameUser($username, $newuser);
		
		$users = $store->getAllUsers();
		$this->assertTrue(isset($users[$newuser]), "UserTest/TestUsernameChange: user rename failed");
		$this->assertTrue(!isset($users[$username]), "UserTest/TestUsernameChange: user rename - old name still exists");
    }*/

	
	function TestRenameUser() {
		global $store;
		global $settings;

		$settings['RequireRegAuth'] = false;

		$username = "unittest" . rand(0, 10000);
		$password = $username;
		$email = "$username@foo.net";
		
		$this->assertTrue( $store->addNewUser($username, $password, $email, true, false, $error), 
                       "DataStoreTest/TestAuthUser: couldn't add user" );
    $hashlink = $store->userHash( $username, $password, $email );
		$store->authNewUser( $hashlink, $username );

		$users = $store->getAllUsers();
		$this->assertTrue( isset($users[$username]), 
                       "DataStoreTest/TestRenameUser: couldn't add user $username" );

		$username2 = "unittest" . rand(0, 10000);
		$store->renameUser($username, $username2);
			
		$users = $store->getAllUsers();
		$this->assertTrue( !isset($users[$username]) && isset($users[$username2]), 
                       "DataStoreTest/TestRenameUser: couldn't rename user from $username to $username2" );
	}

	
	function TestDeleteUser() {

		global $store;

		$username = "usertest" . rand(0, 10000);
		$password = $username;
		$email = "$username@fake.net";

		$result = $store->addNewUser($username, $password, $email, false, false, $error);
		$this->assertTrue($result, "UserTest/TestAuthUserAsUser: couldn't add user - $error");

    $hashlink = $store->userHash( $username, $password, $email );
		$result = $store->authNewUser($hashlink, $username);
		global $errstr;
		$this->assertTrue($result, "UserTest/TestAuthUserAsUser: couldn't auth user - $errstr");

		$user = $store->getUser($username);
		$this->assertTrue(isset($user), "UserTest/TestDeleteUser: user add failed");

		$store->deleteUser($username);
		
		$user = $store->getUser($username);
		$this->assertTrue(!(isset($user)), "UserTest/TestDeleteUser: user delete failed - $username");

		$store->deleteUser("fakeuser" . rand(0, 10000));
	
	}

	function TestJunkyUsernames() {
		global $store;		
		global $errstr;

		$this->Login();
		
		$username = "User Test " . rand(0, 10000);
		$password = $username;
		$email = "junkyuser" . rand(0, 10000) . "@fake.net";

		$result = $store->addNewUser($username, $password, $email, false, false, $error);
		$this->assertTrue($result, "UserTest/TestAuthUser: couldn't add user - $error");

    $hashlink = $store->userHash( $username, $password, $email );
		$result = $store->authNewUser($hashlink, $username);
		$this->assertTrue($result, "UserTest/TestAuthUser: couldn't auth user $username - $errstr");
	
		$username = trim(mb_strtolower($username));
		$user = $store->getUser($username);
		$this->assertTrue(isset($user), 
                      "UserTest/TestAuthUserAsUser: user $username ($email) wasn't authed");

		$utfname = file_get_contents("tests/utftitle.txt");
    $username = encode($utfname). rand(0,10000);
		$email = "junkyuser" . rand(0, 10000) . "@fake.net";

		//print "TEST ADDING $email - $username<br>\n";
    //print "LOWERCASED: " . trim(mb_strtolower($username)) . "<br>";
		$result = $store->addNewUser($username, $password, $email, false, false, $error);
		$this->assertTrue($result, "UserTest/TestAuthUser: couldn't add UTF user - $error");
	  $hashlink = $store->userHash( $username, $password, $email );

		$result = $store->authNewUser($hashlink, $username);
		$this->assertTrue($result, "UserTest/TestAuthUser: couldn't auth UTF user - $errstr");
		
		$result = login($username, $password, $error, false);
		$this->assertTrue($result, 
                      "UserTest/TestAuthUser: UTF user $username ($email) couldnt log in - $error");

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