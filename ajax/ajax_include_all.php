<?php
  if (!isset($_SESSION)){
    session_name('bosbo-session');
    session_start();
  }
  
  if(file_exists("../include/page_functions.php")){
    include "../include/page_functions.php";
  }
  
  if(file_exists("../include/xml_functions.php")){
    include "../include/xml_functions.php";
  }
  
  if(file_exists("../include/db_functions.php")){
    include "../include/db_functions.php";
  }

  if(file_exists("../include/user_functions.php")){
    include "../include/user_functions.php";
  }

?>
