import csv
from pathlib import Path

# Load station names mapped to codes
def load_station_dict(csv_path: Path) -> dict[str, str]:
    station_map: dict[str, str] = {}
    csv_path = Path(csv_path)

    # Open CSV file if it exists
    if not csv_path.exists():
        raise FileNotFoundError(f"Stations CSV not found: {csv_path}")
    with csv_path.open(newline='', encoding='utf-8') as f:
        reader = csv.reader(f)

        # Read and unpack valid station rows
        for row in reader:

            # Skip rows that don't have the expected columns
            if len(row) < 5:
                continue
            official, longname, alias, alpha3, tiploc = row

            # Choose alpha3 if available, else tiploc
            code = alpha3.strip() or tiploc.strip()

            # Skip rows with no valid code
            if not code or code == "\\N":
                continue

            # Normalize and add each name variant
            for key in (official, longname, alias):
                if key and key != "\\N":
                    station_map[key.lower()] = code
    return station_map