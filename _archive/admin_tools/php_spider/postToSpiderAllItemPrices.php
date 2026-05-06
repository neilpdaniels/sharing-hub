<?php
if(file_exists("../../include/php_library_fns/db_functions.php")) {      include "../../include/php_library_fns/db_functions.php";  }
if(file_exists("../../include/php_library_fns/xml_functions.php")) {      include "../../include/php_library_fns/xml_functions.php";  }
if(file_exists("../../include/objects/bosbo_order_class.php")){	    include "../../include/objects/bosbo_order_class.php";	  }
if(file_exists("../../include/objects/bosbo_non_abstract_category_class.php")){	    include "../../include/objects/bosbo_non_abstract_category_class.php";	  }
if(file_exists("bosbo_spider_class.php")) {      include "bosbo_spider_class.php";  }
	
foreach ($_POST as $value) {
	if (strlen(trim($value))>0) {
	$Database = new dbConnection();
	$result = $Database->Query($value);	
	echo "<br />EXECUTED: " . $value . " --- RESULT: " . $result;
	}
}
	// CALCULATE NEW TOTAL PRICES
	$Database = new dbConnection();
	$result = $Database->Query("SELECT `orderid` from `order` WHERE 1");	
	echo "--- ".$Database->Rows();
	for ($i=0; $i<$Database->Rows(); $i++)
	{
		  $orderid  = $Database->unescape($Database->Result($i, "orderid"));
		  if ($orderid>0) {
		  	$tempOrder = new Order();
		  	$tempOrder = $tempOrder->Get($orderid);
		  	$tempOrder->calculateTotalPrice();
		  	$tempOrder->Save();
		  }
	}
	
	// CHECK CATEGORY HIGH AND LOWS
	$Database = new dbConnection();
	$result = $Database->Query("SELECT `categoryid` from `non_abstract_category` WHERE 1");	
	echo "--- ".$Database->Rows();
	for ($i=0; $i<$Database->Rows(); $i++)
	{
		  $categoryid  = $Database->unescape($Database->Result($i, "categoryid"));
		  if ($categoryid>0) {
		  	$tempCat = new Non_abstract_category($categoryid);
		  	$tempCat = $tempCat->Get($categoryid);
		  	$tempCat->checkHighsAndLows();
		  	$tempCat->Save();
		  }
	}
	
	
?>