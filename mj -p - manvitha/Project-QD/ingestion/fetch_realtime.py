import csv
import os
import sys
import time
from datetime import datetime

import requests


# Return the TomTom API key from environment at call time so changes to the env
# (or inline runs) are picked up without reloading the module.
def get_api_key():
    return os.getenv("TOMTOM_API_KEY", "uMX57Tkd0zXgi3QiaDKSZGvygNuEus24")

# Multi-location coordinates
LOCATIONS = [
    (12.9716, 77.5946),
    (12.9352, 77.6245),
    (12.9279, 77.6271),
]

# Output file
OUTPUT_FILE = "data/processed/realtime_data.csv"


def fetch_data(lat, lon):
    api_key = get_api_key()
    if not api_key:
        print("Missing TOMTOM_API_KEY environment variable - set TOMTOM_API_KEY and retry")
        return None

    url = (
        "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
        f"?point={lat},{lon}&key={api_key}"
    )

    try:
        response = requests.get(url, timeout=20)
        if response.status_code != 200:
            print("API Error:", response.status_code)
            return None
        response.raise_for_status()
        data = response.json()

        flow = data.get("flowSegmentData", {})
        speed = flow.get("currentSpeed", None)

        if speed is None:
            print("No speed data received")
            return None

        if speed < 20:
            vehicle_count = 80
        elif speed < 40:
            vehicle_count = 50
        else:
            vehicle_count = 20

        record = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "latitude": lat,
            "longitude": lon,
            "vehicle_count": vehicle_count,
            "speed": speed,
            "road_length": 1.0,
        }
        with open("logs.txt", "a", encoding="utf-8") as file:
            file.write(f"{datetime.now()} - Data fetched\n")
        return [record]

    except Exception as error:
        print("Error fetching data:", error)
        return None


def save_data(records):
    if not records:
        return

    os.makedirs("data/processed", exist_ok=True)
    file_exists = os.path.isfile(OUTPUT_FILE)
    fieldnames = ["timestamp", "latitude", "longitude", "vehicle_count", "speed", "road_length"]

    with open(OUTPUT_FILE, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerows(records)

    print("Data saved:", records)


def run_pipeline():
    all_records = []
    for lat, lon in LOCATIONS:
        records = fetch_data(lat, lon)
        if records:
            all_records.extend(records)
    save_data(all_records)


if __name__ == "__main__":
    while True:
        print("Fetching new data...")
        run_pipeline()
        print("Sleeping for 5 minutes...\n")
        time.sleep(300)
