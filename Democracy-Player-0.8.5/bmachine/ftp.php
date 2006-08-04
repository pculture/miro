<?
/**
 * FTP Class 
 * version 0.50
 * Copyright Raditha Dissanayake 2003
 * Licence Jabber Open Source Licence.
 *
 * vist http://www.raditha.com/ for updates.
 */

  
DEFINE (FPERM,0);
DEFINE (FINODE,1);
DEFINE (FUID,2);
DEFINE (FGID,3);
DEFINE (FSIZE,4);
DEFINE (FMONTH,5);
DEFINE (FDAY,7);
DEFINE (FTIME,7);
DEFINE (FNAME,8);

/**
 * This version of the ftp class works only with unix/linux ftp servers using
 * PASV mode. Active mode support and compatibility with IIS servers would be
 * added at a later date.
 *
 * This class does have any dependencies and you do not need to compile php 
 * with FTP support.
 *
 * I will be delighted to hear about how you have made use of this class but i 
 * have no interest in hearing about your configuration woes :-)
 *
 */
class FTP {

  var $host;
	
  var $sock;
  var $data_sock;
	
  var $errno;
  var $errstr;
  var $message;

  var $user="anonymous";
  var $pass="nobody@nobody.com";
		
  var $enable_log=1;
	
  
  /**
   * constructor
   */
  function FTP($host, $port=21)
  {
    $this->log("host = $host, $port=$port");
    $this->host = $host;
    $this->port = $port;
  }
	
  /**
   * connects to the server and returns the socket which will
   * be null if the connection failed. In which case you should
   * look at the $errno and $errstr variables.
   */
  function connect()
  {
    $this->sock = @fsockopen($this->host,$this->port,&$this->errno,&$this->errstr,30);
    @set_socket_blocking($this->sock, false);
    return $this->sock;
  }


  /**
   * will read data from the socket. Since we are using non blocking 
   * mode, if we attempt to read the data even a millisecond before 
   * it becomes available, the method just returns null.
   *
   * So what's the cure? we will loop for a while and try to read it
   * in multiple times. Note that if we used blocking mode there may
   * be instances when this function NEVER returns.
   */
  function sock_read($i=0)
  {
    $s = fgets($this->sock,4096);

    if($s=='')
      {
	if($i==10)
	  {
	    return "";
	  }
	else
	  {
	    sleep(1);
	    return $this->sock_read($i+1);
	  }
      }
    $this->log("<< $s");
    return $s;
  }
  
  /**
   * move up the directory tree
   */
  function cdup()
  {
    $this->sock_write("CDUP");
    return $this->is_ok();
  }

	
  /**
   * change working directory
   */
  function cwd($path)
  {
    $this->sock_write("CWD $path");
    return $this->check_reply("250");
  }
  
  
  /**
   * change permissions
   */
  function chmod($path, $newperm)
  {
    //print "calling chmod<br>";
    $this->sock_write("SITE CHMOD $newperm $path");
    //print "calling chmod - sent<br>";
    return $this->check_reply("250");
  }


  /**
   * create new directory
   */
  function mkd($path)
  {
    $this->sock_write("MKD $path");
    return $this->check_reply("257");
  }
	
  /*
   * remove a directory
   */
  function rmd($path)
  {
    $this->sock_write("RMD $path");
    return $this->check_reply("250");
  }

  /*
   * Deletes a file
   */
  function dele($path)
  {
    $this->sock_write("DELE $path");
    return $this->check_reply("250");
  }

  function ascii()
  {
    $this->sock_write("TYPE A");
    return $this->check_reply("200");
  }
		
  /**
   * print working directory. Returns a string that contains
   * the path to the current directory.
   */
  function pwd()
  {
    $this->sock_write("PWD");
    if($this->check_reply("257"))
      {
	$parts = split(" ",$this->message);
	return preg_replace('/\"/',"",$parts[1]);
      }
    return "";
  }
		
  /**
   * this is a hack. We are just checking if the server returns a 
   * 5xx number which indentifies an error. We assume that 
   * everything else is ok. Which may not always be true. That's 
   * some functionality which should be improved in the future.
   */
  
  function is_ok()
  {
    $this->message = $this->sock_read();
    //print "is_ok: sock_read done: " . $this->message . "<br>";
    
    if($this->message == "" || preg_match('/^5/',$this->message) )
      {
	//print "bad response<br>";
	return 0;
      }
    else
      {
	//print "good response<br>";
	return 1;
      }
  }

  /**
   * Utility method so that we can take care of logging and
   * adding the carriage return etc.
   */
  function sock_write($s)
  {
    if($s == "")
      {
	//echo "<-- cowardly refusing to write nothing -->";
      }
    else
      {
	$this->log(">> $s");
	@fputs($this->sock,"$s\n");
      }
  }
  
  /**
   * retrieves a listing of the given directory or the current
   * working directory if no path has been specified. Returns
   * a string which contains all the directory entries separated
   * by new lines.
   */
  function dir_list($path="")
  {
    $s="";
    if($this->pasv())
      {
	if($path == '')
	  {
	    $this->sock_write("LIST");
	  }
	else
	  {
	    $this->sock_write("LIST $path");
	  }
	if($this->is_ok())
	  {
	    while(true)
	      {
		$line = fgets($this->data_sock);
		$s .= $line;
		if($line =='')
		  break;
	      }
	  }
      }
    return $s;
  }
	
