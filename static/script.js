$('#navbarNav').on('shown.bs.collapse', function () {
  $('#userDropdown').dropdown('show');
});
$('#navbarNav').on('hidden.bs.collapse', function () {
  $('#userDropdown').dropdown('hide');
});
