<?php
    if(file_exists("../../include/php_library_fns/db_functions.php")){    	include "../../include/php_library_fns/db_functions.php";  	}
  	if(file_exists("../../include/objects/user_functions.php")){    	include "../../include/objects/user_functions.php";  	}
	if(file_exists("../../include/php_library_fns/xml_functions.php")){    	include "../../include/php_library_fns/xml_functions.php";  	}
  	if(file_exists("../../include/objects/bosbo_category_class.php")){  	  	include "../../include/objects/bosbo_category_class.php";    }
  	if(file_exists("../../include/objects/bosbo_category_products_class.php")){  	  	include "../../include/objects/bosbo_category_products_class.php";    }
  	if(file_exists("../../include/objects/bosbo_most_popular_products_class.php")){  	  	include "../../include/objects/bosbo_most_popular_products_class.php";    }
  	if(file_exists("../../include/objects/bosbo_non_abstract_category_class.php")){  	  	include "../../include/objects/bosbo_non_abstract_category_class.php";    }
    if(file_exists("../../include/php_library_fns/random_functions.php")){  	  	include "../../include/php_library_fns/random_functions.php";    }
  	if(file_exists("../../include/php_library_fns/page_functions.php")) {      include "../../include/php_library_fns/page_functions.php";  	}
  	if(file_exists("../../include/php_library_fns/my_bosbo_monitor_db_functions.php")) {      include "../../include/php_library_fns/my_bosbo_monitor_db_functions.php";  }
  if(file_exists("../../include/objects/bosbo_message_class.php")){	    include "../../include/objects/bosbo_message_class.php";  }
  if(file_exists("../../include/objects/bosbo_order_class.php")){	    include "../../include/objects/bosbo_order_class.php"; }
  /*
if (isset($_GET['login'])&&isset($_GET['password'])) {
	$user1 = new User($_GET['login'],'','','','','','','','',$_GET['password'],'','', '');
	if($user1->AuthUser()){
		$user1 = $user1->GetByUsername($_GET['login']);
		$id = $user1->getUserId();
		if ($id<0) {
			
*/

// ADDED 19th Jan 2008 - to  fix bug where NACs are still referenced after deletion
// this means that the category products table will be fully empty when this runs.
// $k will only be run on the first call of the foreach statement below
$k = 0;

$allAbstractCategories = returnAllAbstractCategories();
foreach ($allAbstractCategories as $value)
{
	echo "<br />";
	$mpp = new most_popular_products();
	if ($mpp->exists($value))
	{
		 $mpp->Get($value);
		 // ADDED 19th Jan 2008 - to  fix bug where NACs are still referenced after deletion
                 // this means that the category products table will be fully empty when this runs.
                 // $k will only be run on the first call of the foreach statement below
                 if ($k == 0) {
                       $k = 1;
                       echo "TRUNCATE!!!";
                       $mpp->TruncateTable();
                }
		$mpp->Delete();
		echo "DELETED: $value ___ ";
	}
	
	// get top 10
	$i = returnTenMostPopular($value);
	
	//create new most popular product and save
	$mpp2 = new most_popular_products($value, $i[0], $i[1], $i[2], $i[3], $i[4], $i[5], $i[6], $i[7], $i[8], $i[9]);
	$mpp2->Save();
	echo "ADDED: $value";
	
}			
			
	/*		
		} else {
			echo "ERROR1";
		}
	} else {
		echo "ERROR2";
	}
} else {
	echo "ERROR3";
}
*/

function returnAllAbstractCategories(){
	$categoryList = Array();
	$Database = new dbConnection();
	$query = "SELECT * FROM `category` WHERE `abstractCategory`='1' ORDER BY `name` ASC";
	$Database->Query($query);
	
	echo $Database->Rows() . " ROWS RETURNED";
	for ($i=0; $i < $Database->Rows(); $i++)
	{
		$category = $Database->unescape($Database->Result($i, "categoryid"));
		$categoryList[] = $category;
	}
	return $categoryList;
}
function returnTenMostPopular($a){
	$categoryList = Array();
	$Database = new dbConnection();
	$query = "SELECT * FROM `category_products` WHERE `parent`='".$a."' ORDER BY `popularity` DESC LIMIT 10";
	$Database->Query($query);
	for ($i=0; $i < $Database->Rows(); $i++)
	{
		$category = $Database->unescape($Database->Result($i, "product"));
		$categoryList[] = $category;
	}
	return $categoryList;
}

?>
