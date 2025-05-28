import pandas as pd
import numpy as np
from joblib import dump

# Load CSV and parse service date
def engineer_features(input_csv: str, output_csv: str):
    # Load data and parse service date
    df = pd.read_csv(input_csv)
    df['date_of_service'] = pd.to_datetime(
        df['date_of_service'], dayfirst=True, format='mixed', errors='coerce'
    )

    # Helper to parse time columns
    def parse_dt(row, col_time):
        time_str = row.get(col_time, '')
        if pd.isna(time_str) or time_str == '':
            return pd.NaT
        combined = f"{row['date_of_service'].strftime('%d-%m-%Y')} {time_str}"
        return pd.to_datetime(combined, format="%d-%m-%Y %H:%M", errors='coerce')

    # Parse planned and actual arrival/departure times
    df['planned_arr_dt'] = df.apply(lambda r: parse_dt(r, 'planned_arrival'), axis=1)
    df['actual_arr_dt']  = df.apply(lambda r: parse_dt(r, 'actual_arrival'), axis=1)
    df['planned_dep_dt'] = df.apply(lambda r: parse_dt(r, 'planned_departure'), axis=1)
    df['actual_dep_dt']  = df.apply(lambda r: parse_dt(r, 'actual_departure'), axis=1)

    # Target: arrival delay in minutes
    df['y_delay_mins'] = (df['actual_arr_dt'] - df['planned_arr_dt']).dt.total_seconds() / 60.0
    df = df[df['y_delay_mins'].abs() <= 120].copy()

    # Associated Journey Features
    df['rid_hist_avg_delay'] = df.groupby('rid')['y_delay_mins'].transform('mean')

    # Historical average delay per service
    hist_avg = df.groupby('rid')['y_delay_mins'].mean()
    dump(hist_avg, 'rid_hist_avg.joblib')
    print(f"Saved {len(hist_avg)} service‐averages to rid_hist_avg.joblib")

    # Service schedules: the ordered list of stops per rid
    schedules = df.groupby('rid')['location'].apply(list).to_dict()
    dump(schedules, 'schedules.joblib')
    print(f"Saved schedules for {len(schedules)} services to schedules.joblib")
    df['dep_dev'] = (df['actual_dep_dt'] - df['planned_dep_dt']).dt.total_seconds() / 60.0
    grp = df.groupby(['rid', 'date_of_service'])
    df['first_stop_dev'] = grp['y_delay_mins'].transform('first')
    df['second_stop_dev'] = grp['y_delay_mins'].transform(lambda x: x.iloc[1] if len(x) > 1 else np.nan)

    # Time of day numeric features
    df['planned_arr_minute'] = df['planned_arr_dt'].dt.hour * 60 + df['planned_arr_dt'].dt.minute
    df['planned_dep_minute'] = df['planned_dep_dt'].dt.hour * 60 + df['planned_dep_dt'].dt.minute
    df['hour_of_day'] = df['planned_arr_dt'].dt.hour

    # Calendar features
    df['dow'] = df['date_of_service'].dt.dayofweek
    df['dom'] = df['date_of_service'].dt.day
    df = pd.get_dummies(df, columns=['dow'], prefix='dow')
    df['is_peak'] = (((df['hour_of_day'] >= 7) & (df['hour_of_day'] < 10)) | ((df['hour_of_day'] >= 16) & (df['hour_of_day'] < 19))).astype(int)
    df['is_weekend'] = df[['dow_5', 'dow_6']].max(axis=1).astype(int)

    # Station indexing features
    df['stop_number'] = grp.cumcount() + 1
    total_stops = grp['location'].transform('count')
    df['stop_fraction'] = df['stop_number'] / total_stops
    df['stops_remaining'] = total_stops - df['stop_number']

    # Direction as binary feature
    df['to_norwich'] = (df['direction'] == 'London_to_Norwich').astype(int)
    df = df.drop(columns=['direction'])

    # Select and order final features, keep identifiers
    feature_cols = ['rid', 'location'] + [
        'rid_hist_avg_delay', 'dep_dev', 'first_stop_dev', 'second_stop_dev',
        'dom', 'hour_of_day', 'planned_arr_minute', 'planned_dep_minute',
        'is_peak', 'is_weekend', 'stop_number', 'stop_fraction', 'stops_remaining', 'to_norwich'
    ] + [col for col in df.columns if col.startswith('dow_')]

    # Write out features + target
    output_cols = feature_cols + ['y_delay_mins']
    df[output_cols].to_csv(output_csv, index=False)

# Run feature engineering
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Feature engineer all_services.csv')
    parser.add_argument('--input', type=str, default='all_services.csv')
    parser.add_argument('--output', type=str, default='all_services_with_features.csv')
    args = parser.parse_args()
    engineer_features(args.input, args.output)