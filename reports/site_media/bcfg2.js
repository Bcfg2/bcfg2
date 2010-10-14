function hide_table_array(ar) {
  for(i=0; i < ar.length; i++) {
    toggleMe(ar[i]);
  };
}
function clientdetailload() {
  toggleMe('bad_table');
  toggleMe('modified_table');
  toggleMe('extra_table');
}
function toggleMe(elementId) {
  element = document.getElementById(elementId);
  if (element) {
    element.style.display = (element.style.display != 'none' ? 'none' : '');
  }
}
function pageJump(elementId) {
  url = '';
  element = document.getElementById(elementId);
  if (element) {
    url = element.value;
  }
  if (url) {
    location.href = url;
  }
}
