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

let currentRouteLayer = null; // To store the current route on the map

findPathBtn.addEventListener('click', async () => {
    const startAddress = originInput.value;
    const endAddress = destinationInput.value;

    if (!startAddress || !endAddress) {
        alert('Please enter both origin and destination.');
        return;
    }

    try {
        const response = await fetch('http://127.0.0.1:5000/safepath', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                start_address: startAddress,
                end_address: endAddress
            }),
        });

        const data = await response.json();

        if (response.ok) {
            const route = data.safest_route;
            const safetyScore = data.safety_score;

            // Clear previous route if any
            if (currentRouteLayer) {
                map.removeLayer(currentRouteLayer);
            }

            // Extract coordinates for the route
            const routeCoordinates = [];
            let totalDistance = 0;
            let totalDuration = 0;

            route.legs.forEach(leg => {
                leg.steps.forEach(step => {
                    routeCoordinates.push([step.start_location.lat, step.start_location.lng]);
                    totalDistance += step.distance.value; // meters
                    totalDuration += step.duration.value; // seconds
                });
                // Add the end location of the last step in the leg
                routeCoordinates.push([leg.end_location.lat, leg.end_location.lng]);
            });

            // Draw the route on the map
            currentRouteLayer = L.polyline(routeCoordinates, {color: '#44d07b', weight: 6}).addTo(map);
            map.fitBounds(currentRouteLayer.getBounds());

            // Update mini-stats card
            scoreDisplay.dataset.score = `${Math.round(100 - safetyScore)}%`; // Invert score for display (higher is safer)
            estimatedTimeDisplay.textContent = `Estimated time: ${Math.round(totalDuration / 60)} mins`;

            // Update status bar
            distancePill.textContent = `Distance: ${(totalDistance / 1000).toFixed(1)} km`;
            alertsPill.textContent = `Alerts: ${safetyScore}`; // Using safety score as alerts for now

            // For demonstration, you might want to fetch crime data for visualization
            // fetch('http://127.0.0.1:5000/crime_data')
            // .then(res => res.json())
            // .then(crimeData => {
            //     crimeData.forEach(crime => {
            //         if (crime.LAT_WGS84 && crime.LONG_WGS84) {
            //             L.circleMarker([crime.LAT_WGS84, crime.LONG_WGS84], {radius: 5, color: 'red', fillOpacity: 0.7}).addTo(map);
            //         }
            //     });
            // });

        } else {
            alert(`Error: ${data.error || data.message}`);
        }
    } catch (error) {
        console.error('Error fetching safe path:', error);
        alert('An error occurred while finding the safe path.');
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
