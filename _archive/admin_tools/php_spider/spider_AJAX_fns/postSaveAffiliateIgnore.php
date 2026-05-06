<?php
if(file_exists("../CURL.php")){	    include "../CURL.php"; }
if(file_exists("../bosbo_spider_class.php")) {      include "../bosbo_spider_class.php";  }
if(file_exists("../../../include/php_library_fns/db_functions.php")) {      include "../../../include/php_library_fns/db_functions.php";  }
if(file_exists("../../../include/php_library_fns/xml_functions.php")) {      include "../../../include/php_library_fns/xml_functions.php";  }
if(file_exists("../../../include/objects/bosbo_order_class.php")){	    include "../../../include/objects/bosbo_order_class.php";	  }
if(file_exists("../../../include/objects/bosbo_most_popular_products_class.php")){     include "../../../include/objects/bosbo_most_popular_products_class.php";        }
if(file_exists("../../../include/objects/user_functions.php")){    include "../../../include/objects/user_functions.php";  }
if(file_exists("../../../include/objects/bosbo_affiliate_popular_products_class.php")){    include "../../../include/objects/bosbo_affiliate_popular_products_class.php";  }
if(file_exists("../../../include/php_library_fns/search_functions.php")) {      include "../../../include/php_library_fns/search_functions.php";  }
if(file_exists("../../../include/objects/bosbo_category_class.php")){    include "../../../include/objects/bosbo_category_class.php";  }
if(file_exists("../../../include/objects/bosbo_affiliate_popular_products_ignore_class.php")){    include "../../../include/objects/bosbo_affiliate_popular_products_ignore_class.php";  }


//echo $_POST['product_name'];
echo $_POST['decision'];
//echo $_POST['userid'];
//echo $_POST['categoryid'];

if (strcmp('UNSURE',$_POST['decision'])!=0)
{
//affiliate_popular_products_ignore($userid='', $categoryid='', $aff_prod_name='')
	if(strcmp('ALERT',$_POST['decision'])==0)
	{
		// NEED TO APPEND TO END OF ALERT FILE -- name and web address (need to post)
		$myFile = "newproducts.csv";
		$fh = fopen($myFile, 'a') or die("can't open file");
		fwrite($fh, date('Ymd-g:i:sa O', time()) . "," . $_POST['userid'] . "," . $_POST['product_name'] . "," . $_POST['list_webpage'] . "\r\n");
		fclose($fh);

	} elseif(strcmp('IGNORE',$_POST['decision'])==0) {
		// dont store categoryid
		$new_record = new affiliate_popular_products_ignore($_POST['userid'], '', $_POST['product_name']);
		$new_record->Save();
	} elseif(strcmp('MATCH',$_POST['decision'])==0) {
		// store all details
		$new_record = new affiliate_popular_products_ignore($_POST['userid'], $_POST['categoryid'], $_POST['product_name']);
		$new_record->Save();
	}
} else
{
	echo "leaving as unsure";
}


?>