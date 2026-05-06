/**
 *
 *  This page has had it's initial tidy, but most of the code that's in here can be transferred to the
 *  seperate pages and so use only 1/2 functions with more parameters.  Saves on repeated code.
 *
**/

// these are variables for if the current page needs refreshing on a sign in.
// if currentPage != null then reload.
var currentPage = null;
var expectedHash = "";
var lastTabId = "";
var lastTabCount = "";

function getDivContent(div, url){
    var XMLHttpRequestObject = createXMLrequest();
	
	if(XMLHttpRequestObject) {
		XMLHttpRequestObject.open("GET", url);
		XMLHttpRequestObject.onreadystatechange = function()
		{
			if (XMLHttpRequestObject.readyState == 4 &&
			XMLHttpRequestObject.status == 200) {
				div.innerHTML = XMLHttpRequestObject.responseText;
				delete XMLHttpRequestObject;
				XMLHttpRequestObject = null;
			}
		}
		XMLHttpRequestObject.send(null);
	}
}

function postDivContent(div, url, parameters){
    var XMLHttpRequestObject = createXMLrequest();
	if(XMLHttpRequestObject) {
		XMLHttpRequestObject.open("POST", url);
		XMLHttpRequestObject.setRequestHeader("Content-Type","application/x-www-form-urlencoded");
		XMLHttpRequestObject.onreadystatechange = function()
		{
			if (XMLHttpRequestObject.readyState == 4 &&
			XMLHttpRequestObject.status == 200) {
				div.innerHTML = XMLHttpRequestObject.responseText;
				delete XMLHttpRequestObject;
				XMLHttpRequestObject = null;
			}
		}
		XMLHttpRequestObject.send(parameters);
	}
}

/**
 *
 * History handling functions
 *
 **/

function handleHistory() {
	if (window.location.hash != expectedHash)   {
		//alert(window.location.hash + "   " + expectedHash);
		expectedHash = window.location.hash;
		//if (lastTabId=='' || lastTabCount=='') {
			getCentreContent(expectedHash.substring(1), expectedHash.substring(1));
			 
		/*} else {
			alert(expectedHash.substring(1,1) + "   " +expectedHash.substring(2,2));
			getPage(expectedHash.substring(3),expectedHash.substring(1,1),expectedHash.substring(2,2),expectedHash.substring(3));
		}*/
	}
}
function pollHash() {
	//handleHistory();
	//window.setInterval("handleHistory()", 100);
	//return true;
}
/*
function makeHistory(newHash) {
	window.location.hash = newHash;
	expectedHash = window.location.hash;
	return true;
}*/


