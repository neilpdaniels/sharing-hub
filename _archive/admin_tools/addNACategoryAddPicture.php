<?php
if(file_exists("../include/php_library_fns/xml_functions.php")){	include "../include/php_library_fns/xml_functions.php";}
if(file_exists("../include/php_library_fns/db_functions.php")){	include "../include/php_library_fns/db_functions.php";}
if(file_exists("../include/php_library_fns/mkThumb.php")){	include "../include/php_library_fns/mkThumb.php";}
 
  if(file_exists("../include/objects/bosbo_category_class.php")){
    include "../include/objects/bosbo_category_class.php";
  }
  if(file_exists("../include/objects/bosbo_non_abstract_category_class.php")){
    include "../include/objects/bosbo_non_abstract_category_class.php";
  }
  if(file_exists("../include/objects/bosbo_order_class.php")){
    include "../include/objects/bosbo_order_class.php";
  }
  // the database functions that this page uses
  if(file_exists("../include/php_library_fns/my_bosbo_monitor_db_functions.php")) {
      include "../include/php_library_fns/my_bosbo_monitor_db_functions.php";
  }
if (!isset($_SESSION)){
	session_name('bosbo-session');
	session_start();
}
	
$to_continue = false;
$upload_error = "";


if($_POST["action"] == "Upload Image")
{
	
	

// needed if exif is not configured in php install;
$imtype = -1;
if ($_FILES['userfile']['type'] == 'image/gif') {
	$imtype = 1;
}
elseif ($_FILES['userfile']['type'] == 'image/jpg') {
	$imtype = 2;
}
elseif ($_FILES['userfile']['type'] == 'image/jpeg') {
	$imtype = 2;
}
elseif ($_FILES['userfile']['type'] == 'image/pjpeg') {
	$imtype = 2;
}
elseif ($_FILES['userfile']['type'] == 'image/png') {
	$imtype = 3;
}
	?>
	
	<html>
<head>
  <title>Add Category - Add Picture</title>
  
  <link rel="stylesheet" type="text/css" href="../css/L2_style.css"/>
</head>
<body>
	<?php
  if ($_FILES['userfile']['error'] > 0)
  {
    switch ($_FILES['userfile']['error'])
    {
      //upload_max_filesize
      case 1:  $upload_error = '<div id="xsmall"><b><font color="red">ERROR: chosen file exceeds maximum size allowed</font></b></div>';  break;
      //max_file_size
      case 2:  $upload_error = '<div id="xsmall"><b><font color="red">ERROR: chosen file exceeds maximum size allowed</font></b></div>';  break;
      case 3:  $upload_error = '<div id="xsmall"><b><font color="red">ERROR: file only partially uploaded - please retry</font></b></div>';  break;
      case 4:  $upload_error = '<div id="xsmall"><b><font color="red">ERROR: no file selected - please select file</font></b></div>';  break;
    }
    $to_continue = true;
  } else {

  // Does the file have the right MIME type? pjpeg??
  if (!(($_FILES['userfile']['type'] == 'image/jpeg') || ($_FILES['userfile']['type'] == 'image/pjpeg') || ($_FILES['userfile']['type'] == 'image/jpg') || ($_FILES['userfile']['type'] == 'image/gif') || ($_FILES['userfile']['type'] == 'image/png')))
  {
  	$upload_error = '<div id="xsmall"><b><font color="red">ERROR: chosen file is not of the correct format</font></b></div>';
  	$to_continue = true;
  } else {

  	
  	
  	
  	
  	// remove any other files that have the same name - different extension - stops confusion later
  	if (($_FILES['userfile']['type'] != 'image/jpeg')) {
		if (file_exists("../images/category_images/".$_GET['nacat_id']."_thumb.jpeg")) {
  					unlink("../images/category_images/".$_GET['nacat_id']."_thumb.jpeg");
		}
		if (file_exists("../images/category_images/".$_GET['nacat_id'].".jpeg")) {
  					unlink("../images/category_images/".$_GET['nacat_id'].".jpeg");
		}
  	}
  	if (($_FILES['userfile']['type'] != 'image/pjpeg')) {
		if (file_exists("../images/category_images/".$_GET['nacat_id']."_thumb.jpeg")) {
  					unlink("../images/category_images/".$_GET['nacat_id']."_thumb.jpeg");
		}
		if (file_exists("../images/category_images/".$_GET['nacat_id'].".jpeg")) {
  					unlink("../images/category_images/".$_GET['nacat_id'].".jpeg");
		}
  	}
  	if ($_FILES['userfile']['type'] != 'image/jpg') {
  		if (file_exists("../images/category_images/".$_GET['nacat_id']."_thumb.jpg")) {
  					unlink("../images/category_images/".$_GET['nacat_id']."_thumb.jpg");
		}
		if (file_exists("../images/category_images/".$_GET['nacat_id'].".jpg")) {
  					unlink("../images/category_images/".$_GET['nacat_id'].".jpg");
		}
  	} 
  	if ($_FILES['userfile']['type'] != 'image/gif') {
  		if (file_exists("../images/category_images/".$_GET['nacat_id']."_thumb.gif")) {
  					unlink("../images/category_images/".$_GET['nacat_id']."_thumb.gif");
		}
		if (file_exists("../images/category_images/".$_GET['nacat_id'].".gif")) {
  					unlink("../images/category_images/".$_GET['nacat_id'].".gif");
		}
  	}
  	if ($_FILES['userfile']['type'] != 'image/png') {
  		if (file_exists("../images/category_images/".$_GET['nacat_id']."_thumb.png")) {
  					unlink("../images/category_images/".$_GET['nacat_id']."_thumb.png");
		}
		if (file_exists("../images/category_images/".$_GET['nacat_id'].".png")) {
  					unlink("../images/category_images/".$_GET['nacat_id'].".png");
		}
  	}

  // to get the file extension reverse the string and get the first element
  $nameArray = explode('.', strrev($_FILES['userfile']['name']));
  $file_extension =strtolower(strrev($nameArray[0]));
  
  $upfile = '../images/category_images/originals/'.$_POST["nacat_id"].".".$file_extension;//original - to be deleted
  $upfile_large = '../images/category_images/'.$_POST["nacat_id"].".".$file_extension;//to be large
  $upfile_thumb = '../images/category_images/'.$_POST["nacat_id"]."_thumb.".$file_extension;//to be thumbnail

  if (is_uploaded_file($_FILES['userfile']['tmp_name'])) 
  {
     if (!move_uploaded_file($_FILES['userfile']['tmp_name'], $upfile))
     {
        echo 'Problem: Could not move file to destination directory.  Please contact Bosbo support.';
        exit;
     } else {
     	
     	// this is where we need to modify the picture attributes - for the moment the thumbnail is just the other copied.s
     	//copy($upfile, $upfile_thumb);
     	
     	if (mkthumb($upfile, $upfile_large, $imtype, 150) &&	mkthumb($upfile, $upfile_thumb, $imtype, 102)) {
	     	$cat = new Category();
	     	//$nacat = new Non_abstract_category($_SESSION['currentCategory']);
	     	//$nacat->Get($_SESSION['currentCategory']);	
	     	//$cat->Get($_SESSION['currentCategory']);
	     	$nacat = new Non_abstract_category($_POST["nacat_id"]);
	     	$nacat->Get($_POST["nacat_id"]);	
	     	$cat->Get($_POST["nacat_id"]);
	     	$nacat->setPicture_url($_POST["nacat_id"].".".$file_extension);
	     	$cat->setCategory_thumbnail($_POST["nacat_id"]."_thumb.".$file_extension);
	     	$nacat->Save();
	     	$cat->Save();
	     	unlink('../images/category_images/originals/'.$_POST["nacat_id"].".".$file_extension);
     		echo '<div id="bosbo_logo_small" align="center"><img src="../images/bosbo_logo_small.gif"></div><br><br>';
     		echo '<div id="xsmall">File uploaded successfully</div><br><br><br>';
     		echo '<div align="center" class="bbsmall"><a href="javascript:window.close();" align="center">close this window</a></div>';
     	} else {
     		// error modifing images - the error will already have been displayed.
     		exit;
     	}	
     }
  } 
  else 
  {
    echo 'Problem: Possible file upload attack. Filename: ';
    echo $_FILES['userfile']['name'];
    echo '.<br>Please contact Bosbo support.';
    exit;
  }
  }
  }
}
  

