<?php
  if (!isset($_SESSION)){
    session_name('bosbo-session');
    session_start();
  }
  if(file_exists("../include/php_library_fns/db_functions.php")){
    include "../include/php_library_fns/db_functions.php";
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

$level = 0;
$name = $_POST['name'];
$description = $_POST['description'];
$parentCategory = $_POST[$_POST['pindown_level_text']];
$superParent = $_POST['parentCategory1'];
$keyword = $_POST['keyword'];


//echo "1------" . $parentCategory . " ---- " . $_POST['pindown_level_text'] . "";
if ( ($_POST['name']) and 
	 //($_POST['description'] ) and
 	 ($parentCategory ) and
 	 ($_POST['parentCategory1']) and
 	 ($_POST['keyword'] )
	)
{
	//echo "2------" . $parentCategory;
	
	// add to database
	if ($_POST['abstractCategory'])
	{
		$cat1 = new Category($name, $description, $parentCategory, $keyword . " " . strrev($keyword), $_POST['parentCategory1'] , '1', 'nac_na.gif');
		$cat1->Save();
	} else
	{
		$cat1 = new Category($name, $description, $parentCategory, $keyword . " " . strrev($keyword), $_POST['parentCategory1'], '0', 'nac_na.gif');
		$cat1->Save();
		$n_a_cat1 = new Non_abstract_category($cat1->getCategoryId());
		$n_a_cat1->Save();
		$_SESSION['currentCategory'] = $cat1->getCategoryId();
		header("Location:addNonAbstractCategory.php"); exit();
	}
}
?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1" />
<title>Register</title>

	<SCRIPT type="text/javascript" LANGUAGE="JavaScript" SRC="../js/md5.js"></SCRIPT>
	<script type="text/javascript" src="ajax_admin_functions.js"></script>
<!--	<script type="text/javascript" src="../js/javascript_functions.js"></script>	-->
</head>

<body>
<?php echo "user : " . $_SERVER['REMOTE_USER']; ?>
<p>THIS IS AN ADMIN ONLY TOOL - root node needs to be entered manually</p>

<form id="addCategory" name="addCategory" method="POST" action="<?php $_SERVER['PHP_SELF']; ?>">

	name: <input type="text" name="name" size="25" /><br/>
	description: <input type="text" name="description" size="35" /><br/>
	choose parent category:
	<br>
	<select size="20" name="parentCategory1" >
	<?php
	$ret_arr = returnChildAbstractCategories('1');
	$first = true;
	foreach ($ret_arr as $value)
	{
		$temp_cat = new Category();
		$temp_cat->Get($value);
		
		//first item will be selected - an item will always have a parent
		$selected = "";
		if ($value==86) { $selected = "selected='selected'"; $first=false; }
		?>
		<option 
		value='<?php echo $value . "'
		 " . $selected; ?> 
		ondblclick="
		postPindownContent('getPindown.php', 'level='+document.forms['addCategory'].elements['pindown_level'].value
		+'&node=<?php echo $value; ?>'
		);
		"><?php echo $temp_cat->getName() . "</option>"; ?>
		<?php
	}
	?>
	</select>
	<span id='pindown'>
	<span id='hidden_var'>
	<input type="hidden" name="pindown_level" value="<?php echo $level+1; ?>">
	<input type="hidden" name="pindown_level_text" value="parentCategory<?php echo $level+1; ?>">
	</span>
	</span>

	
	
	<p>&nbsp</p>
	keywords: <input type="text" name="keyword" size="50" /><br/>
	
	<p>change so that select box - with option not to show l1 grids)</p>
	abstract: <input type="checkbox" name='abstractCategory' value="abstractCategory" checked="checked" />
	
	<input type="submit" value="Submit"/>

</form>

</body>
</html>
