<?php
  if (!isset($_SESSION)){
    session_name('bosbo-session');
    session_start();
  }
    if(file_exists("../../include/php_library_fns/db_functions.php")){    	include "../../include/php_library_fns/db_functions.php";  	}
  	if(file_exists("../../include/objects/user_functions.php")){    	include "../../include/objects/user_functions.php";  	}
	if(file_exists("../../include/php_library_fns/xml_functions.php")){    	include "../../include/php_library_fns/xml_functions.php";  	}
  	if(file_exists("../../include/objects/bosbo_category_class.php")){  	  	include "../../include/objects/bosbo_category_class.php";    }
    if(file_exists("../../include/php_library_fns/random_functions.php")){  	  	include "../../include/php_library_fns/random_functions.php";    }
  	if(file_exists("../../include/php_library_fns/page_functions.php")) {      include "../../include/php_library_fns/page_functions.php";  	}
  	if(file_exists("../../include/php_library_fns/my_bosbo_monitor_db_functions.php")) {      include "../../include/php_library_fns/my_bosbo_monitor_db_functions.php";  }
  if(file_exists("../../include/objects/bosbo_message_class.php")){	    include "../../include/objects/bosbo_message_class.php";  }
  if(file_exists("../../include/objects/bosbo_order_class.php")){	    include "../../include/objects/bosbo_order_class.php";	}
  if (isset($_GET['categoryId'])&&isset($_GET['buy'])) {  if (isset($_SESSION['valid_user'])){
  	//load user for use in final review screen.
  	$userReview = new User();
  	$userReview = $userReview->Get($_SESSION['valid_user']);

  // get details about the orders that are to be shown
  $cat1 = new Category();
  $cat1 -> Get($_GET['categoryId']);
  $title = $cat1->getName();
  
  $_SESSION['temporary_order_id']=randomString(16);
?>

<html>
  <head>
    <title>Bosbo</title>
    <link rel="stylesheet" type="text/css" href="../../css/style.css" />
    <link rel="stylesheet" type="text/css" href="../../css/addAmend.css" />
    <link rel="stylesheet" type="text/css" href="../../css/productPage.css" />
	<link rel="stylesheet" type="text/css" href="../../css/calendar_style.css"/>
	<SCRIPT type="text/javascript" LANGUAGE="JavaScript" SRC="../../js/md5.js"></SCRIPT>
	<script type="text/javascript" src="../../ajax/ajax_functions.js"></script>
	<script type="text/javascript" LANGUAGE="JavaScript" src="../../js/page_fns.js"></script>
	<!-- the next 2 lines are the js for the calendar popup -->
	<SCRIPT type="text/javascript" LANGUAGE="JavaScript" SRC="../../js/CalendarPopup.js"></SCRIPT>
	<SCRIPT LANGUAGE="JavaScript">document.write(getCalendarStyles());</SCRIPT>
	<SCRIPT  type="text/javascript" LANGUAGE="JavaScript" ID="js18">
		var cal18 = new CalendarPopup("testdiv1");
		cal18.setCssPrefix("TEST");
		var now = new Date();
		var yesterday = new Date();
		yesterday.setTime( now.getTime() - (24*60*60*1000));
		cal18.addDisabledDates(null,formatDate(yesterday,"yyyy-MM-dd"));
	</SCRIPT>
	
  </head>
  <body  >
    <div id="container">
    <?php
    if (file_exists('../../../xml/xml_menu_definition.xml')) {
    	echo "iiiiiiiiiiiiiiiiiiiiiiiiiiiii";
    } else {
    	echo "-----------------------------";
    }
    
    
    ?>
	  <?php //$shape=displayHeader(readXmlMenuDefinition("../../../xml/xml_menu_definition.xml"));
	  //list($default, $count)=$shape?>
	  <?php displaySearchBar();?>
	  <?php displayLeftSidebar() ?>
	  <div id="centercontent">
	  
<br>
<div id="l2box">
  <div id="partOne">
    <form id="addOrderForm"  name="addOfferPage1" action="">
      <table width="515" border="0" padding="0">
      <tr class="header" width="100%">
        <td><table class="0" border="0"  width="100%">
            <tr>
              <td class="current_offer"><div align="center"><img src="../../images/form/1_red.gif" alt="1" width="27" height="27" /></div></td>
              <td class="not_current"><div align="center"><img src="../../images/form/2.gif" alt="1" width="27" height="27" /></div></td>
              <td class="not_current"><div align="center"><img src="../../images/form/3.gif" alt="1" width="27" height="27" /></div></td>
              <td class="not_current"><div align="center"><img src="../../images/form/4.gif" alt="1" width="27" height="27" /></div></td>
            </tr>
          </table></td>
      </tr>
      <tr>
        <td colspan="4"><p align="center" id="title">You have chosen to place an offer to SELL this item<br />
            "<?php echo $title;
            ?>"</p></td>
      </tr>
      <tr>
      <td colspan="4">
      <table width="100%" border="0">
        <tr>
          <td class="medium">Please fill in some details regarding your order, and the item you wish to sell.  You will be able to review your order before it is submitted. </td>
        </tr>
        <table width="100%" border="0" class="form_item">
          <tr>
            <td width="25" class="name">1)</td>
            <td class="name">Item condition:
              <select name="itemCondition">
                <option value="NEW">New</option>
                <option value="USED">Used</option>
              </select></td>
          </tr>
          <tr>
            <td colspan="2" class="description">Please enter the Item condition </td>
          </tr>
        </table>
        <table width="100%" border="0" class="form_item">
          <tr>
            <td width="25" class="name">2)</td>
            <td class="name">Quantity required:
              <select name="quantityRequired">
                <option value="1">1</option>
                <option value="2">2</option>
                <option value="3">3</option>
                <option value="4">4</option>
                <option value="5">5</option>
                <option value="6">6</option>
                <option value="7">7</option>
                <option value="8">8</option>
                <option value="9">9</option>
                <option value="&gt;9">&gt;9</option>
              </select></td>
          </tr>
          <tr>
            <td colspan="2" class="description">Please enter the number of these items that you wish to sell.</td>
          </tr>
        </table>
        <table width="100%" border="0" class="form_item">
          <tr>
            <td width="25" class="name">3)</td>
            <td class="name">Expiry date:
              <input type="text" name="date18" value="DD/MM/YYYY" size="25"disabled/>
              <input type="image" src="../../images/form/calendar_icon.gif" style="cursor:pointer" alt="calendar" width="16" height="16" onClick="

