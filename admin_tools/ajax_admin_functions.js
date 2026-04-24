// these are variables for if the current page needs refreshing on a sign in.
// if currentPage != null then reload.
var currentPage = null;

// this var is used if the user does a browser refresh... the same page is reloaded.
/*var lastPage = 'pages/home.php';*/

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

function setDivContent(div, url){
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

// param 1 - url of page to get
// param 2 - page to refresh on signin/signout.  null if not to refresh.  This is stored in the global var.
function getCentreContent(url, currentpage) {
	currentPage = currentpage;
	var centerCont = document.getElementById("centercontent");
    if(centerCont){
      centerCont.innerHTML="<p>Loading...</p>";
    }
	setDivContent(centerCont,url);
}

// param 1 - url of page to get
// param 2 - page to refresh on signin/signout.  null if not to refresh.  This is stored in the global var.
function postPindownContent(url, parameters) {
	var hiddenCont = document.getElementById("hidden_var");
	hiddenCont.parentNode.removeChild(hiddenCont);
	var centerCont = document.getElementById("pindown");
    /*if(centerCont){
      centerCont.innerHTML="<p>Loading...</p>";
    }*/
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
	
	if(XMLHttpRequestObject) {
		XMLHttpRequestObject.open("POST", url);
		XMLHttpRequestObject.setRequestHeader("Content-Type","application/x-www-form-urlencoded");
		XMLHttpRequestObject.onreadystatechange = function()
		{
			if (XMLHttpRequestObject.readyState == 4 &&
			XMLHttpRequestObject.status == 200) {
				centerCont.innerHTML = centerCont.innerHTML + XMLHttpRequestObject.responseText;
				delete XMLHttpRequestObject;
				XMLHttpRequestObject = null;
			}
		}
		XMLHttpRequestObject.send(parameters);
	}
}


function postContent(url, parameters) {
	var centerCont = document.getElementById("testResults");
    if(centerCont){
      centerCont.innerHTML="<p>Loading...</p>";
    }
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
	
	if(XMLHttpRequestObject) {
		XMLHttpRequestObject.open("POST", url);
		XMLHttpRequestObject.setRequestHeader("Content-Type","application/x-www-form-urlencoded");
		XMLHttpRequestObject.onreadystatechange = function()
		{
			if (XMLHttpRequestObject.readyState == 4 &&
			XMLHttpRequestObject.status == 200) {
				centerCont.innerHTML = centerCont.innerHTML + XMLHttpRequestObject.responseText;
				delete XMLHttpRequestObject;
				XMLHttpRequestObject = null;
			}
		}
		XMLHttpRequestObject.send(parameters);
	}
}