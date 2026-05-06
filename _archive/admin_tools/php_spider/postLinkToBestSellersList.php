<?php
if (!isset($_SESSION)){

    session_name('bosbo-session');

    session_start();

}

if(file_exists("CURL.php")){	    include "CURL.php"; }
if(file_exists("bosbo_spider_class.php")) {      include "bosbo_spider_class.php";  }
if(file_exists("../../include/php_library_fns/db_functions.php")) {      include "../../include/php_library_fns/db_functions.php";  }
if(file_exists("../../include/php_library_fns/xml_functions.php")) {      include "../../include/php_library_fns/xml_functions.php";  }
if(file_exists("../../include/objects/bosbo_order_class.php")){	    include "../../include/objects/bosbo_order_class.php";	  }
if(file_exists("../../include/objects/bosbo_most_popular_products_class.php")){     include "../../include/objects/bosbo_most_popular_products_class.php";        }
if(file_exists("../../include/objects/user_functions.php")){    include "../../include/objects/user_functions.php";  }
if(file_exists("../../include/objects/bosbo_affiliate_popular_products_class.php")){    include "../../include/objects/bosbo_affiliate_popular_products_class.php";  }
if(file_exists("../../include/php_library_fns/search_functions.php")) {      include "../../include/php_library_fns/search_functions.php";  }
if(file_exists("../../include/objects/bosbo_category_class.php")){    include "../../include/objects/bosbo_category_class.php";  }
if(file_exists("../../include/objects/bosbo_affiliate_popular_products_ignore_class.php")){    include "../../include/objects/bosbo_affiliate_popular_products_ignore_class.php";  }
///if(file_exists("../../include//objects/bosbo_affiliate_popular_products_class.php")){    include "../../include/objects/bosbo_affiliate_popular_products_class.php";  }


/*
  16th Feb 2008.  Neil Daniels
  This file allows a way for affilite/admin users (<0) to add their best sellers
  lists to the affiliate_popular_products table of the db.

  the only parameter DEFINITELY required for entry is the location of the bestsellers list
  ; the user can be taken from the current session.  an ajax test of this (such as that for
  quick order entry MAY be added for ease of use.
*/
echo $_GET['node'];
echo $_GET['bestseller_add'];
echo $_SESSION['valid_user'];

$new_bestlist = new affiliate_popular_products($_SESSION['valid_user'], $_GET['node'], $_GET['bestseller_add']);
$new_bestlist = $new_bestlist->Save(); 
?> 