var otherText = document.forms['addOfferPage1'].elements['date18'];
otherText.disabled = false;
cal18.select(document.forms['addOfferPage1'].date18,'anchor18','dd/MM/yyyy'); return false;" title="select a date from the calendar" name="anchor18" id="anchor18" 
onblur="
var otherText = document.forms['addOfferPage1'].elements['date18'];
otherText.disabled = true;"/> </td>
          </tr>
          <tr>
            <td colspan="2" class="description">Please select the date when you wish your order to expire (orders expire at midnight). This information will not be publically visible. DD/MM/YYYY </td>
          </tr>
        </table>
        
        
        
          <table width="100%" border="0" class="form_item">
            <tr>
              <td width="25" class="name">4)</td>
              <td class="name">Description :</td>
            </tr>
            <tr>
              <td width="25" class="name">&nbsp;</td> 
 	              
              <td class="small"><textarea name="description" cols="50" rows="4" onFocus="doClear(this)">Please enter any specific details about the item (e.g. condition).  You may use up to 250 characters; any extra over this value will be trimmed.</textarea>
              </td>
            </tr>
          </table>        
        </td>
        
        </tr>
        
      </table>
      <table width="100%">
        <tr>
          <td width="50%" align="center"><input type="button" value="Previous" disabled>
          </td>
          <td width="50%" align="center"><input type="button" value="Next" onClick="

	var toReturn = true;
	var errors = '';
	if(document.forms['addOfferPage1'].elements['date18'].value=='DD/MM/YYYY') {
		errors = errors + 'Please enter a valid expiry date\n';
		toReturn = false;
	}
	// check some contents have been specified for the description box
	document.forms['addOfferPage1'].description.value=trim(document.forms['addOfferPage1'].description.value);
	if (document.forms['addOfferPage1'].description.value=='Please enter any specific details about the item (e.g. condition).  You may use up to 250 characters; any extra over this value will be trimmed.'
	|| document.forms['addOfferPage1'].description.value==''
	)
	{
		errors = errors + 'Please enter a description\n';
		toReturn = false;
	}
	// check the length of the description box & trim over 250 chars
	var result = checkMaxLength(document.forms['addOfferPage1'].description, 250);
	if (result!='shorter')
	{
		errors = errors + result + '\n';
		toReturn = false;
	}	
	if(toReturn) {
  		  var quantityCont = document.getElementById('quantityRev');
  		  if(quantityCont) { quantityCont.innerHTML=document.forms['addOfferPage1'].elements['quantityRequired'].value; }
  		  var condCont = document.getElementById('condRev');
  		  if(condCont) { condCont.innerHTML=document.forms['addOfferPage1'].elements['itemCondition'].value; }
  		  var descriptionCont = document.getElementById('descriptionRev');
  		  if(descriptionCont) { descriptionCont.innerHTML=document.forms['addOfferPage1'].elements['description'].value; }	
	}  		
	else {
		alert(errors);
	}
	
