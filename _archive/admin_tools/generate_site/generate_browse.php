<?php
/* 19th Feb 2008
 * Author: Neil Daniels
 * File Desc: This page generates all of the browse_
*/


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

$toGenerate = returnAllAbstractCategories();

foreach ($toGenerate as $categoryid) {
	$openCat = new Category();
	$openCat = $openCat->Get($categoryid);
	//if ($i<2) {
	//	$i++;
	$myFile = "../../pages/navigation/".$openCat->getStaticPageName();
	$fh = fopen($myFile, 'w') or die("can't open file");
	fwrite($fh, getContent($categoryid));
	fclose($fh);
	//}
	
}

function getContent($a) {
//$thisCat = new Category();
//$thisCat->Get($a);

return '<?php
  if (!isset($_SESSION)){
    session_name(\'bosbo-session\');
    session_start();
  }
if (file_exists("../../include/objects/bosbo_category_class.php")) {
    include "../../include/objects/bosbo_category_class.php";
}
if (file_exists("../../include/php_library_fns/db_functions.php")) {
    include "../../include/php_library_fns/db_functions.php";
}
if (file_exists("../../include/php_library_fns/page_functions.php")) {
    include "../../include/php_library_fns/page_functions.php";
}
if (file_exists("../../include/php_library_fns/xml_functions.php")) {
    include "../../include/php_library_fns/xml_functions.php";
}
if (file_exists("../../include/objects/user_functions.php")) {
    include "../../include/objects/user_functions.php";
}
if (file_exists("../../include/php_library_fns/my_bosbo_monitor_db_functions.php")) {
    include "../../include/php_library_fns/my_bosbo_monitor_db_functions.php";
}
if (file_exists("../../include/objects/bosbo_message_class.php")) {
    include "../../include/objects/bosbo_message_class.php";
}
if (file_exists("../../include/objects/bosbo_order_class.php")) {
    include "../../include/objects/bosbo_order_class.php";
}
if (file_exists("../../include/objects/bosbo_non_abstract_category_class.php")) {
    include "../../include/objects/bosbo_non_abstract_category_class.php";
}
if (file_exists("../../include/objects/bosbo_most_popular_products_class.php")) {
    include "../../include/objects/bosbo_most_popular_products_class.php";
}
if (file_exists("../../include/php_library_fns/Input_validation_functions.php")) {
    include "../../include/php_library_fns/Input_validation_functions.php";
}
if (file_exists("../../include/php_library_fns/search_functions.php")) {
    include "../../include/php_library_fns/search_functions.php";
}
$CI_Input = new CI_Input();
$CI_Input->_sanitize_globals(TRUE);
  
  
  
$catNode='.$a.';
$universalCat = new Category();
$universalCat= $universalCat->Get('.$a.');
  // get name for titile

  if (isset($catNode)) {

  	$thisCat = new Category();

  	$thisCat->Get($catNode);

  }
if ($thisCat->Get($catNode)!=0) { 
?>

<!DOCTYPE html>
<html lang="en">
<head>
    <title>Bosbo: <?php echo $thisCat->getName(); ?></title>
    <meta charset="utf-8">
    <link rel="icon" href="../../img/favicon.ico" type="image/x-icon">
    <link rel="shortcut icon" href="../../img/favicon.ico" type="image/x-icon" />
    <meta name="description" content="Your description">
    <meta name="keywords" content="Your keywords">
    <meta name="author" content="Your name">
    <meta name = "format-detection" content = "telephone=no" />
    <link rel="stylesheet" href="../../css/templt/bootstrap.css" type="text/css" media="screen">
    <link rel="stylesheet" href="../../css/templt/responsive.css" type="text/css" media="screen">
    <link rel="stylesheet" href="../../css/templt/style.css" type="text/css" media="screen">
    <link rel="stylesheet" href="../../css/templt/camera.css" type="text/css" media="screen">

<!--        <link rel="stylesheet" type="text/css" href="../css/style.css" />
        <link rel="stylesheet" type="text/css" href="../css/navigation.css" />
        <link rel="stylesheet" type="text/css" href="../css/navigation.css" />        
-->
        <script type="text/javascript" LANGUAGE="JavaScript" SRC="../../js/md5.js"></script >
        <script type = "text/javascript" src = "../../ajax/ajax_functions.js" ></script>
        <script type="text/javascript" LANGUAGE="JavaScript" src="../../js/page_fns.js"></script>
        
    <script type="text/javascript" src="../../js/templt/jquery.equalheights.js"></script>
    <script>
      $(window).load(function() {   
        jQuery(".maxheight").equalHeights();  
      })
    </script>
		<script type="text/javascript" src="../js/templt/jquery.js"></script>
    <script type="text/javascript" src="../../js/templt/superfish.js"></script>
    <script type="text/javascript" src="../../js/templt/jquery.mobilemenu.js"></script>
    <script type="text/javascript" src="../../js/templt/jquery.easing.1.3.js"></script>
    
    <script type="text/javascript" src="../../js/templt/camera.js"></script>
    <!--[if (gt IE 9)|!(IE)]><!-->
          <script type="text/javascript" src="../../js/templt/jquery.mobile.customized.min.js"></script>
    <!--<![endif]-->
    <script>
      $(document).ready(function(){
           jQuery(\'.camera_wrap\').camera();
          });
    </script> 
    
  	<!--[if lt IE 8]>
    		<div style=\'text-align:center\'><a href="http://www.microsoft.com/windows/internet-explorer/default.aspx?ocid=ie6_countdown_bannercode"><img src="http://www.theie6countdown.com/../img/upgrade.jpg"border="0"alt=""/></a></div>  
   	<![endif]-->
    <!--[if lt IE 9]>
      <link rel="stylesheet" href="../../css/templt/ie.css" type="text/css" media="screen">
      <script src="http://html5shim.googlecode.com/svn/trunk/html5.js"></script>
    <![endif]-->
    <script src="http://ajax.googleapis.com/ajax/libs/jquery/1.6.2/jquery.min.js"></script>
<script>
        $(document).ready(function(){
  $(\'#login-trigger\').click(function(){
    $(this).next(\'#login-content\').slideToggle();
    $(this).toggleClass(\'active\');          
    
    if ($(this).hasClass(\'active\')) $(this).find(\'span\').html(\'&#x25B2;\')
      else $(this).find(\'span\').html(\'&#x25BC;\')
    })
});
    </script>

</head>

  <body  >
	  <?php $shape=displayHeader(readXmlMenuDefinition("../../../xml/xml_menu_definition.xml"));
	  list($default, $count)=$shape?>
	  <?php //displaySearchBar();?>
	  <?php //displayLeftSidebar() ?>
<div id="content">

        
    
      <div class="container"> 
            <div class="row">
                 <article class="span12 clearfix">
                   <h2 class="bgh2">our services</h2>
                 </article>
                 <ul class="thumbnails">
                   <li class="span6 thumbnail">
                     <div class="block-thumbnail maxheight">
                       <figure class="img-polaroid"><img src="../../img/page-img.jpg" alt=""></figure>
                       <h3>Dog walking</h3>
                       <p>Lorem ipsum dolor sit amet, consectetuer
adipiscing elit, sed diam nonummy nibh euis
mod tincidunt ut lao.</p>
                        <a href="#" class="link">Read More<span></span></a>
                     </div>
                   </li>
                   <li class="span6 thumbnail">
                     <div class="block-thumbnail maxheight">
                       <figure class="img-polaroid"><img src="../../img/page-img-1.jpg" alt=""></figure>
                       <h3>Play time </h3>
                       <p>Lorem ipsum dolor sit amet, consectetuer
adipiscing elit, sed diam nonummy nibh euis
mod tincidunt ut lao.</p>
                        <a href="#" class="link">Read More<span></span></a>
                     </div>
                   </li>
                
                
                 </ul>
                 <article class="span12 clearfix"><div class="divider"></div></article>
            </div>
            <div class="row">
              <article class="span6">
                <h2 class="h2-indent">Pet Sitting 
Service</h2>
                <ul class="list">
                  <li><a href="#">Dog walking/potty breaks</a></li>
                </ul>
                <a href="#" class="link">Read More<span></span></a>
              </article>
              <article class="span6">
                <h2 class="h2-indent">About wastaco A<span>A</span>A</h2>
                <div class="block-indent">
                  <figure class="img-polaroid"><img src="../../img/page-img-4.jpg" alt=""></figure>
                  <div class="extra-wrap">
                    <h4>“ Professients.”</h4>
                    <p>L nostrud niam.</p>
                      <a href="#" class="link">Read More<span></span></a>
                  </div>
                </div>
              </article>
            </div>
      </div>


<?php

	if (isset($catNode)) {

?>

<div align="center"><p class="bbsmallb"><?php echo $thisCat->getName(); ?>

<?php

// BISCUIT

$node = \'\';

if ($catNode==\'\')

{

  // ROOT NODE MUST HAVE ID 1

  $node = \'1\';

} else {

  $node = $catNode;

}

?>

<p class="bbxsmall" align=\'left\'> you are here: 

<?php 



	$biscuit = \'\';

	$temp_node = $node;

	$bis_vals = array();

	// while loop up until root - this builds a list of numbers for the biscuit

	while ($temp_node!=\'1\')

	{

		$cat1 = new Category();

		$cat1 -> Get($temp_node);

		array_push($bis_vals, $temp_node);	

		$temp_node = $cat1->getParentCategoryId();

	}

	array_reverse($bis_vals);



	?>

		<a href="../home.php" >

		Home</a> /

	<?php

	// while loop up until root - this builds a list of numbers for the biscuit

	$temp_node = array_pop($bis_vals);

	while ($temp_node!=$catNode)

	{

		$cat1 = new Category();

		$cat1 -> Get($temp_node);

		?>

		<a href="<?php echo $cat1->getStaticPageName(); 

		?>" >

		<?php echo $cat1->getName() . 

		"</a> /";

		$temp_node = array_pop($bis_vals);

	}

	$cat1 = new Category();

	$cat1 -> Get($temp_node);

	?>

	<a href="<?php echo $cat1->getStaticPageName(); 	
			if (isset($_GET[\'sort_by\'])) {
				echo "&sort_by=" .$_GET[\'sort_by\'];
			}?>" >

	<?php echo $cat1->getName() . 

	"</a>";

	?>

</p></div>

	<?php

	
	if ($_SESSION[\'valid_user\']<0) {
				?>
 				<div align="center">
				<form name=\'bestseller\'>
				<input type=\'text\' length=\'100\' name=\'bestseller_add\'>
				<input type="button" value="Add bestsellers list!" onClick="parent.location=\'../../admin_tools/php_spider/linkToBestSellersList.php?node=<?php echo $catNode; ?>&bestseller_add=\'+document.forms[\'bestseller\'].elements[\'bestseller_add\'].value"></form></div>
 				<?php
 	}
 			
	//Display sub-categories

	//// WHY DOES THIS RUN ON THE FLY???  IF WE ADD NEW CATS WE SHOULD RE-RUN GENERATION,
	//// THEREFORE ALL SUB CATS COULD BE GENERATED
	$ret_arr = returnChildAbstractCategories($catNode);

	if (sizeof($ret_arr)>0) {

		?>

		<span id="heading1"><h4>Further sub-categories</h4></span>

		<div id="browsebox">

		<!--<li><a href="mutter02.html">Books</a></li>-->

			<table width="100%"><tr>

			<?php

			$tvar = -1;

		

			foreach ($ret_arr as $value)

			{

				$tvar=$tvar+1;

				// if 2 done then new row

				if (($tvar%2)==0) {

					echo "</tr><tr>";

				}

				echo "<td width=\'33%\'>";

				$temp_cat = new Category();

				$temp_cat->Get($value);

				?>
<a href="<?php echo $temp_cat->getStaticPageName(); ?>"><img src="../../images/abstract_category_images/browse_<?php echo $value;?>.jpg" alt="product_image" width="240" height="80"></a>
					<li><a href="<?php echo $temp_cat->getStaticPageName(); ?>" class="bbxxsmall">

				<?php echo $temp_cat->getName() . 

				"</a>";

				if ($temp_cat->getDescription()!=\'\') {

					echo "<br><p class=\'bbxxxsmall\'><i>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;" . $temp_cat->getDescription() . "</i></br></td>";

				}

				echo "</li>";

			}

			?>

			</tr>

			</table>

		</div>

	<?php

	}



	//Display products

	// default to page 1

	if (!(isset($_GET[\'displaySet\']))) {

		$_GET[\'displaySet\'] = 1;

	}

	//if(strcmp($_GET[\'sort_by\'], "1")==0){ echo "selected"; }

	if (!(isset($_GET[\'sort_by\']))) {

		$ret_arr = returnChildNonAbstractCategories($catNode, 100, $_GET[\'displaySet\']);

	} elseif (strcmp($_GET[\'sort_by\'], "1")==0) {

		$ret_arr = returnChildNonAbstractCategories($catNode, 100, $_GET[\'displaySet\'], \'ORDER BY non_abstract_category.rating DESC\');

	} elseif (strcmp($_GET[\'sort_by\'], "2")==0) {

		$ret_arr = returnChildNonAbstractCategories($catNode, 100, $_GET[\'displaySet\'], \'ORDER BY non_abstract_category.newMH ASC\');

	}  elseif (strcmp($_GET[\'sort_by\'], "3")==0) {

		$ret_arr = returnChildNonAbstractCategories($catNode, 100, $_GET[\'displaySet\'], \'ORDER BY non_abstract_category.newMH DESC\');

	}  elseif (strcmp($_GET[\'sort_by\'], "4")==0) {

		$ret_arr = returnChildNonAbstractCategories($catNode, 100, $_GET[\'displaySet\'], \'ORDER BY category.name ASC\');

	}  elseif ($_GET[\'sort_by\']==5) {

		$ret_arr = returnChildNonAbstractCategories($catNode, 100, $_GET[\'displaySet\'], \'ORDER BY category.name DESC\');

	}

	$count = array_shift($ret_arr);
	
	if (sizeof($ret_arr)>0) {

?>

		<span id="heading1"><h4>Products only in this category</h4></span>

<?php 
			
		if ($count>0) {
 			
			if (($count>10)&&($_GET[\'displaySet\']!=-1)) {

				echo "<p class=\'bbxxsmall\' align=\'center\'>showing product(s) <b>" . ((($_GET[\'displaySet\']-1)*10)+1) . "</b> to <b>" . ((($_GET[\'displaySet\']-1)*10)+sizeof($ret_arr)) . "</b> of $count<br />";

				

				/////////// PAGE NUMBERS //////////

				$display_at_end = true;

				echo "page: ";

				$pageNum=1;

				for ($i=0; $i < $count; $i+=10) {

					if ($i>0) { echo " | "; }

					if ($_GET[\'displaySet\']!=$pageNum){

					?>

					<a href="<?php echo $universalCat->getStaticPageName(); ?>?displaySet=<?php echo $pageNum; 

					if (isset($_GET[\'sort_by\'])) {

						echo "&sort_by=" .$_GET[\'sort_by\'];

					}

					?>" class="bbxsmall">

<?php echo $pageNum; ?></a>

				<?php

					} else {

						echo "<span id=\'selectedPageNum\'>".$pageNum."</span>";

					}

					$pageNum++;

				}


?>
<br />
<a href="<?php echo $universalCat->getStaticPageName(); ?>?displaySet=-1<?php
                                        if (isset($_GET[\'sort_by\'])) {
                                                echo "&sort_by=" .$_GET[\'sort_by\'];
                                        }
                                        ?>" class="bbxsmall">Show all items</a>
<?php


				///////////END OF PAGE NUMBERS////////////////

			} else {

				echo "<p class=\'bbxxsmall\' align=\'center\'>showing all $count product(s)</p>";

			}
		}	
?>

<div align="center">

		<form id="sort">

			  <select name="sort_by">

                <option value="1" <?php if(strcmp($_GET[\'sort_by\'], "1")==0){ echo "selected"; }?>>Sort by Popularity</option>

                <option value="2" <?php if(strcmp($_GET[\'sort_by\'], "2")==0){ echo "selected"; }?>>Sort by Price (Ascending)</option>

                <option value="3" <?php if(strcmp($_GET[\'sort_by\'], "3")==0){ echo "selected"; }?>>Sort by Price (Descending)</option>

                <option value="4"  <?php if(strcmp($_GET[\'sort_by\'], "4")==0){ echo "selected"; }?>>Sort by Name (Ascending)</option>

                <option value="5" <?php if(strcmp($_GET[\'sort_by\'], "5")==0){ echo "selected"; }?>>Sort by Name (Descending)</option>

              	</select>

		<input type="button" name="sortby" value="Go" onclick="
parent.location=\'<?php echo $universalCat->getStaticPageName();?>
?sort_by=\'+document.forms[\'sort\'].elements[\'sort_by\'].value<?php
if ($_GET[\'displaySet\']==-1) {
	echo "+\'&displaySet=-1\'";
}?>;">

              </form>

		</div>

		</p>

		<div id="browsebox">

		<!--<li><a href="mutter02.html">Books</a></li>-->

			<table width="100%">

			<?php

			$first= true;

			foreach ($ret_arr as $value)

			{

				$temp_cat = new Category();

				$temp_cat->Get($value);

				$na_cat = new Non_abstract_category($value);

				//$na_cat->Get();

				if ($first) {

					$first = false;

				} else {

					echo \'<tr><td colspan="3"><hr id="separator"></td></tr>\';

				}

				?>

				<tr>

				<td width="60px" align="center">

				<a href="<?php echo $na_cat->getStaticProductPageName($temp_cat->getName()); ?>">

					<img src="../../images/category_images/<?php echo $temp_cat->getCategory_thumbnail(); ?>" alt="product_pic">

				</a>

				</td>

				<td>

					<table>

						<tr>

							<td>

								<a href="<?php echo $na_cat->getStaticProductPageName($temp_cat->getName()); ?>" class="bbxxxsmall">

								<?php echo $temp_cat->getName(); ?> </a>

							</td>

						</tr>

						<tr>

							<td><p class="bbxxxsmall"><?php echo $temp_cat->getDescription(); ?></p>

							</td>

						</tr>

					</table>

				</td>

				<td width="135px" align="center"><span id="medium_blue_text"><?php 

					if ($na_cat->getNewBestOffer()!="**.**") {

						echo "buy new for &pound;".sprintf(\'%0.2f\', $na_cat->getNewBestOffer());

					} else {

						//echo sprintf(\'%0.2f\',0.0) . "(no active adverts)";
						echo "no active adverts";

					}

					 ?></span><br><span id="small_red_text"><?php

					 if ($na_cat->getBestBid()!="**.**") {
						// selling a new item to either a new or used advert
						// person seeking used should be quite happy with new!
						echo "sell for &pound;".sprintf(\'%0.2f\', $na_cat->getBestBid());

					} else {

						//echo sprintf(\'%0.2f\',0.0) . "(no active adverts)";
						echo "no active adverts";

					}

					?></span>

				</td>

				</tr>

			<?php

			}

			?>

			</table>

		</div>

		<?php

		if ($display_at_end){

			echo "<div align=\'center\'><p class=\'bbxxsmall\'>";

				/////////// PAGE NUMBERS //////////

				echo "page: ";

				$pageNum=1;

				for ($i=0; $i < $count; $i+=10) {

					if ($i>0) { echo " | "; }

					if ($_GET[\'displaySet\']!=$pageNum){

					?>

					<a href="<?php echo $universalCat->getStaticPageName(); ?>?displaySet=<?php echo $pageNum; 
					
					if (isset($_GET[\'sort_by\'])) {
						echo "&sort_by=" .$_GET[\'sort_by\'];

					}

					?>" class="bbsmall">

<?php echo $pageNum; ?></a>

				<?php

					} else {

						echo "<span id=\'selectedPageNum\'>".$pageNum."</span>";

					}

					$pageNum++;

				}

				///////////END OF PAGE NUMBERS////////////////

			echo "</p></div>";

		}

	} else {

		$mpp = new most_popular_products();

		$mpp = $mpp->Get($node);

		$mppArray = $mpp->getPopularProducts();

		$prodNum = 0;

		?>

		<span id="heading1"><h4>Popular products in these categories</h4></span>

		<?php

		?>

		<div id="browsebox">

			<table width="100%" id="popularProducts">

			<?php

			$first= true;

			foreach ($mppArray as $value)

			{

				$prodNum++;

				if ($value!=0)

				{

					$temp_cat = new Category();

					$temp_cat->Get($value);

					$na_cat = new Non_abstract_category($value);

					//$na_cat->Get();

					if ($first) {

						$first = false;

					} else {

						 echo \'<tr align="center"><td colspan="3" bgcolor="#C0C0C0" height="2px"></td></tr>\';

						 //echo \'<hr id="separator">\';

					}

					?>

					<tr>

					<td>

						<table>

							<tr>

								<td class="bbxxsmall"><?php echo $prodNum.") ";?>

								</td>

								<td>

									<a href="<?php echo $na_cat->getStaticProductPageName($temp_cat->getName()); ?>" class="bbxxsmall">

									<?php echo $temp_cat->getName(); ?> </a>

								</td>

							</tr>

							<tr>

								<td><p class="bbxxxsmall"><?php echo $temp_cat->getDescription(); ?></p>

								</td>

							</tr>

						</table>

					</td>

					<td width="135px" align="center"><span id="small_blue_text"><?php 

					if ($na_cat->getNewBestOffer()!="**.**") {

						echo "buy new for &pound;" .sprintf(\'%0.2f\', $na_cat->getNewBestOffer());

					} else {

						//echo sprintf(\'%0.2f\',0.0) . "(no active adverts)";
						echo "no active adverts";

					}

					 ?></span><br><span id="small_red_text"><?php

					 if ($na_cat->getBestBid()!="**.**") {

						echo "sell for &pound;".sprintf(\'%0.2f\', $na_cat->getBestBid());

					} else {

						//echo sprintf(\'%0.2f\',0.0) . "(no active adverts)";
						echo "no active adverts";

					}

					?></span>

					</td>

					</tr>

					<?php

				}

			}



			?>

			</table>

		</div>

		<?php

	}

  }

  ?>		<br>

		<div align="center"><a href="requestCategory.php" class="bbxxsmall">Can\'t see the item you want?  Request a product be added to the catalogue!</a></div>
  </div>
  </div>
    <?php displayFooter() ?>

  </body>

</html>
<?php
} else {
	echo "ERROR";
}?>';


}
?>