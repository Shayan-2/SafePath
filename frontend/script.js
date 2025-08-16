const map = L.map('map').setView([43.6532, -79.3832], 13);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
}).addTo(map);

// Get references to HTML elements
const originInput = document.getElementById('origin');
const destinationInput = document.getElementById('destination');
const findPathBtn = document.getElementById('findPathBtn');
const miniStats = document.getElementById('miniStats');
const scoreDisplay = miniStats.querySelector('.score');
const estimatedTimeDisplay = miniStats.querySelector('p');
const distancePill = document.querySelector('.metrics .pill:first-child');
const alertsPill = document.querySelector('.metrics .pill:last-child');
const statusMessage = document.getElementById('statusMessage');
const scoreInfoIcon = document.getElementById('scoreInfoIcon');

// Create tooltip element
const tooltip = document.createElement('div');
tooltip.className = 'safety-score-tooltip';
tooltip.style.cssText = `
    position: absolute;
    background-color: #333;
    color: #fff;
    padding: 10px;
    border-radius: 5px;
    font-size: 14px;
    z-index: 1000;
    max-width: 300px;
    display: none; /* Hidden by default */
    pointer-events: none; /* Allow events to pass through */
`;
document.body.appendChild(tooltip);

const safetyScoreExplanation = `
    Safety (0-100): Higher is safer.
`;

scoreInfoIcon.addEventListener('mouseover', (event) => {
    tooltip.textContent = safetyScoreExplanation;
    tooltip.style.display = 'block';
    // Position the tooltip next to the icon
    tooltip.style.left = `${event.pageX + 10}px`;
    tooltip.style.top = `${event.pageY + 10}px`;
});

scoreInfoIcon.addEventListener('mouseout', () => {
    tooltip.style.display = 'none';
});

let currentRouteLayer = null; // To store the current route on the map
let crimeMarkersLayer = null; // To store the crime markers layer
let routePolylineLayers = []; // To store Leaflet polyline layers for each route
let safestRoutes = []; // Declare safestRoutes in a higher scope
const routesList = document.getElementById('routesList');
let routeNumberMarkersLayer = null; // To store route number markers

// Function to update map and stats based on selected route
function updateSelectedRoute(selectedIndex) {
    routePolylineLayers.forEach((layer, index) => {
        let polylineColor = '#888'; // Default for unselected routes
        let polylineWeight = 4;
        let polylineOpacity = 0.5;

        if (index === selectedIndex) {
            polylineColor = '#44d07b'; // Highlight selected route
            polylineWeight = 6;
            polylineOpacity = 1;
        }
        layer.setStyle({ color: polylineColor, weight: polylineWeight, opacity: polylineOpacity });
    });

    // Update mini-stats card and status bar for the selected route
    const selectedRouteInfo = safestRoutes[selectedIndex];
    const route = selectedRouteInfo.route;
    const safetyScore = selectedRouteInfo.score;

    let totalDistance = 0;
    let totalDuration = 0;
    route.legs.forEach(leg => {
        totalDistance += leg.distance.value;
        totalDuration += leg.duration.value;
    });

    scoreDisplay.dataset.score = `${safetyScore.toFixed(0)}`; // Display as raw score, no percentage
    estimatedTimeDisplay.textContent = `Estimated time: ${Math.round(totalDuration / 60)} mins`;
    distancePill.textContent = `Distance: ${(totalDistance / 1000).toFixed(1)} km`;
    alertsPill.textContent = `Alerts: ${safetyScore.toFixed(0)}`; // Display the actual safety score, rounded

    // Update the conic-gradient fill for the score circle
    scoreDisplay.style.setProperty('--score', `${safetyScore}%`);

    // Update active class in routes list
    Array.from(routesList.children).forEach((child, idx) => {
        if (idx === selectedIndex) {
            child.classList.add('active');
        } else {
            child.classList.remove('active');
        }
    });

    statusMessage.textContent = 'Route Ready'; // Set status to Route Ready

    // Update route number marker for the selected route
    if (routeNumberMarkersLayer) {
        map.removeLayer(routeNumberMarkersLayer);
    }
    const startPoint = route.overview_polyline.points;
    const decodedPath = decodePolyline(startPoint);
    const routeCoordinates = decodedPath.map(point => [point[0], point[1]]);

    const routeNumberIcon = L.divIcon({
        className: 'route-number-icon',
        html: `<div>#${selectedIndex + 1}</div>`,
        iconSize: [30, 30]
    });
    routeNumberMarkersLayer = L.layerGroup().addTo(map);
    L.marker(routeCoordinates[0], {icon: routeNumberIcon}).addTo(routeNumberMarkersLayer);
}

