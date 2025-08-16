# API KEY: AIzaSyAvd-A6T82TwgIYYmA6AOp30F4iFE4CMS0, DO NOT DELETE!!!

from flask import Flask, request, jsonify
from flask_cors import CORS # Import CORS
import os
import pandas as pd
import requests
# from geopy.distance import geodesic # Removed geodesic import
import math
import numpy as np # Import numpy

app = Flask(__name__)
CORS(app) # Enable CORS for your app

API_KEY = "AIzaSyBCFHs1qD4zALdRQZjjz0ZD00s2vjpK4n8"  # Replace with your actual key
DATA_FOLDER = os.path.join(os.path.dirname(__file__), "Data")
SCORE_SCALING_FACTOR = 20 # Tune this to adjust how quickly safety score drops with risk (higher factor = slower drop)

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

def get_routes(start, end, mode="driving"):
    url = f"https://maps.googleapis.com/maps/api/directions/json?origin={start}&destination={end}&key={API_KEY}&alternatives=true&mode={mode}"
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
    
    # Use a set to store indices of crimes already processed for this route
    processed_crime_indices = set()

    # Iterate through each point on the route
    for pt_index, pt in enumerate(points):
        # For each point, iterate through all crime incidents
        for crime_idx, crime in crime_df_filtered.iterrows():
            # Skip if this crime has already been processed for this route
            if crime_idx in processed_crime_indices:
                continue

            crime_loc = (crime['LAT_WGS84'], crime['LONG_WGS84'])
            
            # Validate pt and crime_loc before passing to haversine_distance
            if not (isinstance(pt, (list, tuple)) and len(pt) == 2 and
                    isinstance(pt[0], (int, float)) and isinstance(pt[1], (int, float))):
                # print(f"Warning: Invalid route point format encountered: {pt}. Skipping.") # Already printed above
                continue

            if not (isinstance(crime_loc, (list, tuple)) and len(crime_loc) == 2 and
                    isinstance(crime_loc[0], (int, float)) and isinstance(crime_loc[1], (int, float))):
                print(f"Warning: Invalid crime location format encountered: {crime_loc}. Skipping.")
                continue

            distance = haversine_distance(pt[0], pt[1], crime_loc[0], crime_loc[1]) # Used Haversine
            if distance < 0.5:  # Consider crimes within 0.5 km radius
                # Apply a linear decay for impact based on distance
                weight_factor = 1 - (distance / 0.5)  # 0.5 km is the max effective radius
                
                # Assign weight based on crime category, default to 1 if not found
                category = str(crime.get("MCI_CATEGORY", "Other"))
                offence = str(crime.get("OFFENCE", ""))

                # Accumulate score and mark crime as processed for this route
                # Removed crime_description and reasons.append(crime_description)

                if "Shooting" in offence and "Assault" in category:
                    score += CRIME_WEIGHTS.get("Shooting", CRIME_WEIGHTS.get("Assault", 1)) * weight_factor
                else:
                    score += CRIME_WEIGHTS.get(category, 1) * weight_factor
                
                processed_crime_indices.add(crime_idx) # Mark this crime as processed for this route
                # No break here! Continue checking other crimes against this point and other points.

    return score

def find_safest_route(start_addr, end_addr, mode="driving"):
    start = geocode_address(start_addr)
    end = geocode_address(end_addr)
    start_str = f"{start[0]},{start[1]}"
    end_str = f"{end[0]},{end[1]}"
    routes = get_routes(start_str, end_str, mode)

    scored_routes = []
    for route in routes:
        score = route_safety_score(route, CRIME_DF)
        print(f"Raw risk score for route: {score}") # Debug print
        scored_routes.append({"route": route, "score": score})

    # Sort routes by raw risk score (lower score is safer initially)
    scored_routes.sort(key=lambda x: x["score"])

    # Transform raw risk scores to absolute safety scores (0-100 scale, higher is safer)
    transformed_routes = []

    if not scored_routes:
        return []

    # Recalculate min/max raw scores after all routes are scored
    # (This is important if a route had 0 score before and now has a non-zero one)
    min_raw_score = scored_routes[0]["score"] 
    max_raw_score = scored_routes[-1]["score"] 

    score_range = max_raw_score - min_raw_score

    for sr in scored_routes:
        raw_risk_score = sr["score"]
        
        if raw_risk_score == 0: # Perfectly safe route
            safety_score = 100
        elif score_range == 0: # All routes have the same non-zero raw risk score
            safety_score = 1 # Indicate some risk if all are equally risky
        else:
            # Normalize risk to 0-1, then invert to get safety (0=most risk, 1=least risk)
            normalized_risk = (raw_risk_score - min_raw_score) / score_range
            safety_score = 100 * (1 - normalized_risk) # Scale to 0-100
            
            if safety_score < 1: # Ensure minimum safety score is 1 for risky routes
                safety_score = 1
        
        transformed_routes.append({"route": sr["route"], "score": round(safety_score, 0)})
    
    # Re-sort by transformed safety score (now highest is safest)
    transformed_routes.sort(key=lambda x: x["score"], reverse=True)

    # Return top N safest routes, or all if less than N
    return transformed_routes[:3]

@app.route('/safepath', methods=['POST'])
def get_safest_path():
    data = request.get_json()
    print(f"Received data for /safepath: {data}")
    start_address = data.get('start_address')
    end_address = data.get('end_address')
    commute_mode = data.get('commute_mode', 'driving') # Default to driving

    if not start_address or not end_address:
        return jsonify({"error": "Please provide both start_address and end_address"}), 400

    try:
        safest_routes_info = find_safest_route(start_address, end_address, commute_mode)
        if safest_routes_info:
            # Return a list of routes and their scores
            return jsonify({"safest_routes": safest_routes_info})
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
    # Convert DataFrame to a list of dictionaries, replacing all NaN values with None
    # This ensures proper JSON serialization (NaN is not valid JSON, null is)
    crime_data_for_json = CRIME_DF.sample(100).replace({np.nan: None}).to_dict(orient='records')
    return jsonify(crime_data_for_json)

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