// param 1 - url of page to get
// param 2 - page to refresh on signin/signout.  null if not to refresh.  This is stored in the global var.
function getCentreContent(url, currentpage) { //, root) {
	currentPage = currentpage;
	//alert("------" + lastTabId+lastTabCount);
	/*if (currentpage != null) {
		expectedHash = "#"+currentpage;
	}
	if (currentPage != null) {
		window.location.hash = currentpage;
		//window.location.href = window
	}*/
	var centerCont = document.getElementById("centercontent");
    if(centerCont){
      centerCont.innerHTML="<p>Loading...</p>";
    }
	getDivContent(centerCont,url);
	/*for(i=1;i<=lastTabCount;i++){
      document.getElementById("tab"+i).className="unselected";
      document.getElementById("tabli"+i).className="unselected";
    }*/
}
function postCentreContent(url, currentpage, parameters) {
	currentPage = currentpage;	// THIS SHOULD NOT BE USED AT THE MOMENT
	var centerCont = document.getElementById("centercontent");
    if(centerCont){
      centerCont.innerHTML="<p>Loading...</p>";
    }
    postDivContent(centerCont, url, parameters);
}
function getMyBosboContent(url) {
	var my_bosbo_centre_content = document.getElementById("my_bosbo_centre_content");
    if(my_bosbo_centre_content){
      my_bosbo_centre_content.innerHTML="<p>Loading...</p>";
    }
    getDivContent(my_bosbo_centre_content,url);
}
function postMyBosboContent(url, parameters) {
	var centerCont = document.getElementById("my_bosbo_centre_content");
    if(centerCont){
      centerCont.innerHTML="<p>Loading...</p>";
    }
	postDivContent(centerCont, url, parameters);
}
function postResetPassword(url, parameters) {
	var centerCont = document.getElementById("reset_status");
    if(centerCont){
      centerCont.innerHTML="<p>Checking...</p>";
    }
	postDivContent(centerCont, url, parameters);
}
function postActivateUser(url,  parameters) {
	var centerCont = document.getElementById("activation_status");
    if(centerCont){
      centerCont.innerHTML="<p>Please wait...</p>";
    }
    postDivContent(centerCont, url, parameters);
}
function getStoreFeedback(url) {
	var my_bosbo_Feedback_content = document.getElementById("leaveFeedback");
    if(my_bosbo_Feedback_content){
      my_bosbo_Feedback_content.innerHTML="<p>Loading...</p>";
    }
    getDivContent(my_bosbo_Feedback_content,url);
}
function checkUsernameAvailability(url){ //, url2) {
	getCheckUsernameAvailability(url);
}
function getCheckUsernameAvailability(url) {
	var my_bosbo_Feedback_content = document.getElementById("validUsername");
    if(my_bosbo_Feedback_content){
      my_bosbo_Feedback_content.innerHTML="<p class='bbsmall'><font color='red'>Checking...</font></p>";
    }
    getDivContent(my_bosbo_Feedback_content,url);
}
function getCheckUsernameButton(url) {
	var my_bosbo_Feedback_content = document.getElementById("validUsernameButton");
	getDivContent(my_bosbo_Feedback_content,url);
}
function getPage(url,tabid,num,currentpage) {
  //lastTabId = tabid;
  lastTabCount = num;
  //alert(lastTabId + "  " + lastTabCount);
  
  getCentreContent(url, currentpage);
  for(i=1;i<=num;i++){
    document.getElementById("tab"+i).className="unselected";
    document.getElementById("tabli"+i).className="unselected";
  }
  document.getElementById("tab"+tabid).className="selected";
  document.getElementById("tabli"+tabid).className="selected";
}
function postSaveAff(url, prodMd5, parameters) {
//alert('up to here' + url + prodMd5);
var content = document.getElementById(prodMd5);
    if(content){
      content.innerHTML="<p>Saving...</p>";
    }
	postDivContent(content, url, parameters);
}

function signIn(username, password, root) {
  var signInCont = document.getElementById("signIn");
  var url=root+"pages/user_fns/signInOut/signin.php";
  if(signInCont){
    signInCont.innerHTML="<div><br>Processing...</div>";
  }
  var XMLHttpRequestObject = createXMLrequest();
  if(XMLHttpRequestObject) {
	XMLHttpRequestObject.open("POST", url);
	XMLHttpRequestObject.setRequestHeader("Content-Type","application/x-www-form-urlencoded");
	XMLHttpRequestObject.onreadystatechange = function()
	{
		if (XMLHttpRequestObject.readyState == 4 &&
		XMLHttpRequestObject.status == 200) {
			signInCont.innerHTML = XMLHttpRequestObject.responseText;
			delete XMLHttpRequestObject;
			XMLHttpRequestObject = null;
			if (document.getElementById("SIGNIN_NEEDED").innerHTML==".") {
				window.location.reload();
			}
			// refresh centre content if necessary
			if (currentPage!=null) {
				getCentreContent(currentPage, currentPage);
			}
		}
	}
	XMLHttpRequestObject.send("userName=" + escape(username) + "&password=" + hex_md5(password) + "&root=" +root+ "");
  }
}
function signOut(root) {
  var signInCont = document.getElementById("signIn");
  var url=root+"pages/user_fns/signInOut/signout.php";
  if(signInCont){
    signInCont.innerHTML="<div><br>Processing...</div>";
  }
  var XMLHttpRequestObject = createXMLrequest();
  if(XMLHttpRequestObject) {
	XMLHttpRequestObject.open("POST", url);
	XMLHttpRequestObject.setRequestHeader("Content-Type","application/x-www-form-urlencoded");
	XMLHttpRequestObject.onreadystatechange = function()
	{
		if (XMLHttpRequestObject.readyState == 4 &&
		XMLHttpRequestObject.status == 200) {
			signInCont.innerHTML = XMLHttpRequestObject.responseText;
			delete XMLHttpRequestObject;
			XMLHttpRequestObject = null;
			// refresh centre content if necessary
			window.location.reload();
			if (currentPage!=null) {
				getCentreContent(currentPage, currentPage);
			}
		}
	}
	XMLHttpRequestObject.send("root=" +root+ "");
  }
}

