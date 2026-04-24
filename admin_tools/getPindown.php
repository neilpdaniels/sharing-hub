<?php
/*

used by addCategory's AJAX to get further sub-categories so that a new nacat or acat can be added to the catalogue.

*/

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
  


$level = $_POST['level'];
$node_id = $_POST['node'];

if ( isset($_POST['level']) && isset($_POST['node'])) {
?>
	
	<span id='hidden_var'>
		<input type="hidden" name="test" value="test">
		<input type="hidden" name="pindown_level" value="<?php echo $level+1; ?>">
		<input type="hidden" name="pindown_level_text" value="parentCategory<?php echo $level+1; ?>">
	</span>
	<select size="20" name="parentCategory<?php echo $level+1; ?>" >
	<?php
	$ret_arr = returnChildAbstractCategories($node_id);
	$first = true;
	foreach ($ret_arr as $value)
	{
		$temp_cat = new Category();
		$temp_cat->Get($value);
		
		//first item will be selected - an item will always have a parent
		$selected = "";
		if ($first) { $selected = "selected='selected'"; $first=false; }
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
<?php
}

?>
