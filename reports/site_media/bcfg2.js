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
  var element = document.getElementById(elementId);
  if (element) {
    element.style.display = (element.style.display != 'none' ? 'none' : '');
    var plusminus = document.getElementById("plusminus_" + elementId);
    if (element.style.display == 'none') {
      plusminus.innerHTML = "[+]"
    } else {
      plusminus.innerHTML = "[&ndash;]"
    }
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
