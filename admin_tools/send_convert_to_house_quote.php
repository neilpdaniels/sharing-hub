<?php
if (!isset($_SESSION)){
    session_name('bosbo-session');
    session_start();
  }
if(file_exists("php_spider/bosbo_spider_class.php")) {      include "php_spider/bosbo_spider_class.php";  }
if(file_exists("../include/php_library_fns/db_functions.php")) {      include "../include/php_library_fns/db_functions.php";  }
if(file_exists("../include/php_library_fns/xml_functions.php")) {      include "../include/php_library_fns/xml_functions.php";  }
if(file_exists("../include/objects/bosbo_order_class.php")){	    include "../include/objects/bosbo_order_class.php";	  }


/**
 
orderid
*url
validrobot
active
*preprice
*postprice
*prequantity
*postquantity 
 
 */
if (isset($_SESSION['valid_user']) && isset($_POST['url']) && isset($_POST['preprice'])
&& isset($_POST['postprice'])&& isset($_POST['prequantity'])&& isset($_POST['postquantity'])
&& isset($_POST['order_id']) && isset($_POST['onbehalfof'])
){
	if ($_SESSION['valid_user']<0) {
		$spider = new Spider_data(
		$_POST['order_id'],
		$_POST['url'],
		1,
		1,
		$_POST['preprice'],
		$_POST['postprice'],
		$_POST['prequantity'],
		$_POST['postquantity']);
		$spider_res = $spider->Save();
		echo "started" . $spider_res;
		//if ($spider_res!=0) {
			echo "completed";
			// save changes to order too
			$ord = new Order();
			$ord->Get($_POST['order_id']);
			$ord->setonbehalfof($_POST['onbehalfof']);
			if ($ord->getWebAddress()==-1) {
				$ord->setWebAddress($_POST['url']);
			}
			$ord->Save();
		//}
		?>
		<a href="../">main page</a>
		<?php
		$order_t= new Order();
		$order_t.get($_POST['order_id']);
		$nacat = new Non_abstract_category($order_t.get_categoryId());
		$nacat->Get($_POST['categoryId']);
		$nacat->checkHighsAndLows();
	} else {
		echo "ERROR";
	}
} else {
	echo "ERROR";
}
?>