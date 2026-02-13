from flask import Flask, request, jsonify
from flask_cors import CORS
import uuid
import datetime

app = Flask(__name__)
CORS(app)  # allow requests from frontend

# In-memory "database"
users = {}
rides = {}

# Home route
@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "Nonprofit Ride App API is running"}), 200

# Register a user
@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    if not data or "name" not in data or "role" not in data:
        return jsonify({"error": "Name and role required"}), 400

    user_id = str(uuid.uuid4())
    users[user_id] = {
        "id": user_id,
        "name": data["name"],
        "role": data["role"],  # "driver" or "rider"
        "created_at": datetime.datetime.utcnow().isoformat()
    }
    return jsonify({"message": "User registered successfully", "user_id": user_id}), 201

# Request a ride
@app.route("/request_ride", methods=["POST"])
def request_ride():
    data = request.get_json()
    if not data or "user_id" not in data or "pickup" not in data or "dropoff" not in data:
        return jsonify({"error": "User ID, pickup, and dropoff required"}), 400

    ride_id = str(uuid.uuid4())
    rides[ride_id] = {
        "id": ride_id,
        "user_id": data["user_id"],
        "pickup": data["pickup"],
        "dropoff": data["dropoff"],
        "status": "waiting_for_driver",
        "created_at": datetime.datetime.utcnow().isoformat()
    }
    return jsonify({"message": "Ride requested successfully", "ride_id": ride_id}), 201

# Accept a ride (driver side)
@app.route("/accept_ride", methods=["POST"])
def accept_ride():
    data = request.get_json()
    if not data or "ride_id" not in data or "driver_id" not in data:
        return jsonify({"error": "Ride ID and driver ID required"}), 400

    ride = rides.get(data["ride_id"])
    if not ride:
        return jsonify({"error": "Ride not found"}), 404

    ride["status"] = "accepted"
    ride["driver_id"] = data["driver_id"]
    return jsonify({"message": "Ride accepted", "ride": ride}), 200

# Get all rides
@app.route("/rides", methods=["GET"])
def get_all_rides():
    return jsonify(list(rides.values())), 200

if __name__ == "__main__":
    app.run(debug=True)