function monitor_this_item(user, category) {
	// always called from product_page.php so adress is static
	var url = '../my_bosbo/my_bosbo_fns/addMonitor.php?userId='+user+'&categoryId='+category;
	var monitorDiv = document.getElementById("monitorDiv");
    /*if(monitorDiv){
      monitorDiv.innerHTML="<div></div>";
    }*/
    var XMLHttpRequestObject = createXMLrequest();
	if(XMLHttpRequestObject) {
		XMLHttpRequestObject.open("GET", url);
		XMLHttpRequestObject.onreadystatechange = function()
		{
			if (XMLHttpRequestObject.readyState == 4 &&
			XMLHttpRequestObject.status == 200) {
				monitorDiv.innerHTML = XMLHttpRequestObject.responseText;
				delete XMLHttpRequestObject;
				XMLHttpRequestObject = null;
				window.location.reload();
				/*alert('neil');
				getCentreContent("../../navigation/l2_grid.php?category_id="+category , "../../navigation/l2_grid.php?category_id="+category);
				*/
			}
		}
		XMLHttpRequestObject.send(null);
	}
}
function delete_this_monitor(user, category, referingUrl) {
	// called from pages from the 2nd level down the directory structure.
	var url = '../my_bosbo/my_bosbo_fns/deleteMonitor.php?userId='+user+'&categoryId='+category;
	var deleteDiv = document.getElementById("monitorDiv");
    /*if(deleteDiv){
      deleteDiv.innerHTML="<div></div>";
    }*/
    var XMLHttpRequestObject = createXMLrequest();
	if(XMLHttpRequestObject) {
		XMLHttpRequestObject.open("GET", url);
		XMLHttpRequestObject.onreadystatechange = function()
		{
			if (XMLHttpRequestObject.readyState == 4 &&
			XMLHttpRequestObject.status == 200) {
				deleteDiv.innerHTML = XMLHttpRequestObject.responseText;
				delete XMLHttpRequestObject;
				XMLHttpRequestObject = null;
				window.location.reload();
				/*if (referingUrl == 'my_bosbo_watch_list') {
					getMyBosboContent('../my_bosbo/my_bosbo_watching.php');
				} else {
					getCentreContent("../../navigation/l2_grid.php?category_id="+category , "../../navigation/l2_grid.php?category_id="+category);
				}*/
			}
		}
		XMLHttpRequestObject.send(null);
	}
}

