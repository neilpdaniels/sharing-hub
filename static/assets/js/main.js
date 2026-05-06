(function($){
	
  /* Header fixed on scroll */
  $(window).scroll(function(){
	if ($(window).scrollTop() > 80) {
        $('#site-header').addClass('sticky');
      } else {
        $('#site-header').removeClass('sticky'); 
	}
  });
  
  /* Toggle Fixed Menu */
  $('.show-fixed-menu').click(function(e){
	e.preventDefault();
	$('body').toggleClass('menu-fixed-active');
  });
  
  /* Got to top */
  $('.go_top').click(function(){
    $('html, body').animate({ scrollTop: 0 }, 800);
  }); 
  
  /* Screenshot */
  $('#screenshot').change(function(){
	if (this.files && this.files[0]) {
	  var reader = new FileReader();
	  reader.onload = function(e) { 
        $('#screenshot-holder').html("<img src='"+e.target.result+"' class='mb-5' />");
      }
	  reader.readAsDataURL(this.files[0]);
	}
  });
  
  /* Profile Upload */ 
  $('#upload-profile').change(function(){
	if (this.files && this.files[0]) {
	  var reader = new FileReader();
	  reader.onload = function(e) { 
        $('#profile-box-icon').attr("src", e.target.result);
      }
	  reader.readAsDataURL(this.files[0]);
	}
  });
  
  /* Cover Upload */ 
  $('#change-cover').change(function(){
	if (this.files && this.files[0]) {
	  var reader = new FileReader();
	  reader.onload = function(e) { 
        $('#cover-img').attr("src", e.target.result);
      }
	  reader.readAsDataURL(this.files[0]);
	}
  });
  
  /* Select 2 */
  if($('.select2').length > 0){
    $('.select2').each(function(){
	  $(this).select2({theme: "bootstrap"});
	});
  }
  
  /* Popup */
  $('.popup-with-zoom-anim').magnificPopup({
	  type:'inline',
	  fixedContentPos:false,
	  fixedBgPos:true,
	  overflowY:'auto',
	  closeBtnInside:true,
	  preloader:false,
	  midClick:true,
	  removalDelay:300,
	  mainClass:'my-mfp-zoom-in'
  });
})(jQuery);