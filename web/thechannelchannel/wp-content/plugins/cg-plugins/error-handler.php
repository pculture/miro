<?php
// >>>>> CHAIT DOT NET ENHANCEMENTS

// this should help reduce blank pages on errors...
error_reporting(E_ERROR | E_PARSE);
ini_set("display_errors","1");	

// global in which we'll place all error messages for the page.
$errorLog = '';
$dbgLog = '';
$dieOnAnyError = false;
if (!isset($eh_mailFatalErrors))
	$eh_mailFatalErrors = false;
if (!isset($eh_mailAddress))
	$eh_mailAddress = null;
if (!isset($ignoreNoticeErrors))
	$ignoreNoticeErrors = true;
if (!isset($ignoreWarningErrors))
	$ignoreWarningErrors = true;
// redefine the user error constants - PHP 4 only
define("FATAL", E_USER_ERROR);
define("ERROR", E_USER_WARNING);
define("WARNING", E_USER_NOTICE);

// ADVANCED ERROR HANDLING SYSTEMS.
function DBG_GetBacktrace($backcount=0)
{
	if (!function_exists('debug_backtrace')) return "<pre>no backtrace available</pre>";
	
   $s = '';
   $MAXSTRLEN = 64;
  
   $s = '<pre>';
   $traceArr = debug_backtrace();
   array_shift($traceArr);
   $tabs = sizeof($traceArr)-1;
   if ($backcount) $tabs = min($tabs, $backcount-1);
   $count = 0;
   foreach($traceArr as $arr)
   {
	   $count++;
	   if ($backcount && $count>$backcount) break;
	   if ($count==1) // the error handler!
	   		continue; // skip!
	   
       for ($i=0; $i < $tabs; $i++) $s .= ' &nbsp; ';
       $tabs -= 1;
       $s .= "<span class='backtrace_what'>";
       if (isset($arr['class'])) $s .= $arr['class'].'.';
       $args = array();
       if(!empty($arr['args'])) foreach($arr['args'] as $v)
       {
           if (is_null($v)) $args[] = 'null';
           else if (is_array($v)) $args[] = 'Array['.sizeof($v).']';
           else if (is_object($v)) $args[] = 'Object:'.get_class($v);
           else if (is_bool($v)) $args[] = $v ? 'true' : 'false';
           else
           {
               $v = (string) @$v;
               $str = htmlspecialchars(substr($v,0,$MAXSTRLEN));
               if (strlen($v) > $MAXSTRLEN) $str .= '...';
               $args[] = "\"".$str."\"";
           }
       }
       $s .= $arr['function'].'('.implode(', ',$args).')</span>';
       $Line = (isset($arr['line'])? $arr['line'] : "unknown");
       $File = (isset($arr['file'])? $arr['file'] : "unknown");
       $s .= sprintf("<span class='backtrace_line'> # line %4d, file: <a href=\"file:/%s\">%s</a></span>",
           $Line, $File, $File);
       $s .= "\n";
   }   
   $s .= '</pre>';
   return $s;
}

function dbg_log($errstr, $bt = false, $mailto = '')
{
	global $dbgLog, $user_level;
	if ($mailto)
			mail($mailto, "FATAL ERROR", $errstr);
	else
	if ($user_level>4)
	{
	//	$dbgLog .= "<B>> dbglog:</B> ";
		$dbgLog .= "$errstr<br/>\n";
		if ($bt)
			$dbgLog .= DBG_GetBacktrace(3) . "<br />\n";	
	}
}

function myErrorHandler($errno, $errstr, $errfile, $errline)
{
	global $errorLog, $ignoreNoticeErrors, $dieOnAnyError, $ignoreWarningErrors;
	
	if ($dieOnAnyError)
		die ("err $errno, $errstr ### in $errfile line $errline");

	if ($ignoreNoticeErrors) // disables the early-exit...
	{
		// notices
		if ($errno == 8
		||	$errno == 1024
				) return;
		
		if ($ignoreWarningErrors)
		{
			// warnings
			if ($errno == 2
			||	$errno == 512
					) return;
		}
	}
	
	// temp
	if ($errno==8 &&
	(		false!==(strpos($errstr, 'Undefined index'))
	||	false!==(strpos($errstr, 'Uninitialized string offset'))
	)
		)
		return;

	// temp
	if ($errno==2048 &&
	(		FALSE!==strpos($errstr, 'var: Deprecated')
	||	FALSE!==strpos($errstr, 'Creating default object')
	)
		)
		return;
	
   // define an assoc array of error string
   // in reality the only entries we should
   // consider are 2,8,256,512 and 1024
   $errortype = array (
               1    =>  "Error",
               2    =>  "Warning",
               4    =>  "Parsing Error",
               8    =>  "Notice",
               16  =>  "Core Error",
               32  =>  "Core Warning",
               64  =>  "Compile Error",
               128  =>  "Compile Warning",
               256  =>  "User Error",
               512  =>  "User Warning",
               1024 =>  "User Notice",
               2048 =>	"Runtime Strict"
               );
  
	$output = "PHP Error ($errno) [<b>$errortype[$errno]</b>]: ";
	$output .= "$errstr<br />\n";
	if ($errno==FATAL)
	{
		$output .= "  Fatal error in line $errline of file $errfile";
		$output .= ", PHP " . PHP_VERSION . " (" . PHP_OS . ")<br />\n";
		$output .= "Aborting...<br />\n";
	}
	
	$output .= DBG_GetBacktrace(3) . "<br />\n";

//	error_log($output, 3, "/usr/local/php4/error.log");
//	
	
	if ($errno==FATAL)
	{
		if ($eh_mailFatalErrors && !empty($eh_mailAddress))
			mail($eh_mailAddress, "FATAL PHP ERROR", $output);
		die($output);
		//exit(1);
	}
	else
		$errorLog .= $output;
}


function myErrorOutput()
{
	global $errorLog, $dbgLog;
	
	if ($errorLog || $dbgLog)
	{
		echo "<br/><b>Dumping Logged Messages:</b><br/>";
		echo $dbgLog;
		echo "<br/><b>==========</b><br/>";
		echo $errorLog;
		echo "<b>==========</b><br/><br/>";
	}
	else
	{
		echo "<br/>No errors to report.<br/>";
	}

//	if ($notifyOnAllErrors)
//		mail("cgadmin@chait.net", "PHP ERRORS", $output);

	// and for 'niceness', clear the logs after dump:
	$errorLog = null;
	$dbgLog = null;
}

// Set error handling levels -- need this to make sure all php configs do the same thing.
if (!isset($normalErrorHandler) || !$normalErrorHandler) //$onTestServer) // if on test server, crank it up!
{
	if (isset($showAllErrorCodes) && $showAllErrorCodes)
		error_reporting(E_ALL);
	else
		error_reporting(E_ERROR | E_PARSE);
	// set to the user defined error handler
	$old_error_handler = set_error_handler("myErrorHandler");
}

// <<<<< CHAIT DOT NET ENHANCEMENTS
?>
