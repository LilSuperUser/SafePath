// script.js
const API_BASE = window.location.origin;
const SAFE_ROUTE_URL = `${API_BASE}/api/safe-route/`;
const map = L.map("map").setView([28.6139, 77.209], 13);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);

let clickCount = 0;
let userMarker = null;
let destMarker = null;
let routeLayers = []; // Store all route layers
let allRoutesData = []; // Store route data
let selectedRouteIndex = 0; // Currently selected route

const statusEl = document.getElementById("status");
const statsEl = document.getElementById("stats");

function setStatus(text) {
  statusEl.textContent = text;
}

function setUserLocation(lat, lon) {
  if (userMarker) userMarker.setLatLng([lat, lon]);
  else userMarker = L.marker([lat, lon], { title: "You" }).addTo(map);
  map.setView([lat, lon], 15);
  setStatus("Location acquired.");
}

const fallback_start = [28.474780644693578, 77.47638190820159];
setStatus("Requesting location...");

if (navigator.geolocation) {
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      setUserLocation(pos.coords.latitude, pos.coords.longitude);
      clickCount = 1;
    },
    (err) => {
      console.warn("geolocation error", err);
      setStatus("Using default starting location.");
      setUserLocation(fallback_start[0], fallback_start[1]);
      clickCount = 1;
    },
    { enableHighAccuracy: true },
  );
} else {
  setStatus("Geolocation not supported. Using default starting location.");
  setUserLocation(fallback_start[0], fallback_start[1]);
  clickCount = 1;
}

// CLEAR BUTTON
document.getElementById("clear").addEventListener("click", function () {
  clearAllRoutes();
  if (userMarker) map.removeLayer(userMarker);
  if (destMarker) map.removeLayer(destMarker);

  userMarker = null;
  destMarker = null;
  clickCount = 0;
  allRoutesData = [];
  selectedRouteIndex = 0;

  statsEl.innerHTML = "";
  const listEl = document.querySelector(".available-paths ul");
  if (listEl) listEl.innerHTML = "";
  const bottomTitle = document.querySelector(".bottom-cont h3");
  if (bottomTitle) bottomTitle.textContent = "Select a route";
  setStatus("Cleared. Click map to choose start, then destination.");
});

function clearAllRoutes() {
  routeLayers.forEach((layer) => map.removeLayer(layer));
  routeLayers = [];
}

// MAP CLICK HANDLER
map.on("click", async function (e) {
  clickCount++;

  if (clickCount === 1) {
    // First click: set start OR if userMarker already exists (geolocation), treat as destination:
    if (!userMarker) {
      userMarker = L.marker(e.latlng, { title: "Start" }).addTo(map);
      setStatus("Start selected. Now click destination.");
    } else {
      // if userMarker was already set from geolocation, treat first click as destination
      destMarker = L.marker(e.latlng, { title: "Destination" }).addTo(map);
      setStatus("Destination selected. Fetching routes…");
      await requestMultipleRoutes(
        userMarker.getLatLng().lat,
        userMarker.getLatLng().lng,
        destMarker.getLatLng().lat,
        destMarker.getLatLng().lng,
      );
      clickCount = 2;
    }
    return;
  }

  if (clickCount === 2) {
    // If we reach here because user set start via map (first click) then second click is destination:
    if (!destMarker) {
      destMarker = L.marker(e.latlng, { title: "Destination" }).addTo(map);
      setStatus("Destination selected. Fetching routes…");
      await requestMultipleRoutes(
        userMarker.getLatLng().lat,
        userMarker.getLatLng().lng,
        destMarker.getLatLng().lat,
        destMarker.getLatLng().lng,
      );
    }
    return;
  }

  if (clickCount >= 3) {
    // Reset and treat this click as new start
    clearAllRoutes();
    if (userMarker) map.removeLayer(userMarker);
    if (destMarker) map.removeLayer(destMarker);

    userMarker = null;
    destMarker = null;
    clickCount = 1;
    allRoutesData = [];

    userMarker = L.marker(e.latlng, { title: "Start" }).addTo(map);
    statsEl.innerHTML = "";
    const listEl = document.querySelector(".available-paths ul");
    if (listEl) listEl.innerHTML = "";
    setStatus("Restarted. Start selected – click destination.");
    return;
  }
});

