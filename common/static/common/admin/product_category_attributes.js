document.addEventListener('DOMContentLoaded', function () {
  var categoryField = document.getElementById('id_category_id');
  if (!categoryField) {
    return;
  }

  var isAddPage = window.location.pathname.indexOf('/add/') !== -1;
  if (!isAddPage) {
    return;
  }

  categoryField.addEventListener('change', function () {
    var categoryId = (categoryField.value || '').trim();
    if (!categoryId) {
      return;
    }
    var nextUrl = new URL(window.location.href);
    if (nextUrl.searchParams.get('category_id') === categoryId) {
      return;
    }
    nextUrl.searchParams.set('category_id', categoryId);
    window.location.assign(nextUrl.toString());
  });
});
