import pandas as pd
from joblib import load
from datetime import datetime, timedelta
from pathlib import Path
from datetime import time

# Get base directory safely, fallback if __file__ undefined
try:
    base_dir = Path(__file__).resolve().parent
except NameError:
    base_dir = Path.cwd()

# Load from CSV instead of joblib
model = load(base_dir / 'RandomForest_best_model.joblib')
rid_hist_avg_df = pd.read_csv(base_dir / 'rid_hist_avg.csv')
schedules_df = pd.read_csv(base_dir / 'schedules.csv')

# Convert rid to int index for fast lookup
rid_hist_avg = dict(zip(rid_hist_avg_df.rid.astype(int), rid_hist_avg_df.mean_delay))
schedules = {}
for rid, group in schedules_df.groupby('rid'):
    schedules[rid] = list(group.sort_values('stop_number')['station'])

# Create feature DataFrame for delay prediction model
def make_feature_row(
    rid: str,
    date_of_service: str,
    station: str,
    reported_delay: float,
    planned_arr_str: str,
    planned_dep_str: str,
    direction: str
) -> pd.DataFrame:

    # Debug print input values for feature creation
    print("[DEBUG] Entered make_feature_row")
    print("[DEBUG] Inputs - rid={rid}, station={station}, date={date_of_service}, delay={reported_delay}")

    rid_int = int(rid)
    service_date = pd.to_datetime(date_of_service, format="%d-%m-%Y")

    # Check for missing planned arrival or departure times
    if pd.isna(planned_arr_str) or pd.isna(planned_dep_str):
        raise ValueError("[ERROR] planned_arrival or planned_departure is NaN")

    # Convert planned arrival and departure strings to datetime
    planned_arr_dt = pd.to_datetime(f"{service_date.date()} {planned_arr_str}", format="%Y-%m-%d %H:%M")
    planned_dep_dt = pd.to_datetime(f"{service_date.date()} {planned_dep_str}", format="%Y-%m-%d %H:%M")

    # Check if planned arrival and departure times are valid
    rid_hist_avg_delay = rid_hist_avg.get(rid_int, 0.0)

    # Initialize delay deviation features
    dep_dev = reported_delay
    first_stop_dev = dep_dev
    second_stop_dev = float('nan')

    # Calculate time and date-based features
    dom = service_date.day
    hour_of_day = planned_arr_dt.hour
    planned_arr_minute = hour_of_day * 60 + planned_arr_dt.minute
    planned_dep_minute = planned_dep_dt.hour * 60 + planned_dep_dt.minute
    is_peak = int((7 <= hour_of_day < 10) or (16 <= hour_of_day < 19))
    dow = service_date.weekday()
    dow_cols = {f"dow_{i}": int(dow == i) for i in range(7)}
    is_weekend = int(dow >= 5)

    # Debug print for calculated features
    stop_list = schedules.get(rid_int, [])
    print(f"[DEBUG] stop_list for {rid} → {stop_list}")

    # Check if station is in the stop list
    if not stop_list or station not in stop_list:
        print(f"[ERROR] No schedule found for RID '{rid}'")
        return pd.DataFrame()

    # Calculate stop-related features
    stop_number = stop_list.index(station) + 1
    total_stops = len(stop_list)
    stop_fraction = stop_number / total_stops
    stops_remaining = total_stops - stop_number
    to_norwich = int(direction == 'London_to_Norwich')

    # Debug print for stop-related features
    data = {
        'rid_hist_avg_delay': rid_hist_avg_delay,
        'dep_dev': dep_dev,
        'first_stop_dev': first_stop_dev,
        'second_stop_dev': second_stop_dev,
        'dom': dom,
        'hour_of_day': hour_of_day,
        'planned_arr_minute': planned_arr_minute,
        'planned_dep_minute': planned_dep_minute,
        'is_peak': is_peak,
        'is_weekend': is_weekend,
        'stop_number': stop_number,
        'stop_fraction': stop_fraction,
        'stops_remaining': stops_remaining,
        'to_norwich': to_norwich,
        **dow_cols
    }
    print("[DEBUG] Feature DataFrame:")
    print(pd.DataFrame([data]))
    return pd.DataFrame([data])

# Predict arrival time based on delay features
def predict_arrival_time(query):
    try:
        print(f"[DEBUG] Entering predict_arrival_time with query: {query}")

        # Check if all required fields are present
        X = make_feature_row(
            rid=query['rid'],
            date_of_service=query['date_of_service'],
            station=query['station'],
            reported_delay=query['reported_delay'],
            planned_arr_str=query['planned_arrival'],
            planned_dep_str=query['planned_departure'],
            direction=query['direction']
        )

        # Check if the feature DataFrame is empty
        if X.empty:
            print("[ERROR] Feature DataFrame is empty. Cannot make prediction.")
            print("[DEBUG] Inputs that led to empty DataFrame:", query)
            return "Sorry, I couldn't calculate the arrival time due to missing features."

        print("[DEBUG] Feature row generated successfully")

        # Make sure the model is loaded
        pred_delay = model.predict(X)[0]

        # query['date_of_service'] is a datetime.date
        # query['planned_arrival'] is "HH:MM"
        h, m = map(int, query['planned_arrival'].split(":"))
        base_arrival = datetime.combine(query['date_of_service'], time(hour=h, minute=m))
        new_arrival = base_arrival + timedelta(minutes=pred_delay)

        # Debug print for prediction results
        return (
            f"Your departure delay was {query['reported_delay']:+.0f} min, "
            f"so I predict you’ll arrive at {new_arrival.strftime('%H:%M')}."
        )

    # Handle specific exceptions for better debugging
    except Exception as e:
        print(f"[ERROR] Exception in predict_arrival_time: {e}")
        return "Sorry, I couldn't calculate the arrival time due to an error."