// FETCH AND DISPLAY MULTIPLE ROUTES
async function requestMultipleRoutes(startLat, startLon, endLat, endLon) {
  setStatus("Fetching routes...");
  const url = `${SAFE_ROUTE_URL}?start_lat=${startLat}&start_lon=${startLon}&end_lat=${endLat}&end_lon=${endLon}`;

  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error("Server error " + res.status);

    const data = await res.json();
    console.log("Routes data received:", data);

    // Backend compatibility:
    // Accept both { routes: [...] } and older structure (recommended_safe_route etc.)
    let routes = data.routes || [];

    // If older structure present, convert to routes array for compatibility
    if ((!routes || routes.length === 0) && data.recommended_safe_route) {
      // Build a minimal set: safest, shortest, astar etc.
      routes = [];

      if (data.recommended_safe_route && data.recommended_safe_route.route) {
        routes.push({
          route_name: "Safest (recommended)",
          coordinates: data.recommended_safe_route.route,
          distance_km: (data.recommended_safe_route.distance_km || 0).toFixed
            ? data.recommended_safe_route.distance_km
            : 0,
          safety_rating: Math.max(
            0,
            Math.min(5, 5 - data.recommended_safe_route.avg_risk * 5),
          ), // convert risk->rating
          segments: data.recommended_safe_route.segments || 0,
          avg_risk: data.recommended_safe_route.avg_risk || 0,
          travel_times: data.recommended_safe_route.travel_times || {
            walk: "-",
            bike: "-",
            car: "-",
          },
        });
      }

      if (data.safe_osrm_alternatives && data.safe_osrm_alternatives.length) {
        data.safe_osrm_alternatives.forEach((alt, idx) => {
          routes.push({
            route_name: `OSRM alt #${idx + 1}`,
            coordinates: alt.route || alt.coordinates || [],
            distance_km: alt.distance_km || 0,
            safety_rating: Math.max(
              0,
              Math.min(5, 5 - (alt.avg_risk || 0) * 5),
            ),
            segments: alt.segments || 0,
            avg_risk: alt.avg_risk || 0,
            travel_times: alt.travel_times || {
              walk: "-",
              bike: "-",
              car: "-",
            },
          });
        });
      }
    }

    if (!routes || routes.length === 0) {
      throw new Error("No routes received");
    }

    allRoutesData = routes;
    clearAllRoutes();

    // Draw all routes
    allRoutesData.forEach((route, idx) => {
      const color = getRouteColor(idx, route.safety_rating);
      const layer = L.polyline(
        route.coordinates.map((p) => [p[0], p[1]]),
        {
          color: color,
          weight: idx === 0 ? 6 : 4,
          opacity: idx === 0 ? 0.9 : 0.5,
        },
      ).addTo(map);

      layer.on("click", () => selectRoute(idx));
      routeLayers.push(layer);
    });

    // Fit map to show all routes
    const allPoints = allRoutesData.flatMap((r) =>
      r.coordinates.map((p) => [p[0], p[1]]),
    );
    if (allPoints.length) map.fitBounds(allPoints, { padding: [50, 50] });

    // Update UI
    updateAvailablePathsList();
    selectRoute(0); // Select first route by default

    setStatus(
      `${allRoutesData.length} routes found. Click a route or select from list.`,
    );
  } catch (err) {
    console.error("Route error:", err);
    setStatus("Error: " + err.message);
  }
}

function getRouteColor(index, safetyRating) {
  // Color based on safety rating (0-5)
  if (safetyRating >= 4.5) return "#4CAF50"; // Green - very safe
  if (safetyRating >= 3.5) return "#8BC34A"; // Light green - safe
  if (safetyRating >= 2.5) return "#FFC107"; // Yellow - moderate
  if (safetyRating >= 1.5) return "#FF9800"; // Orange - risky
  return "#E53935"; // Red - dangerous
}

function updateAvailablePathsList() {
  const listEl = document.querySelector(".available-paths ul");
  listEl.innerHTML = "";

  allRoutesData.forEach((route, idx) => {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.onclick = () => selectRoute(idx);

    const safeVal = route.safety_rating || 0;

    btn.innerHTML = `
            <div>
                <h5>${route.route_name} (${Number(route.distance_km).toFixed(2)} km)</h5>
                <div class="innerdiv">
                    <p>Safety Rating: </p>
                    <progress value="${safeVal}" max="5"></progress>
                    <span style="margin-left: 8px; color: #888;">${safeVal.toFixed(1)}/5</span>
                </div>
            </div>
        `;

    li.appendChild(btn);
    listEl.appendChild(li);
  });
}

