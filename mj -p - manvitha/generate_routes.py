import pandas as pd
from pathlib import Path

# Load latest realtime output
csv_path = Path("Project-QD/data/processed/realtime_data.csv")
if not csv_path.exists():
    csv_path = Path("data/processed/realtime_data.csv")
df = pd.read_csv(csv_path, engine="python", on_bad_lines="skip")

# Take latest record
latest = df.iloc[-1]

vehicle_count = int(latest["vehicle_count"])
speed = float(latest["speed"])

# ⚠️ Adjust to avoid overload
vehicle_count = min(vehicle_count, 50)

with open("routes.rou.xml", "w") as f:
    f.write("<routes>\n")

    # Vehicle type (BS6 approximation)
    f.write(f'''
    <vType id="car"
           accel="1.0"
           decel="4.5"
           maxSpeed="{speed}"
           emissionClass="HBEFA3/PC_G_EU6"/>
    ''')

    # Multiple routes so vehicles spread over network
    routes = [
        "A0A1 A1A2 A2B2 B2B1",
        "A0A1 A1A2 A2B2 B2C2",
        "A0A1 A1B1 B1B0 B0C0",
        "A0A1 A1B1 B1B2 B2A2",
        "A0A1 A1B1 B1B2 B2C2",
        "A0A1 A1B1 B1C1 C1C0",
        "A0A1 A1B1 B1C1 C1C2",
        "A0B0 B0B1 B1A1 A1A2",
        "A0B0 B0B1 B1B2 B2A2",
        "A0B0 B0B1 B1B2 B2C2",
    ]
    for idx, route_edges in enumerate(routes):
        f.write(f'<route id="r{idx}" edges="{route_edges}"/>\n')

    # Generate vehicles
    for i in range(vehicle_count):
        depart_time = i * 1  # stagger vehicles
        route_id = f"r{i % len(routes)}"
        f.write(f'<vehicle id="veh{i}" type="car" route="{route_id}" depart="{depart_time}" />\n')

    f.write("</routes>")

print("Routes generated successfully!")