import xml.etree.ElementTree as ET
import pandas as pd
from pathlib import Path


def _resolve_emissions_path():
    candidates = [
        Path("emissions.xml"),
        Path("../emissions.xml"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "Could not find emissions.xml. Run SUMO first so the file is generated."
    )


def _load_root_allow_partial(xml_path):
    try:
        return ET.parse(xml_path).getroot(), False
    except ET.ParseError:
        text = xml_path.read_text(encoding="utf-8", errors="ignore")
        close_tag = "</emission-export>"
        if close_tag not in text:
            # SUMO may still be writing. Close the root virtually so we can parse
            # all complete timesteps that are already on disk.
            text = text.rstrip() + "\n" + close_tag + "\n"
        return ET.fromstring(text), True


def main():
    xml_path = _resolve_emissions_path()
    root, was_partial = _load_root_allow_partial(xml_path)

    data = []
    for timestep in root.findall("timestep"):
        time = timestep.get("time")
        for vehicle in timestep.findall("vehicle"):
            data.append(
                {
                    "time": time,
                    "vehicle_id": vehicle.get("id"),
                    "co2": vehicle.get("CO2"),
                    "fuel": vehicle.get("fuel"),
                    "nox": vehicle.get("NOx"),
                }
            )

    output_dir = Path("data/outputs")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "emissions.csv"

    df = pd.DataFrame(data)
    df.to_csv(output_path, index=False)

    if was_partial:
        print(
            "emissions.xml appears incomplete (SUMO likely still running). "
            f"Parsed available data and wrote: {output_path}"
        )
    else:
        print(f"Emissions CSV generated: {output_path}")


if __name__ == "__main__":
    main()