if(toReturn) {
show('partTwo');return false;
}">
          </td>
        </tr>
      </table>
    </form>
  </div>
  <div id="partTwo" style="display: none;">
   <form id="addOrderForm" name="addOfferPage2" action="">
    <table width="515" border="0" padding="0">
      <tr class="header" width="100%">
        <td><table class="0" border="0"  width="100%">
            <tr>
              <td class="not_current"><div align="center"><img src="../../images/form/1.gif" alt="1" width="27" height="27" /></div></td>
              <td class="current_offer"><div align="center"><img src="../../images/form/2_red.gif" alt="1" width="27" height="27" /></div></td>
              <td class="not_current"><div align="center"><img src="../../images/form/3.gif" alt="1" width="27" height="27" /></div></td>
              <td class="not_current"><div align="center"><img src="../../images/form/4.gif" alt="1" width="27" height="27" /></div></td>
            </tr>
          </table></td>
      </tr>
      <tr>
        <td colspan="4"><p align="center" id="title">You have chosen to place an offer to SELL this item<br />
            "<?php echo $title;
            ?>"</p></td>
      </tr>
      <tr>
        <td colspan="4">
        
        <table width="100%" border="0" class="form_item">
          <tr>
            <td width="25" class="name">5)</td>
            <td class="name">Item Price: &pound;
              <input type="text" name="item_price_pound" value="" size="5" maxlength="7" onblur="updateOfferTotalPrice();"/>
              -
              <input type="text" name="item_price_pence" value="" size="2" maxlength="2" onblur="updateOfferTotalPrice();"/></td>
          </tr>
          <tr>
            <td colspan="2" class="description">Please enter the price that you are selling this item for</td>
          </tr>
        </table>

        <table width="100%" border="0" class="form_item">
          <tr>
            <td width="25" class="name">6)</td>
            <td class="name">Postage and Packaging costs: &pound;
              <input type="text" name="pandp_price_pound" value="" size="5" maxlength="7" onblur="updateOfferTotalPrice();"/>
              -
              <input type="text" name="pandp_price_pence" value="" size="2" maxlength="2" onblur="updateOfferTotalPrice();"/></td>
          </tr>
          <tr>
            <td colspan="2" class="description">Please enter the cost for postage and packaging this item</td>
          </tr>
        </table>
        <table width="100%" border="0" class="form_item">
          <tr>
            <td class="name" align="center">Total cost per item: &pound;
              <input type="text" name="total_price" value="" size="13" maxlength="13" disabled/>
          </tr>
        </table>
        
          <table width="100%" border="0" class="form_item">
            <tr>
              <td width="25" class="name">7)</td>
              <td class="name">Postage insurance available:
                <select name="insurance" onchange="
if(this.value=='YES'){
insurance_price_pound.disabled = false;insurance_price_pence.disabled = false;} else {
insurance_price_pound.disabled = true;insurance_price_pence.disabled = true;
}          
">
                  <option value="YES">Yes</option>
                  <option value="NO" selected>No</option>
                </select>
              &nbsp;&nbsp;Cost:
              <input type="text" name="insurance_price_pound" value="" size="5" maxlength="7" disabled/>
              -
              <input type="text" name="insurance_price_pence" value="" size="2" maxlength="2" disabled/>
              </td>
            </tr>
            <tr>
              <td colspan="2" class="description">Please select if the buyer can have the order posted with insured delivery, and if so, how much extra on top of the normal p&amp;p this will cost.</td>
            </tr>
          </table>
          <table width="100%" border="0" class="form_item">
            <tr>
              <td width="25" class="name">8)</td>
              <td class="name">Payment methods:</td>
            </tr>
            <tr>
              <td colspan="2" class="description">Please select the methods that you would be willing to accept for payment on this item</td>
            </tr>
            <tr>
              <td width="25" class="name">&nbsp;</td>
              <td><table width="100%" border="0">
                  <tr>
                    <td class="small"><input type="checkbox" name="paym" value="Debit/Credit card" />
                      Debit/Credit card</td>
                    <td class="small"><input type="checkbox" name="paym" value="Paypal" />
                      Paypal</td>
                  <tr>
                    <td class="small"><input type="checkbox" name="paym" value="Personal Cheque" />
                      Personal Cheque</td>
                    <td class="small"><input type="checkbox" name="paym" value="Cash" />
                      Cash </td>
                  </tr>
                  <tr>
                    <td class="small"><input type="checkbox" name="paym" value="Bank Transfer" />
                      Bank Transfer </td>
                    <td class="small"><input type="checkbox" name="paym" value="Other" onclick="

