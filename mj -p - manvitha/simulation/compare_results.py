import xml.etree.ElementTree as ET
from pathlib import Path


def get_avg_waiting(file_path):
    tree = ET.parse(file_path)
    root = tree.getroot()

    total_wait = 0
    count = 0

    for trip in root.findall("tripinfo"):
        total_wait += float(trip.get("waitingTime"))
        count += 1

    return total_wait / count if count > 0 else 0.0


def _resolve_existing_path(candidates):
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return path
    return None


def main():
    baseline_path = _resolve_existing_path(["tripinfo_baseline.xml", "tripinfo.xml"])
    vac_path = _resolve_existing_path(["tripinfo_vac.xml"])

    if baseline_path is None:
        print("Baseline trip file not found. Expected tripinfo_baseline.xml or tripinfo.xml")
        return
    if vac_path is None:
        print("VAC trip file not found. Expected tripinfo_vac.xml")
        return

    baseline_avg = get_avg_waiting(baseline_path)
    vac_avg = get_avg_waiting(vac_path)

    print(f"Baseline ({baseline_path.name}) avg waiting: {baseline_avg:.2f}s")
    print(f"VAC ({vac_path.name}) avg waiting: {vac_avg:.2f}s")
    print(f"Improvement: {baseline_avg - vac_avg:.2f}s")


if __name__ == "__main__":
    main()