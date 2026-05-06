<?php

if(file_exists("CURL.php")){	    include "CURL.php"; }
if(file_exists("bosbo_spider_class.php")) {      include "bosbo_spider_class.php";  }
if(file_exists("../../include/php_library_fns/db_functions.php")) {      include "../../include/php_library_fns/db_functions.php";  }
if(file_exists("../../include/php_library_fns/xml_functions.php")) {      include "../../include/php_library_fns/xml_functions.php";  }
if(file_exists("../../include/objects/bosbo_order_class.php")){	    include "../../include/objects/bosbo_order_class.php";	  }

/*


$spider_all = new Spider_data();
$to_spider = $spider_all->get_active_validated_links();

echo sizeof($to_spider);
echo "<br />";
foreach ($to_spider as $value)
{
	$this_spider = new Spider_data();
	$this_spider->Get($value);
	$orderRecord = new Order();
	$orderRecord->Get($value);
	if ($orderRecord->getuserId()==-2) {
		// if web address starts with http://www.tecno
		if (!(stristr($orderRecord->getWebAddress(),"http://www.tecno")==false)) {
		//   then active = -1
		//   order volume = -1
			$this_spider->active=-1;
			$orderRecord->setvolume(-1);
			echo $orderRecord->getWebAddress() . " --- disabled<br />";
		} else {
		//   active = 1
		//   volume = 999999
		//   onbehalfof = Jessops.com	
			$this_spider->active=1;
			$orderRecord->userId=-6;
			$orderRecord->setonbehalfof("Jessops.com");
			$orderRecord->setvolume(9999999);
			echo $orderRecord->getWebAddress() . " --- converted<br />";
			//$orderRecord->setvolume(-1);
			
		//NOT NEEDED $this_spider->active=1;
		}
		//$orderRecord->setonbehalfof('Jessops.com');
		//$this_spider->setPrequantity('<div class="stockstatus">');
		//$this_spider->setPostquantity('</a>');
		$this_spider->Save();
		$orderRecord->Save();
	} else {
		if (!(stristr($orderRecord->getWebAddress(),"http://www.jesso")==false)) {
			echo  "JESSOPS - USER " . $orderRecord->getuserId();
		}
	}
}
*/


$spider_all = new Spider_data();
$to_spider = $spider_all->get_active_validated_links();

echo sizeof($to_spider);
echo "<br />";
foreach ($to_spider as $value)
{
	$this_spider = new Spider_data();
	$this_spider->Get($value);
	$orderRecord = new Order();
	$orderRecord->Get($value);
	if ($orderRecord->getuserId()==-7) {
	
			$this_spider->prepostage = "from &#163;";
			$this_spider->postpostage = "</li>";
		$this_spider->Save();
	}
}

?>