if(this.checked){
var otherText = document.forms['addOfferPage2'].elements['others'];
otherText.disabled = false;} else {
var otherText = document.forms['addOfferPage2'].elements['others'];
otherText.disabled = true;
}
"/>
                      Other
                      <input name="others" type="text" value="please specify" size="30" maxlength="40" onFocus="doClear(this)" disabled/>
                    </td>
                  </tr>
                </table></td>
            </tr>
          </table>
</td>
      </tr>
    </table>
    <table width="100%">
      <tr>
        <td width="50%" align="center"><input type="button" value="Previous" onClick="show('partOne'); return false;" onKeyPress="show('partOne'); return false;">
        </td>
        <td width="50%" align="center"><input type="button" value="Next" onClick="
	var toReturn = true;
	var errors = '';
	if(document.forms['addOfferPage2'].elements['item_price_pound'].value=='') {
		errors = errors + 'Please enter a valid item price with both pounds and pence\n';
		toReturn = false;
	}
	else if(document.forms['addOfferPage2'].elements['item_price_pence'].value=='') {
		errors = errors + 'Please enter a valid item price with both pounds and pence\n';
		toReturn = false;
	}
	var pounds = validateIntegerField(document.forms['addOfferPage2'].elements['item_price_pound']);
	if (pounds!='integer'){
		updateOfferTotalPrice();
		errors = errors + pounds + '\n';
		toReturn = false;
	}
	var pence = validateIntegerField(document.forms['addOfferPage2'].elements['item_price_pence']);
	if (pence!='integer'){
		updateOfferTotalPrice();
		errors = errors + pence + '\n';
		toReturn = false;
	}
	if (document.forms['addOfferPage2'].elements['item_price_pence'].value.length==1) {
		document.forms['addOfferPage2'].elements['item_price_pence'].value='0'+document.forms['addOfferPage2'].elements['item_price_pence'].value;
	}
	
	if(document.forms['addOfferPage2'].elements['pandp_price_pound'].value=='') {
		errors = errors + 'Please enter a valid price for p&p with both pounds and pence\n';
		toReturn = false;
	}
	else if(document.forms['addOfferPage2'].elements['pandp_price_pence'].value=='') {
		errors = errors + 'Please enter a valid price for p&p with both pounds and pence\n';
		toReturn = false;
	}
	pounds = validateIntegerField(document.forms['addOfferPage2'].elements['pandp_price_pound']);
	if (pounds!='integer'){
		errors = errors + pounds + '\n';
		updateOfferTotalPrice();
		toReturn = false;
	}
	pence = validateIntegerField(document.forms['addOfferPage2'].elements['pandp_price_pence']);
	if (pence!='integer'){
		errors = errors + pence + '\n';
		updateOfferTotalPrice();
		toReturn = false;
	}
	if (document.forms['addOfferPage2'].elements['pandp_price_pence'].value.length==1) {
		document.forms['addOfferPage2'].elements['pandp_price_pence'].value='0'+document.forms['addOfferPage2'].elements['pandp_price_pence'].value;
	}	
	if (document.forms['addOfferPage2'].elements['insurance'].value=='YES') {
		if(document.forms['addOfferPage2'].elements['insurance_price_pound'].value=='') {
			errors = errors + 'Please enter a valid price for insurance with both pounds and pence\n';
			toReturn = false;
		}
		else if(document.forms['addOfferPage2'].elements['insurance_price_pence'].value=='') {
			errors = errors + 'Please enter a valid price for insurance with both pounds and pence\n';
			toReturn = false;
		}
		pounds = validateIntegerField(document.forms['addOfferPage2'].elements['insurance_price_pound']);
		if (pounds!='integer'){
			errors = errors + pounds + '\n';
			toReturn = false;
		} else {
			if(document.forms['addOfferPage2'].elements['insurance_price_pound'].value<0) {
				errors = errors + 'Please enter a positive insurance price with both pounds and pence\n';
				toReturn = false;
			}
		}
		pence = validateIntegerField(document.forms['addOfferPage2'].elements['insurance_price_pence']);
		if (pence!='integer'){
			errors = errors + pence + '\n';
			toReturn = false;
		} else {
			if(document.forms['addOfferPage2'].elements['insurance_price_pound'].value<0) {
				errors = errors + 'Please enter a positive insurance price with both pounds and pence\n';
				toReturn = false;
			}
		}
		if (document.forms['addOfferPage2'].elements['insurance_price_pence'].value.length==1) {
			document.forms['addOfferPage2'].elements['insurance_price_pence'].value='0'+document.forms['addOfferPage2'].elements['insurance_price_pence'].value;
		}
	}
	var c_value = '';
	// check at least one payment method has been specified
	for (var i=0; i < document.forms['addOfferPage2'].paym.length; i++)
    	{
    		// check at least one is filled in
   			if (document.forms['addOfferPage2'].paym[i].checked)
      		{
      			c_value = c_value + i + '\n';
      		}
   	}
	if (c_value=='') {
		errors = errors + 'Please enter at least one payment method\n';
		toReturn = false;
	}
	// check that if 'others' is filled in then there is some text provided
	if (document.forms['addOfferPage2'].paym[document.forms['addOfferPage2'].paym.length-1].checked)
	{
		document.forms['addOfferPage2'].others.value=trim(document.forms['addOfferPage2'].others.value);
		if (document.forms['addOfferPage2'].others.value=='please specify'
		|| document.forms['addOfferPage2'].others.value==''
		)
		{
			errors = errors + 'Please specify the other payment methods\n';
			toReturn = false;
		}
	}
	if(toReturn) {
		  var insuredCont = document.getElementById('insuredRev');
  		  if(insuredCont) {
  		  	if (document.forms['addOfferPage2'].elements['insurance'].value == 'NO') {
  		  		insuredCont.innerHTML='not available';
  		  	} else {
  		  		insuredCont.innerHTML= 'available for a premium of &pound;' + 
  		  		document.forms['addOfferPage2'].elements['insurance_price_pound'].value + '.' +
  		  		document.forms['addOfferPage2'].elements['insurance_price_pence'].value;
  		  	}
  		  }
  		  var payment_methodsCont = document.getElementById('payment_methodsRev');
  		  var paymentMethods = '';
  		  for (var i=0; i < document.forms['addOfferPage2'].paym.length; i++)
	  	  {
    		// if it's checked
   			if (document.forms['addOfferPage2'].paym[i].checked)
      		{
      			//if others is checked
	  	  		if (document.forms['addOfferPage2'].paym.length-1==i)
		  		{
					paymentMethods = paymentMethods + document.forms['addOfferPage2'].others.value + ', ';
		  		} else {
		  			paymentMethods = paymentMethods + document.forms['addOfferPage2'].paym[i].value + ', ';
		  		}
      		}
	   	  }
	   	  var str_paymentMethods = new String(paymentMethods);
	   	  paymentMethods =  (paymentMethods.substring(0, paymentMethods.length-2));
	   	  if (payment_methodsCont) { payment_methodsCont.innerHTML=paymentMethods; }
	   	  
	   	  
	   	  var priceCont1 = document.getElementById('price1Rev');
  		  if(priceCont1){
    		priceCont1.innerHTML=document.forms['addOfferPage2'].elements['total_price'].value;
  		  }
		  var priceCont2 = document.getElementById('price2Rev');
  		  if(priceCont2){  		 
    		priceCont2.innerHTML='&pound'+document.forms['addOfferPage2'].elements['item_price_pound'].value+'.'+
    		document.forms['addOfferPage2'].elements['item_price_pence'].value + ' + ' +
    		document.forms['addOfferPage2'].elements['pandp_price_pound'].value + '.' +
    		document.forms['addOfferPage2'].elements['pandp_price_pence'].value + 'p&p';
  		  }
	}
	else {
		alert(errors);
	}

