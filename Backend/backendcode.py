# API KEY: AIzaSyAvd-A6T82TwgIYYmA6AOp30F4iFE4CMS0, DO NOT DELETE!!!

from flask import Flask, request, jsonify
from flask_cors import CORS # Import CORS
import os
import pandas as pd
import requests
# from geopy.distance import geodesic # Removed geodesic import
import math

app = Flask(__name__)
CORS(app) # Enable CORS for your app

API_KEY = "AIzaSyBCFHs1qD4zALdRQZjjz0ZD00s2vjpK4n8"  # Replace with your actual key
DATA_FOLDER = os.path.join(os.path.dirname(__file__), "Data")

# Define weights for different crime categories (example weights, can be adjusted)
CRIME_WEIGHTS = {
    "Assault": 5,
    "Robbery": 4,
    "Break and Enter": 3,
    "Theft Over": 2,
    "Theft From Motor Vehicle": 1,
    "Auto Theft": 1,
    "Homicide": 10,
    "Shooting": 8,
    "Other": 1
}

def load_crime_data(data_folder):
    dfs = []
    for file in os.listdir(data_folder):
        if file.endswith(".csv"):
            df = pd.read_csv(os.path.join(data_folder, file))
            dfs.append(df)
    combined_df = pd.concat(dfs, ignore_index=True)
    print("\n--- Combined Crime Data Info ---")
    print(combined_df.info())
    print("\n--- First 5 rows of Combined Crime Data ---")
    print(combined_df.head())
    print("\n----------------------------------")
    return combined_df

# Load crime data once when the app starts
CRIME_DF = load_crime_data(DATA_FOLDER)
CRIME_DF['LAT_WGS84'] = pd.to_numeric(CRIME_DF['LAT_WGS84'], errors='coerce')
CRIME_DF['LONG_WGS84'] = pd.to_numeric(CRIME_DF['LONG_WGS84'], errors='coerce')
CRIME_DF = CRIME_DF.dropna(subset=['LAT_WGS84', 'LONG_WGS84'])

def geocode_address(address):
    # Using Google Geocoding API instead of Nominatim
    geocode_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={API_KEY}"
    response = requests.get(geocode_url)
    data = response.json()

    if data["status"] == "OK":
        location = data["results"][0]["geometry"]["location"]
        return (location["lat"], location["lng"])
    else:
        raise ValueError(f"Could not geocode address: {address}. Status: {data['status']}")

def get_routes(start, end):
    url = f"https://maps.googleapis.com/maps/api/directions/json?origin={start}&destination={end}&key={API_KEY}&alternatives=true"
    response = requests.get(url)
    data = response.json()
    return data.get("routes", [])

def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371  # Radius of Earth in kilometers

    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad

    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance = R * c
    return distance

def route_safety_score(route, crime_df):
    points = []
    for leg in route["legs"]:
        for step in leg["steps"]:
            lat = step["start_location"].get("lat")
            lng = step["start_location"].get("lng")

            # Validate extracted lat and lng
            if not (isinstance(lat, (int, float)) and isinstance(lng, (int, float))):
                print(f"Warning: Invalid lat/lng in route step: lat={lat}, lng={lng}. Skipping this point.")
                continue # Skip this point if coordinates are not valid numbers

            points.append((lat, lng))
    
    score = 0
    crime_df_filtered = crime_df.dropna(subset=['LAT_WGS84', 'LONG_WGS84'])

    for _, crime in crime_df_filtered.iterrows():
        crime_loc = (crime['LAT_WGS84'], crime['LONG_WGS84'])
        for pt in points:
            # Validate pt and crime_loc before passing to haversine_distance
            if not (isinstance(pt, (list, tuple)) and len(pt) == 2 and
                    isinstance(pt[0], (int, float)) and isinstance(pt[1], (int, float))):
                print(f"Warning: Invalid route point format encountered: {pt}. Skipping.")
                continue

            if not (isinstance(crime_loc, (list, tuple)) and len(crime_loc) == 2 and
                    isinstance(crime_loc[0], (int, float)) and isinstance(crime_loc[1], (int, float))):
                print(f"Warning: Invalid crime location format encountered: {crime_loc}. Skipping.")
                continue

            distance = haversine_distance(pt[0], pt[1], crime_loc[0], crime_loc[1]) # Used Haversine
            if distance < 0.5:  # Still consider crimes within 0.5 km radius
                # Apply a linear decay for impact based on distance
                weight_factor = 1 - (distance / 0.5)  # 0.5 km is the max effective radius
                
                # Assign weight based on crime category, default to 1 if not found
                category = str(crime.get("MCI_CATEGORY", "Other"))
                offence = str(crime.get("OFFENCE", ""))

                # Specific handling for "Shooting" within "Assault" category if needed
                if "Shooting" in offence and "Assault" in category:
                    score += CRIME_WEIGHTS.get("Shooting", CRIME_WEIGHTS.get("Assault", 1)) * weight_factor
                else:
                    score += CRIME_WEIGHTS.get(category, 1) * weight_factor
                break

    return score

def find_safest_route(start_addr, end_addr):
    start = geocode_address(start_addr)
    end = geocode_address(end_addr)
    start_str = f"{start[0]},{start[1]}"
    end_str = f"{end[0]},{end[1]}"
    routes = get_routes(start_str, end_str)

    best_route = None
    best_score = float('inf')
    for route in routes:
        score = route_safety_score(route, CRIME_DF)  # Use pre-loaded CRIME_DF
        if score < best_score:
            best_score = score
            best_route = route
    return best_route, best_score

@app.route('/safepath', methods=['POST'])
def get_safest_path():
    data = request.get_json()
    print(f"Received data for /safepath: {data}")
    start_address = data.get('start_address')
    end_address = data.get('end_address')

    if not start_address or not end_address:
        return jsonify({"error": "Please provide both start_address and end_address"}), 400

    try:
        route, score = find_safest_route(start_address, end_address)
        if route:
            return jsonify({
                "safest_route": route,
                "safety_score": score
            })
        else:
            return jsonify({"message": "No route found"}), 404
    except Exception as e:
        import traceback # Import traceback here
        print("\n--- EXPLICIT ERROR TRACEBACK IN /safepath ---")
        traceback.print_exc() # Print to console
        print("--------------------------------------------------")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/crime_data', methods=['GET'])
def get_crime_data():
    # For now, return a sample of the loaded crime data
    # In a real application, you might want to filter this by location/type
    return jsonify(CRIME_DF.sample(100).to_dict(orient='records'))

@app.route('/autocomplete', methods=['GET'])
def autocomplete():
    query = request.args.get('q', '')
    if not query:
        return jsonify([])
    
    # geolocator = Nominatim(user_agent="safepath") # Removed Nominatim import, so this line is removed
    # try:
    #     locations = geolocator.geocode(query, exactly_one=False, limit=5)
    #     suggestions = [loc.address for loc in locations] if locations else []
    #     return jsonify(suggestions)
    # except Exception as e:
    #     print(f"Error during geocoding autocomplete: {e}")
    #     return jsonify([])
    # Since Nominatim is removed, this function will now return an empty list or raise an error
    # For now, returning an empty list as a placeholder
    return jsonify([])

if __name__ == '__main__':
    app.run(debug=False)