// need to put in another clause or 
if($_POST["action"] != "Upload Image" || $to_continue==true) {
	if (isset($_GET['nacat_id']) || isset($_POST["nacat_id"])) {  	

  	?>

<html>
<head>
  <title>Add Offer - Add Picture</title>
  
  <link rel="stylesheet" type="text/css" href="../css/L2_style.css"/>
</head>
<body>

  <div id="bosbo_logo_small" align="center"><img src="../images/bosbo_logo_small.gif"></div><br>
  <?php
  if ($upload_error!="") { echo $upload_error; }
  ?>
  <form enctype="multipart/form-data" method="POST" action="<?php echo $_SERVER['PHP_SELF']."?nacat_id=".$_GET['nacat_id'];?>">
    <div id="xsmall">
      Please select the image you wish to be associated with your offer.  The image must have a format of either jpeg, gif or png, and must be under 500 kilobytes (approx. 0.5mb) in size.
    </div><br>
    <input type="hidden" name="MAX_FILE_SIZE" value="500000">
    <input name="userfile" type="file" size="50">
    <input type="hidden" name="nacat_id" value="<?php echo $_GET['nacat_id']; ?>"
    <br><br>
    <div align="center"><input type="submit" value="Upload Image" name="action"></div>
  </form>
</body>
</html>
<?php
} else {
?>
<html>
<head>
  <title>Add Offer - Add Picture</title>
  
  <link rel="stylesheet" type="text/css" href="../css/L2_style.css"/>
</head>
<body>
  <div id="bosbo_logo_small" align="center"><img src="../images/bosbo_logo_small.gif"></div>
    <div id="xsmall">
      ERROR - please contact Bosbo support
    </div>
</body>
</html>
<?php
}
}

?>