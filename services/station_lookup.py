import csv
import os

# Load once at startup
def load_station_data():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(base_dir, 'station_codes.csv')

    data = {}
    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            name = row['Description'].strip().lower()
            crs = row['CRS'].strip().upper()
            tiploc = row['Tiploc'].strip().upper()
            if crs and tiploc:
                data[crs] = {'tiploc': tiploc, 'name': name}
    return data

# Load once and cache
station_data = load_station_data()

def get_name_from_tiploc(tiploc_code):
    tiploc_code = tiploc_code.upper()
    for crs, info in station_data.items():
        if info.get('tiploc') == tiploc_code:
            return info.get('name')
    return None

# Get TIPLOC from CRS code
def get_tiploc_from_crs(crs_code):
    return station_data.get(crs_code.upper(), {}).get('tiploc')

# Get station name from CRS code
def get_name_from_crs(crs_code):
    return station_data.get(crs_code.upper(), {}).get('name')

# Test CRS to TIPLOC and name lookups
if __name__ == '__main__':
    print(get_tiploc_from_crs('NRW'))
    print(get_tiploc_from_crs('EGH'))
    print(get_tiploc_from_crs('LST'))

    print(get_name_from_crs('NRW'))
    print(get_name_from_crs('EGH'))
    print(get_name_from_crs('LST'))