// Function to reset UI to initial state
function resetUIState() {
    scoreDisplay.dataset.score = '0'; // Reset score to 0
    estimatedTimeDisplay.textContent = 'Estimated time: -- mins';
    distancePill.textContent = 'Distance: -- km';
    alertsPill.textContent = 'Alerts: --';
    statusMessage.textContent = 'Enter origin and destination';
    routesList.innerHTML = ''; // Clear route list

    if (currentRouteLayer) {
        map.removeLayer(currentRouteLayer);
        currentRouteLayer = null; // Important: reset the layer
    }
    if (crimeMarkersLayer) {
        map.removeLayer(crimeMarkersLayer);
        crimeMarkersLayer = null; // Important: reset the layer
    }
    if (routeNumberMarkersLayer) { // Clear route number markers
        map.removeLayer(routeNumberMarkersLayer);
        routeNumberMarkersLayer = null; // Important: reset the layer
    }

    routePolylineLayers = []; // Clear stored polyline layers
    safestRoutes = []; // Clear stored route data
}

// Initial UI reset when the script loads
resetUIState();

findPathBtn.addEventListener('click', async () => {
    const startAddress = originInput.value;
    const endAddress = destinationInput.value;
    const selectedMode = document.querySelector('input[name="commuteMode"]:checked').value;

    if (!startAddress || !endAddress) {
        alert('Please enter both origin and destination.');
        return;
    }

    // Show loading indicator and clear previous results by calling resetUIState
    resetUIState(); // Clear all previous data and layers
    statusMessage.textContent = 'Finding safest routes...'; // Set loading message

    try {
        const response = await fetch('http://127.0.0.1:5000/safepath', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                start_address: startAddress,
                end_address: endAddress,
                commute_mode: selectedMode // Send the selected commute mode
            }),
        });

        const data = await response.json();

        if (response.ok) {
            safestRoutes = data.safest_routes; // Assign to the higher-scoped variable
            // console.log('Safest Routes received from backend:', safestRoutes); // Remove debugging log

            if (safestRoutes.length === 0) {
                alert("No routes found for the given locations.");
                return;
            }

            // Clear previous routes and markers
            if (currentRouteLayer) {
                map.removeLayer(currentRouteLayer);
            }
            if (crimeMarkersLayer) {
                map.removeLayer(crimeMarkersLayer);
            }
            crimeMarkersLayer = L.layerGroup().addTo(map);

            routePolylineLayers = []; // Clear previous route polyline layers
            routesList.innerHTML = ''; // Clear previous route list items

            let allRouteLayers = L.layerGroup();
            let bounds = L.latLngBounds();
            // routeNumberMarkersLayer = L.layerGroup().addTo(map); // Removed: moved to updateSelectedRoute for dynamic display

            safestRoutes.forEach((routeInfo, index) => {
                const route = routeInfo.route;
                const safetyScore = routeInfo.score;

                const overviewPolyline = route.overview_polyline.points;
                const decodedPath = decodePolyline(overviewPolyline);

                const routeCoordinates = decodedPath.map(point => [point[0], point[1]]);

                // Initial styling for all routes (safest is prominent, others are subtle)
                let polylineColor = '#888';
                let polylineWeight = 4;
                let polylineOpacity = 0.5;

                if (index === 0) { // Safest route is prominent by default
                    polylineColor = '#44d07b';
                    polylineWeight = 6;
                    polylineOpacity = 1;
                }

                // console.log(`Drawing Route #${index + 1}: Color=${polylineColor}, Weight=${polylineWeight}, Opacity=${polylineOpacity}`); // Remove debugging log
                // console.log(`Route #${index + 1} Start: [${routeCoordinates[0][0]}, ${routeCoordinates[0][1]}] End: [${routeCoordinates[routeCoordinates.length - 1][0]}, ${routeCoordinates[routeCoordinates.length - 1][1]}]`); // Remove debugging log

                const routeLayer = L.polyline(routeCoordinates, {color: polylineColor, weight: polylineWeight, opacity: polylineOpacity});
                routePolylineLayers.push(routeLayer); // Store the layer
                routeLayer.addTo(allRouteLayers);
                bounds.extend(routeLayer.getBounds());

                // Add route number marker
                const startPoint = routeCoordinates[0];
                const routeNumberIcon = L.divIcon({
                    className: 'route-number-icon',
                    html: `<div>#${index + 1}</div>`,
                    iconSize: [30, 30]
                });
                // Only add the route number marker to the map if it's the selected route
                // This way, only one route number is visible at a time
                if (index === 0) { // Using selectedIndex from updateSelectedRoute context
                    // Clear previous route number markers and add only the selected one
                    if (routeNumberMarkersLayer) {
                        map.removeLayer(routeNumberMarkersLayer);
                    }
                    routeNumberMarkersLayer = L.layerGroup().addTo(map); // Create a new layer group for the active marker
                    L.marker(startPoint, {icon: routeNumberIcon}).addTo(routeNumberMarkersLayer);
                }
                
                // Note: The route number markers will only appear for the *selected* route now.
                // If you want all routes to have numbers initially, we would need a different approach.

                // Create and append route list item
                const routeItem = document.createElement('div');
                routeItem.classList.add('route-item');
                routeItem.innerHTML = `
                    <span>Route #${index + 1}</span>
                    <span>Safety Score: ${safetyScore.toFixed(0)}</span>
                `;
                routeItem.addEventListener('click', () => updateSelectedRoute(index));
                routesList.appendChild(routeItem);
            });

            allRouteLayers.addTo(map);
            currentRouteLayer = allRouteLayers; // Store the layer group

            if (bounds.isValid()) {
                map.fitBounds(bounds);
            }

            // Select the first route by default
            if (safestRoutes.length > 0) {
                updateSelectedRoute(0);
            }

            // Fetch and visualize crime data remains the same
            console.log('Fetching crime data...');
            fetch('http://127.0.0.1:5000/crime_data')
            .then(res => {
                console.log('Crime data fetch response status:', res.status, res.ok);
                if (!res.ok) {
                    throw new Error(`HTTP error! status: ${res.status}`);
                }
                return res.json();
            })
            .then(crimeData => {
                console.log('Received crime data:', crimeData);
                if (crimeData.length === 0) {
                    console.log('No crime data received.');
                }
                crimeData.forEach(crime => {
                    if (crime.LAT_WGS84 && crime.LONG_WGS84) {
                        console.log('Adding crime marker at:', crime.LAT_WGS84, crime.LONG_WGS84);
                        // Create a circle marker for each crime location
                        const marker = L.circleMarker([crime.LAT_WGS84, crime.LONG_WGS84], {
                            radius: 5,
                            color: 'red',
                            fillColor: '#f03',
                            fillOpacity: 0.7
                        }).addTo(crimeMarkersLayer);

                        // Add a popup with crime details
                        marker.bindPopup(`<b>Crime Category:</b> ${crime.MCI_CATEGORY || 'N/A'}<br><b>Offence:</b> ${crime.OFFENCE || 'N/A'}<br><b>Date:</b> ${crime.OCC_DATE || 'N/A'}`);
                    }
                });
            })
            .catch(error => {
                console.error('Error fetching or processing crime data:', error);
                statusMessage.textContent = 'Error loading crime data.';
            });

        } else {
            alert(`Error: ${data.error || data.message}`);
            statusMessage.textContent = 'Error finding route.';
        }
    } catch (error) {
        console.error('Error fetching safe path:', error);
        alert('An error occurred while finding the safe path.');
        statusMessage.textContent = 'An error occurred.';
    }
});

