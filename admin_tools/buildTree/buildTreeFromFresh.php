<?php
  if (!isset($_SESSION)){
    session_name('bosbo-session');
    session_start();
  }
    if(file_exists("../../include/php_library_fns/db_functions.php")){    	include "../../include/php_library_fns/db_functions.php";  	}
  	if(file_exists("../../include/objects/user_functions.php")){    	include "../../include/objects/user_functions.php";  	}
	if(file_exists("../../include/php_library_fns/xml_functions.php")){    	include "../../include/php_library_fns/xml_functions.php";  	}
  	if(file_exists("../../include/objects/bosbo_category_class.php")){  	  	include "../../include/objects/bosbo_category_class.php";    }
  	if(file_exists("../../include/objects/bosbo_category_products_class.php")){  	  	include "../../include/objects/bosbo_category_products_class.php";    }
  	if(file_exists("../../include/objects/bosbo_non_abstract_category_class.php")){  	  	include "../../include/objects/bosbo_non_abstract_category_class.php";    }
    if(file_exists("../../include/php_library_fns/random_functions.php")){  	  	include "../../include/php_library_fns/random_functions.php";    }
  	if(file_exists("../../include/php_library_fns/page_functions.php")) {      include "../../include/php_library_fns/page_functions.php";  	}
  	if(file_exists("../../include/php_library_fns/my_bosbo_monitor_db_functions.php")) {      include "../../include/php_library_fns/my_bosbo_monitor_db_functions.php";  }
  if(file_exists("../../include/objects/bosbo_message_class.php")){	    include "../../include/objects/bosbo_message_class.php";  }
  if(file_exists("../../include/objects/bosbo_order_class.php")){	    include "../../include/objects/bosbo_order_class.php";	}
/*
for each none abstact category.
	while get parent != ""
		if no product/category mapping already present
			add one - popularity 0


if (isset($_GET['login'])&&isset($_GET['password'])) {
	$user1 = new User($_GET['login'],'','','','','','','','',$_GET['password'],'','', '');
	if($user1->AuthUser()){
		$user1 = $user1->GetByUsername($_GET['login']);
		$id = $user1->getUserId();
		if ($id<0) {
*/			
$allNACs = new Non_abstract_category(1);
$allNACs = $allNACs->getAllNACs();

// ADDED 19th Jan 2008 - to  fix bug where NACs are still referenced after deletion
// this means that the category products table will be fully empty when this runs.
// $k will only be run on the first call of the foreach statement below
$k = 0;

foreach ($allNACs as $value)
{
	echo "1) ". $value . "<br />";
	$category = new Category();
	$category = $category->get($value);
	$parentCategoryId = $category->getParentCategoryId();
	while ($parentCategoryId>0) {
		echo "next<br/>";
		// if mapping already exists remove it to update popularity
		// should never be called as of 19th Jan 2008 
		$catPro = new category_products();
		if (($catPro->exists($parentCategoryId, $value))) {
			$catProToDel = new category_products($parentCategoryId, $value);
			// ADDED 19th Jan 2008 - to  fix bug where NACs are still referenced after deletion
			// this means that the category products table will be fully empty when this runs.
			// $k will only be run on the first call of the foreach statement below
                        if ($k == 0) {
                               $k = 1;
				echo "TRUNCATE!!!";
				$catProToDel->TruncateTable();
                        }
			$catProToDel->Delete();
			//$catProToDel->Save();
			echo "Deleting $parentCategoryId --- $value<br />";
		}
		//then add
		$thisnac = new Non_abstract_category($value);
		$thisnac = $thisnac->Get($value);
		$catProToSave = new category_products($parentCategoryId, $value, $thisnac->getRating());
		$catProToSave->Save();
		echo "Adding $parentCategoryId --- $value --- rating: ".$thisnac->getRating()."<br />";
			
		$category = $category->get($parentCategoryId);
		$parentCategoryId = $category->getParentCategoryId();
	}
}

	
			
/*		} else {
			echo "ERROR1";
		}
	} else {
		echo "ERROR2";
	}
} else {
	echo "ERROR3";
}*/


?>
