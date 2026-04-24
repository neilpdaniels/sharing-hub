<?php
  if (!isset($_SESSION)){
    session_name('bosbo-session');
    session_start();
  }
  
    if(file_exists("../../include/php_library_fns/db_functions.php")){    	include "../../include/php_library_fns/db_functions.php";  	}
  	if(file_exists("../../include/objects/user_functions.php")){    	include "../../include/objects/user_functions.php";  	}
	if(file_exists("../../include/php_library_fns/xml_functions.php")){    	include "../../include/php_library_fns/xml_functions.php";  	}
  	if(file_exists("../../include/objects/bosbo_non_abstract_category_class.php")){  	  	include "../../include/objects/bosbo_non_abstract_category_class.php";    }
  	if(file_exists("../../include/objects/bosbo_category_class.php")){  	  	include "../../include/objects/bosbo_category_class.php";    }
    if(file_exists("../../include/php_library_fns/random_functions.php")){  	  	include "../../include/php_library_fns/random_functions.php";    }
  	if(file_exists("../../include/php_library_fns/page_functions.php")) {      include "../../include/php_library_fns/page_functions.php";  	}
  	if(file_exists("../../include/php_library_fns/my_bosbo_monitor_db_functions.php")) {      include "../../include/php_library_fns/my_bosbo_monitor_db_functions.php";  }
  if(file_exists("../../include/objects/bosbo_message_class.php")){	    include "../../include/objects/bosbo_message_class.php";  }
  if(file_exists("../../include/objects/bosbo_order_class.php")){	    include "../../include/objects/bosbo_order_class.php";	}
    	    if(file_exists("../../include/php_library_fns/Input_validation_functions.php")){    include "../../include/php_library_fns/Input_validation_functions.php";  }
$CI_Input = new CI_Input();
$CI_Input->_sanitize_globals(TRUE);

$nac1  = new Non_abstract_category(1);
$allNACs = $nac1->getAllNACs();
echo "SIZE OF :" . sizeof($allNACs);

foreach ($allNACs as $singleNAC) {
	$AC = new Category();
	$AC = $AC->Get($singleNAC);
	$AC->Delete();
	
	$nac2 = new Non_abstract_category($singleNAC);
	$nac2 = $nac2->Get($singleNAC);
	$nac2->Delete();	
	echo "DELETING";
}

?>