if(toReturn) {
show('partThree');return false;
}
">
        </td>
      </tr>
    </table>
    </form>
  </div>

  <div id="partThree" style="display: none;">
   <form id="addOrderForm" name="addOfferPage3" action="">
    <table width="515" border="0" padding="0">
      <tr class="header" width="100%">
        <td><table class="0" border="0"  width="100%">
            <tr>
              <td class="not_current"><div align="center"><img src="../../images/form/1.gif" alt="1" width="27" height="27" /></div></td>
              <td class="not_current"><div align="center"><img src="../../images/form/2.gif" alt="1" width="27" height="27" /></div></td>
              <td class="current_offer"><div align="center"><img src="../../images/form/3_red.gif" alt="1" width="27" height="27" /></div></td>
              <td class="not_current"><div align="center"><img src="../../images/form/4.gif" alt="1" width="27" height="27" /></div></td>
            </tr>
          </table></td>
      </tr>
      <tr>
        <td colspan="4"><p align="center" id="title">You have chosen to place an offer to SELL this item<br />
            "<?php echo $title;
            ?>"</p></td>
      </tr>
      <tr>
        <td colspan="4"><table width="100%" border="0" class="form_item">
            <tr>
              <td width="25" class="name">9)</td>
              <td class="name">Picture of item:
                <input type="button" value="Add picture" onClick="javascript:popupNew('addOfferAddPicture.php?temp_order_id=<?php echo $_SESSION['temporary_order_id'];?>', 250, 475);"></td>
            </tr>
            <tr>
              <td colspan="2" class="description">You may add a picture of the item you are selling to be shown alongside your order.  This can be uploaded through the "Add picture" button above.  The full order can be viewed before submission.</td>
            </tr>
          </table>
          <table width="100%" border="0" class="form_item">
            <tr>
              <td width="25" class="name">10)</td>
              <td class="name">Order Type:
                <select name="internal" onchange="
