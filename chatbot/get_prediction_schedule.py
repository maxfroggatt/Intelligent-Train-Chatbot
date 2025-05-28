import pandas as pd
from pathlib import Path

# Load the schedule CSV once at startup
base_dir = Path(__file__).resolve().parent
schedules_df = pd.read_csv(base_dir / "all_services.csv")

# Retrieve schedule data for a train by RID and stations
def get_prediction_schedule(rid, current_station, destination_station):
    try:
        # Convert rid to integer if needed to match the CSV type
        rid_int = int(rid)
    except ValueError:
        print(f"[ERROR] RID '{rid}' is not a valid integer.")
        return None

    journey_df = schedules_df[schedules_df["rid"] == rid_int]

    # Check if journey exists for given rid
    if journey_df.empty:
        print(f"[ERROR] No journey found for rid: {rid_int}")
        return None

    # Get stop rows
    current_row = journey_df[journey_df["location"] == current_station]
    dest_row = journey_df[journey_df["location"] == destination_station]

    # Validate current and destination station data exists
    if current_row.empty or dest_row.empty:
        print(f"[ERROR] Missing station rows for {current_station} or {destination_station}")
        return None

    # Extract schedule details from station rows
    date = current_row.iloc[0]["date_of_service"]
    direction = current_row.iloc[0]["direction"]
    planned_arrival = dest_row.iloc[0]["planned_arrival"]
    planned_departure = dest_row.iloc[0]["planned_departure"]

    # Handle missing planned departure time
    if pd.isna(planned_departure):
        print(f"[WARN] Missing planned_departure for {destination_station}")
        planned_departure = planned_arrival

    # Return extracted schedule information as dictionary
    return {
        "date_of_service": date,
        "planned_arrival": planned_arrival,
        "planned_departure": planned_departure,
        "direction": direction
    }