var map = null;
var markersArray = [];

function initMap() {
  var myLatLng = {lat: 0, lng: 0};

  map = new google.maps.Map(document.getElementById('map'), {
    zoom: 3,
    center: myLatLng
  });

  getAndDisplayUnits();
  startUpdateLoop();
}

function startUpdateLoop() {
  setInterval(function() {
    getAndDisplayUnits();
  }, 60000);
}

function clearOverlays() {
  for (var i = 0; i < markersArray.length; i++ ) {
    markersArray[i].setMap(null);
  }
  markersArray = new Array();
}

function getLastHereDateFromLocalStorage() {
  var retrievedObject = localStorage.getItem('lastHere');
  if (retrievedObject) {
    return new Date(retrievedObject);
  }
  return new Date(0);
}

function storeLastHereDateToLocalStorage(lastHere) {
  localStorage.setItem('lastHere', lastHere);
}

function getAndDisplayUnits() {
  var xhttp = new XMLHttpRequest();
  xhttp.onreadystatechange = function() {
    if (xhttp.readyState == XMLHttpRequest.DONE && xhttp.status == 200) {
      clearOverlays();

      var greetings = JSON.parse(xhttp.responseText);
      var lastHere = getLastHereDateFromLocalStorage();
      var latestEventDT = new Date(0);
      var contentStrings = [];

      var avgLat = 0;
      var avgLong = 0;

      for (i = 0; i < greetings.length; ++i) {
        var greeting = greetings[i];

        var latlong = {lat: greeting.lat, lng: greeting.long};
        avgLat += greeting.lat;
        avgLong += greeting.long;
        var marker = null;
        var eventDT = new Date(greeting.eventDT);

        if (eventDT >= lastHere) {
          marker = new google.maps.Marker({
            position: latlong,
            map: map,
            animation: google.maps.Animation.DROP
          });
        } else {
          marker = new google.maps.Marker({
            position: latlong,
            map: map
          });
        }

        if (eventDT > latestEventDT) {
          latestEventDT = eventDT;
        }

        contentStrings.push("<b>" + greeting.eventDT + "</b><br /><a href=\""+ greeting.photo +"\" target=\"_blank\"><img src=\""+ greeting.thumbnail +"\" /></a><p>" +greeting.notes+"</p><p>Photo taken on: "+greeting.photoDT+"</p>");
        var infowindow = new google.maps.InfoWindow();

        google.maps.event.addListener(marker, 'click', (function(marker, i) {
             return function() {
                 infowindow.setContent(contentStrings[i]);
                 infowindow.open(map, marker);
             }
         })(marker, i));

         markersArray.push(marker);
      }
      map.setCenter(new google.maps.LatLng(avgLat/greetings.length,avgLong/greetings.length));

      latestEventDT.setSeconds(latestEventDT.getSeconds() + 1);
      storeLastHereDateToLocalStorage(latestEventDT);
    }
  }
  xhttp.open("GET", "/v1/api", true);
  xhttp.send();
}
