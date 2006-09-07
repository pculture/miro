<?php

//
// Based on code found online at:
// http://php.net/manual/en/function.xml-parse-into-struct.php
//
// Author of original concept: Eric Pollmann
// Released into public domain September 2003
// http://eric.pollmann.net/work/public_domain/
// GO THERE IF YOU WANT THE ORIGINAL WORK. ;)
//
// Aside from pieces of the array translation, this class has been
// COMPLETELY rewritten by: David Chait
// For specific use with CHAITGEAR PHP libraries: CG-AMAZON, CG-FEEDREAD
// http://www.chait.net
//
// Many things the original system couldn't handle:
// - raw SOCKET handling, for better management of XML streams
// - auto-UTF-8 conversion of non ISO/ASCII feeds
// - simplified 'collapsing' of single-entry fields & children
// ... and more.

if (!isset($XATTR))
{
	function betterUSleep($usec)
	{
	   $start = gettimeofday();
	
	   do
	   {
	       $stop = gettimeofday();
	       $timePassed = 1000000 * ($stop['sec'] - $start['sec'])
	           + $stop['usec'] - $start['usec'];
	   }
	   while ($timePassed < $usec);
	}

	class cgsocket
	{
		var $sock = null;
		var $err = null;
		var $errstr = null;
		var $data = null;
		var $lines = null;
		var $maxline = 0;
		var $linenum = 0;
		
		function open($host, $port=80)
		{
//			if (!function_exists('socket_create')) die('no socket_create, no socket functions?!?!');
			$socket = socket_create(AF_INET, SOCK_STREAM, SOL_TCP);
			if ($socket==FALSE)
			{
				$this->hadError();
				return(FALSE);
			}
			// else ready.
			//socket_set_nonblock($socket);
			$sleepytime = 300; // ms
			$iterations = 10; //($timeout * 1000 / $sleepytime);
			while (!@socket_connect($socket, $host, $port))
			{
				$err = socket_last_error($socket);
//				echo '['.'] '.$err.' == '.socket_strerror($err)."<br/>"; flush();
				if ($err>10000)
				{
					if		($err == 10035) $err = 115; // A non-blocking socket operation could not be completed immediately. 
					else if ($err == 10037) $err = 114; // An operation was attempted on a non-blocking socket that already had an operation in progress. 
					else if ($err == 10056) break; //$err = 114; // A connect request was made on an already connected socket. 
					else //if		(0 && $err == 11001)
					{ // no such host == 11001
						socket_close($socket);
						$this->hadError();
						return(FALSE);
					}
				}
				//else
				//die(socket_strerror($err) . "\n");

				//echo "$iterations..."; flush();
				if ($iterations--<0)
				{
					socket_close($socket);
					$this->hadError();
					return(FALSE);
					//die("Connection timed out.\n");
				}
				
				if ($err==114 || $err==115) // then sleep some...
					betterUSleep(1000 * $sleepytime);
			}
			
			socket_set_block($socket);
			//or die("Unable to set block on socket\n");		
			// store it.
			$this->sock = $socket;
			return(true);
		}
		
		function read($len=0)
		{
			$string = '';
			//if len==0, loop until done with data...
			if ($len==0) $len = 65535;
//			while (0<($res = socket_recv($this->sock, $tmp, 1024, 0)))
			while ($tmp = socket_read($this->sock, $len))
				$string .= $tmp;
//			$err = socket_last_error($socket);
//			echo '[READ] '.$err.' == '.socket_strerror($err)."<br/>"; flush();
			return($string);
		}
		
		function gets()
		{
			if ($this->data == null)
			{
				// read ALL data there is to read.
				$this->data = $this->read();
				$this->lines = explode("\r\n", $this->data);
				$this->maxline = count($this->lines);
				$this->linenum = 0;
			}
			
			if ($this->linenum < $this->maxline)
			{
				$out = $this->lines[$this->linenum]."\r\n"; // add back the removed line endings!!!
				$this->linenum++;
				return($out);
			}
			return(FALSE);
		}
		
		function getsleft() // gets all remaining data...
		{
			$out = '';
			while ($this->linenum < $this->maxline)
			{
				$out .= $this->lines[$this->linenum]."\r\n"; // add back the removed line endings!!!
				$this->linenum++;
			}
			return($out);
		}
		
		function write($string, $len=0)
		{
			$this->data = null; // clear on write;
			
			if ($len==0) $len = strlen($string);
			$tw = 0;
//			while($tw<$len)
			{
				$bw = socket_send($this->sock, $string, $len, 0); // add partial-write-completion handling at some point...
//				echo "}} WRITE [$bw of $len] $string<br/>";
				if ($bw===FALSE) return(FALSE);
				$tw += $bw;
			}
			return($tw);
		}
		
		function close()
		{
			socket_shutdown($this->sock);
			socket_close($this->sock);
			$this->sock = null;
		}
		
		function hadError()
		{
			$this->err = socket_last_error();
			$this->errstr = socket_strerror($this->err);
		}
		
		function wasError()
		{
			return $this->err;
		}
		
		function wasErrorString()
		{
			return $this->errstr;
		}
	}
	
	$XATTR = '_ATTR';
	$XVALUE = '_VALUE';
	$XTAG = '_TAG';
	if (!isset($DebugXML)) $DebugXML = 0;
	
	function debugme($str)
	{
		global $DebugXML;
		if ($DebugXML)
		{
			if (function_exists("dbglog"))
				dbglog($str);
			else
			{
				echo $str."<br>";
				flush();
			}
		}
	}	
	
	class XMLParser
	{
		var $data;		// Input XML data buffer
		var $vals;		// Struct created by xml_parse_into_struct
		// $flatten == reduce single-entry arrays whenever possible.
		var $index_numeric;	// Index tags by numeric position, not name.
												//   useful for ordered XML like CallXML.
		var $root_tag;
		var $timeout = 5; // defaults to a 5s timeout, for keeping things performing nicely.
		var $setSourceFailed = '';
		
		var $uni = false; // unicode/uft8 stream.
	
		function XMLParser()
		{
			// noop for now.
		}
		
		// Read in XML on object creation.
		// We can take raw XML data, a stream, a filename, or a url.
		function setSource($data_source, $data_source_type='raw')
		{
			global $DebugXML, $useStdXMLRetrieval;
			
			global $AmazonDebug;
			if ($AmazonDebug>2 && !$DebugXML) $DebugXML = 1;
			
			$this->data = '';
	
			if ($data_source_type == 'raw')
				$this->data = $data_source;
			else
			if ($data_source_type == 'stream')
			{
				while (!feof($data_source))
					$this->data .= fread($data_source, 16000);
			}
			else
			if ($data_source_type == 'file')
			{
				if (file_exists($data_source))
					$this->data = file_get_contents($data_source);
				else
					return(false);
			}
			else // assume it's a url
			{
				if ($DebugXML) debugme("<br>############################ XMLPARSER<br>");
				if (isset($useStdXMLRetrieval) && $useStdXMLRetrieval) // old method
				{
					if (!($fp = @fopen($data_source,'r')))
					{
					$this->setSourceFailed = "XMLParser failed to open URL: [$data_source]";
						return false;
					}
					
			    if (function_exists("stream_set_timeout"))			stream_set_timeout( $fp, $this->timeout );
			    else if (function_exists("socket_set_timeout"))	socket_set_timeout( $fp, $this->timeout );
			    else if (function_exists("set_socket_timeout"))	set_socket_timeout( $fp, $this->timeout );
			    
					while (!feof($fp))
						$this->data .= fread($fp, 16000);
					fclose($fp);
				}
				else
				{
					$url = $data_source;
					$redirectCount = 0;
					$relocated = true;
					if (function_exists('socket_create'))
					//if (!function_exists('stream_socket_client'))
						$sock = new cgsocket();
					while ($relocated) // in case relocated...
					{
						$relocated = false;
						$tok = parse_url($url);
						debugme("XMLParser: trying to read [$url], timeout = " . $this->timeout);
						if ($sock)
						{
							$err = (!$sock->open($tok['host']));
							$errno = $sock->wasError();
								$errstr = $sock->wasErrorString();
						}
						else
							$err = (!($fp = fsockopen($tok['host'], 80, $errno, $errstr))); //, $this->timeout)))
						if ($err)
						{
							$this->setSourceFailed = "XMLParser failed to open (".$tok['host'].")<br/>URL: [$data_source]<br/>Error #$errno:<br/><strong>$errstr</strong><br/>Check the feed URL is valid.";
							//die($this->setSourceFailed);
							debugme($this->setSourceFailed);
							return(false);
						}
						else
						{
							$lf = "\r\n";
							$req = '';
							$req .= "GET ".$tok['path'];
							if (isset($tok['query']) && $tok['query']) $req .= '?'.$tok['query'];
							if (isset($tok['fragment']) && $tok['fragment']) $req .= '#'.$tok['fragment'];
							$req .= " HTTP/1.1".$lf;
							$req .= "Host: " .$tok['host'].$lf;
							$req .= "User-Agent: CHAITGEAR XMLParser (www.chait.net)".$lf;
							$req .= "Connection: close".$lf;
							$req .= $lf;
							if ($sock) $sock->write($req);
							else fputs($fp, $req);
							if ($DebugXML>1) debugme(str_replace($lf," ",$req)); // inline strip down linefeeds..
						}
											
						$ready2go = 0;
						$findNewLocation = false;
						$linenum = 0;
						$chunked = false;
						$chunkSize = 0;
						$fullsize = 0; // start as 0 to flag us
						while (1)
						{											
							if ($ready2go==0)
							{
								if ($sock) $curline = $sock->gets();
								else $curline = fgets($fp, 4096);
								if ($curline===FALSE) break;
								$linenum++;
if ($DebugXML>3) echo "\nLINE $linenum:<br/><pre>".safehtmlentities(serialize($curline))."</pre><br/>";
								
								if ($DebugXML>3) debugme(safehtmlentities(str_replace($lf,'',$curline)));
								
								
								//if ($curline=="\r\n")
								if ($curline{0}=="\r" || $curline{0}=="\n") // empty line
								{
									$ready2go++;
									continue;
								}
									
								if ($linenum==1) // response header?
								{
									if (FALSE===strpos($curline, "HTTP/")) // it's a simple answer
										$ready2go = true;
									else // valid header line
									{
										$response = explode(' ', $curline); // sep by spaces
										$statcode = $response[1];
										$statclass = $statcode{0}; // first digit
										if ($statclass==2) // okay class
										{
										}
										else
										if ($statclass==3) // relocation class
											$findNewLocation = true;
										else
										if ($statclass==4) // UGH class
										{
											debugme("OUCH, error $statcode $response[2]");
											$this->setSourceFailed = "XMLParser Error: $statcode $response[2]";
											for ($i=3; $i<count($response); $i++)
												 $this->setSourceFailed .= ' '.$response[$i];
//											$this->setSourceFailed .= " -- trying to access URL: $data_source";
							debugme($this->setSourceFailed);
											return(false); // time to go
										}
										else
										if ($statclass==5) // BAD BAD class
										{
											debugme("OUCH, error $statcode $response[2]");
											$this->setSourceFailed = "XMLParser Error: $statcode $response[2]";
											for ($i=3; $i<count($response); $i++)
												 $this->setSourceFailed .= ' '.$response[$i];
//											$this->setSourceFailed .= " -- trying to access URL: $data_source";
							debugme($this->setSourceFailed);
											return(false); // time to go
										}
									}
								}
								else
								if (0===strpos($curline, "Content-Length:"))
								{
									$response = explode(' ', $curline); // sep by spaces
									$fullsize = intval($response[1]);
								}
								else
								if (0===strpos($curline, "Transfer-Encoding: chunked"))
								{
									$chunked = true;
								}
								else
								if (0===strpos($curline, "Location:") && $findNewLocation)
								{
									$relocated = true;
									$response = explode(' ', $curline); // sep by spaces
									$curline = $response[1];
									if ($offset = strpos($curline, "\r"))
										$curline = substr($curline, 0, $offset);
									elseif ($offset = strpos($curline, "\n"))
										$curline = substr($curline, 0, $offset);
									$url = $curline;
									debugme("\n>> REDIRECT: NEW URL @ $url");
									break; // we don't need any further information.. move along.
									// may need to strip off \r\n?
								}
								// can handle Location header redirection if needed...
							}
							else // ready2go
							{
								$alldone = false;
								$lefttoread = 0;
								$rawdata = '';
								if (!$chunked && $fullsize)
									$lefttoread = $fullsize;
								
								if ($sock)
									$rawdata = $sock->getsleft();
								else
									while (!feof($fp)) $rawdata .= fread($fp, 16000);
								
								$rawoff = 0;
								$rawmax = strlen($rawdata);
								
								if (!$chunked && !$lefttoread)
								{
									$alldone = true;
									$this->data = &$rawdata;
									if ($DebugXML>3) debugme("[GOT ALL $rawmax] = ".safehtmlentities($rawdata));
								}

								while (!$alldone) // chunked processing loop.
								{
									// first, grab the chunk length.
									if (!$lefttoread)
									{
										$linelen = strpos($rawdata, "\r\n", $rawoff); // find next ending.
										$linelen += 2; // account for CRLF
										$linelen -= $rawoff; // the 'real' length...
										$curline = substr($rawdata, $rawoff, $linelen);
										$rawoff += $linelen; // update raw offset
										if ($DebugXML>3) debugme("[[ ($linelen) GOT CHUNK LEN = ".safehtmlentities($curline)." ]]");
										
										if ($offset = strpos($curline, ';'))
											$curline = substr($curline, 0, $offset);
										elseif ($offset = strpos($curline, "\r"))
											$curline = substr($curline, 0, $offset);
										elseif ($offset = strpos($curline, "\n"))
											$curline = substr($curline, 0, $offset);
										if ($curline=='0')
										{
											$alldone = true;
											if ($DebugXML>3) debugme("HIT ALLDONE CASE.");
										}
											
										$len = hexdec($curline);
										//if ($len<=0) $alldone = true; // this is what SHOULD be done, but WP feeds fail.
										$lefttoread = $len;
									}
								
									if ($DebugXML>3) debugme(">>>>> LEN = $lefttoread");
									while($lefttoread>0)
									{
										if ($rawoff > $rawmax)
										{
											if ($DebugXML>0) debugme("!!!!! Was [$lefttoread] left, but hit an feof state!");
											break;
										}

																				$linelen = $lefttoread;
										$curline = substr($rawdata, $rawoff, $linelen); // ignore CRLF
										$linelen += 2; // account for CRLF
										$lefttoread -= $linelen;
										$rawoff += $linelen; // update raw offset, account for CRLF
										$len = strlen($curline);
										$this->data .= $curline;
										
										if ($DebugXML > 3)
										{
											debugme("[[linelen = $linelen, rawoff = $rawoff, len = $len, left = $lefttoread ]] ");
											debugme(safehtmlentities($curline));
										}
									}
									
									if ($fullsize) break; // we're done.
									$lefttoread = 0;
								}
								
								break;
							}
						} // while !feof
						
						if ($sock) $sock->close();
						else fclose($fp);
						
						if ($relocated)
						{
							$this->data = ''; // clear any data.
							$redirectCount++;
							if ($redirectCount>4) // stop possible infinite bounces.
								break;
						}
					} // while !relocated
				} // old/new method
			}

			$this->encoding = 'UTF-8'; // default, since it works for most everything...
			// try to convert if needed NOW!
			preg_match('/encoding="([^"]+)"/i', $this->data, $matches);
			if (!empty($matches) && !empty($matches[1]))
				$this->encoding = strtoupper($matches[1]);
			if ($DebugXML>0) debugme("XML: encoding = $this->encoding"); //, matches=".serialize($matches));
			if ($this->encoding != 'UTF-8' && $this->encoding != 'ISO-8859-1' && $this->encoding != 'US-ASCII')
			{
				if ($DebugXML>0) {echo "ENCODING NEEDS CONVERSION<br>"; flush();}
				if ($DebugXML>0) debugme("ENCODING NEEDS CONVERSION");
				if (!function_exists('iconv'))
				{
					$this->setSourceFailed = "XMLParser Error: source data is $this->encoding, should be UTF-8";
					if ($DebugXML>0) debugme("XML encoding was $this->encoding, iconv not available...");
//							debugme($this->setSourceFailed);
					return(false);
				}

				if ($DebugXML>0) debugme("Converting to UTF8");
				$this->data = iconv($this->encoding, "UTF-8", $this->data);
				$this->encoding = 'UTF-8';
				$this->data = preg_replace('/encoding="([^"]+)"/i', 'encoding="'.$this->encoding.'"', $this->data);
			}
			
			if ($this->encoding=='UTF-8')
				$this->uni = true; // temp flag it might be unicode.

			if ($DebugXML)
			{
				$fp = fopen("RAW.XML",'w');
				fwrite($fp, $this->data, strlen($this->data));
				fclose($fp);
			}				
//			if (!function_exists("dbglog")) die("NO DBGLOG FROM XMLPARSER????");
//			dbglog("################################################ XMLPARSER #########");
			return(true);
		}
	
		// Parse the XML file into a verbose, flat array struct.
		// Then, coerce that into a simple nested array.
		function getTree($tag_root='', $tag_sub='', $flatten=true, $index_numeric=false)
		{
			global $DebugXML;
	
			$this->index_numeric = $index_numeric; // the only thing that needs to be in object.
		
			$parser = xml_parser_create($this->encoding);
			xml_parser_set_option($parser, XML_OPTION_SKIP_WHITE, 1);
			xml_parser_set_option($parser, XML_OPTION_CASE_FOLDING, FALSE);
			xml_parse_into_struct($parser, $this->data, $vals, $index); 
			xml_parser_free($parser);
	
			if ($DebugXML>2)
			{
				$fp = fopen("XML1_RAWARRAY.PHP",'w');
				$rawarray = print_r($vals, TRUE);
				fwrite($fp, $rawarray, strlen($rawarray));
				fclose($fp);
			}
			
			$i = -1;
			$Ret = $this->getchildren($vals, $i);
	
			if ($DebugXML>2)
			{
				$fp = fopen("XML2_PARSEDTREE.PHP",'w');
				$rawarray = print_r($Ret, TRUE);
				fwrite($fp, $rawarray, strlen($rawarray));
				fclose($fp);
			}
	
			if ($flatten)
			{
	//			echo serialize($Ret);
				$Ret = $this->flattenChildren($Ret);
			}
			
	//		dbglog(serialize($Ret));

			if ($DebugXML>2)
			{
				$fp = fopen("XML3_FLATTREE.PHP",'w');
				$rawarray = print_r($Ret, TRUE);
				fwrite($fp, $rawarray, strlen($rawarray));
				fclose($fp);
			}
	
	
			if ($tag_root)
			{
				$rootnode = &$Ret[$tag_root];
				if ($rootnode == null || !count($rootnode))
					return null; // we're done.
				$Ret = &$rootnode;
				
				if ($tag_sub)
				{
					if (!isset($Ret[$tag_sub]))
						return null; // we're done.
							
					$rootnode = &$Ret[$tag_sub];
					if ($rootnode == null || !count($rootnode))
						return null; // we're done.
					$Ret = &$rootnode;
				}
				
				if ($DebugXML)
				{
					$fp = fopen("XML4_ROOTEDTREE.PHP",'w');
					$rawarray = print_r($Ret, TRUE);
					fwrite($fp, $rawarray, strlen($rawarray));
					fclose($fp);
				}
			}
			
			return ($Ret);
		}
	
		//====================================================
		// internal function: build a node of the tree
		function buildtag($thisvals, $vals, &$i, $type)
		{
			global $XATTR,$XVALUE,$XTAG;
			$tag = null;
	
			if (isset($thisvals['attributes']))
				$tag[$XATTR] = $thisvals['attributes']; 
	
			// complete tag, just return it for storage in array
			if ($type === 'complete')
			{
				//$tag[$XVALUE] = 0; // set it, just set it 'false'.
				if (isset($thisvals['value']))
					$tag[$XVALUE] = $thisvals['value'];
			}	
			// open tag, recurse
			else
			{
				$newtags = $this->getchildren($vals, $i);
				if (empty($tag))
					$tag = $newtags;
				else
					$tag = array_merge($tag, $newtags);
			}
	
			return $tag;
		}
	
		// internal function: build an nested array representing children
		function getchildren($vals, &$i)
		{ 
			global $DebugXML;
			global $XATTR,$XVALUE,$XTAG;
			$children = array();     // Contains node data
	
			// Node has CDATA before it's children
			if ($i > -1 && isset($vals[$i]['value']))
				$children[$XVALUE] = $vals[$i]['value'];
	
			// Loop through children, until hit close tag or run out of tags
			while (++$i < count($vals))
			{
				$type = $vals[$i]['type'];
	
				// 'cdata':	Node has CDATA after one of it's children -- (Add to cdata found before in this case)
				if ($type === 'cdata')
				{
					$children[$XVALUE] .= $vals[$i]['value'];
				}
				else // 'complete':	At end of current branch, 'open':	Node has children, recurse
				if ($type === 'complete' || $type === 'open')
				{
					$tag = $this->buildtag($vals[$i], $vals, $i, $type);
					if ($this->index_numeric)
					{
						$tag[$XTAG] = $vals[$i]['tag'];
						$children[] = $tag;
					}
					else
						$children[$vals[$i]['tag']][] = $tag;
				}
				else // 'close:	End of node, return collected data -- Do not increment $i or nodes disappear!
				if ($type === 'close')
					break;
			}
			
			$newkids = $children;
	
			return $newkids;
		} 
	
		function flattenChildren($kids, $level=0)
		{
			global $DebugXML;
			global $XATTR,$XVALUE,$XTAG;
			$newkids = array();
			
			$doit = ($DebugXML>3);
			
			$keylog = 'Keys = ';
			$k = count($kids);
			foreach($kids as $key => $value)
			{
				if ($value==null) continue;
				
				if ($doit) dbglog("Key[$level] = $key :: ".($key==$XVALUE?'<>':substr($value,0,10)));
		//		if ($root_tag!='' && $root_tag!=$key) continue;
		
				if ($k==1 && $key===$XVALUE)
				{
					if ($doit) dbglog("Singleton ($key)");
					if (is_array($value)) return($this->flattenChildren($value, $level+1));
					return($value);
				}
				
				$newvalue = &$value;
					
				if ($key===$XTAG || $key===$XATTR)
				{
					if (is_array($value))
						$newvalue = $this->flattenChildren($value, $level+1);
				}
				else
				if (is_array($value))
				{
					$newvalue = $this->flattenChildren($value, $level+1);
					if (is_array($newvalue) &&
							count($newvalue) == 1)
					{
						$keya = array_keys($newvalue);
						$newkey = &$keya[0];
						if ($doit) dbglog(">>> collapsing: $key $newkey");
						$newvalue = &$newvalue[$newkey];
						/*
						if (is_array($newvalue) &&
								count($newvalue) == 0) // empty array...
							$newvalue = null;
						*/
						if ($doit) dbglog("collapsed: $key ");
					}
				}
				
				$newkids[$key] = $newvalue;
			}
				
			return($newkids);
		}
	
	}
}

?>