  /**
   * this function will return a handle that can be used to 
   * retrieve a file on the FTP host. 
   */
  function retr($path)
  {
    if($this->pasv())
      {
	$this->sock_write("RETR $path");
	if($this->is_ok())
	  {
	    return $this->data_sock;
	  }
      }
    
    return "";
  }
	
  /**
   * stores the file given in $localpath on the remote server as
   * $remotePath
   */
  function stor($localPath,$remotePath)
  {
    $this->log("<h3>uploading $localPath</h3>");
    if($this->pasv())
      {
	$this->sock_write("STOR $remotePath");
	if($this->is_ok())
	  {
	    $fp = fopen($localPath,"rb");
	    
	    
	    if($fp) {
		
	      while(!feof($fp)) {
		$s = fread($fp,4096);
		fwrite($this->data_sock,$s);
	      }
	      fclose($fp);
	      fclose($this->data_sock);
	      //print "here<br>";
	      if($this->check_reply("226")) {
		//print "good upload!<br>";
		return 1;
	      }
	      return 1;
	    }
	    return 0;
	  }
      }
  }

  /**
   * establishes a passive mode data connection
   */
  function pasv()
  {
    $this->sock_write("PASV");
    
    
    if($this->is_ok()) {
	
	$offset = strpos($this->message,"(");
	
	$s = substr($this->message,++$offset,strlen($this->messsage)-2);
	$parts = split(",",trim($s));
	$data_host = "$parts[0].$parts[1].$parts[2].$parts[3]";
	$data_port = ((int)$parts[4] << 8) + (int) $parts[5];
	
	$this->data_sock = fsockopen($data_host,$data_port,&$errno,&$errstr,30);
	return $this->data_sock;
      }
    return "";
  }
	
	
	
  /**
   * log the user in with the given username and password, default
   * to annoymous with a dud email address if no username password
   * have been given.
   */
  function login($user="",$pass="")
  {
    /* no overloading in PHP */
    if($user=='') $user = $this->user;
    if($pass=='') $pass = $this->pass;
    
    $this->sock_write("USER $user");
    if($this->is_ok())
      {
	$this->sock_write("PASS $pass");
	
	if($this->check_reply("230"))
	  {
	    return 1;
	  }
      }
    
    ob_flush();
    return 0;
  }
	
  /**
   * match the response from the server with the given status code
   */
  function check_reply($code)
  {
    if($code=='230')
      {
	while(1)
	  {
	    if($this->is_ok())
	      {
		if( preg_match('/^230 /',$this->message))
		  {
		    return 1;
		  }
		
	      }						
	    else
	      {
		return 0;
	      }
	    
	  }
      }
    else
      {
	if($this->is_ok())
	  {
	    $pat = '/^'. $code .'/';
	    if( preg_match($pat,$this->message))
	      {
		return 1;
	      }
	    
	  }	
	return 0;
      }
  }
  
  /**
   * Rename From this file ...
   */
  function rnfr($filename)
  {
    sock_write("RNFR $filename");
    if(is_ok())
      {
	return 1;
      }
    else
      {
	return 0;
      }
  }
  
  /**
   * .. rename to this file
   */
  function rnto($filename)
  {
    sock_write("RNTO $filename");
    if(is_ok())
      {
	return 1;
      }
    else
      {
	return 0;
      }
  }
  /**
   * change this method to suite your log system.
   * be sure to setting the $enable_log to 1 
   */
  function log($str)
  {
    if ( stristr($str, "> PASS") ) {
      $str = ">> PASS ********";
    }
    
    echo "$str<br>\n";
  }
  
  /**
   * login with this user name..
   */
  
  function set_user($user)
  {
    $this->user=$user;
  }
  /**
   * .. and this password.
   */
  
  function set_pass($pass)
  {
    $this->pass =$pass;
  }
  
}

/**
 * this is not a member of the FTP class because it does not
 * work directly with the FTP server in any way. It will instead
 * process the output from the FTP server.
 *
 * Notice that the Table does not have the table start and end
 * tag. this is to allow you to create a header outside of this
 * function.
 *
 * Overall i think template schemes of this nature suck but to
 * use my beloved XSLT would be overkill.
 */
function show_list($data)
{

	$list = split("\n",$data);

	$pattern = "/[dwrx\-]{10}/";
	
	$list = array_slice($list,1,count($list)-1);
	foreach($list as $file)
	{
		if($file == '')
		{
			continue;
		}
		
		$del="";
		$file = preg_split("/ /",$file,20,PREG_SPLIT_NO_EMPTY);
		
		/*
		 * directory download has to be implemented in a different manner
		 * so we will just ignore directories for now.
		 */
		if(preg_match('/^d/',trim($file[FPERM])))
		{
			$downlink = "index.php?act=cwd&dir=". urlencode(trim("$path".$file[FNAME]));	
			$del = "rmdir";
		}
		else
		{
			$downlink = "getfile.php?filename=". urlencode("$path".$file[FNAME]);
			$del="delete";
		}
		
		printf('<tr><td class="cell1">%s</td><td class="cell1">%s</td>
					<td class="cell1">%s</td><td class="cell1">%s</td>
					<td class="cell1">%s %s %s</td>
					<td class="cell1"><a href="%s">%s</a></td>
					<td class="cell1"><a href="index.php?act=%s">%s</a></td>
				</tr>',
				$file[FPERM],$file[FUID],$file[FGID], $file[FSIZE],
				$file[FMONTH],$file[FDAY],$file[FTIME],
				$downlink, $file[FNAME], "{$del}&dir=".urlencode(trim("$path".$file[FNAME])),
				$del
			  );
	}
}


?>