if(this.value=='EXTERNAL'){
external_address.disabled = false;} else {
external_address.disabled = true;
}          
">
                  <option value="INTERNAL" selected>Internal</option>
                  <option value="EXTERNAL">External</option>
                </select>
              </td>
            </tr>

            <tr>
              <td colspan="2" class="description">Please select if the order is to be dealt with internally (anyone who wishes to buy off you will contact you via Bosbo messages and automatic emails) or externally (on selecting to buy, the purchaser will be directed to an external webpage where you are selling this item). For external orders, an external webpage address from where the product can be bought must be supplied.  The supplied address must be the full address (i.e. including "http://"):</td>
            </tr>
            <tr>
              <td width="25" class="name">&nbsp;</td>
              <td class="name">Address:&nbsp;&nbsp;
              <input type="text" name="external_address" value="http://www.example.com/product.html" size="50" maxlength="150" disabled/></td>
            </tr>
          </table>
          </td>
      </tr>
    </table>
    <table width="100%">
      <tr>
        <td width="50%" align="center"><input type="button" value="Previous" onClick="show('partTwo'); return false;" onKeyPress="show('partTwo'); return false;">
        </td>
        <td width="50%" align="center"><input type="button" value="Next" 
onClick="

var toReturn = true;
	var errors = '';
	if(document.forms['addOfferPage3'].elements['internal'].value=='EXTERNAL') {
		document.forms['addOfferPage3'].elements['external_address'].value=trim(document.forms['addOfferPage3'].elements['external_address'].value);
		if (document.forms['addOfferPage3'].elements['external_address'].value=='' ||
		document.forms['addOfferPage3'].elements['external_address'].value=='http://www.example.com/product.html') {
			errors = errors + 'Please enter a valid web page where the user can find your item.  Any incorrectly supplied addresses may result in your account being suspended.\n';
			toReturn = false;
		} else if (!(isUrl(document.forms['addOfferPage3'].elements['external_address'].value))) {
			errors = errors + 'The website address that you have specified appears to be incorrect. Please review this.\n';
			toReturn = false;
		}
	}
	if(toReturn) {
  		  var transaction_typeCont = document.getElementById('transaction_typeRev');
  		  if(transaction_typeCont) { transaction_typeCont.innerHTML=document.forms['addOfferPage3'].elements['internal'].value; }
  		  // next bit added in seperate function:
  		  getAddOrderPictureThumb('<?php echo $_SESSION['temporary_order_id']; ?>', '');
  	}
	else {
		alert(errors);
	}

