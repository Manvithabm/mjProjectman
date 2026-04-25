import argparse
import csv
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests


def to_snake_case(name: str) -> str:
    text = name.strip().lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def load_data(input_path: Path) -> Tuple[List[Dict[str, str]], List[str]]:
    with input_path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        headers = reader.fieldnames or []
    return rows, headers


def preprocess_data(rows: List[Dict[str, str]], headers: List[str]) -> List[Dict[str, object]]:
    normalized_headers = []
    for header in headers:
        normalized = to_snake_case(header)
        if normalized == "congestion_level":
            normalized = "congestion_level_score"
        normalized_headers.append(normalized)

    numeric_fields = {
        "traffic_volume": int,
        "average_speed": float,
        "travel_time_index": float,
        "congestion_level_score": float,
        "road_capacity_utilization": float,
        "incident_reports": int,
        "environmental_impact": float,
        "public_transport_usage": float,
        "traffic_signal_compliance": float,
        "parking_usage": float,
        "pedestrian_and_cyclist_count": int,
    }

    cleaned_rows: List[Dict[str, object]] = []
    for row in rows:
        if any((value is None) or (str(value).strip() == "") for value in row.values()):
            continue

        output_row: Dict[str, object] = {}
        valid_row = True

        for old_header, new_header in zip(headers, normalized_headers):
            value = row[old_header].strip()

            if new_header == "date":
                try:
                    output_row[new_header] = datetime.strptime(value, "%Y-%m-%d").date().isoformat()
                except ValueError:
                    valid_row = False
                    break
            elif new_header in numeric_fields:
                caster = numeric_fields[new_header]
                try:
                    output_row[new_header] = caster(float(value)) if caster is int else float(value)
                except ValueError:
                    valid_row = False
                    break
            elif new_header in {"weather_conditions", "roadwork_and_construction_activity"}:
                output_row[new_header] = value.lower()
            else:
                output_row[new_header] = value

        if not valid_row:
            continue

        speed = max(float(output_row["average_speed"]), 1.0)
        traffic_density = float(output_row["traffic_volume"]) / speed
        output_row["traffic_density"] = round(traffic_density, 2)

        if traffic_density < 500:
            output_row["congestion_level"] = "low"
        elif traffic_density < 1000:
            output_row["congestion_level"] = "medium"
        else:
            output_row["congestion_level"] = "high"

        cleaned_rows.append(output_row)

    return cleaned_rows


def to_canonical_historical(rows: List[Dict[str, object]]) -> List[Dict[str, object]]:
    canonical_rows: List[Dict[str, object]] = []
    for row in rows:
        speed = float(row["average_speed"])
        vehicle_count = int(row["traffic_volume"])
        road_length = 1.0
        density = vehicle_count / max(speed * road_length, 1.0)

        canonical_rows.append(
            {
                "timestamp": f'{row["date"]}T00:00:00',
                "speed": speed,
                "vehicle_count": vehicle_count,
                "road_length": road_length,
                "traffic_density": round(density, 2),
                "congestion_level": row["congestion_level"],
                "source": "historical_dataset",
            }
        )
    return canonical_rows


def load_realtime_data(realtime_input_path: Path) -> List[Dict[str, object]]:
    suffix = realtime_input_path.suffix.lower()
    if suffix == ".json":
        with realtime_input_path.open(encoding="utf-8") as file:
            data = json.load(file)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
            return data["data"]
        if isinstance(data, dict):
            return [data]
        raise ValueError("Unsupported JSON structure for realtime input.")

    with realtime_input_path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        return list(reader)


def fetch_tomtom_flow_data(api_key: str, point: str) -> List[Dict[str, object]]:
    url = (
        "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
        f"?point={point}&key={api_key}"
    )
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    data = response.json()

    if isinstance(data, dict) and "flowSegmentData" in data and isinstance(data["flowSegmentData"], dict):
        return [data["flowSegmentData"]]
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return data
    return []


def map_tomtom_to_canonical(realtime_rows: List[Dict[str, object]]) -> List[Dict[str, object]]:
    mapped_rows: List[Dict[str, object]] = []
    for row in realtime_rows:
        if "currentSpeed" not in row:
            continue

        try:
            speed = float(row["currentSpeed"])
        except (TypeError, ValueError):
            continue

        if speed < 20:
            vehicle_count = 80
        elif speed < 40:
            vehicle_count = 50
        else:
            vehicle_count = 20

        road_length = 1.0
        density = vehicle_count / max(speed * road_length, 1.0)
        if density < 500:
            congestion_level = "low"
        elif density < 1000:
            congestion_level = "medium"
        else:
            congestion_level = "high"

        mapped_rows.append(
            {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "speed": speed,
                "vehicle_count": vehicle_count,
                "road_length": road_length,
                "traffic_density": round(density, 2),
                "congestion_level": congestion_level,
                "source": "tomtom_realtime",
            }
        )
    return mapped_rows


def save_data(rows: List[Dict[str, object]], output_path: Path) -> None:
    if not rows:
        raise ValueError("No rows available to save after preprocessing.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def ingest(
    input_path: Path,
    output_path: Path,
    aligned_output_path: Path,
    realtime_input_path: Optional[Path] = None,
    tomtom_api_key: Optional[str] = None,
    tomtom_point: str = "12.9716,77.5946",
) -> None:
    rows, headers = load_data(input_path)
    processed_rows = preprocess_data(rows, headers)
    save_data(processed_rows, output_path)
    historical_canonical_rows = to_canonical_historical(processed_rows)

    realtime_canonical_rows: List[Dict[str, object]] = []
    if realtime_input_path:
        realtime_rows = load_realtime_data(realtime_input_path)
        realtime_canonical_rows = map_tomtom_to_canonical(realtime_rows)
    elif tomtom_api_key:
        realtime_rows = fetch_tomtom_flow_data(tomtom_api_key, tomtom_point)
        realtime_canonical_rows = map_tomtom_to_canonical(realtime_rows)

    aligned_rows = historical_canonical_rows + realtime_canonical_rows
    save_data(aligned_rows, aligned_output_path)

    print(f"Input rows: {len(rows)}")
    print(f"Output rows: {len(processed_rows)}")
    print(f"Saved: {output_path}")
    print(f"Aligned rows: {len(aligned_rows)}")
    print(f"Saved aligned: {aligned_output_path}")
    if realtime_input_path:
        print(f"Realtime records mapped: {len(realtime_canonical_rows)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest and preprocess Bangalore traffic data.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/raw/Bangalore_traffic.csv"),
        help="Path to input raw CSV file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/Bangalore_traffic_clean.csv"),
        help="Path to save processed CSV file.",
    )
    parser.add_argument(
        "--realtime-input",
        type=Path,
        default=None,
        help="Optional TomTom realtime input path (.csv or .json).",
    )
    parser.add_argument(
        "--aligned-output",
        type=Path,
        default=Path("data/processed/Bangalore_traffic_aligned.csv"),
        help="Path to save merged canonical dataset (historical + realtime).",
    )
    parser.add_argument(
        "--tomtom-api-key",
        type=str,
        default=os.getenv("TOMTOM_API_KEY"),
        help="TomTom API key. If omitted, reads TOMTOM_API_KEY env var.",
    )
    parser.add_argument(
        "--tomtom-point",
        type=str,
        default="12.9716,77.5946",
        help="Lat,lon point for TomTom flow query.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    ingest(
        args.input,
        args.output,
        args.aligned_output,
        args.realtime_input,
        args.tomtom_api_key,
        args.tomtom_point,
    )
