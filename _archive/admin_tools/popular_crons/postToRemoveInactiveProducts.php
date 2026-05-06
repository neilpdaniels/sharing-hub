<?php
if(file_exists("../../include/php_library_fns/db_functions.php")) {      include "../../include/php_library_fns/db_functions.php";  }
if(file_exists("../../include/php_library_fns/xml_functions.php")) {      include "../../include/php_library_fns/xml_functions.php";  }
if(file_exists("../../include/objects/bosbo_order_class.php")){	    include "../../include/objects/bosbo_order_class.php";	  }
if(file_exists("../../include/objects/bosbo_non_abstract_category_class.php")){	    include "../../include/objects/bosbo_non_abstract_category_class.php";	  }
if(file_exists("bosbo_spider_class.php")) {      include "bosbo_spider_class.php";  }
	
foreach ($_POST as $value) {
	if (strlen(trim($value))>0) {
	$Database = new dbConnection();
	$query1 = "DELETE from `category`  WHERE `categoryid` = " . $value . " LIMIT 1";
	$result1 = $Database->Query($query1);	
        $query2 = "DELETE from `non_abstract_category`  WHERE `categoryid` = " . $value . " LIMIT 1";
        $result2 = $Database->Query($query2);
	echo "<br />EXECUTED FOR: " . $value . " --- RESULT: " . $result1 . " - " . $result2;
	echo $query1;
	}
}
?>