if(toReturn) {
show('partFour');return false;
}"
>
        </td>
      </tr>
    </table>
    </form>
  </div>
  <div id="partFour" style="display: none;">
    <form id="addOrderForm" name="orderReviewForm" action="">
      <table width="515" border="0" padding="0">
        <tr class="header" width="100%">
          <td><table class="0" border="0"  width="100%">
              <tr>
              <td class="not_current"><div align="center"><img src="../../images/form/1.gif" alt="1" width="27" height="27" /></div></td>
              <td class="not_current"><div align="center"><img src="../../images/form/2.gif" alt="1" width="27" height="27" /></div></td>
              <td class="not_current"><div align="center"><img src="../../images/form/3.gif" alt="1" width="27" height="27" /></div></td>
              <td class="current_offer"><div align="center"><img src="../../images/form/4_red.gif" alt="1" width="27" height="27" /></div></td>
              </tr>
            </table></td>
        </tr>
        <tr>
          <td class="medium">please review your order before submitting. </td>
        </tr>
        <tr class="newOrder">
          <td><div id="wrapper">
              <!-- This should really be class -->
              <div>
                <table width="100%" border="0" padding="0" id="bid_width">
                  <tr>
                    <td width="15%"><div id="js_dropdown_cell"><span id="condRev"></span></div></td>
                    <td><div id="js_dropdown_cell"><span id="transaction_typeRev"></span></div></td>
                    <td width="15%" id="price"><div id="js_dropdown_cell">&pound;<span id="price1Rev"></span></div></td>
                  </tr>
                  <tr valign="top">
                    <td colspan="3"><div id="content">
                        <div>
                          <table width="100%" class="order_default">
                            <tr>
                              <td class="detail">Price inc. p&p: </td>
                              <td><span id="price2Rev"></span></td>
                            </tr>
                            <tr>
                              <td class="detail">Insured delivery: </td>
                              <td><span id="insuredRev"></span></td>
                            </tr>
                            <tr>
                              <td class="detail">buyer: </td>
                              <td><a href="javascript:popupNew('../../navigation/userinfo_popup.php?id=<?php echo $_SESSION['valid_user'];?>', 450, 450);" title="View user information.  This link will open in a new browser window."><?php echo $userReview->getUserName(); ?></a></td>
                            </tr>
                            <tr>
                              <td class="detail">location: </td>
                              <td><span id="locationRev"><?php echo $userReview->getLocation(); ?></span></td>
                            </tr>
                            <tr>
                              <td class="detail">payment methods: </td>
                              <td><span id="payment_methodsRev"></span></td>
                            </tr>
                            <tr>
                              <td class="detail">Quantity:</td>
                              <td><span id="quantityRev"></span>
							  </td>
                            </tr>
                          </table>
                          
							<table width="100%" border="0" class="order_default">
								<tr>
								  <td><p><b>Description: </b><span id="descriptionRev"></span></p>
								  <td width="102"><span id="picture_thumbRev"><img src='../../images/user_images/default.gif' alt='No supplied image for this order.'/></span></td>
								</tr>
							</table> 
                          <table width="100%" border="0" class="order_default">
                            <tr>
                              
                            </tr>
                          </table>
                          <table width="100%" border="0" class="order_default">
                            <tr>
                              <td colspan="2"><div align="center">
                                  <input type="button" value="buy" disabled>
                                </div></td>
                            </tr>
                          </table>
                        </div>
                      </div></td>
                  </tr>
                </table>
              </div>
            </div></td>
        </tr>
        <tr>
          <td class="bbsmall">Submittion of this For Sale Advert places it onto the product page until it expires.<br><br>
          A transaction will be created for any person who responds to your advert.  This is to be used for 
          further communications, and any payments and deliveries.  A transaction is not a legally binding 
          contract. Bosbo always advises caution and, if possible, the use of an escrow service.
          </td>
        </tr>
      </table>
          <table width="100%">
      <tr>
        <td width="50%" align="center"><input type="button" value="Previous" onClick="show('partThree'); return false;" onKeyPress="show('partThree'); return false;">
        </td>
        <td width="50%" align="center"><input type="button" value="Confirm Order" onClick="
this.disabled=true;
submitOffer(<?php echo $_GET['categoryId']; ?>);"
onKeyPress="this.disabled=true; submitOffer(<?php echo $_GET['categoryId'] ;?>);">
        </td>
      </tr>
    </table>
    </form>
  </div>