// Autocomplete functionality
function debounce(func, delay) {
    let timeout;
    return function(...args) {
        const context = this;
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(context, args), delay);
    };
}

async function fetchAutocompleteSuggestions(inputElement, datalistElement) {
    const query = inputElement.value;
    if (query.length < 3) { // Only search if query is at least 3 characters long
        datalistElement.innerHTML = '';
        return;
    }

    try {
        const response = await fetch(`http://127.0.0.1:5000/autocomplete?q=${encodeURIComponent(query)}`);
        const suggestions = await response.json();

        datalistElement.innerHTML = ''; // Clear previous suggestions
        suggestions.forEach(suggestion => {
            const option = document.createElement('option');
            option.value = suggestion;
            datalistElement.appendChild(option);
        });
    } catch (error) {
        console.error('Error fetching autocomplete suggestions:', error);
    }
}

const originDatalist = document.createElement('datalist');
originDatalist.id = 'originSuggestions';
originInput.setAttribute('list', 'originSuggestions');
document.body.appendChild(originDatalist);

const destinationDatalist = document.createElement('datalist');
destinationDatalist.id = 'destinationSuggestions';
destinationInput.setAttribute('list', 'destinationSuggestions');
document.body.appendChild(destinationDatalist);

originInput.addEventListener('input', debounce(() => {
    fetchAutocompleteSuggestions(originInput, originDatalist);
}, 500));

destinationInput.addEventListener('input', debounce(() => {
    fetchAutocompleteSuggestions(destinationInput, destinationDatalist);
}, 500));

// Helper function to decode Google Encoded Polylines
function decodePolyline(encoded) {
    let len = encoded.length;
    let index = 0;
    let lat = 0;
    let lng = 0;
    let array = [];

    while (index < len) {
        let b;
        let shift = 0;
        let result = 0;
        do {
            b = encoded.charCodeAt(index++) - 63;
            result |= (b & 0x1f) << shift;
            shift += 5;
        } while (b >= 0x20);
        let dlat = ((result & 1) ? ~(result >> 1) : (result >> 1));
        lat += dlat;

        shift = 0;
        result = 0;
        do {
            b = encoded.charCodeAt(index++) - 63;
            result |= (b & 0x1f) << shift;
            shift += 5;
        } while (b >= 0x20);
        let dlng = ((result & 1) ? ~(result >> 1) : (result >> 1));
        lng += dlng;

        array.push([lat / 1E5, lng / 1E5]);
    }
    return array;
}
