# SafePath

SafePath helps users find the safest route in Toronto by combining Leaflet Javacript Library for interactive maps with real police crime data.

## Features

- Calculates routes that avoid high-risk areas
- Uses Toronto Police open data for crime analysis
- Fast backend with caching and spatial indexing
- Simple frontend for user input and results

## How to Run

1. Install dependencies:
   pip install flask flask-cors pandas requests numpy scipy

2. Start the backend:
   python Backend/backendcode.py

3. Serve the frontend:
   - Use VS Code’s Go Live extension or run:
       cd frontend
       python -m http.server 8000
   - Open your browser to http://127.0.0.1:8000

## API Endpoints

- POST /safest-route
  Request JSON:
    { "start": "Start Address", "end": "Destination Address" }
  Response: Safest route and directions

## Data

- Crime CSV files are stored in Backend/Data
- Uses Google Maps and Geocoding APIs (API key required)

## Team - RouteGuardians
- Muhammad Shayan Khattak
- Sarim Khan
- Daniel Zhang
