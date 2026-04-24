<?php
  if (!isset($_SESSION)){
    session_name('bosbo-session');
    session_start();
  }
  if(file_exists("../include/php_library_fns/db_functions.php")){
    include "../include/php_library_fns/db_functions.php";
  }
  if(file_exists("../include/php_library_fns/user_functions.php")){
    include "../include/php_library_fns/user_functions.php";
  }
  if(file_exists("../include/objects/bosbo_category_class.php")){
    include "../include/objects/bosbo_category_class.php";
  }
  if(file_exists("../include/objects/bosbo_non_abstract_category_class.php")){
    include "../include/objects/bosbo_non_abstract_category_class.php";
  }
  if(file_exists("../include/php_library_fns/xml_functions.php")){
    include "../include/php_library_fns/xml_functions.php";
  }
  if(file_exists("../include/objects/bosbo_order_class.php")){
    include "../include/objects/bosbo_order_class.php";
  }
  // the database functions that this page uses
  if(file_exists("../include/php_library_fns/my_bosbo_monitor_db_functions.php")) {
      include "../include/php_library_fns/my_bosbo_monitor_db_functions.php";
  }

if ($_POST['completed'])
{
	$n_a_cat1 = new Non_abstract_category($_SESSION['currentCategory']);
	$n_a_cat1->Get($_SESSION['currentCategory']);
	$cat1 = new Category();
	$cat1->Get($_SESSION['currentCategory']);
	if ($_POST['official_website'])
	{
	$n_a_cat1->setOfficialWebsite($_POST['official_website']);
	}
	if ($_POST['description'])
	{
	$n_a_cat1->setDescription($_POST['description']);
	}
	/*if ($_POST['picture_url'])
	{
	$n_a_cat1->setPicture_url($_POST['picture_url']);
	$cat1->setCategory_thumbnail($_POST['picture_url']);
	}*/
	$n_a_cat1->initialiseLows();
	$n_a_cat1->Save();
	$cat1->Save();
	header("Location:addCategory.php"); exit();
}

?>

<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1" />
<title>Register</title>
	<script type="text/javascript" LANGUAGE="JavaScript" src="../js/page_fns.js"></script>
</head>

<body>
<form id="nonAbstractDetails" name="nonAbstractDetails" method="post" action="<?php $_SERVER['PHP_SELF']; ?>">

	official website: <input type="text" name="official_website" size="100" /><br/>
	description: <textarea name="description" cols="100" rows="6"></textarea><br/>
	
	<?php
	// picture URL is just a string - needs to be manually uploaded. 
	// users will be presented with an upload form which will do this for them.
	?>
	
	<!--picture URL: <input type="text" name="picture_url" size="100" /><br/>-->
	<input type="button" value="Add picture" onClick="javascript:popupNew('addNACategoryAddPicture.php?nacat_id=<?php echo $_SESSION['currentCategory'];?>', 250, 475);"><br>
	
	<p>May decide to put a picture upload form in the next page</p>
	<input type="hidden" name="completed" value="true">
	<input type="submit" value="Submit"/>

</form>

</body>
</html>