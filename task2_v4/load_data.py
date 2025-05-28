import pandas as pd
from pathlib import Path

def load_and_combine_data(data_folder: str = 'data', years=None) -> pd.DataFrame:
    """
    Load CSVs for 2022-2024 and both directions from the specified folder,
    rename key timetable and actual time columns, and concatenate into one DataFrame.
    Keeps all original fields and writes combined CSV to current directory.
    """
    if years is None:
        years = [2022, 2023, 2024]

    dfs = []
    # Directions correspond to filenames
    directions = ['London_to_Norwich', 'Norwich_to_London']

    # Loop through CSVs by year and direction
    for year in years:
        for direction in directions:
            filename = f"{year}_service_details_{direction}.csv"
            filepath = Path(data_folder) / filename
            if not filepath.exists():
                print(f"Warning: {filepath.resolve()} not found, skipping.")
                continue

            # Read raw CSV with all columns
            df = pd.read_csv(filepath)

            if 'toc_code' in df.columns:
                df = df.drop(columns=['toc_code'])

            # Rename timetable and actual columns if present
            rename_map = {
                'gbtt_pta': 'planned_arrival',       # timetable arrival
                'gbtt_ptd': 'planned_departure',     # timetable departure
                'actual_ta': 'actual_arrival',       # actual arrival
                'actual_td': 'actual_departure'      # actual departure
            }
            # Apply only existing columns
            existing_map = {k: v for k, v in rename_map.items() if k in df.columns}
            df = df.rename(columns=existing_map)

            # Merge duplicate/overlapping columns
            # For each target, if there's a '_time' variant, coalesce
            for base in ['planned_arrival', 'planned_departure', 'actual_arrival', 'actual_departure']:
                time_col = base + '_time'
                if base in df.columns and time_col in df.columns:
                    # use non-null from time_col when base is null
                    df[base] = df[base].fillna(df[time_col])
                    # drop the extra column
                    df = df.drop(columns=[time_col])
            # If only time_col exists without base, rename it
            for base in ['planned_arrival', 'planned_departure', 'actual_arrival', 'actual_departure']:
                time_col = base + '_time'
                if time_col in df.columns and base not in df.columns:
                    df = df.rename(columns={time_col: base})

            # Add metadata columns
            df['year'] = year
            df['direction'] = direction
            dfs.append(df)

    # Combine all DataFrames or return empty
    if dfs:
        combined = pd.concat(dfs, ignore_index=True, sort=False)
    else:
        combined = pd.DataFrame()

    # Write combined CSV to current directory
    output_file = 'all_services.csv'
    combined.to_csv(output_file, index=False)
    print(f"Combined dataset written to {output_file} with {len(combined)} rows.")
    return combined

# Run data loading and show summary
if __name__ == '__main__':
    df_all = load_and_combine_data(data_folder='data')
    print(df_all.info())