</div>
</div>
<?php
  } else {
?>



<html>
  <head>
    <title>Bosbo</title>
    <link rel="stylesheet" type="text/css" href="../../css/style.css" />
    <link rel="stylesheet" type="text/css" href="../../css/L2_style.css"/>
	<link rel="stylesheet" type="text/css" href="../../css/calendar_style.css"/>
	<link rel="stylesheet" type="text/css" href="../../css/my_bosbo.css"/>
	<SCRIPT type="text/javascript" LANGUAGE="JavaScript" SRC="../../js/md5.js"></SCRIPT>
	<script type="text/javascript" src="../../ajax/ajax_functions.js"></script>
	<script type="text/javascript" LANGUAGE="JavaScript" src="../../js/validation_fns.js"></script>
	<script type="text/javascript" LANGUAGE="JavaScript" src="../../js/page_fns.js"></script>
	<!-- the next 2 lines are the js for the calendar popup -->
	<SCRIPT type="text/javascript" LANGUAGE="JavaScript" SRC="../../js/CalendarPopup.js"></SCRIPT>
	<SCRIPT LANGUAGE="JavaScript">document.write(getCalendarStyles());</SCRIPT>
	<SCRIPT  type="text/javascript" LANGUAGE="JavaScript" ID="js18">
		var cal18 = new CalendarPopup("testdiv1");
		cal18.setCssPrefix("TEST");
		var now = new Date();
		var yesterday = new Date();
		yesterday.setTime( now.getTime() - (24*60*60*1000));
		cal18.addDisabledDates(null,formatDate(yesterday,"yyyy-MM-dd"));
	</SCRIPT>
	
  </head>
  <body  >
    <div id="container">
	  <?php $shape=displayHeader(readXmlMenuDefinition("../../../xml/xml_menu_definition.xml"));
	  list($default, $count)=$shape?>
	  <?php displaySearchBar();?>
	  <?php displayLeftSidebar() ?>
	  <div id="centercontent">

<?php
  	displayWarning("You must be logged in to access your account.<br>Please login to continue.");
?>
</div>
<?php
  }
  } else {
?>


<html>
  <head>
    <title>Bosbo</title>
    <link rel="stylesheet" type="text/css" href="../../css/style.css" />
    <link rel="stylesheet" type="text/css" href="../../css/L2_style.css"/>
	<link rel="stylesheet" type="text/css" href="../../css/calendar_style.css"/>
	<link rel="stylesheet" type="text/css" href="../../css/my_bosbo.css"/>
	<SCRIPT type="text/javascript" LANGUAGE="JavaScript" SRC="../../js/md5.js"></SCRIPT>
	<script type="text/javascript" src="../../ajax/ajax_functions.js"></script>
	<script type="text/javascript" LANGUAGE="JavaScript" src="../../js/validation_fns.js"></script>
	<script type="text/javascript" LANGUAGE="JavaScript" src="../../js/page_fns.js"></script>
	<!-- the next 2 lines are the js for the calendar popup -->
	<SCRIPT type="text/javascript" LANGUAGE="JavaScript" SRC="../../js/CalendarPopup.js"></SCRIPT>
	<SCRIPT LANGUAGE="JavaScript">document.write(getCalendarStyles());</SCRIPT>
	<SCRIPT  type="text/javascript" LANGUAGE="JavaScript" ID="js18">
		var cal18 = new CalendarPopup("testdiv1");
		cal18.setCssPrefix("TEST");
		var now = new Date();
		var yesterday = new Date();
		yesterday.setTime( now.getTime() - (24*60*60*1000));
		cal18.addDisabledDates(null,formatDate(yesterday,"yyyy-MM-dd"));
	</SCRIPT>
	
  </head>
  <body  >
    <div id="container">
	  <?php $shape=displayHeader(readXmlMenuDefinition("../../../xml/xml_menu_definition.xml"));
	  list($default, $count)=$shape?>
	  <?php displaySearchBar();?>
	  <?php displayLeftSidebar() ?>
	  <div id="centercontent">
	  
<div>error - please contact Bosbo support
</div></div>
<?php  	
  }
?>  
	  <?php displayRightSidebar() ?>
    </div>
    
    <!-- DIV for the calendar.  Needs to be placed outside of the page div, for absolute positioning -->
    <DIV ID="testdiv1" STYLE="position:absolute;visibility:hidden;background-color:white;layer-background-color:white;"></DIV>
    <?php displayFooter() ?>
  </body>
</html>