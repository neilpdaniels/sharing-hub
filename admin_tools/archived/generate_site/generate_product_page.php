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
if(file_exists("../../include/objects/bosbo_non_abstract_category_class.php")){    include "../../include/objects/bosbo_non_abstract_category_class.php";  }
if(file_exists("../../include/objects/bosbo_affiliate_popular_products_ignore_class.php")){    include "../../include/objects/bosbo_affiliate_popular_products_ignore_class.php";  }

$nac1 = new Non_abstract_category('-1');  // NAC with -1 (null)
$toGenerate = $nac1->getAllNACs();

$i=0;
foreach ($toGenerate as $categoryid) {
	$openNACat = new Non_abstract_category($categoryid);
	$openCat = $openNACat->Get($categoryid);
	$openCat = new Category();
	$openCat = $openCat->Get($categoryid);
	//if ($i<2) {
	//  $i++;
	$myFile = "../../pages/navigation/".$openNACat->getStaticProductPageName($openCat->getName());
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
  if(file_exists("../../include/php_library_fns/xml_functions.php")){    include "../../include/php_library_fns/xml_functions.php";  }
  if(file_exists("../../include/php_library_fns/db_functions.php")){    include "../../include/php_library_fns/db_functions.php";  }
  if(file_exists("../../include/php_library_fns/random_functions.php")){  	  	include "../../include/php_library_fns/random_functions.php";  }
  if(file_exists("../../include/objects/user_functions.php")){    include "../../include/objects/user_functions.php";  }
  if(file_exists("../../include/objects/bosbo_category_class.php")){    include "../../include/objects/bosbo_category_class.php";  }
  if(file_exists("../../include/objects/bosbo_non_abstract_category_class.php")){    include "../../include/objects/bosbo_non_abstract_category_class.php";  }
  if(file_exists("../../include/objects/bosbo_order_class.php")){    include "../../include/objects/bosbo_order_class.php";  }
  if(file_exists("../../include/php_library_fns/my_bosbo_monitor_db_functions.php")) {      include "../../include/php_library_fns/my_bosbo_monitor_db_functions.php";  }
  if(file_exists("../../include/php_library_fns/page_functions.php")) {      include "../../include/php_library_fns/page_functions.php";  }
  if(file_exists("../../include/objects/bosbo_message_class.php")){	    include "../../include/objects/bosbo_message_class.php";  }
    	    if(file_exists("../../include/php_library_fns/Input_validation_functions.php")){    include "../../include/php_library_fns/Input_validation_functions.php";  }
$CI_Input = new CI_Input();
$CI_Input->_sanitize_globals(TRUE);
  
  
$universalCatId = '.$a.';

  // moved up here so can be used in page title
  if (isset($universalCatId)) {
	  $thisCategory = $universalCatId;
	  // get details about the orders that are to be shown
	  $cat1 = new Category();
	  $exists = $cat1 -> Get($thisCategory);
	  $title = $cat1->getName();
  }
 if (strlen($title)!=0) {
?>	


<html>
  <head>
    <title>Bosbo: <?php echo $title; ?></title>
    <link rel="stylesheet" type="text/css" href="../../css/style.css" />
    <link rel="stylesheet" type="text/css" href="../../css/productPage.css" />
    <META name=\'description\' content=\'compare the best buy/sell prices for new/used items of <?php echo $title; ?>\'>
    <META name=\'keywords\' content=\'compare prices, pice comparison , best prices, new products, used products,  <?php echo $title; ?>\'>
	<SCRIPT type="text/javascript" LANGUAGE="JavaScript" SRC="../../js/md5.js"></SCRIPT>
	<script type="text/javascript" src="../../ajax/ajax_functions.js"></script>
	<script type="text/javascript" LANGUAGE="JavaScript" src="../../js/page_fns.js"></script>
  </head>
  <body  >
    <div id="container">
	  <?php $shape=displayHeader(readXmlMenuDefinition("../../../xml/xml_menu_definition.xml"));
	  list($default, $count)=$shape?>
	  <?php displaySearchBar();?>
	  <?php displayLeftSidebar() ?>
	  <div id="centercontent">  
  <?php
  if (isset($universalCatId)) {
	  
	  $nonAbsCat1 = new Non_abstract_category($thisCategory);
	  $nonAbsCat1 -> Get($thisCategory);
	  $nonAbsCat1->increaseRating();
	  $nonAbsCat1->Save();
	  
	  $allBids = $nonAbsCat1->getBids();
	  $allOffers = $nonAbsCat1->getOffers();
	  ?>
	
	<div>
	<?php
	
	echo "<p id=\'centre\'>".$title."</p>";
	$biscuit = \'\';
	$temp_node = $thisCategory;
	// ignore the first one
	$cat2 = new Category();
	$cat2 -> Get($temp_node);
	$parCatId = $cat2->getParentCategoryId();
	$bis_vals = array();
	// while loop up until root - this builds a list of numbers for the biscuit
	while ($temp_node!=\'1\')
	{
		$cat2 = new Category();
		$cat2 -> Get($temp_node);
		array_push($bis_vals, $temp_node);	
		$temp_node = $cat2->getParentCategoryId();
	}
	array_reverse($bis_vals);

	
	?>
		<p id="small_left">Location: <a href="../home.php" >
		Home</a> /
	<?php
	// while loop up until root - this builds the biscuit
	$temp_node = array_pop($bis_vals);
	while ($temp_node!=$parCatId)
	{
		$cat2 = new Category();
		$cat2 -> Get($temp_node);
		?>
		<a href="<?php echo $cat2->getStaticPageName();?>">
		<?php echo $cat2->getName() . 
		"</a> /";
		$temp_node = array_pop($bis_vals);
	}
	$cat2 = new Category();
	$cat2 -> Get($temp_node);
	?>
	<a href="<?php echo $cat2->getStaticPageName(); ?>">
	<?php echo $cat2->getName() . 
	"</a></p>";
	$counter = 0;
	?>
	<table width="100%">
	<tr>
			<?php if ($nonAbsCat1->getPictureUrl()!=\'\') { ?>
		<td width="152" valign="top"  align="center">
			<img src="../../images/category_images/<?php echo $nonAbsCat1->getPictureUrl(); ?>" alt="product_image">
			<?php } else { ?>
		<td width="152" valign="center" align="center">
			<img src="../../images/category_images/<?php echo $cat2->getCategory_thumbnail(); ?>" alt="product_image">
			<?php } ?>
		</td>
		<td id="product_description" align="left">
			<span id="product_description_title">Manufacturer\'s Description</span>
			<br><?php echo $nonAbsCat1->getDescription(); ?>
			<br><br>Manufacturer\'s website: 
			<?php
			$site = $nonAbsCat1->getOfficialWebsite();
			if (strlen($site)>0) {
				?>
			<a href="<?php echo $site; ?>">click here</a>
				<?php
			} else {
				echo "not supplied";
			}
			?>
		</td>
	</tr>
	</table>
	<br>
	<h4 id="section_head">Current Prices</h4>
	  <div id="l2box">
	    <table align="center" border="0" padding="0">
	      <tr>
	        <td colspan="2" align="center"> <span id="small_centre">Below are the current orders that are open within Bosbo.</span>
	          <div id="xsmall">Please select an order to view further details.</div></td>
	      </tr>
	      <tr valign="top">
	        <td id="bids"><table width="100%" border="0" padding="0">
	            <tr>
	              <td><div id="thWrapper">
	                  <table width="100%" border="0" padding="0">
	                    <tr>
	                      <td width="100%"><div id="thCell_sell">Wanted Items.</div></td>
	                    </tr>
	                  </table>
	                </div></td>
	            </tr>
	            <?php
	//for ($i =0; $i<(sizeof($allBids)); $i++)  {
	foreach ($allBids as $value)
	{
	  $counter++;
	  	$order = new Order();
		$order ->Get($value);
	
		$condition = "";
		if ($order->getUsed()==1) { 
			$condition = "USED";
			?>
	            <tr class="usedOrder">    
	    <?php } else { 
	    	$condition = "NEW";
	    	?>
	    		<tr class="newOrder">
	    <?php } ?>
	              <td><div id="wrapper"> <!-- This should really be class -->
	                  <div id="wrapper<?php echo $counter; ?>">
	                    <table width="100%" border="0" padding="0" id="bid_width">
	                      <tr style="cursor:pointer" onClick="showGrid(<?php echo $counter.\', \'.$value; ?>);" onMouseOver="wrapper<?php echo $counter; ?>.style.background=\'#994444\';" onMouseOut="wrapper<?php echo $counter; ?>.style.background=\'#999999\';" title="click to show/hide order details">
	                        <?php //height<?php echo $counter; .toggle(); ?>
	                        <td width="15%"><div id="js_dropdown_cell"><?php echo $condition; ?></div></td>
	                        <td><div id="js_dropdown_cell"><?php if($order->isInternal()) { echo "internal transaction"; } else { echo "external transaction"; }?></div></td>
	                        <td width="15%" id="price"><div id="js_dropdown_cell">&pound;<?php echo sprintf(\'%0.2f\', $order->getTotalPrice()); ?></div></td>
	                      </tr>
	                      <tr valign="top">
	                        <td colspan="3"><div id="content">
	                            <div id="content<?php echo $counter; ?>" style="display : none ;"></div>
	                          </div></td>
	                      </tr>
	                    </table>
	                  </div>
	                </div></td>
	            </tr>
	            <?php
	}
	?>
	          </table>
	        </td>
	        <td id="offers"><table width="100%" border="0" padding="0">
	            <tr>
	              <td><div id="thWrapper">
	                  <table width="100%" border="0" padding="0">
	                    <tr>
	                      <td width="100%"><div id="thCell_buy">Items For Sale.</div></td>
	                    </tr>
	                  </table>
	                </div></td>
	            </tr>
	            <?php
	//for ($i =0; $i<(sizeof($allOffers)); $i++)  {
	foreach ($allOffers as $value)
	{
	  $counter++;
	  	$order = new Order();
		$order ->Get($value);
	
		$condition = "";
		if ($order->getUsed()==1) { 
			$condition = "USED";
			?>
	            <tr class="usedOrder">    
	    <?php } else { 
	    	$condition = "NEW";
	    	?>
	    		<tr class="newOrder">
	    <?php } ?>
	              <td><div id="wrapper">
	                  <div id="wrapper<?php echo $counter; ?>">
	                    <table width="100%" border="0" padding="0" id="offer_width">
	                      <tr style="cursor:pointer" onClick="showGrid(<?php echo $counter.\', \'.$value; ?>);" onMouseOver="wrapper<?php echo $counter; ?>.style.background=\'#444499\';" onMouseOut="wrapper<?php echo $counter; ?>.style.background=\'#999999\';" title="click to show/hide order details">
	                        <td width="15%" id="price"><div id="js_dropdown_cell">&pound;<?php echo sprintf(\'%0.2f\', $order->getTotalPrice()); ?></div></td>
	                        <td><div id="js_dropdown_cell"><?php
	                        	if($order->isInternal()) 
	                        	{
	                        		echo "internal transaction"; 
	                        	} else {
	                        		if ($order->getuserId()!="-100") {
	                        			echo "external transaction";
	                        		} else {
	                        			echo "external-quoted";
	                        		}
	                        	}?></div></td>
	                        <td width="15%"><div id="js_dropdown_cell"><?php echo $condition; ?></div></td>
	                      </tr>
	                      <tr valign="top">
	                        <td colspan="3"><div id="content">
	                            <div id="content<?php echo $counter; ?>" style="display : none ;"> </div>
	                          </div></td>
	                      </tr>
	                    </table>
	                  </div>
	                </div></td>
	            </tr>
	            <?php
	}
	?>
	          </table></td>
	      </tr>
	  <tr>
	    <td colspan="2" id="xsmall">
	      Don\'t like these prices? Just place your own order on the market; it\'s free, easy, and there\'s no obligation to buy or sell!
	    </td>
	  </tr>
	  	<tr>
	  	  <td align="center" id="small_blue">
	      <a id="small_blue_text" title="place a buy order and join the above list of orders" style="cursor:pointer" href="../../pages/transaction_fns/Adding_order/addBid.php?categoryId=<?php echo $thisCategory; ?>&buy=1">
	        Want to BUY?<br>Place a Wanted Advert!
	      </a></td>
	      <td align="center" id="small_red">
	      <a id="small_red_text" title="place a sell order and join the above list of orders" style="cursor:pointer" href="../../pages/transaction_fns/Adding_order/addOffer.php?categoryId=<?php echo $thisCategory; ?>&buy=0">
	        Want to SELL?<br>Place a For Sale Advert!
	      </a></td>
	  </tr>
	    </table>
		  <br>
		  <div id="refine">
		    <p id="refine_title">Refine view:</p>
		    <ul>
		      <form id="refineForm" name="refineForm">
		        <label>I want to see
		        <select name="refineNUs" onChange="refineNewUsed();">
		          <option value="new">only new</option>
		          <option value="used">only used</option>
		          <option value="newandused" selected="selected">new and used</option>
		        </select>
		        </label>
		        <label>items and I want orders from which i can
		        <select name="refineBO" onChange="refineBidsOffers();">
		          <option value="buy">buy</option>
		          <option value="sell">sell</option>
		          <option value="buyandsell" selected="selected">buy and sell</option>
		        </select>
		        </label>
		      </form>
		    </ul>
		  </div>
  	  </div>
	  <br>
	    <h4 id="section_head">Historic pricing information</h4>
	    <div id="l2box">
	    <table width="100%" id="historic_pricing">
	    	<tr>
	    		<th>&nbsp;</th>
	    		<th>new item prices (&pound;)*</th>
	    		<th>used item prices (&pound;)*</th>
	    	</tr>
	    	<tr id="odd">
	    		<td>Monthly high</td>
	    		<td><?php echo sprintf(\'%0.2f\', $nonAbsCat1->getNewMH()); ?></td>
	    		<td><?php echo sprintf(\'%0.2f\', $nonAbsCat1->getUsedMH()); ?></td>
	    	</tr>
	    	<tr id="even">
	    		<td>Monthly low</td>
	    		<td><?php echo sprintf(\'%0.2f\', $nonAbsCat1->getNewML()); ?></td>
	    		<td><?php echo sprintf(\'%0.2f\', $nonAbsCat1->getUsedML()); ?></td>
	    	</tr>
	    	<tr id="odd">
	    		<td>All time high</td>
	    		<td><?php echo sprintf(\'%0.2f\', $nonAbsCat1->getNewATH()); ?></td>
	    		<td><?php echo sprintf(\'%0.2f\', $nonAbsCat1->getUsedATH()); ?></td>
	    	</tr>
	    	<tr id="even">
	    		<td>All time low</td>
	    		<td><?php echo sprintf(\'%0.2f\', $nonAbsCat1->getNewATL()); ?></td>
	    		<td><?php echo sprintf(\'%0.2f\', $nonAbsCat1->getUsedATL()); ?></td>
	    	</tr>
	    </table>
	    <p id="historic_pricing_asterix">* all prices are the cheapest sell price in the timespan indicated</p>
	  </div>
<?php
if (isset($_SESSION[\'valid_user\'])){
?>

<br>
<div id="monitorDiv" align="center">
<?php	
	if(monitorAlreadyExists($_SESSION[\'valid_user\'], $thisCategory)) {
?>
<input type="button" value="stop monitoring this item" onclick="delete_this_monitor(<?php echo $_SESSION[\'valid_user\']; ?>, <?php echo $thisCategory; ?>, \'product_page\');">
<?php
	} else {
?>
<input type="button" value="monitor this item" onclick="monitor_this_item(<?php echo $_SESSION[\'valid_user\']; ?>, <?php echo $thisCategory; ?>);">
<?php
	}
?>
</div>
<?php
}
  } else {
  	?>
  	<B>ERROR</B>
  	<?php
  }
?>
	</div>
	  </div>
	  <?php displayRightSidebar() ?>
    </div>
    <?php displayFooter() ?>
  </body>
</html>
<?php
} else {
	echo "ERROR";
}
?>';
}
?>
