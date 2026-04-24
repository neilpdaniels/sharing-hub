<?php

if(file_exists("CURL.php")){	    include "CURL.php"; }

/*if (isset($_GET['login'])&&isset($_GET['password'])) {
	$user1 = new User($_GET['login'],'','','','','','','','',$_GET['password'],'','', '');
	if($user1->AuthUser()){
		$user1 = $user1->GetByUsername($_GET['login']);
		$id = $user1->getUserId();
		if ($id<0) {
*/


$to_spider = array(
  'http://www.amazon.co.uk/robots.txt' => $amazon_co_uk,
  'http://www.play.com/robots.txt' => $play_com,
  'http://www.rankhour.com/robots.txt' => $rankhour_com,
  'http://www.empiredirect.co.uk/robots.txt' => $empiredirect_co_uk,
  'http://www.tecno.co.uk/robots.txt' => $tecno_co_uk,
  'http://www.jessops.com/robots.txt' => $jessops_com
  );
foreach ($to_spider as $key => $value)
{
  	echo "[LOG_TRACE] checked ROBOTS.TXT for " . $key ."<br />";
	$url = new CURL();
	echo "***BEFORE***<br />";
	echo $url->get($key);
	echo "<br />&&&AFTER&&&<br /><br /><br /><br /><br />";
}

/*		} else {
			echo "ERROR1";
		}
	} else {
		echo "ERROR2";
	}
} else {
	echo "ERROR3";
}
*/

?>