function selectRoute(index) {
  if (index < 0 || index >= allRoutesData.length) return;

  selectedRouteIndex = index;
  const route = allRoutesData[index];

  // Update route appearance
  routeLayers.forEach((layer, idx) => {
    if (idx === index) {
      layer.setStyle({ weight: 6, opacity: 0.95 });
      if (layer.bringToFront) layer.bringToFront();
    } else {
      layer.setStyle({ weight: 4, opacity: 0.4 });
    }
  });

  // Update stats panel
  statsEl.innerHTML = "";
  const li = (txt) => {
    const el = document.createElement("li");
    el.textContent = txt;
    return el;
  };

  statsEl.appendChild(li(`Route: ${route.route_name}`));
  statsEl.appendChild(
    li(`Distance: ${Number(route.distance_km).toFixed(2)} km`),
  );
  statsEl.appendChild(
    li(`Safety Rating: ${(route.safety_rating || 0).toFixed(1)}/5`),
  );
  statsEl.appendChild(li(`Segments: ${route.segments || 0}`));
  statsEl.appendChild(li(`Avg Risk: ${(route.avg_risk || 0).toFixed(3)}`));

  // Update bottom panel
  const bottomTitle = document.querySelector(".bottom-cont h3");
  if (bottomTitle) bottomTitle.textContent = route.route_name;

  const safetyProgress = document.getElementById("crime-safety-progress");
  if (safetyProgress) safetyProgress.value = route.safety_rating || 0;

  const crimeBasedH4s = document.querySelectorAll(".crime-based h4");
  if (crimeBasedH4s.length >= 2) {
    crimeBasedH4s[1].textContent = `Safety Rating: ${(route.safety_rating || 0).toFixed(1)}/5`;
  }

  const travelList = document.querySelector(".time-based ul");
  if (travelList) {
    travelList.innerHTML = `
            <li>Walk: ${route.travel_times && route.travel_times.walk ? route.travel_times.walk : "-"} min</li>
            <li>Bike: ${route.travel_times && route.travel_times.bike ? route.travel_times.bike : "-"} min</li>
            <li>Car: ${route.travel_times && route.travel_times.car ? route.travel_times.car : "-"} min</li>
        `;
  }

  // Highlight selected route in list
  document
    .querySelectorAll(".available-paths ul li button")
    .forEach((btn, idx) => {
      if (idx === index) {
        btn.style.backgroundColor = "#404040";
      } else {
        btn.style.backgroundColor = "#2A2A2A";
      }
    });
}

// Geocoding
async function geocode(place) {
  const url = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(place)}`;
  const res = await fetch(url);
  const data = await res.json();
  if (data.length === 0) return null;
  return {
    lat: parseFloat(data[0].lat),
    lon: parseFloat(data[0].lon),
  };
}

// DIRECTIONS BUTTON
document
  .getElementById("directions-btn")
  .addEventListener("click", async () => {
    const fromText = document.getElementById("from-input").value.trim();
    const toText = document.getElementById("to-input").value.trim();

    if (!fromText || !toText) {
      alert("Please enter both locations.");
      return;
    }

    setStatus("Finding locations...");

    const fromLoc = await geocode(fromText);
    const toLoc = await geocode(toText);

    if (!fromLoc) {
      setStatus("Starting location not found.");
      return;
    }
    if (!toLoc) {
      setStatus("Destination not found.");
      return;
    }

    if (userMarker) map.removeLayer(userMarker);
    if (destMarker) map.removeLayer(destMarker);

    userMarker = L.marker([fromLoc.lat, fromLoc.lon], { title: "Start" }).addTo(
      map,
    );
    destMarker = L.marker([toLoc.lat, toLoc.lon], {
      title: "Destination",
    }).addTo(map);

    map.setView([fromLoc.lat, fromLoc.lon], 13);

    setStatus("Fetching routes...");
    await requestMultipleRoutes(fromLoc.lat, fromLoc.lon, toLoc.lat, toLoc.lon);
  });