// Part 1 - Actual Grid - MAKES AJAX REQUEST
var counterNum;
var wrapperCont
var iNum;
var iMax;
function showGrid($counter, $orderId) {
  counterNum = "content"+$counter;
  wrapperCont = document.getElementById("content"+$counter);
  if (wrapperCont.style.display == "none") {
  	  //  should always be called from 2 nodes down the grid, so this is static.
  	  // we can calculate the root and pass this in if this turns out to be necessary
	  var url="../../pages/navigation/l2_grid_order.php?orderId="+$orderId;
	  wrapperCont.style.height = 0	+'px';	  
	  iNum=0;
	  // iMax should be the MINIMUM size of the data returned from AJAX l2_grid_order.php
	  iMax=150;
	  wrapperCont.style.display = "block";
	  increaseGridSize();
	  // Request to server is made every time a section is expanded.
	  // whether opened before or not
	  if(wrapperCont){
	    wrapperCont.innerHTML="<br/><br/><br/><br/><div align='center'>Loading...</div><br/><br/><br/><br/>";
	  }
	  getDivContent(wrapperCont,url);
  } else {
	  // the <div> is expanded so needs collapsing.
	  iNum=150;
	  iMax=0;
	  decreaseGridSize();
  }
}
function increaseGridSize() {
	iNum=iNum+50;//67;
	wrapperCont.style.height = iNum + 'px';
	if (iNum<iMax) {
		setTimeout(increaseGridSize, 1)
	} else {
		// remove expands to 200px, and then to complete height of div - FOR MOZILLA.
		wrapperCont.style.height = '';
	}
}
function decreaseGridSize() {
	// look at using min-height in Mozilla and IE7 and only height in >IE6 if we
	// want the content to never outgrow the box.
	wrapperCont.style.height = iNum + 'px'
	iNum=iNum-75;//100;
	if (iNum>=iMax) {
		setTimeout(decreaseGridSize, 5)
	} else {
		wrapperCont.style.display= "none";
	}
}

function getAddOrderPictureThumb(tempSessionId, orderId) {
  var pictCont = document.getElementById("picture_thumbRev");
  if (orderId!='') {
	  var url="../Adding_order/getOfferThumbnail.php?tempSessionId=" + tempSessionId +
  "&currentOrderId=" +orderId;
  } else {
  	var url="../Adding_order/getOfferThumbnail.php?tempSessionId=" + tempSessionId;
  }
  if(pictCont){
    pictCont.innerHTML="<span>Loading Image...</span>";
  }
  getDivContent(pictCont,url);
}

/** THESE ARE THE FUNCTIONS THAT AJAX RELIES ON **/
function addEvent(obj, evType, fn, useCapture){
  if (obj.addEventListener){
    obj.addEventListener(evType, fn, useCapture);
    return true;
  } else if (obj.attachEvent){
    var r = obj.attachEvent("on"+evType, fn);
    return r;
  } else {
    alert("Handler could not be attached");
  }
}
function removeEvent(obj, evType, fn, useCapture){
  if (obj.removeEventListener){
    obj.removeEventListener(evType, fn, useCapture);
    return true;
  } else if (obj.detachEvent){
    var r = obj.detachEvent("on"+evType, fn);
    return r;
  } else {
    alert("Handler could not be removed");
  }
}
function createXMLrequest(){
    var XMLHttpRequestObject = false;
    // put the following in a function:
	try {
    XMLHttpRequestObject = new XMLHttpRequest();
  } catch (trymicrosoft) {
    try {
      XMLHttpRequestObject = new ActiveXObject("Msxml2.XMLHTTP");
    } catch (othermicrosoft) {
      try {
        XMLHttpRequestObject = new ActiveXObject("Microsoft.XMLHTTP");
      } catch (failed) {
        XMLHttpRequestObject = null;
      }
    }
  }
  if (XMLHttpRequestObject == null)
    alert("Error creating request object!");
  return XMLHttpRequestObject;
}










/** these should be built into the page that sends them;  **/
function submitOfferAmendment(orderId, category) {
	//calc what web address should be
	var webAdress = '';
	if(document.forms['addOfferPage3'].elements['internal'].value=="INTERNAL") {
		webAddress = '-1';
	} else {
		webAddress = document.forms['addOfferPage3'].elements['external_address'].value;
	}
	
	postCentreContent("sendAmendOffer.php", '' , "condition="+escape(document.getElementById('condRev').innerHTML)
		+"&quantity="+escape(document.getElementById('quantityRev').innerHTML)
		+"&expiryDate="+escape(document.forms['addOfferPage1'].elements['date18'].value)
		+"&totalPrice="+escape(document.getElementById('price1Rev').innerHTML)
		+"&itemPrice="+escape(document.forms['addOfferPage2'].elements['item_price_pound'].value+"."+
		    		document.forms['addOfferPage2'].elements['item_price_pence'].value)
		+"&pandpPrice="+escape(document.forms['addOfferPage2'].elements['pandp_price_pound'].value + "." +
		    		document.forms['addOfferPage2'].elements['pandp_price_pence'].value)
		+"&insured="+escape(document.getElementById('insuredRev').innerHTML)
		+"&insurancePrice="+escape(document.forms['addOfferPage2'].elements['insurance_price_pound'].value + "." +
		document.forms['addOfferPage2'].elements['insurance_price_pence'].value
		)
		+"&payment_methods="+escape(document.getElementById('payment_methodsRev').innerHTML)
		+"&description="+escape(document.getElementById('descriptionRev').innerHTML)
		//images will be moved in sendOffer.php
		+"&picture="+escape(document.forms['orderReviewForm'].elements['fullsizeLocation'].value)
		+"&picturethumb="+escape(document.forms['orderReviewForm'].elements['thumbnailLocation'].value)
		+"&webAddress="+escape(webAddress)
		+"&orderId="+orderId
		+"&buy=0"
	);
}
function submitOffer(category) {
//calc what web address should be
var webAdress = '';
if(document.forms['addOfferPage3'].elements['internal'].value=="INTERNAL") {
	webAddress = '-1';
} else {
	webAddress = document.forms['addOfferPage3'].elements['external_address'].value;
}
postCentreContent("sendOffer.php", '' , "condition="+escape(document.getElementById('condRev').innerHTML)
	+"&quantity="+escape(document.getElementById('quantityRev').innerHTML)
	+"&expiryDate="+escape(document.forms['addOfferPage1'].elements['date18'].value)
	+"&totalPrice="+escape(document.getElementById('price1Rev').innerHTML)
	+"&itemPrice="+escape(document.forms['addOfferPage2'].elements['item_price_pound'].value+"."+
	    		document.forms['addOfferPage2'].elements['item_price_pence'].value)
	+"&pandpPrice="+escape(document.forms['addOfferPage2'].elements['pandp_price_pound'].value + "." +
	    		document.forms['addOfferPage2'].elements['pandp_price_pence'].value)
	+"&insured="+escape(document.getElementById('insuredRev').innerHTML)
	+"&insurancePrice="+escape(document.forms['addOfferPage2'].elements['insurance_price_pound'].value + "." +
	document.forms['addOfferPage2'].elements['insurance_price_pence'].value
	)
	+"&payment_methods="+escape(document.getElementById('payment_methodsRev').innerHTML)
	+"&description="+escape(document.getElementById('descriptionRev').innerHTML)
	//images will be moved in sendOffer.php
	+"&picture="+escape(document.forms['orderReviewForm'].elements['fullsizeLocation'].value)
	+"&picturethumb="+escape(document.forms['orderReviewForm'].elements['thumbnailLocation'].value)
	+"&webAddress="+escape(webAddress)
	+"&categoryId="+category
	+"&buy=0"
);
}

function submitHitBid(tempOrderId, orderId) {
	/*postCentreContent('pages/transaction_fns/Hitting/sendHitBid.php', '' , "&expiryDate="+escape(document.forms['hitBitPage'].elements['date18'].value)
		+"&description="+escape(document.forms['hitBitPage'].elements['description'].value)
		+"&tempOrderId="+tempOrderId
		+"&orderId="+orderId
	);*/
}